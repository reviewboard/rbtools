import logging
import os
import re
import sys

from rbtools.clients import PatchResult, SCMClient, RepositoryInfo
from rbtools.clients.errors import (AmendError, MergeError, PushError,
                                    InvalidRevisionSpecError,
                                    TooManyRevisionsError)
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.svn import SVNClient, SVNRepositoryInfo
from rbtools.utils.checks import check_install, is_valid_version
from rbtools.utils.console import edit_text
from rbtools.utils.diffs import (normalize_patterns,
                                 remove_filenames_matching_patterns)
from rbtools.utils.process import die, execute


class GitClient(SCMClient):
    """
    A wrapper around git that fetches repository information and generates
    compatible diffs. This will attempt to generate a diff suitable for the
    remote repository, whether git, SVN or Perforce.
    """
    name = 'Git'

    supports_diff_exclude_patterns = True
    supports_patch_revert = True

    can_amend_commit = True
    can_merge = True
    can_push_upstream = True
    can_delete_branch = True

    def __init__(self, **kwargs):
        super(GitClient, self).__init__(**kwargs)
        # Store the 'correct' way to invoke git, just plain old 'git' by
        # default.
        self.git = 'git'

        self._original_cwd = None

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
            'commit_id':   (optional) The ID of the single commit being posted,
                           if not using a range.

        These will be used to generate the diffs to upload to Review Board (or
        print). The diff for review will include the changes in (base, tip],
        and the parent diff (if necessary) will include (parent_base, base].

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
            # tracking branch automatically.
            parent_branch = self.get_parent_branch()
            head_ref = self._rev_parse(self.get_head_ref())[0]
            merge_base = self._rev_parse(
                self._get_merge_base(head_ref, self.upstream_branch))[0]

            result = {
                'tip': head_ref,
                'commit_id': head_ref,
            }

            if parent_branch:
                result['base'] = self._rev_parse(parent_branch)[0]
                result['parent_base'] = merge_base
            else:
                result['base'] = merge_base

            # Since the user asked us to operate on HEAD, warn them about a
            # dirty working directory
            if self.has_pending_changes():
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
                merge_base = execute([self.git, 'merge-base', parsed[0],
                                      parsed[1]]).strip()
                result = {
                    'base': merge_base,
                    'tip': parsed[0],
                }
            else:
                raise InvalidRevisionSpecError(
                    'Unexpected result while parsing revision spec')

            parent_base = self._get_merge_base(result['base'],
                                               self.upstream_branch)
            if parent_base != result['base']:
                result['parent_base'] = parent_base
        else:
            raise TooManyRevisionsError

        return result

    def get_repository_info(self):
        """Get repository information for the current Git working tree.

        This function changes the directory to the top level directory of the
        current working tree.
        """
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

        git_dir = execute([self.git, "rev-parse", "--git-dir"],
                          ignore_errors=True).rstrip("\n")

        if git_dir.startswith("fatal:") or not os.path.isdir(git_dir):
            return None

        # Sometimes core.bare is not set, and generates an error, so ignore
        # errors. Valid values are 'true' or '1'.
        bare = execute([self.git, 'config', 'core.bare'],
                       ignore_errors=True).strip()
        self.bare = bare in ('true', '1')

        # If we are not working in a bare repository, then we will change
        # directory to the top level working tree lose our original position.
        # However, we need the original working directory for file exclusion
        # patterns, so we save it here.
        if self._original_cwd is None:
            self._original_cwd = os.getcwd()

        # Running in directories other than the top level of
        # of a work-tree would result in broken diffs on the server
        if not self.bare:
            git_top = execute([self.git, "rev-parse", "--show-toplevel"],
                              ignore_errors=True).rstrip("\n")

            # Top level might not work on old git version se we use git dir
            # to find it.
            if (git_top.startswith('fatal:') or not os.path.isdir(git_dir)
                or git_top.startswith('cygdrive')):
                git_top = git_dir

            os.chdir(os.path.abspath(git_top))

        self.head_ref = execute([self.git, 'symbolic-ref', '-q',
                                 'HEAD'], ignore_errors=True).strip()

        # We know we have something we can work with. Let's find out
        # what it is. We'll try SVN first, but only if there's a .git/svn
        # directory. Otherwise, it may attempt to create one and scan
        # revisions, which can be slow. Also skip SVN detection if the git
        # repository was specified on command line.
        git_svn_dir = os.path.join(git_dir, 'svn')

        if (not getattr(self.options, 'repository_url', None) and
            os.path.isdir(git_svn_dir) and len(os.listdir(git_svn_dir)) > 0):
            data = execute([self.git, "svn", "info"], ignore_errors=True)

            m = re.search(r'^Repository Root: (.+)$', data, re.M)

            if m:
                path = m.group(1)
                m = re.search(r'^URL: (.+)$', data, re.M)

                if m:
                    base_path = m.group(1)[len(path):] or "/"
                    m = re.search(r'^Repository UUID: (.+)$', data, re.M)

                    if m:
                        uuid = m.group(1)
                        self.type = "svn"

                        # Get SVN tracking branch
                        if getattr(self.options, 'tracking', None):
                            self.upstream_branch = self.options.tracking
                        else:
                            data = execute([self.git, "svn", "rebase", "-n"],
                                           ignore_errors=True)
                            m = re.search(r'^Remote Branch:\s*(.+)$', data,
                                          re.M)

                            if m:
                                self.upstream_branch = m.group(1)
                            else:
                                sys.stderr.write('Failed to determine SVN '
                                                 'tracking branch. Defaulting'
                                                 'to "master"\n')
                                self.upstream_branch = 'master'

                        return SVNRepositoryInfo(path=path,
                                                 base_path=base_path,
                                                 uuid=uuid,
                                                 supports_parent_diffs=True)
            else:
                # Versions of git-svn before 1.5.4 don't (appear to) support
                # 'git svn info'.  If we fail because of an older git install,
                # here, figure out what version of git is installed and give
                # the user a hint about what to do next.
                version = execute([self.git, "svn", "--version"],
                                  ignore_errors=True)
                version_parts = re.search('version (\d+)\.(\d+)\.(\d+)',
                                          version)
                svn_remote = execute(
                    [self.git, "config", "--get", "svn-remote.svn.url"],
                    ignore_errors=True)

                if (version_parts and svn_remote and
                    not is_valid_version((int(version_parts.group(1)),
                                          int(version_parts.group(2)),
                                          int(version_parts.group(3))),
                                         (1, 5, 4))):
                    die("Your installation of git-svn must be upgraded to "
                        "version 1.5.4 or later")

        # Okay, maybe Perforce (git-p4).
        git_p4_ref = os.path.join(git_dir, 'refs', 'remotes', 'p4', 'master')
        if os.path.exists(git_p4_ref):
            data = execute([self.git, 'config', '--get', 'git-p4.port'],
                           ignore_errors=True)
            m = re.search(r'(.+)', data)
            if m:
                port = m.group(1)
            else:
                port = os.getenv('P4PORT')

            if port:
                self.type = 'perforce'
                self.upstream_branch = 'remotes/p4/master'
                return RepositoryInfo(path=port,
                                      base_path='',
                                      supports_parent_diffs=True)

        # Nope, it's git then.
        # Check for a tracking branch and determine merge-base
        self.upstream_branch = ''
        if self.head_ref:
            short_head = self._strip_heads_prefix(self.head_ref)
            merge = execute([self.git, 'config', '--get',
                             'branch.%s.merge' % short_head],
                            ignore_errors=True).strip()
            remote = execute([self.git, 'config', '--get',
                              'branch.%s.remote' % short_head],
                             ignore_errors=True).strip()

            merge = self._strip_heads_prefix(merge)

            if remote and remote != '.' and merge:
                self.upstream_branch = '%s/%s' % (remote, merge)

        url = None
        if getattr(self.options, 'repository_url', None):
            url = self.options.repository_url
            self.upstream_branch = self.get_origin(self.upstream_branch,
                                                   True)[0]
        else:
            self.upstream_branch, origin_url = \
                self.get_origin(self.upstream_branch, True)

            if not origin_url or origin_url.startswith("fatal:"):
                self.upstream_branch, origin_url = self.get_origin()

            url = origin_url.rstrip('/')

            # Central bare repositories don't have origin URLs.
            # We return git_dir instead and hope for the best.
            if not url:
                url = os.path.abspath(git_dir)

                # There is no remote, so skip this part of upstream_branch.
                self.upstream_branch = self.upstream_branch.split('/')[-1]

        if url:
            self.type = "git"
            return RepositoryInfo(path=url, base_path='',
                                  supports_parent_diffs=True)
        return None

    def _strip_heads_prefix(self, ref):
        """Strips prefix from ref name, if possible."""
        return re.sub(r'^refs/heads/', '', ref)

    def get_origin(self, default_upstream_branch=None, ignore_errors=False):
        """Get upstream remote origin from options or parameters.

        Returns a tuple: (upstream_branch, remote_url)
        """
        upstream_branch = (getattr(self.options, 'tracking', None) or
                           default_upstream_branch or
                           'origin/master')
        upstream_remote = upstream_branch.split('/')[0]
        origin_url = execute(
            [self.git, "config", "--get", "remote.%s.url" % upstream_remote],
            ignore_errors=True).rstrip("\n")
        return (upstream_branch, origin_url)

    def scan_for_server(self, repository_info):
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = super(GitClient, self).scan_for_server(repository_info)

        if server_url:
            return server_url

        # TODO: Maybe support a server per remote later? Is that useful?
        url = execute([self.git, "config", "--get", "reviewboard.url"],
                      ignore_errors=True).strip()
        if url:
            return url

        if self.type == "svn":
            # Try using the reviewboard:url property on the SVN repo, if it
            # exists.
            prop = SVNClient().scan_for_server_property(repository_info)

            if prop:
                return prop
        elif self.type == 'perforce':
            prop = PerforceClient().scan_for_server(repository_info)

            if prop:
                return prop

        return None

    def get_raw_commit_message(self, revisions):
        """Extracts the commit message based on the provided revision range."""
        return execute(
            [self.git, 'log', '--reverse', '--pretty=format:%s%n%n%b',
             '^%s' % revisions['base'], revisions['tip']],
            ignore_errors=True).strip()

    def get_parent_branch(self):
        """Returns the parent branch."""
        parent_branch = getattr(self.options, 'parent_branch', None)

        if self.type == 'perforce':
            parent_branch = parent_branch or 'p4'

        return parent_branch

    def get_head_ref(self):
        """Returns the HEAD reference."""
        head_ref = "HEAD"

        if self.head_ref:
            head_ref = self.head_ref

        return head_ref

    def _get_merge_base(self, rev1, rev2):
        """Returns the merge base."""
        return execute([self.git, "merge-base", rev1, rev2]).strip()

    def _rev_parse(self, revisions):
        """Runs `git rev-parse` and returns a list of revisions."""
        if not isinstance(revisions, list):
            revisions = [revisions]

        return execute([self.git, 'rev-parse'] + revisions).strip().split('\n')

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             extra_args=[]):
        """Perform a diff using the given revisions.

        If no revisions are specified, this will do a diff of the contents of
        the current branch since the tracking branch (which defaults to
        'master'). If one revision is specified, this will get the diff of that
        specific change. If two revisions are specified, this will do a diff
        between those two revisions.

        If a parent branch is specified via the command-line options, or would
        make sense given the requested revisions and the tracking branch, this
        will also return a parent diff.
        """
        exclude_patterns = normalize_patterns(exclude_patterns,
                                              self._get_root_directory(),
                                              cwd=self.original_cwd)

        try:
            merge_base = revisions['parent_base']
        except KeyError:
            merge_base = revisions['base']

        diff_lines = self.make_diff(merge_base,
                                    revisions['base'],
                                    revisions['tip'],
                                    include_files,
                                    exclude_patterns)

        if 'parent_base' in revisions:
            parent_diff_lines = self.make_diff(merge_base,
                                               revisions['parent_base'],
                                               revisions['base'],
                                               include_files,
                                               exclude_patterns)

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
                  exclude_patterns):
        """Performs a diff on a particular branch range."""
        rev_range = "%s..%s" % (base, tip)

        if include_files:
            include_files = ['--'] + include_files

        git_cmd = [self.git, '-c', 'core.quotepath=false']

        if self.type in ('svn', 'perforce'):
            diff_cmd_params = ['--no-color', '--no-prefix', '-r', '-u']
        elif self.type == 'git':
            diff_cmd_params = ['--no-color', '--full-index',
                               '--ignore-submodules']
            git_cmd.extend(['-c', 'diff.noprefix=false'])

            if (self.capabilities is not None and
                self.capabilities.has_capability('diffs', 'moved_files')):
                diff_cmd_params.append('-M')
            else:
                diff_cmd_params.append('--no-renames')
        else:
            assert False

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
            if self.type == 'git':
                changed_files_cmd.append('-r')

            changed_files = execute(
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
                exclude_patterns, base_dir=self._get_root_directory())

            diff_lines = []

            for filename in changed_files:
                lines = execute(diff_cmd + [rev_range, '--', filename],
                                split_lines=True,
                                with_errors=False,
                                ignore_errors=True,
                                none_on_ignored_error=True,
                                log_output_on_error=False,
                                results_unicode=False)

                if lines is None:
                    logging.error(
                        'Could not get diff for all files (git-diff failed '
                        'for "%s"). Refusing to return a partial diff.' %
                        filename)

                    diff_lines = None
                    break

                diff_lines += lines

        else:
            diff_lines = execute(diff_cmd + [rev_range] + include_files,
                                 split_lines=True,
                                 with_errors=False,
                                 ignore_errors=True,
                                 none_on_ignored_error=True,
                                 log_output_on_error=False,
                                 results_unicode=False)

        if self.type == 'svn':
            return self.make_svn_diff(merge_base, diff_lines)
        elif self.type == 'perforce':
            return self.make_perforce_diff(merge_base, diff_lines)
        else:
            return b''.join(diff_lines)

    def make_svn_diff(self, merge_base, diff_lines):
        """
        Formats the output of git diff such that it's in a form that
        svn diff would generate. This is needed so the SVNTool in Review
        Board can properly parse this diff.
        """
        rev = execute([self.git, "svn", "find-rev", merge_base]).strip()

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
        """Format the output of git diff to look more like perforce's."""
        diff_data = b''
        filename = b''
        p4rev = b''

        # Find which depot changelist we're based on
        log = execute([self.git, 'log', merge_base], ignore_errors=True)

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
                data = execute(
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
        """Checks if there are changes waiting to be committed.

        Returns True if the working directory has been modified or if changes
        have been staged in the index, otherwise returns False.
        """
        status = execute(['git', 'status', '--porcelain',
                          '--untracked-files=no'])
        return status != ''

    def amend_commit_description(self, message, revisions):
        """Update a commit message to the given string.

        Since git can amend only the most recent commit, an AmendError will be
        raised if revisions points to a commit other than the the most recent
        commit.
        """
        if revisions and revisions['tip']:
            commit_ids = execute([self.git, 'rev-parse', 'HEAD',
                                  revisions['tip']], split_lines=True)
            head_id = commit_ids[0].strip()
            revision_id = commit_ids[1].strip()

            if head_id != revision_id:
                raise AmendError('Commit "%s" is not the latest commit, '
                                 'and thus cannot be modified' % revision_id)

        execute([self.git, 'commit', '--amend', '-m', message])

    def apply_patch(self, patch_file, base_path=None, base_dir=None, p=None,
                    revert=False):
        """Apply the given patch to index.

        This will take the given patch file and apply it to the index,
        scheduling all changes for commit.
        """
        cmd = ['git', 'apply', '-3']

        if revert:
            cmd.append('-R')

        if p:
            cmd += ['-p', p]

        cmd.append(patch_file)

        rc, data = self._execute(cmd, with_errors=True, return_error_code=True)

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
        """Commits the given modified files.

        This is expected to be called after applying a patch. This commits the
        patch using information from the review request, opening the commit
        message in $EDITOR to allow the user to update it.
        """
        if run_editor:
            modified_message = edit_text(message)
        else:
            modified_message = message

        if all_files:
            execute(['git', 'add', '--all', ':/'])
        elif files:
            execute(['git', 'add'] + files)

        execute(['git', 'commit', '-m', modified_message,
                 '--author="%s <%s>"' % (author.fullname, author.email)])

    def delete_branch(self, branch_name, merged_only=True):
        """Deletes the specified branch.

        If merged_only is False, then the branch will be deleted even if not
        yet merged into an upstream branch.
        """
        if merged_only:
            delete_flag = '-d'
        else:
            delete_flag = '-D'

        execute(['git', 'branch', delete_flag, branch_name])

    def merge(self, target, destination, message, author, squash=False,
              run_editor=False):
        """Merges the target branch with destination branch."""
        rc, output = execute(
            ['git', 'checkout', destination],
            ignore_errors=True,
            return_error_code=True)

        if rc:
            raise MergeError("Could not checkout to branch '%s'.\n\n%s" %
                             (destination, output))

        if squash:
            method = '--squash'
        else:
            method = '--no-ff'

        rc, output = execute(
            ['git', 'merge', target, method, '--no-commit'],
            ignore_errors=True,
            return_error_code=True)

        if rc:
            raise MergeError("Could not merge branch '%s' into '%s'.\n\n%s" %
                             (target, destination, output))

        self.create_commit(message, author, run_editor)

    def push_upstream(self, remote_branch):
        """Pushes the current branch to upstream."""
        origin_url = self.get_origin()[1]
        rc, output = execute(
            ['git', 'pull', '--rebase', origin_url, remote_branch],
            ignore_errors=True,
            return_error_code=True)

        if rc:
            raise PushError('Could not pull changes from upstream.')

        rc, output = execute(
            ['git', 'push', origin_url, remote_branch],
            ignore_errors=True,
            return_error_code=True)

        if rc:
            raise PushError("Could not push branch '%s' to upstream" %
                            remote_branch)

    def get_current_branch(self):
        """Returns the name of the current branch."""
        return execute([self.git, "rev-parse", "--abbrev-ref", "HEAD"],
                       ignore_errors=True).strip()

    def _get_root_directory(self):
        """Get the root directory of the repository as an absolute path."""
        git_dir = execute([self.git, "rev-parse", "--git-dir"],
                          ignore_errors=True).rstrip("\n")

        if git_dir.startswith("fatal:") or not os.path.isdir(git_dir):
            logging.error("Could not find git repository path.")
            return None

        return os.path.abspath(os.path.join(git_dir, ".."))

    @property
    def original_cwd(self):
        """Get the original current working directory."""
        if self._original_cwd is None:
            # If this is None, then we haven't called get_repository_info and
            # shouldn't have changed directories.
            self._original_cwd = os.getcwd()

        return self._original_cwd
