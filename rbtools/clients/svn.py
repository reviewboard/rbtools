import re

from rbtools.client import Client, Repository

class SVNClient(Client):
    """A Cleint for SVN repositories"""

    def get_info(self):
        """Returns information about the repository
        
        This is an actual implementation that returns info about the SVN repo
        """

        if not self.util.check_install('svn help'):
            return None

        # Get the SVN repository path (either via a working copy or
        # a supplied URI)
        svn_info_params = ["svn", "info"]

        if self.url:
            svn_info_params.append(self.url)

        data = self.util.execute(svn_info_params,
                       ignore_errors=True)

        m = re.search(r'^Repository Root: (.+)$', data, re.M)

        if not m:
            return None

        path = m.group(1)

        m = re.search(r'^URL: (.+)$', data, re.M)

        if not m:
            return None

        base_path = m.group(1)[len(path):] or "/"

        m = re.search(r'^Repository UUID: (.+)$', data, re.M)

        if not m:
            return None

        # Now that we know it's SVN, make sure we have GNU diff installed,
        # and error out if we don't.
        self.check_gnu_diff()

        return SVNRepository(path, base_path, m.group(1))

    def diff(self, files):
        """
        Performs a diff across all modified files in a Subversion repository.

        SVN repositories do not support branches of branches in a way that
        makes parent diffs possible, so we never return a parent diff
        (the second value in the tuple).
        """
        return (self.do_diff(["svn", "diff", "--diff-cmd=diff"] + files),
                None)

    def do_diff(self, cmd, repository_info=None):
        """
        Performs the actual diff operation, handling renames and converting
        paths to absolute.
        """
        diff = self.util.execute(cmd, split_lines=True)
        diff = self.handle_renames(diff)
        diff = self.convert_to_absolute_paths(diff, repository_info)

        return ''.join(diff)

    def handle_renames(self, diff_content):
        """
        The output of svn diff is incorrect when the file in question came
        into being via svn mv/cp. Although the patch for these files are
        relative to its parent, the diff header doesn't reflect this.
        This function fixes the relevant section headers of the patch to
        portray this relationship.
        """

        # svn diff against a repository URL on two revisions appears to
        # handle moved files properly, so only adjust the diff file names
        # if they were created using a working copy.
        if self.url:
            return diff_content

        result = []

        from_line = ""

        for line in diff_content:
            if line.startswith('--- '):
                from_line = line
                continue

            # This is where we decide how mangle the previous '--- '
            if line.startswith('+++ '):
                to_file, _ = self.parse_filename_header(line[4:])
                info = self.svn_info(to_file)

                if info.in("Copied From URL"):
                    self.url = info["Copied From URL"]
                    root = info["Repository Root"]
                    from_file = urllib.unquote(url[len(root):])
                    result.append(from_line.replace(to_file, from_file))
                else:
                    result.append(from_line)  # as is, no copy performed

            # We only mangle '---' lines. All others get added straight to
            # the output.
            result.append(line)

        return result

    def svn_info(self, path):
        """Return a dict which is the result of 'svn info' at a given path."""
        svninfo = {}

        for info in self.util.execute(["svn", "info", path],
                            split_lines=True):
            parts = info.strip().split(": ", 1)

            if len(parts) == 2:
                key, value = parts
                svninfo[key] = value

        return svninfo

            # Adapted from server code parser.py
    def parse_filename_header(self, s):
        parts = None

        if "\t" in s:
            # There's a \t separating the filename and info. This is the
            # best case scenario, since it allows for filenames with spaces
            # without much work. The info can also contain tabs after the
            # initial one; ignore those when splitting the string.
            parts = s.split("\t", 1)

        # There's spaces being used to separate the filename and info.
        # This is technically wrong, so all we can do is assume that
        # 1) the filename won't have multiple consecutive spaces, and
        # 2) there's at least 2 spaces separating the filename and info.
        if "  " in s:
            parts = re.split(r"  +", s)

        if parts:
            parts[1] = '\t' + parts[1]
            return parts

        # strip off ending newline, and return it as the second component
        return [s.split('\n')[0], '\n']

    def convert_to_absolute_paths(self, diff_content, repository_info):
        """
        Converts relative paths in a diff output to absolute paths.
        This handles paths that have been svn switched to other parts of the
        repository.
        """

        result = []

        for line in diff_content:
            front = None

            if line.startswith('+++ ') or line.startswith('--- ') or \
                                            line.startswith('Index: '):
                front, line = line.split(" ", 1)

            if front:

                if line.startswith('/'):  # already absolute
                    line = front + " " + line
                else:
                    # filename and rest of line (usually the revision
                    # component)
                    file, rest = self.parse_filename_header(line)

                    # If working with a diff generated outside of a working
                    # copy, then file paths are already absolute, so just
                    # add initial slash.
                    if self.url:
                        path = urllib.unquote(
                            "%s/%s" % (repository_info.base_path, file))
                    else:
                        info = self.svn_info(file)
                        self.url = info["URL"]
                        root = info["Repository Root"]
                        path = urllib.unquote(url[len(root):])

                    line = front + " " + path + rest

            result.append(line)

        return result
        
        
    def check_gnu_diff():
        """
        Checks if GNU diff is installed, and informs the user if it's not.
        """
        has_gnu_diff = False

        try:
            result = execute(['diff', '--version'], ignore_errors=True)
            has_gnu_diff = 'GNU diffutils' in result
        except OSError:
            pass

        if not has_gnu_diff:
            sys.stderr.write('\n')
            sys.stderr.write('GNU diff is required for Subversion '
                             'repositories. Make sure it is installed\n')
            sys.stderr.write('and in the path.\n')
            sys.stderr.write('\n')

            if os.name == 'nt':
                sys.stderr.write('On Windows, you can install this from:\n')
                sys.stderr.write(GNU_DIFF_WIN32_URL)
                sys.stderr.write('\n')

            self.die()


