"""A client for Bazaar and Breezy."""

import logging
import os
import re
from typing import List, Optional, cast

from rbtools.clients.base.repository import RepositoryInfo
from rbtools.clients.base.scmclient import (BaseSCMClient,
                                            SCMClientDiffResult,
                                            SCMClientRevisionSpec)
from rbtools.clients.errors import (SCMClientDependencyError,
                                    TooManyRevisionsError)
from rbtools.deprecation import (RemovedInRBTools50Warning,
                                 deprecate_non_keyword_only_args)
from rbtools.utils.checks import check_install
from rbtools.utils.diffs import filter_diff, normalize_patterns
from rbtools.utils.process import run_process


USING_PARENT_PREFIX = 'Using parent branch '


class BazaarClient(BaseSCMClient):
    """A client for Bazaar and Breezy.

    This is a wrapper that fetches repository information and generates
    compatible diffs.

    It supports the legacy Bazaar client, as well as the modern Breezy.

    Version Changed:
        2.0.1:
        Added support for Breezy.
    """

    scmclient_id = 'bazaar'
    name = 'Bazaar'
    server_tool_names = 'Bazaar'
    supports_diff_exclude_patterns = True
    supports_parent_diffs = True
    can_branch = True

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

    def __init__(self, **kwargs) -> None:
        """Initialize the client.

        Args:
            **kwargs (dict):
                Keyword arguments to pass through to the base class.
        """
        super(BazaarClient, self).__init__(**kwargs)

        # The command used to execute bzr.
        self._bzr: str = ''

        # Separately (since either bzr or brz might be used), we want to
        # maintain a flag indicating if this is Breezy, since it changes
        # some semantics.
        self._is_breezy: Optional[bool] = None

    @property
    def bzr(self) -> str:
        """The name of the command line tool for Breezy or Bazaar.

        Callers must call :py:meth:`setup` or :py:meth:`has_dependencies`
        before accessing this. This will be required starting in RBTools 5.0.

        This will fall back to "bzr" if neither Bazaar nor Breezy is installed.

        Type:
            str
        """
        bzr = self._bzr

        if not bzr:
            # This will log a deprecation warning if checking dependencies for
            # the first time.
            self.has_dependencies(expect_checked=True)

            if not self._bzr:
                # Fall back to "bzr" as a default.
                bzr = 'bzr'
                self._bzr = bzr

        return bzr

    @property
    def is_breezy(self) -> bool:
        """Whether the client will be working with Breezy, instead of Bazaar.

        Callers must call :py:meth:`setup` or :py:meth:`has_dependencies`
        before accessing this. This will be required starting in RBTools 5.0.

        Type:
            bool
        """
        is_breezy = self._is_breezy

        if is_breezy is None:
            # This will log a deprecation warning if checking dependencies for
            # the first time.
            self.has_dependencies(expect_checked=True)

            if self._is_breezy is None:
                self._is_breezy = False

        return cast(bool, is_breezy)

    def check_dependencies(self) -> None:
        """Check whether the base dependencies needed are available.

        This will check for both :command:`brz` (Breezy) or :command:`bzr`
        (which may be Bazaar or a Breezy symlink).

        Version Added:
            4.0

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                Neither :command:`bzr` nor :command:`brz` could be found.
        """
        if check_install(['brz', 'help']):
            # This is Breezy.
            self._bzr = 'brz'
            self._is_breezy = True
        elif check_install(['bzr', 'help']):
            # This is either a legacy Bazaar (aliased to bzr) or the
            # modern Breezy. Let's find out.
            version = (
                run_process(['bzr', '--version'],
                            ignore_errors=True)
                .stdout_bytes
                .read()
            )

            self._is_breezy = version.startswith(b'Breezy')
            self._bzr = 'bzr'
        else:
            raise SCMClientDependencyError(missing_exes=[('brz', 'bzr')])

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        # NOTE: This can be removed once check_dependencies() is mandatory.
        if not self.has_dependencies(expect_checked=True):
            logging.debug('Unable to execute "brz help" or "bzr help": '
                          'skipping Bazaar')
            return None

        bzr_info = (
            run_process([self.bzr, 'info'],
                        ignore_errors=True)
            .stdout
            .read()
        )

        if 'ERROR: Not a branch:' in bzr_info:
            return None

        if '(format: git)' in bzr_info:
            # This is a Git repository, which Breezy will happily use, but
            # we want to prioritize Git.
            return None

        # This is a branch, let's get its attributes:
        branch_match = re.search(self.BRANCH_REGEX, bzr_info, re.MULTILINE)

        if not branch_match:
            return None

        path = branch_match.group('branch_path')

        if path == '.':
            path = os.getcwd()

        return path

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        path = self.get_local_path()

        if not path:
            return None

        return RepositoryInfo(
            path=path,
            base_path='/',  # Diffs are always relative to the root.
            local_path=path)

    def parse_revision_spec(
        self,
        revisions: List[str] = [],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The diff for review will include the changes in (base,
        tip], and the parent diff (if necessary) will include (parent,
        base].

        If a single revision is passed in, this will return the parent of
        that revision for "base" and the passed-in revision for "tip".

        If zero revisions are passed in, this will return the current HEAD
        as 'tip', and the upstream branch as 'base', taking into account
        parent branches explicitly specified via :option:`--parent`.

        Args:
            revisions (list of str, optional):
                A list of revisions as specified by the user.

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates ``base`` and ``tip``.

            ``parent_base`` will be populated if using
            :option:`--parent`.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.
        """
        n_revs = len(revisions)
        result: SCMClientRevisionSpec

        # TODO: Update _get_revno() to raise exceptions if we fail to parse
        #       revisions, rather than returning `None` values.

        if n_revs == 0:
            # No revisions were passed in--start with HEAD, and find the
            # submit branch automatically.
            result = {
                'base': self._get_revno('ancestor:'),
                'tip': self._get_revno(),
            }
        elif n_revs == 1 or n_revs == 2:
            # If there's a single argument, try splitting it on '..'
            if n_revs == 1:
                revisions = self.REVISION_SEPARATOR_REGEX.split(revisions[0])
                n_revs = len(revisions)

            if n_revs == 1:
                # Single revision. Extract the parent of that revision to use
                # as the base.
                result = {
                    'base': self._get_revno('before:' + revisions[0]),
                    'tip': self._get_revno(revisions[0]),
                }
            elif n_revs == 2:
                # Two revisions.
                result = {
                    'base': self._get_revno(revisions[0]),
                    'tip': self._get_revno(revisions[1]),
                }
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

        if self.options and self.options.parent_branch:
            result['parent_base'] = result['base']
            result['base'] = self._get_revno(
                'ancestor:%s' % self.options.parent_branch)

        return result

    def _get_revno(
        self,
        revision_spec: Optional[str] = None,
    ) -> Optional[str]:
        """Convert a revision spec to a revision number.

        Args:
            revision_spec (str, optional):
                The revision spec to convert.

        Returns:
            str:
            A new revision spec that contains a revision number instead of a
            symbolic revision.
        """
        command: List[str] = [self.bzr, 'revno']

        if revision_spec:
            command += ['-r', revision_spec]

        result = (
            run_process(command)
            .stdout
            .readlines()
        )

        if len(result) == 1:
            return 'revno:%s' % result[0]
        elif len(result) == 2 and result[0].startswith(USING_PARENT_PREFIX):
            branch = result[0][len(USING_PARENT_PREFIX):]
            return 'revno:%s:%s' % (result[1], branch)
        else:
            return None

    @deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
    def diff(
        self,
        revisions: SCMClientRevisionSpec,
        *,
        include_files: List[str] = [],
        exclude_patterns: List[str] = [],
        **kwargs,
    ) -> SCMClientDiffResult:
        """Perform a diff using the given revisions.

        If the revision spec is empty, this returns the diff of the current
        branch with respect to its parent. If a single revision is passed in,
        this returns the diff of the change introduced in that revision. If two
        revisions are passed in, this will do a diff between those two
        revisions.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            include_files (list of str, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of str, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

            extra_args (list, unused):
                Additional arguments to be passed to the diff generation.
                Unused for Bazaar.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary containing keys documented in
            :py:class:`SCMClientDiffResult`.

            This will only populate the ``diff`` key.
        """
        repository_info = self.get_repository_info()
        assert repository_info is not None
        assert repository_info.path is not None
        assert isinstance(repository_info.path, str)

        parent_base = revisions.get('parent_base')
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        exclude_patterns = normalize_patterns(exclude_patterns,
                                              base_dir=repository_info.path)

        diff = self._get_range_diff(base=base,
                                    tip=tip,
                                    repository_info=repository_info,
                                    include_files=include_files,
                                    exclude_patterns=exclude_patterns)

        if parent_base:
            assert isinstance(parent_base, str)

            parent_diff = self._get_range_diff(
                base=parent_base,
                tip=base,
                repository_info=repository_info,
                include_files=include_files,
                exclude_patterns=exclude_patterns)
        else:
            parent_diff = None

        return {
            'diff': diff,
            'parent_diff': parent_diff,
        }

    def _get_range_diff(
        self,
        *,
        base: str,
        tip: str,
        repository_info: RepositoryInfo,
        include_files: List[str],
        exclude_patterns: List[str],
    ) -> Optional[bytes]:
        """Return the diff between 'base' and 'tip'.

        Args:
            base (str):
                The name of the base revision.

            tip (str):
                The name of the tip revision.

            repository_info (rbtools.utils.base.repository.RepositoryInfo):
                The repository information.

            include_files (list of str):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of str, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

        Returns:
            bytes:
            The generated diff contents.

            This will be ``None`` if the diff would be empty.
        """
        diff_cmd: List[str] = [
            self.bzr,
            'diff',
            '-q',
        ]

        if self.is_breezy:
            # Turn off the "old/" and "new/" prefixes. This is mostly to
            # ensure consistency with legacy Bazaar and for compatibility
            # with versions of Review Board that expect legacy Bazaar diffs.
            diff_cmd.append('--prefix=:')

        diff_cmd += [
            '-r',
            '%s..%s' % (base, tip),
        ] + include_files

        diff = iter(
            run_process(diff_cmd,
                        ignore_errors=True,
                        log_debug_output_on_error=False)
            .stdout_bytes
        )

        if exclude_patterns:
            assert isinstance(repository_info.path, str)

            diff = filter_diff(diff=diff,
                               file_index_re=self.INDEX_FILE_RE,
                               exclude_patterns=exclude_patterns,
                               base_dir=repository_info.path)

        return b''.join(diff) or None

    def get_raw_commit_message(
        self,
        revisions: SCMClientRevisionSpec,
    ) -> str:
        """Extract the commit message based on the provided revision range.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

        Returns:
            str:
            The commit messages of all commits between (base, tip].
        """
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

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
        log_cmd: List[str] = [
            self.bzr,
            'log',
            '-r',
            '%s..%s' % (base, tip),
        ]

        # Find out how many commits there are, then log limiting to one fewer.
        # This is because diff treats the range as (r1, r2] while log treats
        # the lange as [r1, r2].
        n_revs = len(
            run_process(log_cmd + ['--line'],
                        ignore_errors=True)
            .stdout
            .readlines()
        ) - 1

        lines = iter(
            run_process(log_cmd + ['--gnu-changelog', '-l', str(n_revs)],
                        ignore_errors=True)
            .stdout
        )

        message = []

        for line in lines:
            # We only care about lines that start with a tab (commit message
            # lines) or blank lines.
            if line.startswith('\t'):
                message.append(line[1:])
            elif not line.strip():
                message.append(line)

        return ''.join(message).strip()

    def get_current_branch(self) -> str:
        """Return the name of the current branch.

        Returns:
            str:
            A string with the name of the current branch.
        """
        return (
            run_process([self.bzr, 'nick'],
                        ignore_errors=True)
            .stdout
            .read()
            .strip()
        )
