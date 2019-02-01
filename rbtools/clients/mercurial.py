"""A client for Mercurial."""

from __future__ import unicode_literals

import logging
import os
import re
import uuid

from six.moves.urllib.parse import urlsplit, urlunparse

from rbtools.clients import PatchResult, SCMClient, RepositoryInfo
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError,
                                    SCMError)
from rbtools.clients.svn import SVNClient
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_empty_files
from rbtools.utils.console import edit_text
from rbtools.utils.process import execute


class MercurialClient(SCMClient):
    """A client for Mercurial.

    This is a wrapper around the hg executable that fetches repository
    information and generates compatible diffs.
    """

    name = 'Mercurial'
    supports_diff_exclude_patterns = True
    can_branch = True
    can_bookmark = True

    PRE_CREATION = '/dev/null'
    PRE_CREATION_DATE = 'Thu Jan 01 00:00:00 1970 +0000'

    def __init__(self, **kwargs):
        """Initialize the client.

        Args:
            **kwargs (dict):
                Keyword arguments to pass through to the superclass.
        """
        super(MercurialClient, self).__init__(**kwargs)

        self.hgrc = {}
        self._type = 'hg'
        self._remote_path = ()
        self._initted = False
        self._hg_env = {
            'HGPLAIN': '1',
        }

        self._hgext_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            '..', 'helpers', 'hgext.py'))

        # `self._remote_path_candidates` is an ordered set of hgrc
        # paths that are checked if `tracking` option is not given
        # explicitly.  The first candidate found to exist will be used,
        # falling back to `default` (the last member.)
        self._remote_path_candidates = ['reviewboard', 'origin', 'parent',
                                        'default']

    @property
    def hidden_changesets_supported(self):
        """Return whether the repository supports hidden changesets.

        Mercurial 1.9 and above support hidden changesets. These are changesets
        that have been hidden from regular repository view. They still exist
        and are accessible, but only if the --hidden command argument is
        specified.

        Since we may encounter hidden changesets (e.g. the user specifies
        hidden changesets as part of the revision spec), we need to be aware
        of hidden changesets.
        """
        if not hasattr(self, '_hidden_changesets_supported'):
            # The choice of command is arbitrary. parents for the initial
            # revision should be fast.
            result = execute(['hg', 'parents', '--hidden', '-r', '0'],
                             ignore_errors=True,
                             with_errors=False,
                             none_on_ignored_error=True)
            self._hidden_changesets_supported = result is not None

        return self._hidden_changesets_supported

    @property
    def hg_root(self):
        """Return the root of the working directory.

        This will return the root directory of the current repository. If the
        current working directory is not inside a mercurial repository, this
        returns None.
        """
        if not hasattr(self, '_hg_root'):
            root = execute(['hg', 'root'], env=self._hg_env,
                           ignore_errors=True)

            if not root.startswith('abort:'):
                self._hg_root = root.strip()
            else:
                self._hg_root = None

        return self._hg_root

    def _init(self):
        """Initialize the client."""
        if self._initted or not self.hg_root:
            return

        self._load_hgrc()

        svn_info = execute(['hg', 'svn', 'info'], ignore_errors=True)

        if (not svn_info.startswith('abort:') and
            not svn_info.startswith('hg: unknown command') and
            not svn_info.lower().startswith('not a child of')):
            self._type = 'svn'
            self._svn_info = svn_info
        else:
            self._type = 'hg'

            for candidate in self._remote_path_candidates:
                rc_key = 'paths.%s' % candidate

                if rc_key in self.hgrc:
                    self._remote_path = (candidate, self.hgrc[rc_key])
                    logging.debug('Using candidate path %r: %r',
                                  self._remote_path[0], self._remote_path[1])
                    break

        self._initted = True

    def get_repository_info(self):
        """Return the repository info object.

        Returns:
            rbtools.clients.RepositoryInfo:
            The repository info structure.
        """
        if not check_install(['hg', '--help']):
            logging.debug('Unable to execute "hg --help": skipping Mercurial')
            return None

        self._init()

        if not self.hg_root:
            # hg aborted => no mercurial repository here.
            return None

        if self._type == 'svn':
            return self._calculate_hgsubversion_repository_info(self._svn_info)
        else:
            path = self.hg_root
            base_path = '/'

            if self._remote_path:
                path = self._remote_path[1]
                base_path = ''

            return RepositoryInfo(path=path,
                                  base_path=base_path,
                                  local_path=self.hg_root,
                                  supports_parent_diffs=True)

    def parse_revision_spec(self, revisions=[]):
        """Parse the given revision spec.

        Args:
            revisions (list of unicode, optional):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use SCM-native syntaxes such as ``r1..r2`` or ``r1:r2``.
                SCMTool-specific overrides of this method are expected to deal
                with such syntaxes.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.

        Returns:
            dict:
            A dictionary with the following keys:

            ``base`` (:py:class:`unicode`):
                A revision to use as the base of the resulting diff.

            ``tip`` (:py:class:`unicode`):
                A revision to use as the tip of the resulting diff.

            ``parent_base`` (:py:class:`unicode`, optional):
                The revision to use as the base of a parent diff.

            ``commit_id`` (:py:class:`unicode`, optional):
                The ID of the single commit being posted, if not using a range.

            These will be used to generate the diffs to upload to Review Board (or
            print). The diff for review will include the changes in (base, tip],
            and the parent diff (if necessary) will include (parent, base].

            If zero revisions are passed in, this will return the outgoing changes
            from the parent of the working directory.

            If a single revision is passed in, this will return the parent of that
            revision for "base" and the passed-in revision for "tip". This will
            result in generating a diff for the changeset specified.

            If two revisions are passed in, they will be used for the "base"
            and "tip" revisions, respectively.

            In all cases, a parent base will be calculated automatically from
            changesets not present on the remote.
        """
        self._init()

        n_revisions = len(revisions)

        if n_revisions == 1:
            # If there's a single revision, try splitting it based on hg's
            # revision range syntax (either :: or ..). If this splits, then
            # it's handled as two revisions below.
            revisions = re.split(r'\.\.|::', revisions[0])
            n_revisions = len(revisions)

        result = {}
        if n_revisions == 0:
            # No revisions: Find the outgoing changes. Only consider the
            # working copy revision and ancestors because that makes sense.
            # If a user wishes to include other changesets, they can run
            # `hg up` or specify explicit revisions as command arguments.
            if self._type == 'svn':
                result['base'] = self._get_parent_for_hgsubversion()
                result['tip'] = '.'
            else:
                # Ideally, generating a diff for outgoing changes would be as
                # simple as just running `hg outgoing --patch <remote>`, but
                # there are a couple problems with this. For one, the
                # server-side diff parser isn't equipped to filter out diff
                # headers such as "comparing with..." and
                # "changeset: <rev>:<hash>". Another problem is that the output
                # of `hg outgoing` potentially includes changesets across
                # multiple branches.
                #
                # In order to provide the most accurate comparison between
                # one's local clone and a given remote (something akin to git's
                # diff command syntax `git diff <treeish>..<treeish>`), we have
                # to do the following:
                #
                # - Get the name of the current branch
                # - Get a list of outgoing changesets, specifying a custom
                #   format
                # - Filter outgoing changesets by the current branch name
                # - Get the "top" and "bottom" outgoing changesets
                #
                # These changesets are then used as arguments to
                # `hg diff -r <rev> -r <rev>`.
                #
                # Future modifications may need to be made to account for odd
                # cases like having multiple diverged branches which share
                # partial history--or we can just punish developers for doing
                # such nonsense :)
                outgoing = \
                    self._get_bottom_and_top_outgoing_revs_for_remote(rev='.')
                if outgoing[0] is None or outgoing[1] is None:
                    raise InvalidRevisionSpecError(
                        'There are no outgoing changes')
                result['base'] = self._identify_revision(outgoing[0])
                result['tip'] = self._identify_revision(outgoing[1])
                result['commit_id'] = result['tip']
                # Since the user asked us to operate on tip, warn them about a
                # dirty working directory.
                if (self.has_pending_changes() and
                    not self.config.get('SUPPRESS_CLIENT_WARNINGS', False)):
                    logging.warning('Your working directory is not clean. Any '
                                    'changes which have not been committed '
                                    'to a branch will not be included in your '
                                    'review request.')

            if self.options.parent_branch:
                result['parent_base'] = result['base']
                result['base'] = self._identify_revision(
                    self.options.parent_branch)
        elif n_revisions == 1:
            # One revision: Use the given revision for tip, and find its parent
            # for base.
            result['tip'] = self._identify_revision(revisions[0])
            result['commit_id'] = result['tip']
            result['base'] = self._execute(
                ['hg', 'parents', '--hidden', '-r', result['tip'],
                 '--template', '{node|short}']).split()[0]
            if len(result['base']) != 12:
                raise InvalidRevisionSpecError(
                    "Can't determine parent revision"
                )
        elif n_revisions == 2:
            # Two revisions: Just use the given revisions
            result['base'] = self._identify_revision(revisions[0])
            result['tip'] = self._identify_revision(revisions[1])
        else:
            raise TooManyRevisionsError

        if 'base' not in result or 'tip' not in result:
            raise InvalidRevisionSpecError(
                '"%s" does not appear to be a valid revision spec' % revisions)

        if self._type == 'hg' and 'parent_base' not in result:
            # If there are missing changesets between base and the remote, we
            # need to generate a parent diff.
            outgoing = self._get_outgoing_changesets(self._get_remote_branch(),
                                                     rev=result['base'])

            logging.debug('%d outgoing changesets between remote and base.',
                          len(outgoing))

            if not outgoing:
                return result

            parent_base = self._execute(
                ['hg', 'parents', '--hidden', '-r', outgoing[0][1],
                 '--template', '{node|short}']).split()

            if len(parent_base) == 0:
                raise Exception(
                    'Could not find parent base revision. Ensure upstream '
                    'repository is not empty.')

            result['parent_base'] = parent_base[0]

            logging.debug('Identified %s as parent base',
                          result['parent_base'])

        return result

    def _identify_revision(self, revision):
        """Identify the given revision.

        Args:
            revision (unicode):
                The revision.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The specified revision could not be identified.

        Returns:
            unicode:
            The global revision ID of the commit.
        """
        identify = self._execute(
            ['hg', 'identify', '-i', '--hidden', '-r', str(revision)],
            ignore_errors=True, none_on_ignored_error=True)

        if identify is None:
            raise InvalidRevisionSpecError(
                '"%s" does not appear to be a valid revision' % revision)
        else:
            return identify.split()[0]

    def _calculate_hgsubversion_repository_info(self, svn_info):
        """Return repository info for an hgsubversion checkout.

        Args:
            svn_info (unicode):
                The SVN info output.

        Returns:
            rbtools.clients.RepositoryInfo:
            The repository info structure, if available.
        """
        def _info(r):
            m = re.search(r, svn_info, re.M)

            if m:
                return urlsplit(m.group(1))
            else:
                return None

        self._type = 'svn'

        root = _info(r'^Repository Root: (.+)$')
        url = _info(r'^URL: (.+)$')

        if not (root and url):
            return None

        scheme, netloc, path, _, _ = root
        root = urlunparse([scheme, root.netloc.split('@')[-1], path,
                           '', '', ''])
        base_path = url.path[len(path):]

        return RepositoryInfo(path=root,
                              base_path=base_path,
                              local_path=self.hg_root,
                              supports_parent_diffs=True)

    def _load_hgrc(self):
        """Load the hgrc file."""
        for line in execute(['hg', 'showconfig'], split_lines=True):
            line = line.split('=', 1)

            if len(line) == 2:
                key, value = line
            else:
                key = line[0]
                value = ''

            self.hgrc[key] = value.strip()

    def get_raw_commit_message(self, revisions):
        """Return the raw commit message.

        This extracts all descriptions in the given revision range and
        concatenates them, most recent ones going first.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

        Returns:
            bytes:
            The commit messages of all commits between (base, tip].
        """
        rev1 = revisions['base']
        rev2 = revisions['tip']

        delim = str(uuid.uuid1())
        descs = self._execute(
            ['hg', 'log', '--hidden', '-r', '%s::%s' % (rev1, rev2),
             '--template', '{desc}%s' % delim],
            env=self._hg_env,
            results_unicode=False)
        # This initial element in the base changeset, which we don't
        # care about. The last element is always empty due to the string
        # ending with <delim>.
        descs = descs.split(delim)[1:-1]

        return b'\n\n'.join([desc.strip() for desc in descs])

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             no_renames=False, extra_args=[]):
        """Perform a diff using the given revisions.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            include_files (list of unicode, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of unicode, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

            extra_args (list, unused):
                Additional arguments to be passed to the diff generation.
                Unused for mercurial.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.

            ``parent_diff`` (:py:class:`bytes`, optional):
                The contents of the parent diff, if available.

            ``commit_id`` (:py:class:`unicode`, optional):
                The commit ID to include when posting, if available.

            ``base_commit_id` (:py:class:`unicode`, optional):
                The ID of the commit that the change is based on, if available.
                This is necessary for some hosting services that don't provide
                individual file access.
        """
        self._init()

        diff_cmd = ['hg', 'diff', '--hidden', '--nodates']

        if self.supports_empty_files():
            diff_cmd.append('-g')

        if self._type == 'svn':
            diff_cmd.append('--svn')

        diff_cmd += include_files

        for pattern in exclude_patterns:
            diff_cmd.append('-X')
            diff_cmd.append(pattern)

        diff = self._execute(
            diff_cmd + ['-r', revisions['base'], '-r', revisions['tip']],
            env=self._hg_env, log_output_on_error=False, results_unicode=False)

        if 'parent_base' in revisions:
            base_commit_id = revisions['parent_base']
            parent_diff = self._execute(
                diff_cmd + ['-r', base_commit_id, '-r', revisions['base']],
                env=self._hg_env, results_unicode=False)
        else:
            base_commit_id = revisions['base']
            parent_diff = None

        # If reviewboard requests a relative revision via hgweb it will fail
        # since hgweb does not support the relative revision syntax (^1, -1).
        # Rewrite this relative node id to an absolute node id.
        base_commit_id = self._execute(
            ['hg', 'log', '-r', base_commit_id, '--template', '{node}'],
            env=self._hg_env, results_unicode=False)

        return {
            'diff': diff,
            'parent_diff': parent_diff,
            'commit_id': revisions.get('commit_id'),
            'base_commit_id': base_commit_id,
        }

    def _get_files_in_changeset(self, rev):
        """Return a set of all files in the specified changeset.

        Args:
            rev (unicode):
                A changeset identifier.

        Returns:
            set:
            A set of filenames in the changeset.
        """
        cmd = ['hg', 'locate', '-r', rev]

        files = execute(cmd, env=self._hg_env, ignore_errors=True,
                        none_on_ignored_error=True)

        if files:
            files = files.replace('\\', '/')  # workaround for issue 3894

            return set(files.splitlines())

        return set()

    def _get_parent_for_hgsubversion(self):
        """Return the parent Subversion branch.

        Returns the parent branch defined in the command options if it exists,
        otherwise returns the parent Subversion branch of the current
        repository.

        Returns:
            unicode:
            The branch branch for the hgsubversion checkout.
        """
        return (getattr(self.options, 'tracking', None) or
                execute(['hg', 'parent', '--svn', '--template',
                        '{node}\n']).strip())

    def _get_remote_branch(self):
        """Return the remote branch assoicated with this repository.

        If the remote branch is not defined, the parent branch of the
        repository is returned.

        Returns:
            unicode:
            The name of the tracking branch.
        """
        remote = getattr(self.options, 'tracking', None)

        if not remote:
            try:
                remote = self._remote_path[0]
            except IndexError:
                remote = None

        if not remote:
            raise SCMError('Could not determine remote branch to use for '
                           'diff creation. Specify --tracking-branch to '
                           'continue.')

        return remote

    def create_commit(self, message, author, run_editor,
                      files=[], all_files=False):
        """Commit the given modified files.

        This is expected to be called after applying a patch. This commits the
        patch using information from the review request, opening the commit
        message in $EDITOR to allow the user to update it.

        Args:
            message (unicode):
                The commit message to use.

            author (object):
                The author of the commit. This is expected to have ``fullname``
                and ``email`` attributes.

            run_editor (bool):
                Whether to run the user's editor on the commmit message before
                committing.

            files (list of unicode, optional):
                The list of filenames to commit.

            all_files (bool, optional):
                Whether to commit all changed files, ignoring the ``files``
                argument.
        """
        if run_editor:
            modified_message = edit_text(message)
        else:
            modified_message = message

        hg_command = ['hg', 'commit', '-m', modified_message]

        try:
            hg_command.append('-u %s <%s>' % (author.fullname, author.email))
        except AttributeError:
            # Users who have marked their profile as private won't include the
            # fullname or email fields in the API payload. Just commit as the
            # user running RBTools.
            logging.warning('The author has marked their Review Board profile '
                            'information as private. Committing without '
                            'author attribution.')

        execute(hg_command + files)

    def _get_current_branch(self):
        """Return the current branch of this repository.

        Returns:
            unicode:
            The name of the currently checked-out branch.
        """
        return execute(['hg', 'branch'], env=self._hg_env).strip()

    def _get_bottom_and_top_outgoing_revs_for_remote(self, rev=None):
        """Return the bottom and top outgoing revisions.

        Args:
            rev (unicode, optional):
                An optional revision to limit the results. If specified, only
                outgoing changesets which are ancestors of this revision will
                be included.

        Returns:
            tuple:
            A 2-tuple containing the bottom and top outgoing revisions for the
            changesets between the current branch and the remote branch.
        """
        remote = self._get_remote_branch()
        current_branch = self._get_current_branch()

        outgoing = [o for o in self._get_outgoing_changesets(remote, rev=rev)
                    if current_branch == o[2]]

        if outgoing:
            top_rev, bottom_rev = \
                self._get_top_and_bottom_outgoing_revs(outgoing)
        else:
            top_rev = None
            bottom_rev = None

        return bottom_rev, top_rev

    def _get_outgoing_changesets(self, remote, rev=None):
        """Return the outgoing changesets between us and a remote.

        Args:
            remote (unicode):
                The name of the remote.

            rev (unicode, optional):
                An optional revision to limit the results. If specified, only
                outgoing changesets which are ancestors of this revision will
                be included.

        Returns:
            list:
            A list of tuples, each containing ``(rev, node, branch)``, for each
            outgoing changeset. The list will be sorted in revision order.
        """
        outgoing_changesets = []
        args = ['hg', '-q', 'outgoing', '--template',
                '{rev}\\t{node|short}\\t{branch}\\n',
                remote]
        if rev:
            args.extend(['-r', rev])

        # We must handle the special case where there are no outgoing commits
        # as mercurial has a non-zero return value in this case.
        raw_outgoing = execute(args,
                               env=self._hg_env,
                               extra_ignore_errors=(1,))

        for line in raw_outgoing.splitlines():
            if not line:
                continue

            # Ignore warning messages that hg might put in, such as
            # "warning: certificate for foo can't be verified (Python too old)"
            if line.startswith('warning: '):
                continue

            rev, node, branch = [f.strip() for f in line.split('\t')]
            branch = branch or 'default'

            if not rev.isdigit():
                raise Exception('Unexpected output from hg: %s' % line)

            logging.debug('Found outgoing changeset %s:%s', rev, node)

            outgoing_changesets.append((int(rev), node, branch))

        return outgoing_changesets

    def _get_top_and_bottom_outgoing_revs(self, outgoing_changesets):
        """Return top and bottom outgoing revisions for the given changesets.

        Args:
            outgoing_changesets (list):
                A list of outgoing changesets.

        Returns:
            tuple:
            A 2-tuple containing the top and bottom revisions for the given
            outgoing changesets.
        """
        revs = set(t[0] for t in outgoing_changesets)

        top_rev = max(revs)
        bottom_rev = min(revs)

        for rev, node, branch in reversed(outgoing_changesets):
            parents = execute(
                ['hg', 'log', '-r', str(rev), '--template', '{parents}'],
                env=self._hg_env)
            parents = re.split(':[^\s]+\s*', parents)
            parents = [int(p) for p in parents if p != '']

            parents = [p for p in parents if p not in outgoing_changesets]

            if len(parents) > 0:
                bottom_rev = parents[0]
                break
            else:
                bottom_rev = rev - 1

        bottom_rev = max(0, bottom_rev)

        return top_rev, bottom_rev

    def scan_for_server(self, repository_info):
        """Find the Review Board server matching this repository.

        Args:
            repository_info (rbtools.clients.RepositoryInfo):
                The repository information structure.

        Returns:
            unicode:
            The Review Board server URL, if available.
        """
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = \
            super(MercurialClient, self).scan_for_server(repository_info)

        if not server_url and self.hgrc.get('reviewboard.url'):
            server_url = self.hgrc.get('reviewboard.url').strip()

        if not server_url and self._type == 'svn':
            # Try using the reviewboard:url property on the SVN repo, if it
            # exists.
            prop = SVNClient().scan_for_server_property(repository_info)

            if prop:
                return prop

        return server_url

    def _execute(self, cmd, *args, **kwargs):
        """Execute an hg command.

        Args:
            cmd (list of unicode):
                A command line to execute.

            *args (list):
                Addditional arguments to pass to
                :py:func:`rbtools.utils.process.execute`.

            **kwargs (dict):
                Addditional keyword arguments to pass to
                :py:func:`rbtools.utils.process.execute`.

        Returns:
            tuple:
            The result of the execute call.
        """
        if not self.hidden_changesets_supported and '--hidden' in cmd:
            cmd = [p for p in cmd if p != '--hidden']

        # Add our extension which normalizes settings. This is the easiest
        # way to normalize settings since it doesn't require us to chase
        # a tail of diff-related config options.
        cmd.extend([
            '--config',
            'extensions.rbtoolsnormalize=%s' % self._hgext_path
        ])

        return execute(cmd, *args, **kwargs)

    def has_pending_changes(self):
        """Check if there are changes waiting to be committed.

        Returns:
            bool:
            ``True`` if the working directory has been modified, otherwise
            returns ``False``.
        """
        status = execute(['hg', 'status', '--modified', '--added',
                          '--removed', '--deleted'])
        return status != ''

    def apply_patch(self, patch_file, base_path=None, base_dir=None, p=None,
                    revert=False):
        """Apply the given patch.

        This will take the given patch file and apply it to the working
        directory.

        Args:
            patch_file (unicode):
                The name of the patch file to apply.

            base_path (unicode, unused):
                The base path that the diff was generated in. All hg diffs are
                absolute to the repository root, so this is unused.

            base_dir (unicode, unused):
                The path of the current working directory relative to the root
                of the repository. All hg diffs are absolute to the repository
                root, so this is unused.

            p (unicode, optional):
                The prefix level of the diff.

            revert (bool, optional):
                Whether the patch should be reverted rather than applied.

        Returns:
            rbtools.clients.PatchResult:
            The result of the patch operation.
        """
        cmd = ['hg', 'patch', '--no-commit']

        if p:
            cmd += ['-p', p]

        cmd.append(patch_file)

        rc, data = self._execute(cmd, with_errors=True, return_error_code=True)

        return PatchResult(applied=(rc == 0), patch_output=data)

    def apply_patch_for_empty_files(self, patch, p_num, revert=False):
        """Return whether any empty files in the patch are applied.

        Args:
            patch (bytes):
                The contents of the patch.

            p_num (unicode):
                The prefix level of the diff.

            revert (bool, optional):
                Whether the patch should be reverted rather than applied.

        Returns:
            ``True`` if there are empty files in the patch. ``False`` if there
            were no empty files, or if an error occurred while applying the
            patch.
        """
        patched_empty_files = False
        added_files = re.findall(r'--- %s\t%s\n'
                                 r'\+\+\+ b/(\S+)\t[^\r\n\t\f]+\n'
                                 r'(?:[^@]|$)'
                                 % (self.PRE_CREATION,
                                    re.escape(self.PRE_CREATION_DATE)), patch)
        deleted_files = re.findall(r'--- a/(\S+)\t[^\r\n\t\f]+\n'
                                   r'\+\+\+ %s\t%s\n'
                                   r'(?:[^@]|$)'
                                   % (self.PRE_CREATION,
                                      re.escape(self.PRE_CREATION_DATE)),
                                   patch)

        if added_files:
            added_files = self._strip_p_num_slashes(added_files, int(p_num))
            make_empty_files(added_files)
            result = execute(['hg', 'add'] + added_files, ignore_errors=True,
                             none_on_ignored_error=True)

            if result is None:
                logging.error('Unable to execute "hg add" on: %s',
                              ', '.join(added_files))
            else:
                patched_empty_files = True

        if deleted_files:
            deleted_files = self._strip_p_num_slashes(deleted_files,
                                                      int(p_num))
            result = execute(['hg', 'remove'] + deleted_files,
                             ignore_errors=True, none_on_ignored_error=True)

            if result is None:
                logging.error('Unable to execute "hg remove" on: %s',
                              ', '.join(deleted_files))
            else:
                patched_empty_files = True

        return patched_empty_files

    def supports_empty_files(self):
        """Return whether the RB server supports added/deleted empty files.

        Returns:
            bool:
            ``True`` if the Review Board server supports showing empty files.
        """
        return (self.capabilities and
                self.capabilities.has_capability('scmtools', 'mercurial',
                                                 'empty_files'))

    def get_current_bookmark(self):
        """Return the name of the current bookmark.

        Returns:
            unicode:
            A string with the name of the current bookmark.
        """
        return execute(['hg', 'id', '-B'], ignore_errors=True).strip()
