"""A client for Git."""

from __future__ import unicode_literals

import logging
import os
import re
import sys

from rbtools.clients import PatchResult, SCMClient, RepositoryInfo
from rbtools.clients.errors import (AmendError, MergeError, PushError,
                                    InvalidRevisionSpecError,
                                    TooManyRevisionsError,
                                    SCMError)
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.svn import SVNClient, SVNRepositoryInfo
from rbtools.utils.checks import check_install, is_valid_version
from rbtools.utils.console import edit_text
from rbtools.utils.diffs import (normalize_patterns,
                                 remove_filenames_matching_patterns)
from rbtools.utils.process import execute


class GitClient(SCMClient):
    """A client for Git.

    This is a wrapper around the git executable that fetches repository
    information and generates compatible diffs. This will attempt to generate a
    diff suitable for the remote repository, whether git, SVN or Perforce.
    """

    name = 'Git'
    supports_diff_exclude_patterns = True
    supports_no_renames = True
    supports_patch_revert = True
    can_amend_commit = True
    can_merge = True
    can_push_upstream = True
    can_delete_branch = True
    can_branch = True

    TYPE_GIT = 0
    TYPE_GIT_SVN = 1
    TYPE_GIT_P4 = 2

    def __init__(self, **kwargs):
        """Initialize the client.

        Args:
            **kwargs (dict):
                Keyword arguments to pass through to the superclass.
        """
        super(GitClient, self).__init__(**kwargs)

        # Store the 'correct' way to invoke git, just plain old 'git' by
        # default.
        self.git = 'git'
        self._git_toplevel = None
        self._type = None

    def _supports_git_config_flag(self):
        """Return whether the installed version of git supports the -c flag.

        This will execute ``git --version`` on the first call and cache the
        result.

        Returns:
            bool:
            ``True`` if the user's installed git supports ``-c``.
        """
        if not hasattr(self, '_git_version_at_least_180'):
            self._git_version_least_180 = False

            version_str = execute([self.git, 'version'], ignore_errors=True,
                                  none_on_ignored_error=True)

            if version_str:
                m = re.search('(\d+)\.(\d+)\.(\d+)', version_str)

                if m:
                    git_version = (int(m.group(1)),
                                   int(m.group(2)),
                                   int(m.group(3)))

                    self._git_version_at_least_180 = git_version >= (1, 8, 0)

        return self._git_version_at_least_180

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

            These will be used to generate the diffs to upload to Review Board
            (or print). The diff for review will include the changes in (base,
            tip], and the parent diff (if necessary) will include (parent_base,
            base].

            If a single revision is passed in, this will return the parent of
            that revision for "base" and the passed-in revision for "tip".

            If zero revisions are passed in, this will return the current HEAD
            as "tip", and the upstream branch as "base", taking into account
            parent branches explicitly specified via --parent.
        """
        n_revs = len(revisions)
        result = {}

        if n_revs == 0:
            # No revisions were passed in. Start with HEAD, and find the
            # tracking branch automatically.
            head_ref = self._rev_parse(self.get_head_ref())[0]
            parent_branch = self._get_parent_branch()
            remote = self._find_remote(parent_branch)
            parent_ref = self._rev_parse(parent_branch)[0]

            merge_base = self._rev_list_youngest_remote_ancestor(
                parent_ref, remote)

            result = {
                'base': parent_ref,
                'tip': head_ref,
                'commit_id': head_ref,
            }

            if parent_ref != merge_base:
                result['parent_base'] = merge_base

            # Since the user asked us to operate on HEAD, warn them about a
            # dirty working directory.
            if (self.has_pending_changes() and
                not self.config.get('SUPPRESS_CLIENT_WARNINGS', False)):
                logging.warning('Your working directory is not clean. Any '
                                'changes which have not been committed '
                                'to a branch will not be included in your '
                                'review request.')

        elif n_revs == 1 or n_revs == 2:
            # Let `git rev-parse` sort things out.
            parsed = self._rev_parse(revisions)

            n_parsed_revs = len(parsed)
            assert n_parsed_revs <= 3

            if n_parsed_revs == 1:
                # Single revision. Extract the parent of that revision to use
                # as the base.
                parent = self._rev_parse('%s^' % parsed[0])[0]
                result = {
                    'base': parent,
                    'tip': parsed[0],
                    'commit_id': parsed[0],
                }
            elif n_parsed_revs == 2:
                if parsed[1].startswith('^'):
                    # Passed in revisions were probably formatted as
                    # "base..tip". The rev-parse output includes all ancestors
                    # of the first part, and none of the ancestors of the
                    # second. Basically, the second part is the base (after
                    # stripping the ^ prefix) and the first is the tip.
                    result = {
                        'base': parsed[1][1:],
                        'tip': parsed[0],
                    }
                else:
                    # First revision is base, second is tip
                    result = {
                        'base': parsed[0],
                        'tip': parsed[1],
                    }
            elif n_parsed_revs == 3 and parsed[2].startswith('^'):
                # Revision spec is diff-since-merge. Find the merge-base of the
                # two revs to use as base.
                merge_base = self._execute([self.git, 'merge-base', parsed[0],
                                            parsed[1]]).strip()
                result = {
                    'base': merge_base,
                    'tip': parsed[0],
                }
            else:
                raise InvalidRevisionSpecError(
                    'Unexpected result while parsing revision spec')

            parent_branch = self._get_parent_branch()
            remote = self._find_remote(parent_branch)
            parent_base = self._rev_list_youngest_remote_ancestor(
                result['base'], remote)

            if parent_base != result['base']:
                result['parent_base'] = parent_base
        else:
            raise TooManyRevisionsError

        return result

    def get_repository_info(self):
        """Get repository information for the current Git working tree.

        Returns:
            rbtools.clients.RepositoryInfo:
            The repository info structure.
        """
        # Temporarily reset the toplevel. This is necessary for making things
        # work correctly in unit tests where we may be moving the cwd around a
        # lot.
        self._git_toplevel = None

        if not check_install(['git', '--help']):
            # CreateProcess (launched via subprocess, used by check_install)
            # does not automatically append .cmd for things it finds in PATH.
            # If we're on Windows, and this works, save it for further use.
            if (sys.platform.startswith('win') and
                check_install(['git.cmd', '--help'])):
                self.git = 'git.cmd'
            else:
                logging.debug('Unable to execute "git --help" or "git.cmd '
                              '--help": skipping Git')
                return None

        git_dir = self._execute([self.git, 'rev-parse', '--git-dir'],
                                ignore_errors=True).rstrip('\n')

        if git_dir.startswith('fatal:') or not os.path.isdir(git_dir):
            return None

        # Sometimes core.bare is not set, and generates an error, so ignore
        # errors. Valid values are 'true' or '1'.
        bare = execute([self.git, 'config', 'core.bare'],
                       ignore_errors=True).strip()
        self.bare = bare in ('true', '1')

        # Running in directories other than the top level of
        # of a work-tree would result in broken diffs on the server
        if not self.bare:
            git_top = execute([self.git, 'rev-parse', '--show-toplevel'],
                              ignore_errors=True).rstrip('\n')

            # Top level might not work on old git version se we use git dir
            # to find it.
            if (git_top.startswith(('fatal:', 'cygdrive')) or
                not os.path.isdir(git_dir)):
                git_top = git_dir

            self._git_toplevel = os.path.abspath(git_top)

        self._head_ref = self._execute(
            [self.git, 'symbolic-ref', '-q', 'HEAD'],
            ignore_errors=True).strip()

        # We know we have something we can work with. Let's find out
        # what it is. We'll try SVN first, but only if there's a .git/svn
        # directory. Otherwise, it may attempt to create one and scan
        # revisions, which can be slow. Also skip SVN detection if the git
        # repository was specified on command line.
        git_svn_dir = os.path.join(git_dir, 'svn')

        if (not getattr(self.options, 'repository_url', None) and
            os.path.isdir(git_svn_dir) and
            len(os.listdir(git_svn_dir)) > 0):
            data = self._execute([self.git, 'svn', 'info'], ignore_errors=True)

            m = re.search(r'^Repository Root: (.+)$', data, re.M)

            if m:
                path = m.group(1)
                m = re.search(r'^URL: (.+)$', data, re.M)

                if m:
                    base_path = m.group(1)[len(path):] or '/'
                    m = re.search(r'^Repository UUID: (.+)$', data, re.M)

                    if m:
                        uuid = m.group(1)
                        self._type = self.TYPE_GIT_SVN

                        m = re.search(r'Working Copy Root Path: (.+)$', data,
                                      re.M)

                        if m:
                            local_path = m.group(1)
                        else:
                            local_path = self._git_toplevel

                        return SVNRepositoryInfo(path=path,
                                                 base_path=base_path,
                                                 local_path=local_path,
                                                 uuid=uuid,
                                                 supports_parent_diffs=True)
            else:
                # Versions of git-svn before 1.5.4 don't (appear to) support
                # 'git svn info'.  If we fail because of an older git install,
                # here, figure out what version of git is installed and give
                # the user a hint about what to do next.
                version = self._execute([self.git, 'svn', '--version'],
                                        ignore_errors=True)
                version_parts = re.search('version (\d+)\.(\d+)\.(\d+)',
                                          version)
                svn_remote = self._execute(
                    [self.git, 'config', '--get', 'svn-remote.svn.url'],
                    ignore_errors=True)

                if (version_parts and svn_remote and
                    not is_valid_version((int(version_parts.group(1)),
                                          int(version_parts.group(2)),
                                          int(version_parts.group(3))),
                                         (1, 5, 4))):
                    raise SCMError('Your installation of git-svn must be '
                                   'upgraded to version 1.5.4 or later.')

        # Okay, maybe Perforce (git-p4).
        git_p4_ref = os.path.join(git_dir, 'refs', 'remotes', 'p4', 'master')
        if os.path.exists(git_p4_ref):
            data = self._execute([self.git, 'config', '--get', 'git-p4.port'],
                                 ignore_errors=True)
            m = re.search(r'(.+)', data)
            if m:
                port = m.group(1)
            else:
                port = os.getenv('P4PORT')

            if port:
                self._type = self.TYPE_GIT_P4
                return RepositoryInfo(path=port,
                                      base_path='',
                                      local_path=self._git_toplevel,
                                      supports_parent_diffs=True)

        # Nope, it's git then.
        # Check for a tracking branch and determine merge-base
        self._type = self.TYPE_GIT
        url = None

        if getattr(self.options, 'repository_url', None):
            url = self.options.repository_url
        else:
            upstream_branch = self._get_parent_branch()
            url = self._get_origin(upstream_branch).rstrip('/')

            if url.startswith('fatal:'):
                raise SCMError('Could not determine remote URL for upstream '
                               'branch %s' % upstream_branch)

            # Central bare repositories don't have origin URLs.
            # We return git_dir instead and hope for the best.
            if not url:
                url = os.path.abspath(git_dir)

        if url:
            return RepositoryInfo(path=url,
                                  base_path='',
                                  local_path=self._git_toplevel,
                                  supports_parent_diffs=True)
        return None

    def _strip_heads_prefix(self, ref):
        """Strip the heads prefix off of a reference name.

        Args:
            ref (unicode):
                The full name of a branch.

        Returns:
            unicode:
            The bare name of the branch without the ``refs/heads/`` prefix.
        """
        return re.sub(r'^refs/heads/', '', ref)

    def _get_origin(self, upstream_branch):
        """Return the remote URL for the given upstream branch.

        Args:
            upstream_branch (unicode):
                The name of the upstream branch.

        Returns:
            tuple of unicode:
            A 2-tuple, containing the upstream branch name and the remote URL.
        """
        upstream_remote = upstream_branch.split('/')[0]
        return self._execute(
            [self.git, 'config', '--get', 'remote.%s.url' % upstream_remote],
            ignore_errors=True).rstrip('\n')

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
        server_url = super(GitClient, self).scan_for_server(repository_info)

        if server_url:
            return server_url

        # TODO: Maybe support a server per remote later? Is that useful?
        url = self._execute([self.git, 'config', '--get', 'reviewboard.url'],
                            ignore_errors=True).strip()
        if url:
            return url

        if self._type == self.TYPE_GIT_SVN:
            # Try using the reviewboard:url property on the SVN repo, if it
            # exists.
            prop = SVNClient().scan_for_server_property(repository_info)

            if prop:
                return prop
        elif self._type == self.TYPE_GIT_P4:
            prop = PerforceClient().scan_for_server(repository_info)

            if prop:
                return prop

        return None

    def get_raw_commit_message(self, revisions):
        """Extract the commit message based on the provided revision range.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

        Returns:
            unicode:
            The commit messages of all commits between (base, tip].
        """
        return self._execute(
            [self.git, 'log', '--reverse', '--pretty=format:%s%n%n%b',
             '^%s' % revisions['base'], revisions['tip']],
            ignore_errors=True).strip()

    def _get_parent_branch(self):
        """Return the parent branch.

        Returns:
            unicode:
            The name of the current parent branch.
        """
        # If the user has manually specified the parent, return that.
        parent_branch = (getattr(self.options, 'parent_branch', None) or
                         getattr(self.options, 'tracking', None))

        if parent_branch:
            return parent_branch

        if self._type == self.TYPE_GIT_SVN:
            data = self._execute(
                [self.git, 'svn', 'rebase', '-n'],
                ignore_errors=True)
            m = re.search(r'^Remote Branch:\s*(.+)$', data, re.M)

            if m:
                return m.group(1)
            else:
                logging.warning('Failed to determine SVN tracking branch. '
                                'Defaulting to "master"\n')
                return 'master'
        elif self._type == self.TYPE_GIT_P4:
            return 'p4/master'
        elif self._type == self.TYPE_GIT:
            if self._head_ref:
                short_head = self._strip_heads_prefix(self._head_ref)
                merge = self._strip_heads_prefix(self._execute(
                    [self.git, 'config', '--get',
                     'branch.%s.merge' % short_head],
                    ignore_errors=True).strip())
                remote = self._get_remote(short_head)

                if remote and remote != '.' and merge:
                    return '%s/%s' % (remote, merge)

            return 'origin/master'
        else:
            raise ValueError('Unknown git client type %s' % self._type)

    def get_head_ref(self):
        """Return the HEAD reference.

        Returns:
            unicode:
            The name of the HEAD reference.
        """
        return self._head_ref or 'HEAD'

    def _rev_parse(self, revisions):
        """Parse a git symbolic reference.

        Args:
            revisions (unicode or list):
                A set of revisions passed in by the user. This can either be a
                single revision name or a range.

        Returns:
            list of unicode:
            A list of the parsed revision data. This can be either 1, 2, or 3
            elements long, depending on the exact string provided.
        """
        if not isinstance(revisions, list):
            revisions = [revisions]

        revisions = self._execute([self.git, 'rev-parse'] + revisions)
        return revisions.strip().split('\n')

    def _rev_list_youngest_remote_ancestor(self, local_branch, remote):
        """Return the youngest ancestor of ``local_branch`` on ``remote``.

        Args:
            local_branch (unicode):
                The commit whose ancestor we are trying to find.

            remote (unicode):
                This is most commonly ``origin``, but can be changed via
                configuration or command line options. This represents the
                remote which is configured in Review Board.

        Returns:
            unicode:
            The youngest ancestor of local_branch that is also contained in
            the remote repository (where youngest means the commit that can
            be reached from local_branch by following the least number of
            parent links).
        """
        local_commits = self._execute(
            [self.git, 'rev-list', local_branch, '--not',
             '--remotes=%s' % remote])
        local_commits = local_commits.split()

        if local_commits == []:
            # We are currently at a commit also available to the remote.
            return local_branch

        local_commit = local_commits[-1]
        youngest_remote_commit = self._rev_parse('%s^' % local_commit)[0]
        logging.debug('Found youngest remote git commit %s',
                      youngest_remote_commit)
        return youngest_remote_commit

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             no_renames=False, extra_args=[]):
        """Perform a diff using the given revisions.

        If no revisions are specified, this will do a diff of the contents of
        the current branch since the tracking branch (which defaults to
        'master'). If one revision is specified, this will get the diff of that
        specific change. If two revisions are specified, this will do a diff
        between those two revisions.

        If a parent branch is specified via the command line options, or would
        make sense given the requested revisions and the tracking branch, this
        will also return a parent diff.

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
                Unused for git.

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
        exclude_patterns = normalize_patterns(exclude_patterns,
                                              self._git_toplevel,
                                              cwd=os.getcwd())

        try:
            merge_base = revisions['parent_base']
        except KeyError:
            merge_base = revisions['base']

        diff_lines = self.make_diff(merge_base,
                                    revisions['base'],
                                    revisions['tip'],
                                    include_files,
                                    exclude_patterns,
                                    no_renames)

        if 'parent_base' in revisions:
            parent_diff_lines = self.make_diff(merge_base,
                                               revisions['parent_base'],
                                               revisions['base'],
                                               include_files,
                                               exclude_patterns,
                                               no_renames)

            base_commit_id = revisions['parent_base']
        else:
            parent_diff_lines = None
            base_commit_id = revisions['base']

        return {
            'diff': diff_lines,
            'parent_diff': parent_diff_lines,
            'commit_id': revisions.get('commit_id'),
            'base_commit_id': base_commit_id,
        }

    def make_diff(self, merge_base, base, tip, include_files,
                  exclude_patterns, no_renames=False):
        """Perform a diff on a particular branch range.

        Args:
            merge_base (unicode):
                The ID of the merge base commit. This is only used when
                creating diffs with git-svn or git-p4 clones.

            base (unicode):
                The ID of the base commit for the diff.

            tip (unicode):
                The ID of the tip commit for the diff.

            include_files (list of unicode):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of unicode):
                A list of shell-style glob patterns to blacklist during diff
                generation.

        Returns:
            bytes:
            The diff between (base, tip].
        """
        rev_range = '%s..%s' % (base, tip)

        if include_files:
            include_files = ['--'] + include_files

        git_cmd = [self.git]

        if self._supports_git_config_flag():
            git_cmd.extend(['-c', 'core.quotepath=false'])

        if self._type in (self.TYPE_GIT_SVN, self.TYPE_GIT_P4):
            diff_cmd_params = ['--no-color', '--no-prefix', '-r', '-u']
        elif self._type == self.TYPE_GIT:
            diff_cmd_params = ['--no-color', '--full-index',
                               '--ignore-submodules']

            if self._supports_git_config_flag():
                git_cmd.extend(['-c', 'diff.noprefix=false'])

            if (not no_renames and
                self.capabilities is not None and
                self.capabilities.has_capability('diffs', 'moved_files')):
                diff_cmd_params.append('-M')
            else:
                diff_cmd_params.append('--no-renames')
        else:
            raise ValueError('Unknown git client type %s' % self._type)

        # By default, don't allow using external diff commands. This prevents
        # things from breaking horribly if someone configures a graphical diff
        # viewer like p4merge or kaleidoscope. This can be overridden by
        # setting GIT_USE_EXT_DIFF = True in ~/.reviewboardrc
        if not self.config.get('GIT_USE_EXT_DIFF', False):
            diff_cmd_params.append('--no-ext-diff')

        diff_cmd = git_cmd + ['diff'] + diff_cmd_params

        if exclude_patterns:
            # If we have specified files to exclude, we will get a list of all
            # changed files and run `git diff` on each un-excluded file
            # individually.
            changed_files_cmd = git_cmd + ['diff-tree'] + diff_cmd_params

            if self._type in (self.TYPE_GIT_SVN, self.TYPE_GIT_P4):
                # We don't want to send -u along to git diff-tree because it
                # will generate diff information along with the list of
                # changed files.
                changed_files_cmd.remove('-u')
            elif self._type == self.TYPE_GIT:
                changed_files_cmd.append('-r')

            changed_files = self._execute(
                changed_files_cmd + [rev_range] + include_files,
                split_lines=True,
                with_errors=False,
                ignore_errors=True,
                none_on_ignored_error=True,
                log_output_on_error=False)

            # The output of git diff-tree will be a list of entries that have
            # changed between the two revisions that we give it. The last part
            # of the line is the name of the file that has changed.
            changed_files = remove_filenames_matching_patterns(
                (filename.split()[-1] for filename in changed_files),
                exclude_patterns, base_dir=self._git_toplevel)

            diff_lines = []

            for filename in changed_files:
                lines = self._execute(diff_cmd + [rev_range, '--', filename],
                                      split_lines=True,
                                      with_errors=False,
                                      ignore_errors=True,
                                      none_on_ignored_error=True,
                                      log_output_on_error=False,
                                      results_unicode=False)

                if lines is None:
                    logging.error(
                        'Could not get diff for all files (git-diff failed '
                        'for "%s"). Refusing to return a partial diff.',
                        filename)

                    diff_lines = None
                    break

                diff_lines += lines

        else:
            diff_lines = self._execute(diff_cmd + [rev_range] + include_files,
                                       split_lines=True,
                                       with_errors=False,
                                       ignore_errors=True,
                                       none_on_ignored_error=True,
                                       log_output_on_error=False,
                                       results_unicode=False)

        if self._type == self.TYPE_GIT_SVN:
            return self.make_svn_diff(merge_base, diff_lines)
        elif self._type == self.TYPE_GIT_P4:
            return self.make_perforce_diff(merge_base, diff_lines)
        else:
            return b''.join(diff_lines)

    def make_svn_diff(self, merge_base, diff_lines):
        """Format a git-svn diff to apply correctly against an SVN repository.

        This reformats the diff from a git-svn clone to look like it came from
        :command:`svn diff`. This is needed so that the SVNTool in Review Board
        can properly parse the diff.

        Args:
            merge_base (unicode):
                The ID of the merge base commit. This is only used when
                creating diffs with :command:`git svn` or :command:`git p4`
                clones.

            diff_lines (list of bytes):
                The lines of the diff.

        Returns:
            bytes:
            The reformatted diff contents.
        """
        rev = self._execute([self.git, 'svn', 'find-rev', merge_base]).strip()

        if not rev:
            return None

        diff_data = b''
        original_file = b''
        filename = b''
        newfile = False

        for i, line in enumerate(diff_lines):
            if line.startswith(b'diff '):
                # Grab the filename and then filter this out.
                # This will be in the format of:
                #
                # diff --git a/path/to/file b/path/to/file
                info = line.split(b' ')
                diff_data += b'Index: %s\n' % info[2]
                diff_data += b'=' * 67
                diff_data += b'\n'
            elif line.startswith(b'index '):
                # Filter this out.
                pass
            elif line.strip() == b'--- /dev/null':
                # New file
                newfile = True
            elif (line.startswith(b'--- ') and i + 1 < len(diff_lines) and
                  diff_lines[i + 1].startswith(b'+++ ')):
                newfile = False
                original_file = line[4:].strip()
                diff_data += b'--- %s\t(revision %s)\n' % (original_file, rev)
            elif line.startswith(b'+++ '):
                filename = line[4:].strip()
                if newfile:
                    diff_data += b'--- %s\t(revision 0)\n' % filename
                    diff_data += b'+++ %s\t(revision 0)\n' % filename
                else:
                    # We already printed the "--- " line.
                    diff_data += b'+++ %s\t(working copy)\n' % original_file
            elif (line.startswith(b'new file mode') or
                  line.startswith(b'deleted file mode')):
                # Filter this out.
                pass
            elif line.startswith(b'Binary files '):
                # Add the following so that we know binary files were
                # added/changed.
                diff_data += b'Cannot display: file marked as a binary type.\n'
                diff_data += b'svn:mime-type = application/octet-stream\n'
            else:
                diff_data += line

        return diff_data

    def make_perforce_diff(self, merge_base, diff_lines):
        """Format a git-p4 diff to apply correctly against a P4 repository.

        This reformats the diff from a :command:`git p4` clone to look like it
        came from a Perforce repository. This is needed so that the
        PerforceTool in Review Board can properly parse the diff.

        Args:
            merge_base (unicode):
                The ID of the merge base commit. This is only used when
                creating diffs with :command:`git svn` or
                :command:`git p4` clones.

            diff_lines (list of bytes):
                The lines of the diff.

        Returns:
            bytes:
            The reformatted diff contents.
        """
        diff_data = b''
        filename = b''
        p4rev = b''

        # Find which depot changelist we're based on
        log = self._execute([self.git, 'log', merge_base], ignore_errors=True)

        for line in log:
            m = re.search(br'[rd]epo.-paths = "(.+)": change = (\d+).*\]',
                          log, re.M)

            if m:
                base_path = m.group(1).strip()
                p4rev = m.group(2).strip()
                break
            else:
                # We should really raise an error here, base_path is required
                pass

        for i, line in enumerate(diff_lines):
            if line.startswith(b'diff '):
                # Grab the filename and then filter this out.
                # This will be in the format of:
                #    diff --git a/path/to/file b/path/to/file
                filename = line.split(b' ')[2].strip()
            elif (line.startswith(b'index ') or
                  line.startswith(b'new file mode ')):
                # Filter this out
                pass
            elif (line.startswith(b'--- ') and i + 1 < len(diff_lines) and
                  diff_lines[i + 1].startswith(b'+++ ')):
                data = self._execute(
                    ['p4', 'files', base_path + filename + '@' + p4rev],
                    ignore_errors=True, results_unicode=False)
                m = re.search(br'^%s%s#(\d+).*$' % (re.escape(base_path),
                                                    re.escape(filename)),
                              data, re.M)
                if m:
                    file_version = m.group(1).strip()
                else:
                    file_version = 1

                diff_data += b'--- %s%s\t%s%s#%s\n' % (base_path, filename,
                                                       base_path, filename,
                                                       file_version)
            elif line.startswith(b'+++ '):
                # TODO: add a real timestamp
                diff_data += b'+++ %s%s\t%s\n' % (base_path, filename,
                                                  b'TIMESTAMP')
            else:
                diff_data += line

        return diff_data

    def has_pending_changes(self):
        """Check if there are changes waiting to be committed.

        Returns:
            bool:
            ``True`` if the working directory has been modified or if changes
            have been staged in the index.
        """
        status = self._execute(['git', 'status', '--porcelain',
                                '--untracked-files=no',
                                '--ignore-submodules=dirty'])
        return status != ''

    def amend_commit_description(self, message, revisions):
        """Update a commit message to the given string.

        Args:
            message (unicode):
                The commit message to use when amending the commit.

            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

        Raises:
            rbtools.clients.errors.AmendError:
                The requested revision tip was not the most recent commit.
                Unless rewriting the entire series of commits, git can only
                amend the latest commit on the branch.
        """
        if revisions and revisions['tip']:
            commit_ids = self._execute(
                [self.git, 'rev-parse', 'HEAD', revisions['tip']],
                split_lines=True)
            head_id = commit_ids[0].strip()
            revision_id = commit_ids[1].strip()

            if head_id != revision_id:
                raise AmendError('Commit "%s" is not the latest commit, '
                                 'and thus cannot be modified' % revision_id)

        self._execute([self.git, 'commit', '--amend', '-m', message])

    def apply_patch(self, patch_file, base_path=None, base_dir=None, p=None,
                    revert=False):
        """Apply the given patch to index.

        This will take the given patch file and apply it to the index,
        scheduling all changes for commit.

        Args:
            patch_file (unicode):
                The name of the patch file to apply.

            base_path (unicode, unused):
                The base path that the diff was generated in. All git diffs are
                absolute to the repository root, so this is unused.

            base_dir (unicode, unused):
                The path of the current working directory relative to the root
                of the repository. All git diffs are absolute to the repository
                root, so this is unused.

            p (unicode, optional):
                The prefix level of the diff.

            revert (bool, optional):
                Whether the patch should be reverted rather than applied.

        Returns:
            rbtools.clients.PatchResult:
            The result of the patch operation.
        """
        cmd = ['git', 'apply', '-3']

        if revert:
            cmd.append('-R')

        if p:
            cmd += ['-p', p]

        cmd.append(patch_file)

        rc, data = self._execute(cmd, ignore_errors=True, with_errors=True,
                                 return_error_code=True)

        if rc == 0:
            return PatchResult(applied=True, patch_output=data)
        elif 'with conflicts' in data:
            return PatchResult(
                applied=True,
                has_conflicts=True,
                conflicting_files=[
                    line.split(' ', 1)[1]
                    for line in data.splitlines()
                    if line.startswith('U')
                ],
                patch_output=data)
        else:
            return PatchResult(applied=False, patch_output=data)

    def create_commit(self, message, author, run_editor,
                      files=[], all_files=False):
        """Commit the given modified files.

        This is expected to be called after applying a patch. This commits the
        patch using information from the review request, opening the commit
        message in :envvar:`$EDITOR` to allow the user to update it.

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

        if all_files:
            self._execute(['git', 'add', '--all', ':/'])
        elif files:
            self._execute(['git', 'add'] + files)

        cmd = ['git', 'commit', '-m', modified_message]

        try:
            cmd.append('--author="%s <%s>"'
                       % (author.fullname, author.email))
        except AttributeError:
            # Users who have marked their profile as private won't include the
            # fullname or email fields in the API payload. Just commit as the
            # user running RBTools.
            logging.warning('The author has marked their Review Board profile '
                            'information as private. Committing without '
                            'author attribution.')

        self._execute(cmd)

    def delete_branch(self, branch_name, merged_only=True):
        """Delete the specified branch.

        Args:
            branch_name (unicode):
                The name of the branch to delete.

            merged_only (bool, optional):
                Whether to limit branch deletion to only those branches which
                have been merged into the current HEAD.
        """
        if merged_only:
            delete_flag = '-d'
        else:
            delete_flag = '-D'

        self._execute(['git', 'branch', delete_flag, branch_name])

    def merge(self, target, destination, message, author, squash=False,
              run_editor=False):
        """Merge the target branch with destination branch.

        Args:
            target (unicode):
                The name of the branch to merge.

            destination (unicode):
                The name of the branch to merge into.

            message (unicode):
                The commit message to use.

            author (object):
                The author of the commit. This is expected to have ``fullname``
                and ``email`` attributes.

            squash (bool, optional):
                Whether to squash the commits or do a plain merge.

            run_editor (bool, optional):
                Whether to run the user's editor on the commmit message before
                committing.

        Raises:
            rbtools.clients.errors.MergeError:
                An error occurred while merging the branch.
        """
        rc, output = self._execute(
            ['git', 'checkout', destination],
            ignore_errors=True,
            return_error_code=True)

        if rc:
            raise MergeError('Could not checkout to branch "%s".\n\n%s' %
                             (destination, output))

        if squash:
            method = '--squash'
        else:
            method = '--no-ff'

        rc, output = self._execute(
            ['git', 'merge', target, method, '--no-commit'],
            ignore_errors=True,
            return_error_code=True)

        if rc:
            raise MergeError('Could not merge branch "%s" into "%s".\n\n%s' %
                             (target, destination, output))

        self.create_commit(message, author, run_editor)

    def push_upstream(self, local_branch):
        """Push the current branch to upstream.

        Args:
            local_branch (unicode):
                The name of the branch to push.

        Raises:
            rbtools.client.errors.PushError:
                The branch was unable to be pushed.
        """
        remote = self._get_remote(local_branch)

        if remote is None:
            raise PushError('Could not determine remote for branch "%s".'
                            % local_branch)

        rc, output = self._execute(
            ['git', 'pull', '--rebase', remote, local_branch],
            ignore_errors=True,
            return_error_code=True)

        if rc:
            raise PushError('Could not pull changes from upstream.')

        rc, output = self._execute(
            ['git', 'push', remote, local_branch],
            ignore_errors=True,
            return_error_code=True)

        if rc:
            raise PushError('Could not push branch "%s" to upstream.' %
                            local_branch)

    def get_current_branch(self):
        """Return the name of the current branch.

        Returns:
            unicode:
            The name of the directory corresponding to the root of the current
            working directory (whether a plain checkout or a git worktree). If
            no repository can be found, this will return None.
        """
        return self._execute([self.git, 'rev-parse', '--abbrev-ref', 'HEAD'],
                             ignore_errors=True).strip()

    def _execute(self, cmdline, *args, **kwargs):
        """Execute a git command within the correct cwd.

        Args:
            cmdline (list of unicode):
                A command-line to execute.

            *args (list):
                Positional arguments to pass through to
                :py:func:`rbtools.utils.process.execute`.

            *kwargs (dict):
                Keyword arguments to pass through to
                :py:func:`rbtools.utils.process.execute`.

        Returns:
            tuple:
            The result from the execute call.
        """
        return execute(cmdline, cwd=self._git_toplevel, *args, **kwargs)

    def _get_remote(self, local_branch):
        """Return the remote for a given branch.

        Args:
            local_branch (unicode):
                The name of the local branch.

        Returns:
            unicode:
            The name of the remote corresponding to the local branch. May
            return None if there is no remote.
        """
        rc, output = self._execute(
            ['git', 'config', '--get', 'branch.%s.remote' % local_branch],
            ignore_errors=True,
            return_error_code=True)

        if rc == 0:
            return output.strip()
        else:
            return None

    def _find_remote(self, local_or_remote_branch):
        """Find the remote given a branch name.

        This takes in a branch name which can be either a local or remote
        branch, and attempts to determine the name of the remote.

        Args:
            local_or_remote_branch (unicode):
                The name of a branch to find the remote for.

        Returns:
            unicode:
            The name of the remote for the given branch. Returns ``origin`` if
            no associated remote can be found.

        Raises:
            rbtools.clients.errors.SCMError:
                The current repository did not have any remotes configured.
        """
        all_remote_branches = [
            branch.strip()
            for branch in self._execute(['git', 'branch', '--remotes'],
                                        split_lines=True)
        ]

        if local_or_remote_branch in all_remote_branches:
            return local_or_remote_branch.split('/', 1)[0]

        remote = self._get_remote(local_or_remote_branch)

        if remote:
            return remote

        all_remotes = self._execute(['git', 'remote'], split_lines=True)

        if len(all_remotes) >= 1:
            # We prefer "origin" if it's present, otherwise just choose at
            # random.
            if 'origin' in all_remotes:
                return 'origin'
            else:
                logging.warning('Could not determine specific upstream remote '
                                'to use for diffs. We recommend setting '
                                'TRACKING_BRANCH in reviewboardrc to your '
                                'nearest upstream remote branch.')
                return all_remotes[0]
        else:
            raise SCMError('This clone has no configured remotes.')
