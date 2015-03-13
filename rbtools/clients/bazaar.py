from __future__ import unicode_literals

import logging
import os
import re

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import TooManyRevisionsError
from rbtools.utils.checks import check_install
from rbtools.utils.diffs import filter_diff, normalize_patterns
from rbtools.utils.process import execute


USING_PARENT_PREFIX = 'Using parent branch '


class BazaarClient(SCMClient):
    """
    Bazaar client wrapper that fetches repository information and generates
    compatible diffs.

    The :class:`RepositoryInfo` object reports whether the repository supports
    parent diffs (every branch with a parent supports them).
    """
    name = 'Bazaar'

    supports_diff_exclude_patterns = True

    INDEX_FILE_RE = re.compile(b"===.+'(.+?)'\n")

    # Regular expression that matches the path to the current branch.
    #
    # For branches with shared repositories, Bazaar reports
    # "repository branch: /foo", but for standalone branches it reports
    # "branch root: /foo".
    BRANCH_REGEX = (
        r'\w*(repository branch|branch root|checkout root|checkout of branch):'
        r' (?P<branch_path>.+)$')

    # Revision separator (two ..s without escaping, and not followed by a /).
    # This is the same regex used in bzrlib/option.py:_parse_revision_spec.
    REVISION_SEPARATOR_REGEX = re.compile(r'\.\.(?![\\/])')

    def get_repository_info(self):
        """
        Find out information about the current Bazaar branch (if any) and
        return it.
        """
        if not check_install(['bzr', 'help']):
            logging.debug('Unable to execute "bzr help": skipping Bazaar')
            return None

        bzr_info = execute(['bzr', 'info'], ignore_errors=True)

        if 'ERROR: Not a branch:' in bzr_info:
            # This is not a branch:
            repository_info = None
        else:
            # This is a branch, let's get its attributes:
            branch_match = re.search(self.BRANCH_REGEX, bzr_info, re.MULTILINE)

            path = branch_match.group('branch_path')
            if path == '.':
                path = os.getcwd()

            repository_info = RepositoryInfo(
                path=path,
                base_path='/',    # Diffs are always relative to the root.
                supports_parent_diffs=True)

        return repository_info

    def parse_revision_spec(self, revisions=[]):
        """Parses the given revision spec.

        The 'revisions' argument is a list of revisions as specified by the
        user. Items in the list do not necessarily represent a single revision,
        since the user can use SCM-native syntaxes such as "r1..r2" or "r1:r2".
        SCMTool-specific overrides of this method are expected to deal with
        such syntaxes.

        This will return a dictionary with the following keys:
            'base':        A revision to use as the base of the resulting diff.
            'tip':         A revision to use as the tip of the resulting diff.
            'parent_base': (optional) The revision to use as the base of a
                           parent diff.

        These will be used to generate the diffs to upload to Review Board (or
        print). The diff for review will include the changes in (base, tip],
        and the parent diff (if necessary) will include (parent, base].

        If a single revision is passed in, this will return the parent of that
        revision for 'base' and the passed-in revision for 'tip'.

        If zero revisions are passed in, this will return the current HEAD as
        'tip', and the upstream branch as 'base', taking into account parent
        branches explicitly specified via --parent.
        """
        n_revs = len(revisions)
        result = {}

        if n_revs == 0:
            # No revisions were passed in--start with HEAD, and find the
            # submit branch automatically.
            result['tip'] = self._get_revno()
            result['base'] = self._get_revno('ancestor:')
        elif n_revs == 1 or n_revs == 2:
            # If there's a single argument, try splitting it on '..'
            if n_revs == 1:
                revisions = self.REVISION_SEPARATOR_REGEX.split(revisions[0])
                n_revs = len(revisions)

            if n_revs == 1:
                # Single revision. Extract the parent of that revision to use
                # as the base.
                result['base'] = self._get_revno('before:' + revisions[0])
                result['tip'] = self._get_revno(revisions[0])
            elif n_revs == 2:
                # Two revisions.
                result['base'] = self._get_revno(revisions[0])
                result['tip'] = self._get_revno(revisions[1])
            else:
                raise TooManyRevisionsError

            # XXX: I tried to automatically find the parent diff revision here,
            # but I really don't understand the difference between submit
            # branch, parent branch, bound branches, etc. If there's some way
            # to know what to diff against, we could use
            #     'bzr missing --mine-only --my-revision=(base) --line'
            # to see if we need a parent diff.
        else:
            raise TooManyRevisionsError

        if self.options.parent_branch:
            result['parent_base'] = result['base']
            result['base'] = self._get_revno(
                'ancestor:%s' % self.options.parent_branch)

        return result

    def _get_revno(self, revision_spec=None):
        command = ['bzr', 'revno']
        if revision_spec:
            command += ['-r', revision_spec]

        result = execute(command).strip().split('\n')

        if len(result) == 1:
            return 'revno:' + result[0]
        elif len(result) == 2 and result[0].startswith(USING_PARENT_PREFIX):
            branch = result[0][len(USING_PARENT_PREFIX):]
            return 'revno:%s:%s' % (result[1], branch)

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             extra_args=[]):
        """Returns the diff for the given revision spec.

        If the revision spec is empty, this returns the diff of the current
        branch with respect to its parent. If a single revision is passed in,
        this returns the diff of the change introduced in that revision. If two
        revisions are passed in, this will do a diff between those two
        revisions.

        The summary and description are set if guessing is enabled.
        """
        exclude_patterns = normalize_patterns(exclude_patterns,
                                              self.get_repository_info().path)

        diff = self._get_range_diff(revisions['base'], revisions['tip'],
                                    include_files, exclude_patterns)

        if 'parent_base' in revisions:
            parent_diff = self._get_range_diff(
                revisions['parent_base'], revisions['base'], include_files,
                exclude_patterns)
        else:
            parent_diff = None

        return {
            'diff': diff,
            'parent_diff': parent_diff,
        }

    def _get_range_diff(self, base, tip, include_files, exclude_patterns=[]):
        """Return the diff between 'base' and 'tip'."""
        diff_cmd = ['bzr', 'diff', '-q', '-r',
                    '%s..%s' % (base, tip)] + include_files
        diff = execute(diff_cmd, ignore_errors=True, log_output_on_error=False,
                       split_lines=True, results_unicode=False)

        if diff:
            if exclude_patterns:
                diff = filter_diff(diff, self.INDEX_FILE_RE, exclude_patterns,
                                   base_dir=self.get_repository_info().path)

            return b''.join(diff)
        else:
            return None

    def get_raw_commit_message(self, revisions):
        # The result is content in the form of:
        #
        # 2014-01-02  First Name  <email@address>
        #
        # <tab>line 1
        # <tab>line 2
        # <tab>...
        #
        # 2014-01-02  First Name  <email@address>
        #
        # ...
        log_cmd = ['bzr', 'log', '-r',
                   '%s..%s' % (revisions['base'], revisions['tip'])]

        # Find out how many commits there are, then log limiting to one fewer.
        # This is because diff treats the range as (r1, r2] while log treats
        # the lange as [r1, r2].
        lines = execute(log_cmd + ['--line'],
                        ignore_errors=True, split_lines=True)
        n_revs = len(lines) - 1

        lines = execute(log_cmd + ['--gnu-changelog', '-l', str(n_revs)],
                        ignore_errors=True, split_lines=True)

        message = []

        for line in lines:
            # We only care about lines that start with a tab (commit message
            # lines) or blank lines.
            if line.startswith('\t'):
                message.append(line[1:])
            elif not line.strip():
                message.append(line)

        return ''.join(message).strip()
