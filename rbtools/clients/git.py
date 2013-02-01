import os
import re
import sys

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.svn import SVNClient, SVNRepositoryInfo
from rbtools.utils.checks import check_install
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

    def _strip_heads_prefix(self, ref):
        """ Strips prefix from ref name, if possible """
        return re.sub(r'^refs/heads/', '', ref)

    def get_repository_info(self):
        if not check_install('git --help'):
            # CreateProcess (launched via subprocess, used by check_install)
            # does not automatically append .cmd for things it finds in PATH.
            # If we're on Windows, and this works, save it for further use.
            if (sys.platform.startswith('win') and
                check_install('git.cmd --help')):
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
                        if self.options.parent_branch:
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
                svn_remote = execute([self.git, "config", "--get",
                                      "svn-remote.svn.url"],
                                      ignore_errors=True)

                if (version_parts and
                    not self.is_valid_version((int(version_parts.group(1)),
                                               int(version_parts.group(2)),
                                               int(version_parts.group(3))),
                                              (1, 5, 4)) and
                    svn_remote):
                    die("Your installation of git-svn must be upgraded to "
                        "version 1.5.4 or later")

        # Okay, maybe Perforce.
        # TODO

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
            self.upstream_branch = self.get_origin(self.upstream_branch, True)[0]
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

    def get_origin(self, default_upstream_branch=None, ignore_errors=False):
        """Get upstream remote origin from options or parameters.

        Returns a tuple: (upstream_branch, remote_url)
        """
        upstream_branch = (getattr(self.options, 'tracking', None) or
                           default_upstream_branch or
                           'origin/master')
        upstream_remote = upstream_branch.split('/')[0]
        origin_url = execute([self.git, "config", "--get",
                              "remote.%s.url" % upstream_remote],
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

        return None

    def diff(self, args):
        """
        Performs a diff across all modified files in the branch, taking into
        account a parent branch.
        """
        parent_branch = self.options.parent_branch
        head_ref = "HEAD"
        if self.head_ref:
            head_ref = self.head_ref

        self.merge_base = execute([self.git, "merge-base",
                                   self.upstream_branch,
                                   head_ref]).strip()

        if parent_branch:
            diff_lines = self.make_diff(parent_branch)
            parent_diff_lines = self.make_diff(self.merge_base, parent_branch)
        else:
            diff_lines = self.make_diff(self.merge_base, head_ref)
            parent_diff_lines = None

        if (getattr(self.options, 'guess_summary', None) and
            not getattr(self.options, 'summary', None)):
            s = execute([self.git, "log", "--pretty=format:%s", "HEAD^.."],
                              ignore_errors=True)
            self.options.summary = s.replace('\n', ' ').strip()

        if (getattr(self.options, 'guess_description', None) and
            not getattr(self.options, 'description', None)):
            self.options.description = execute(
                [self.git, "log", "--pretty=format:%s%n%n%b",
                 (parent_branch or self.merge_base) + ".."],
                ignore_errors=True).strip()

        return (diff_lines, parent_diff_lines)

    def make_diff(self, ancestor, commit=""):
        """
        Performs a diff on a particular branch range.
        """
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

    def diff_between_revisions(self, revision_range, args, repository_info):
        """Perform a diff between two arbitrary revisions"""

        head_ref = "HEAD"
        if self.head_ref:
            head_ref = self.head_ref

        # Make a parent diff to the first of the revisions so that we
        # never end up with broken patches:
        self.merge_base = execute([self.git, "merge-base",
                                   self.upstream_branch,
                                   head_ref]).strip()

        if ":" not in revision_range:
            # only one revision is specified

            # Check if parent contains the first revision and make a
            # parent diff if not:
            pdiff_required = execute([self.git, "branch", "-r",
                                      "--contains", revision_range])
            parent_diff_lines = None

            if not pdiff_required:
                parent_diff_lines = self.make_diff(self.merge_base,
                                                   revision_range)

            if self.options.guess_summary and not self.options.summary:
                s = execute([self.git, "log", "--pretty=format:%s",
                             revision_range + ".."], ignore_errors=True)
                self.options.summary = s.replace('\n', ' ').strip()

            if (self.options.guess_description and
                not self.options.description):
                self.options.description = execute(
                    [self.git, "log", "--pretty=format:%s%n%n%b",
                     revision_range + ".."],
                    ignore_errors=True).strip()

            return (self.make_diff(revision_range), parent_diff_lines)
        else:
            r1, r2 = revision_range.split(":")
            # Check if parent contains the first revision and make a
            # parent diff if not:
            pdiff_required = execute([self.git, "branch", "-r",
                                      "--contains", r1])
            parent_diff_lines = None

            if not pdiff_required:
                parent_diff_lines = self.make_diff(self.merge_base, r1)

            if self.options.guess_summary and not self.options.summary:
                s = execute([self.git, "log", "--pretty=format:%s",
                             "%s..%s" % (r1, r2)], ignore_errors=True)
                self.options.summary = s.replace('\n', ' ').strip()

            if (self.options.guess_description and
                not self.options.description):
                self.options.description = execute(
                    [self.git, "log", "--pretty=format:%s%n%n%b",
                     "%s..%s" % (r1, r2)],
                    ignore_errors=True).strip()

            return (self.make_diff(r1, r2), parent_diff_lines)

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
