import os
import re
import sys

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError)
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.svn import SVNClient, SVNRepositoryInfo
from rbtools.utils.checks import check_install
from rbtools.utils.console import edit_text
from rbtools.utils.process import die, execute


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
        user. Items in the list do not necessary represent a single revision,
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
            }

            if parent_branch:
                result['base'] = self._rev_parse(parent_branch)[0]
                result['parent_base'] = merge_base
            else:
                result['base'] = merge_base
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

            pdiff_required = not execute(
                [self.git, 'branch', '-r', '--contains', result['base']])
            if pdiff_required:
                result['parent_base'] = self._get_merge_base(result['base'],
                                                             self.upstream_branch)
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
                return None

        git_dir = execute([self.git, "rev-parse", "--git-dir"],
                          ignore_errors=True).rstrip("\n")

        if git_dir.startswith("fatal:") or not os.path.isdir(git_dir):
            return None
        self.bare = execute([self.git, "config",
                             "core.bare"]).strip() == 'true'

        # post-review in directories other than the top level of
        # of a work-tree would result in broken diffs on the server
        if not self.bare:
            git_top = execute([self.git, "rev-parse", "--show-toplevel"],
                              ignore_errors=True).rstrip("\n")

            # Top level might not work on old git version se we use git dir
            # to find it.
            if git_top.startswith("fatal:") or not os.path.isdir(git_dir):
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
                        if getattr(self.options, 'parent_branch', None):
                            self.upstream_branch = self.options.parent_branch
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
                    not self.is_valid_version((int(version_parts.group(1)),
                                               int(version_parts.group(2)),
                                               int(version_parts.group(3))),
                                              (1, 5, 4))):
                    die("Your installation of git-svn must be upgraded to "
                        "version 1.5.4 or later")

        # Okay, maybe Perforce (git-p4).
        git_p4_ref = os.path.join(git_dir, 'refs', 'remotes', 'p4', 'master')
        data = execute([self.git, 'config', '--get', 'git-p4.port'],
                       ignore_errors=True)
        m = re.search(r'(.+)', data)
        if m and os.path.exists(git_p4_ref):
            port = m.group(1)
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

    def extract_summary(self, revision_range=None):
        """Extracts the summary based on the provided revision range."""
        if not revision_range or ":" not in revision_range:
            command = [self.git, "log", "--pretty=format:%s", "HEAD^!"]
        else:
            r1, r2 = revision_range.split(":")
            command = [self.git, "log", "--pretty=format:%s", "%s^!" % r2]

        return execute(command, ignore_errors=True).strip()

    def extract_description(self, revision_range=None):
        """Extracts the description based on the provided revision range."""
        if revision_range and ":" not in revision_range:
            command = [self.git, "log", "--pretty=format:%s%n%n%b",
                       revision_range + ".."]
        elif revision_range:
            r1, r2 = revision_range.split(":")
            command = [self.git, "log", "--pretty=format:%s%n%n%b",
                       "%s..%s" % (r1, r2)]
        else:
            parent_branch = self.get_parent_branch()
            head_ref = self.get_head_ref()
            merge_base = self._get_merge_base(head_ref, self.upstream_branch)
            command = [self.git, "log", "--pretty=format:%s%n%n%b",
                       (parent_branch or merge_base) + ".."]

        return execute(command, ignore_errors=True).strip()

    def _set_summary(self, revision_range=None):
        """Sets the summary based on the provided revision range.

        Extracts and sets the summary if guessing is enabled and summary is not
        yet set.
        """
        if (getattr(self.options, 'guess_summary', None) and
                not getattr(self.options, 'summary', None)):
            self.options.summary = self.extract_summary(revision_range)

    def _set_description(self, revision_range=None):
        """Sets the description based on the provided revision range.

        Extracts and sets the description if guessing is enabled and
        description is not yet set.
        """
        if (getattr(self.options, 'guess_description', None) and
                not getattr(self.options, 'description', None)):
            self.options.description = self.extract_description(revision_range)

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

    def _diff(self, revisions):
        """
        Handle the internals of generating a diff from the given revisions.
        """
        # TODO: this will get refactored yet again once all the SCMClients
        # implement the revision parsing method and 'rbt post' and
        # 'post-review' get changed to orchestrate the whole process.
        revisions = self.parse_revision_spec(revisions)

        diff_lines = self.make_diff(revisions['base'], revisions['tip'])

        if 'parent_base' in revisions:
            parent_diff_lines = self.make_diff(revisions['parent_base'],
                                               revisions['base'])
            base_commit_id = revisions['parent_base']
        else:
            parent_diff_lines = None
            base_commit_id = revisions['base']

        return {
            'diff': diff_lines,
            'parent_diff': parent_diff_lines,
            'base_commit_id': base_commit_id,
        }

    def diff(self, args):
        """Performs a diff across all modified files in the branch.

        The diff takes into account the parent branch.
        """
        # TODO: this should use the parsed revisions
        self._set_summary()
        self._set_description()

        return self._diff([])

    def diff_between_revisions(self, revision_range, args, repository_info):
        """Perform a diff between two arbitrary revisions."""
        # TODO: this should use the parsed revisions
        self._set_summary(revision_range)
        self._set_description(revision_range)

        return self._diff([revision_range])

    def make_diff(self, ancestor, commit=""):
        """Performs a diff on a particular branch range."""
        if commit:
            rev_range = "%s..%s" % (ancestor, commit)
        else:
            rev_range = ancestor

        if self.type == "svn":
            diff_lines = execute([self.git, "diff", "--no-color",
                                  "--no-prefix", "--no-ext-diff", "-r", "-u",
                                  rev_range],
                                 split_lines=True)
            return self.make_svn_diff(ancestor, diff_lines)
        elif self.type == "perforce":
            diff_lines = execute([self.git, "diff", "--no-color",
                                  "--no-prefix", "-r", "-u", rev_range],
                                 split_lines=True)
            return self.make_perforce_diff(ancestor, diff_lines)
        elif self.type == "git":
            cmdline = [self.git, "diff", "--no-color", "--full-index",
                       "--no-ext-diff", "--ignore-submodules", "--no-renames",
                       rev_range]

            if (self.capabilities is not None and
                self.capabilities.has_capability('diffs', 'moved_files')):
                cmdline.append('-M')

            return execute(cmdline)

        return None

    def make_svn_diff(self, parent_branch, diff_lines):
        """
        Formats the output of git diff such that it's in a form that
        svn diff would generate. This is needed so the SVNTool in Review
        Board can properly parse this diff.
        """
        rev = execute([self.git, "svn", "find-rev", parent_branch]).strip()

        if not rev and self.merge_base:
            rev = execute([self.git, "svn", "find-rev",
                           self.merge_base]).strip()

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

    def make_perforce_diff(self, parent_branch, diff_lines):
        """Format the output of git diff to look more like perforce's."""
        diff_data = ''
        filename = ''
        p4rev = ''

        # Find which depot changelist we're based on
        log = execute([self.git, 'log', parent_branch], ignore_errors=True)

        for line in log:
            m = re.search(r'[rd]epo.-paths = "(.+)": change = (\d+)\]', log, re.M)

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
        status = execute(['git', 'status', '--porcelain'])
        return status != ''

    def apply_patch(self, patch_file, base_path=None, base_dir=None, p=None):
        """
        Apply the patch patch_file and return True if the patch was
        successful, otherwise return False.
        """
        if p:
            cmd = ['git', 'apply', '-p', p, patch_file]
        else:
            cmd = ['git', 'apply', patch_file]

        self._execute(cmd)

    def create_commmit(self, message, author):
        modified_message = edit_text(message)
        execute(['git', 'add', '--all', ':/'])
        execute(['git', 'commit', '-m', modified_message,
                 '--author="%s <%s>"' % (author.fullname, author.email)])

    def get_current_branch(self):
        """Returns the name of the current branch."""
        return execute([self.git, "rev-parse", "--abbrev-ref", "HEAD"],
                       ignore_errors=True).strip()
