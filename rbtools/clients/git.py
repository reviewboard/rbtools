import logging
import os
import re
import sys
import functools

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError)
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.svn import SVNClient, SVNRepositoryInfo
from rbtools.utils.checks import check_install
from rbtools.utils.console import edit_text
from rbtools.utils.process import die, execute

# https://wiki.python.org/moin/PythonDecoratorLibrary
# ignores kwargs
def memoize(obj):
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        if args not in cache:
            cache[args] = obj(*args, **kwargs)
        return cache[args]
    return memoizer

class GitClient(SCMClient):
    """
    A wrapper around git that fetches repository information and generates
    compatible diffs. This will attempt to generate a diff suitable for the
    remote repository, whether git, SVN or Perforce.
    """
    name = 'Git'

    def __init__(self, **kwargs):
        super(GitClient, self).__init__(**kwargs)
        # Store the 'correct' way to invoke git, just plain old 'git' by
        # default.
        self.git = 'git'

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
            return self._get_git_svn_info()
        elif self._is_subgit_configured():
            return self._get_subgit_info()

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
        self.upstream_branch, url = self._get_git_remote_tracking_info()
        if url:
            self.type = "git"
            return RepositoryInfo(path=url, base_path='',
                                  supports_parent_diffs=True)

        return None
        
    def _get_git_remote_tracking_info(self):
        upstream_branch = ''
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
                upstream_branch = '%s/%s' % (remote, merge)

        url = None
        if getattr(self.options, 'repository_url', None):
            url = self.options.repository_url
            upstream_branch = self.get_origin(upstream_branch,
                                              True)[0]
        else:
            upstream_branch, origin_url = \
                self.get_origin(upstream_branch, True)

            if not origin_url or origin_url.startswith("fatal:"):
                upstream_branch, origin_url = self.get_origin()

            url = origin_url.rstrip('/')

            # Central bare repositories don't have origin URLs.
            # We return git_dir instead and hope for the best.
            if not url:
                url = os.path.abspath(git_dir)

                # There is no remote, so skip this part of upstream_branch.
                upstream_branch = upstream_branch.split('/')[-1]
                
        return upstream_branch, url

        
    def _get_git_svn_info(self):
        data = execute([self.git, "svn", "rebase", "-n"],
                        ignore_errors=True)
        m = re.search(r'^Remote Branch:\s*(.+)$', data,
                      re.M)
        if m:
            upstream_branch = m.group(1)
        else:
            sys.stderr.write('Failed to determine SVN '
                             'tracking branch. Defaulting'
                             'to "master"\n')
            upstream_branch = 'master'

        svn_info = execute([self.git, "svn", "info"], ignore_errors=True)
        return self._parse_svn_info(svn_info, upstream_branch)
    
    def _parse_svn_info(self, svn_info, upstream_branch):
        m = re.search(r'^Repository Root: (.+)$', svn_info, re.M)
        if m:
            path = m.group(1)
            m = re.search(r'^URL: (.+)$', svn_info, re.M)
            if m:
                base_path = m.group(1)[len(path):] or "/"
                m = re.search(r'^Repository UUID: (.+)$', svn_info, re.M)
                if m:
                    uuid = m.group(1)
                    self.type = "svn"
                    # Get SVN tracking branch
                    if getattr(self.options, 'tracking', None):
                        self.upstream_branch = self.options.tracking
                    else:
                        # already discovered from git-svn or subgit info
                        self.upstream_branch = upstream_branch
                        
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
                not self.is_valid_version((int(version_parts.group(1)),
                                           int(version_parts.group(2)),
                                           int(version_parts.group(3))),
                                          (1, 5, 4))):
                die("Your installation of git-svn must be upgraded to "
                    "version 1.5.4 or later")
        
        return None

    def _is_subgit_configured(self):
        svn_remote_url = self._get_subgit_svn_url()
        return (svn_remote_url is not None)
        
    def _get_git_remote_server_info(self):
        git_url = execute([self.git, "config", "--get", "remote.origin.url"])
        git_url = git_url.strip()
        ssh_url_regexes = [
            '(?:git\+)?ssh://([A-Za-z0-9@:.]+?)(/.+)', # ssh://host.com/path/to/repo
            '([A-Za-z0-9@:.]+):(.+)', # host.com:path/to/repo
        ]
        logging.debug("Parsing remote git URL: %s" % git_url)

        server, path = None, None
        for regex in ssh_url_regexes:
            match = re.search(regex, git_url)
            if match:
                server, path = match.groups([1, 2])
                break
        if server is None:
            logging.debug("Failed to parse git remote URL")
            return None
        logging.debug("Got git remote server,path: %s,%s" % (server, path))
        return server, path

    @memoize
    def _get_subgit_svn_url(self):
        server, path = self._get_git_remote_server_info()
        
        remote_cmd = "git config -f %s/subgit/config --get svn.url" % path
        svn_remote_url = execute(['ssh', server, remote_cmd])
        if not svn_remote_url:
            logging.debug("Failed to retrieve SVN url from remote Subgit configuration")
            return None

        svn_remote_url = svn_remote_url.replace("file://", "svn+ssh://%s" % server)
        svn_remote_url = svn_remote_url.strip()
        logging.debug("Got remote SVN url from Subgit: %s" % svn_remote_url)
        return svn_remote_url

    def _get_subgit_info(self):
        svn_remote = self._get_subgit_svn_url()
        server, path = self._get_git_remote_server_info()
        svn_info = execute(["svn", "info", svn_remote])
        
        upstream_branch, url = self._get_git_remote_tracking_info()
        return self._parse_svn_info(svn_info, upstream_branch)

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

    def is_valid_version(self, actual, expected):
        """
        Takes two tuples, both in the form:
            (major_version, minor_version, micro_version)
        Returns true if the actual version is greater than or equal to
        the expected version, and false otherwise.
        """
        return ((actual[0] > expected[0]) or
                (actual[0] == expected[0] and actual[1] > expected[1]) or
                (actual[0] == expected[0] and actual[1] == expected[1] and
                 actual[2] >= expected[2]))

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
        if self.type == 'perforce':
            parent_branch = self.options.parent_branch or 'p4'
        else:
            parent_branch = self.options.parent_branch

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

    def diff(self, revisions, files=[], extra_args=[]):
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
        try:
            merge_base = revisions['parent_base']
        except KeyError:
            merge_base = revisions['base']

        diff_lines = self.make_diff(merge_base,
                                    revisions['base'],
                                    revisions['tip'],
                                    files)

        if 'parent_base' in revisions:
            parent_diff_lines = self.make_diff(merge_base,
                                               revisions['parent_base'],
                                               revisions['base'],
                                               files)
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

    def make_diff(self, merge_base, base, tip, files):
        """Performs a diff on a particular branch range."""
        rev_range = "%s..%s" % (base, tip)

        if files:
            files = ['--'] + files

        if self.type in ('svn', 'perforce'):
            diff_cmd = [self.git, 'diff', '--no-color', '--no-prefix', '-r',
                        '-u', rev_range]
        elif self.type == "git":
            diff_cmd = [self.git, 'diff', '--no-color', '--full-index',
                        '--ignore-submodules', '--no-renames', rev_range]

            if (self.capabilities is not None and
                self.capabilities.has_capability('diffs', 'moved_files')):
                diff_cmd.append('-M')
        else:
            return None

        # By default, don't allow using external diff commands. This prevents
        # things from breaking horribly if someone configures a graphical diff
        # viewer like p4merge or kaleidoscope. This can be overridden by
        # setting GIT_USE_EXT_DIFF = True in ~/.reviewboardrc
        if self.user_config.get('GIT_USE_EXT_DIFF', False):
            diff_cmd.append('--no-ext-diff')

        diff_lines = execute(diff_cmd + files,
                             split_lines=True,
                             with_errors=False,
                             ignore_errors=True,
                             none_on_ignored_error=True)

        if self.type == 'svn':
            return self.make_svn_diff(merge_base, diff_lines)
        elif self.type == 'perforce':
            return self.make_perforce_diff(merge_base, diff_lines)
        else:
            return ''.join(diff_lines)

    def _get_svn_revision(self, merge_base):
        if self._is_subgit_configured():
            line = execute([self.git, 'notes', 'show', merge_base],
                           ignore_errors=True,
                           none_on_ignored_error=True)
            if line:
                return re.search("^r([0-9]+)", line).group(1)
            else:
                logging.error("subgit configured, but couldn't find svn revision for git ref")
                logging.error("You may need to add this line to .git/config:")
                logging.error("-----------")
                logging.error("[remote \"origin\"]")
                logging.error("    ...")
                logging.error("    fetch = +refs/svn/map:refs/notes/commits")
                logging.error("-----------")
                logging.error("and then run 'git fetch', then try again.")
                die("Failed to get svn revision for git ref")
        else:
            return execute([self.git, "svn", "find-rev", merge_base]).strip()

    def make_svn_diff(self, merge_base, diff_lines):
        """
        Formats the output of git diff such that it's in a form that
        svn diff would generate. This is needed so the SVNTool in Review
        Board can properly parse this diff.
        """
        rev = self._get_svn_revision(merge_base)

        if not rev:
            return None

        diff_data = ""
        filename = ""
        newfile = False

        for line in diff_lines:
            if line.startswith("diff "):
                # Grab the filename and then filter this out.
                # This will be in the format of:
                #
                # diff --git a/path/to/file b/path/to/file
                info = line.split(" ")
                diff_data += "Index: %s\n" % info[2]
                diff_data += "=" * 67
                diff_data += "\n"
            elif line.startswith("index "):
                # Filter this out.
                pass
            elif line.strip() == "--- /dev/null":
                # New file
                newfile = True
            elif line.startswith("--- "):
                newfile = False
                diff_data += "--- %s\t(revision %s)\n" % \
                             (line[4:].strip(), rev)
            elif line.startswith("+++ "):
                filename = line[4:].strip()
                if newfile:
                    diff_data += "--- %s\t(revision 0)\n" % filename
                    diff_data += "+++ %s\t(revision 0)\n" % filename
                else:
                    # We already printed the "--- " line.
                    diff_data += "+++ %s\t(working copy)\n" % filename
            elif line.startswith("new file mode"):
                # Filter this out.
                pass
            elif line.startswith("Binary files "):
                # Add the following so that we know binary files were
                # added/changed.
                diff_data += "Cannot display: file marked as a binary type.\n"
                diff_data += "svn:mime-type = application/octet-stream\n"
            else:
                diff_data += line

        return diff_data

    def make_perforce_diff(self, merge_base, diff_lines):
        """Format the output of git diff to look more like perforce's."""
        diff_data = ''
        filename = ''
        p4rev = ''

        # Find which depot changelist we're based on
        log = execute([self.git, 'log', merge_base], ignore_errors=True)

        for line in log:
            m = re.search(r'[rd]epo.-paths = "(.+)": change = (\d+).*\]', log, re.M)

            if m:
                base_path = m.group(1).strip()
                p4rev = m.group(2).strip()
                break
            else:
                # We should really raise an error here, base_path is required
                pass

        for line in diff_lines:
            if line.startswith('diff '):
                # Grab the filename and then filter this out.
                # This will be in the format of:
                #    diff --git a/path/to/file b/path/to/file
                filename = line.split(' ')[2].strip()
            elif (line.startswith('index ') or
                  line.startswith('new file mode ')):
                # Filter this out
                pass
            elif line.startswith('--- '):
                data = execute(
                    ['p4', 'files', base_path + filename + '@' + p4rev],
                    ignore_errors=True)
                m = re.search(r'^%s%s#(\d+).*$' % (re.escape(base_path),
                                                   re.escape(filename)),
                              data, re.M)
                if m:
                    fileVersion = m.group(1).strip()
                else:
                    fileVersion = 1

                diff_data += '--- %s%s\t%s%s#%s\n' % (base_path, filename,
                                                      base_path, filename,
                                                      fileVersion)
            elif line.startswith('+++ '):
                # TODO: add a real timestamp
                diff_data += '+++ %s%s\t%s\n' % (base_path, filename,
                                                 'TIMESTAMP')
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

    def apply_patch(self, patch_file, base_path=None, base_dir=None, p=None):
        """Apply the given patch to index.

        This will take the given patch file and apply it to the index,
        scheduling all changes for commit.
        """
        if p:
            cmd = ['git', 'apply', '--index', '-p', p, patch_file]
        else:
            cmd = ['git', 'apply', '--index', patch_file]

        self._execute(cmd)

    def create_commit(self, message, author, files=[], all_files=False):
        modified_message = edit_text(message)

        if all_files:
            execute(['git', 'add', '--all', ':/'])
        elif files:
            execute(['git', 'add'] + files)

        execute(['git', 'commit', '-m', modified_message,
                 '--author="%s <%s>"' % (author.fullname, author.email)])

    def get_current_branch(self):
        """Returns the name of the current branch."""
        return execute([self.git, "rev-parse", "--abbrev-ref", "HEAD"],
                       ignore_errors=True).strip()