class SVNRepository(Repository):
    """
    A representation of a SVN source code repository. This version knows how to
    find a matching repository on the server even if the URLs differ.
    """

    def __init__(self, path, base_path, uuid, supports_parent_diffs=False):
        RepositoryInfo.__init__(self, path, base_path,
                                supports_parent_diffs=supports_parent_diffs)
        self.uuid = uuid

    def find_server_repository_info(self, server):
        """
        The point of this function is to find a repository on the server that
        matches self, even if the paths aren't the same. (For example, if self
        uses an 'http' path, but the server uses a 'file' path for the same
        repository.) It does this by comparing repository UUIDs. If the
        repositories use the same path, you'll get back self, otherwise you'll
        get a different SvnRepositoryInfo object (with a different path).
        """
        repositories = server.get_repositories()

        for repository in repositories:

            if repository['tool'] != 'Subversion':
                continue

            info = self._get_repository_info(server, repository)

            if not info or self.uuid != info['uuid']:
                continue

            repos_base_path = info['url'][len(info['root_url']):]
            relpath = self._get_relative_path(self.base_path, repos_base_path)

            if relpath:
                return SvnRepositoryInfo(info['url'], relpath, self.uuid)

        # We didn't find a matching repository on the server. We'll just return
        # self and hope for the best.
        return self

    def _get_repository_info(self, server, repository):

        try:
            return server.get_repository_info(repository['id'])
        except APIError, e:
            # If the server couldn't fetch the repository info, it will return
            # code 210. Ignore those.
            # Other more serious errors should still be raised, though.

            if e.error_code == 210:
                return None

            raise e

    def _get_relative_path(self, path, root):
        pathdirs = self._split_on_slash(path)
        rootdirs = self._split_on_slash(root)

        # root is empty, so anything relative to that is itself
        if len(rootdirs) == 0:
            return path

        # If one of the directories doesn't match, then path is not relative
        # to root.
        if rootdirs != pathdirs:
            return None

        # All the directories matched, so the relative path is whatever
        # directories are left over. The base_path can't be empty, though, so
        # if the paths are the same, return '/'
        if len(pathdirs) == len(rootdirs):
            return '/'
        else:
            return '/'.join(pathdirs[len(rootdirs):])

    def _split_on_slash(self, path):
        # Split on slashes, but ignore multiple slashes and throw away any
        # trailing slashes.
        split = re.split('/*', path)

        if split[-1] == '':
            split = split[0:-1]
        return split