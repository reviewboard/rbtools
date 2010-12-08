import os
import re

from rbtools.clients.client import Client, Repository
from rbtools.clients.svn import SVNClient, SVNRepository


class GitClient(Client):
    """A client for Git repositories"""

    upstream_branch = None

    def _strip_heads_prefix(self, ref):
        """ Strips prefix from ref name, if possible """
        return re.sub(r'^refs/heads/', '', ref)

    def get_info(self, parent_branch='master'):
        """Returns information about the repository

        This is an actual implementation that returns info about the Git repo
        """

        if not self.util.check_install('git --help'):
            return None

        git_dir = self.util.execute(["git", "rev-parse", "--git-dir"],
                          ignore_errors=True).strip()

        if git_dir.startswith("fatal:") or not os.path.isdir(git_dir):
            return None

        # post-review in directories other than the top level of
        # of a work-tree would result in broken diffs on the server
        os.chdir(os.path.dirname(os.path.abspath(git_dir)))

        self.head_ref = self.util.execute(['git', 'symbolic-ref', \
                                            '-q', 'HEAD']).strip()

        # We know we have something we can work with. Let's find out
        # what it is. We'll try SVN first.
        data = self.util.execute(["git", "svn", "info"], ignore_errors=True)

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
                    self.upstream_branch = parent_branch or 'master'

                    return SVNRepository(path=path, base_path=base_path,
                                             uuid=uuid,
                                             supports_parent_diffs=True,
                                             util=self.util)
        else:
            # Versions of git-svn before 1.5.4 don't (appear to) support
            # 'git svn info'. If we fail because of an older git install,
            # here, figure out what version of git is installed and give
            # the user a hint about what to do next.
            version = self.util.execute(["git", "svn", "--version"], \
                                        ignore_errors=True)
            version_parts = re.search('version (\d+)\.(\d+)\.(\d+)',
                                      version)
            svn_remote = self.util.execute(["git", "config", "--get",
                                  "svn-remote.svn.url"], ignore_errors=True)

            if (version_parts and
                not self.is_valid_version((int(version_parts.group(1)),
                                           int(version_parts.group(2)),
                                           int(version_parts.group(3))),
                                          (1, 5, 4)) and
                svn_remote):
                die("Your installation of git-svn must be upgraded to " + \
                    "version 1.5.4 or later")

        # Okay, maybe Perforce.
        # TODO

        # Nope, it's git then.
        # Check for a tracking branch and determine merge-base
        short_head = self._strip_heads_prefix(self.head_ref)
        merge = self.util.execute(['git', 'config', '--get',
                         'branch.%s.merge' % short_head],
                        ignore_errors=True).strip()
        remote = self.util.execute(['git', 'config', '--get',
                          'branch.%s.remote' % short_head],
                         ignore_errors=True).strip()

        merge = self._strip_heads_prefix(merge)
        self.upstream_branch = ''

        if remote and remote != '.' and merge:
            self.upstream_branch = '%s/%s' % (remote, merge)

        self.upstream_branch, origin_url = self.get_origin( \
                                self.upstream_branch, True)

        if not origin_url or origin_url.startswith("fatal:"):
            self.upstream_branch, origin_url = self.get_origin()

        self.url = origin_url.rstrip('/')

        if self.url:
            self.type = "git"
            return Repository(path=self.url, base_path='',
                                  supports_parent_diffs=True)

        return None

    def get_origin(self, default_upstream_branch=None, ignore_errors=False):
        """Get upstream remote origin from options or parameters.

        Returns a tuple: (upstream_branch, remote_url)
        """
        upstream_branch = default_upstream_branch or \
                          'origin/master'
        upstream_remote = upstream_branch.split('/')[0]
        origin_url = self.util.execute(["git", "config", \
                                    "remote.%s.url" % upstream_remote], \
                                    ignore_errors=ignore_errors)

        return (upstream_branch, origin_url.rstrip('\n'))

    def is_valid_version(self, actual, expected):
        """
        Takes two tuples, both in the form:
            (major_version, minor_version, micro_version)
        Returns true if the actual version is greater than or equal to
        the expected version, and false otherwise.
        """
        return (actual[0] > expected[0]) or \
               (actual[0] == expected[0] and actual[1] > expected[1]) or \
               (actual[0] == expected[0] and actual[1] == expected[1] and \
                actual[2] >= expected[2])

    def scan_for_server(self, repository_info):
        """Scans for a git server

        Scans looking for a Git server, or failing that an SVN server
        """

        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = super(GitClient, self).scan_for_server( \
                                                            repository_info)
        if server_url:
            return server_url

        # TODO: Maybe support a server per remote later? Is that useful?
        self.url = self.util.execute(["git", "config", "--get", \
                            "reviewboard.url"], ignore_errors=True).strip()

        if self.url:
            return self.url

        if self.type == "svn":
            # Try using the reviewboard:url property on the SVN repo, if it
            # exists.
            prop = SVNClient(self.url, \
                        self.util).scan_for_server_property(repository_info)

            if prop:
                return prop

        return None

    def diff(self, args=None):
        """Creates a diff

        Performs a diff across all modified files in the branch, taking into
        account a parent branch.
        """

        self.merge_base = self.util.execute(["git", "merge-base", \
                                self.upstream_branch, self.head_ref]).strip()

        diff_lines = self.make_diff(self.merge_base, self.head_ref)
        parent_diff_lines = None

        return (diff_lines, parent_diff_lines)

    def make_diff(self, ancestor, commit=""):
        """
        Performs a diff on a particular branch range.
        """
        rev_range = "%s..%s" % (ancestor, commit)

        if self.type == "svn":
            diff_lines = self.util.execute(["git", "diff", "--no-color", \
                                        "--no-prefix", "-r", "-u", \
                                        rev_range], split_lines=True)
            return self.make_svn_diff(ancestor, diff_lines)
        elif self.type == "git":
            return self.util.execute(["git", "diff", "--no-color", \
                                    "--full-index", rev_range])

        return None

    def make_svn_diff(self, parent_branch, diff_lines):
        """Creates a diff for an svn server

        Formats the output of git diff such that it's in a form that
        svn diff would generate. This is needed so the SVNTool in Review
        Board can properly parse this diff.
        """
        rev = self.util.execute(["git", "svn", "find-rev", \
                                    parent_branch]).strip()

        if not rev:
            return None

        diff_data = ""
        filename = ""
        revision = ""
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
                # added/changed
                diff_data += "Cannot display: file marked as a binary type.\n"
                diff_data += "svn:mime-type = application/octet-stream\n"
            else:
                diff_data += line

        return diff_data

    def diff_between_revisions(self, revision_range, args, repository_info):
        """Perform a diff between two arbitrary revisions"""
        if ":" not in revision_range:
            # only one revision is specified

            return self.make_diff(revision_range)
        else:
            r1, r2 = revision_range.split(":")

            return self.make_diff(r1, r2)
