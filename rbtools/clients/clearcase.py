import logging
import os
import sys

from rbtools.api.errors import APIError
from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.utils.checks import check_gnu_diff, check_install
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import die, execute

# This specific import is necessary to handle the paths for
# cygwin enabled machines.
if (sys.platform.startswith('win')
    or sys.platform.startswith('cygwin')):
    import ntpath as cpath
else:
    import posixpath as cpath


class ClearCaseClient(SCMClient):
    """
    A wrapper around the clearcase tool that fetches repository
    information and generates compatible diffs.
    This client assumes that cygwin is installed on windows.
    """
    name = 'ClearCase'
    viewtype = None

    def __init__(self, **kwargs):
        super(ClearCaseClient, self).__init__(**kwargs)

    def get_repository_info(self):
        """Returns information on the Clear Case repository.

        This will first check if the cleartool command is
        installed and in the path, and post-review was run
        from inside of the view.
        """
        if not check_install('cleartool help'):
            return None

        viewname = execute(["cleartool", "pwv", "-short"]).strip()
        if viewname.startswith('** NONE'):
            return None

        # Now that we know it's ClearCase, make sure we have GNU diff installed,
        # and error out if we don't.
        check_gnu_diff()

        property_lines = execute(["cleartool", "lsview", "-full", "-properties",
                                  "-cview"], split_lines=True)
        for line in property_lines:
            properties = line.split(' ')
            if properties[0] == 'Properties:':
                # Determine the view type and check if it's supported.
                #
                # Specifically check if webview was listed in properties
                # because webview types also list the 'snapshot'
                # entry in properties.
                if 'webview' in properties:
                    die("Webviews are not supported. You can use post-review"
                        " only in dynamic or snapshot view.")
                if 'dynamic' in properties:
                    self.viewtype = 'dynamic'
                else:
                    self.viewtype = 'snapshot'

                break

        # Find current VOB's tag
        vobstag = execute(["cleartool", "describe", "-short", "vob:."],
                            ignore_errors=True).strip()
        if "Error: " in vobstag:
            die("To generate diff run post-review inside vob.")

        root_path = execute(["cleartool", "pwv", "-root"],
                              ignore_errors=True).strip()
        if "Error: " in root_path:
            die("To generate diff run post-review inside view.")

        # From current working directory cut path to VOB.
        # VOB's tag contain backslash character before VOB's name.
        # I hope that first character of VOB's tag like '\new_proj'
        # won't be treat as new line character but two separate:
        # backslash and letter 'n'
        cwd = os.getcwd()
        base_path = cwd[:len(root_path) + len(vobstag)]

        return ClearCaseRepositoryInfo(path=base_path,
                              base_path=base_path,
                              vobstag=vobstag,
                              supports_parent_diffs=False)

    def check_options(self):
        if ((self.options.revision_range or self.options.tracking)
            and self.viewtype != "dynamic"):
            die("To generate diff using parent branch or by passing revision "
                "ranges, you must use a dynamic view.")

    def _determine_version(self, version_path):
        """Determine numeric version of revision.

        CHECKEDOUT is marked as infinity to be treated
        always as highest possible version of file.
        CHECKEDOUT, in ClearCase, is something like HEAD.
        """
        branch, number = cpath.split(version_path)
        if number == 'CHECKEDOUT':
            return float('inf')
        return int(number)

    def _construct_extended_path(self, path, version):
        """Combine extended_path from path and version.

        CHECKEDOUT must be removed becasue this one version
        doesn't exists in MVFS (ClearCase dynamic view file
        system). Only way to get content of checked out file
        is to use filename only."""
        if not version or version.endswith('CHECKEDOUT'):
            return path

        return "%s@@%s" % (path, version)

    def _sanitize_branch_changeset(self, changeset):
        """Return changeset containing non-binary, branched file versions.

        Changeset contain only first and last version of file made on branch.
        """
        changelist = {}

        for path, previous, current in changeset:
            version_number = self._determine_version(current)

            if path not in changelist:
                changelist[path] = {
                    'highest': version_number,
                    'current': current,
                    'previous': previous
                }

            if version_number == 0:
                # Previous version of 0 version on branch is base
                changelist[path]['previous'] = previous
            elif version_number > changelist[path]['highest']:
                changelist[path]['highest'] = version_number
                changelist[path]['current'] = current

        # Convert to list
        changeranges = []
        for path, version in changelist.iteritems():
            changeranges.append(
                (self._construct_extended_path(path, version['previous']),
                 self._construct_extended_path(path, version['current']))
            )

        return changeranges

    def _sanitize_checkedout_changeset(self, changeset):
        """Return changeset containing non-binary, checkdout file versions."""

        changeranges = []
        for path, previous, current in changeset:
            changeranges.append(
                (self._construct_extended_path(path, previous),
                self._construct_extended_path(path, current))
            )

        return changeranges

    def _directory_content(self, path):
        """Return directory content ready for saving to tempfile."""

        return ''.join([
            '%s\n' % s
            for s in sorted(os.listdir(path))
        ])

    def _construct_changeset(self, output):
        return [
            info.split('\t')
            for info in output.strip().split('\n')
        ]

    def get_checkedout_changeset(self):
        """Return information about the checked out changeset.

        This function returns: kind of element, path to file,
        previews and current file version.
        """
        changeset = []
        # We ignore return code 1 in order to
        # omit files that Clear Case can't read.
        output = execute([
            "cleartool",
            "lscheckout",
            "-all",
            "-cview",
            "-me",
            "-fmt",
            r"%En\t%PVn\t%Vn\n"],
            extra_ignore_errors=(1,),
            with_errors=False)

        if output:
            changeset = self._construct_changeset(output)

        return self._sanitize_checkedout_changeset(changeset)

    def get_branch_changeset(self, branch):
        """Returns information about the versions changed on a branch.

        This takes into account the changes on the branch owned by the
        current user in all vobs of the current view.
        """
        changeset = []

        # We ignore return code 1 in order to
        # omit files that Clear Case can't read.
        if sys.platform.startswith('win'):
            CLEARCASE_XPN = '%CLEARCASE_XPN%'
        else:
            CLEARCASE_XPN = '$CLEARCASE_XPN'

        output = execute([
            "cleartool",
            "find",
            "-all",
            "-version",
            "brtype(%s)" % branch,
            "-exec",
            'cleartool descr -fmt ' \
            r'"%En\t%PVn\t%Vn\n" ' \
            + CLEARCASE_XPN],
            extra_ignore_errors=(1,),
            with_errors=False)

        if output:
            changeset = self._construct_changeset(output)

        return self._sanitize_branch_changeset(changeset)

    def diff(self, files):
        """Performs a diff of the specified file and its previous version."""

        if self.options.tracking:
            changeset = self.get_branch_changeset(self.options.tracking)
        else:
            changeset = self.get_checkedout_changeset()

        return self.do_diff(changeset)

    def diff_between_revisions(self, revision_range, args, repository_info):
        """Performs a diff between passed revisions or branch."""

        # Convert revision range to list of:
        # (previous version, current version) tuples
        revision_range = revision_range.split(';')
        changeset = zip(revision_range[0::2], revision_range[1::2])

        return (self.do_diff(changeset)[0], None)

    def diff_files(self, old_file, new_file):
        """Return unified diff for file.

        Most effective and reliable way is use gnu diff.
        """
        diff_cmd = ["diff", "-uN", old_file, new_file]
        dl = execute(diff_cmd, extra_ignore_errors=(1, 2),
                     translate_newlines=False)

        # If the input file has ^M characters at end of line, lets ignore them.
        dl = dl.replace('\r\r\n', '\r\n')
        dl = dl.splitlines(True)

        # Special handling for the output of the diff tool on binary files:
        #     diff outputs "Files a and b differ"
        # and the code below expects the output to start with
        #     "Binary files "
        if (len(dl) == 1 and
            dl[0].startswith('Files %s and %s differ' % (old_file, new_file))):
            dl = ['Binary files %s and %s differ\n' % (old_file, new_file)]

        # We need oids of files to translate them to paths on reviewboard
        # repository.
        old_oid = execute(["cleartool", "describe", "-fmt", "%On", old_file])
        new_oid = execute(["cleartool", "describe", "-fmt", "%On", new_file])

        if dl == [] or dl[0].startswith("Binary files "):
            if dl == []:
                dl = ["File %s in your changeset is unmodified\n" % new_file]

            dl.insert(0, "==== %s %s ====\n" % (old_oid, new_oid))
            dl.append('\n')
        else:
            dl.insert(2, "==== %s %s ====\n" % (old_oid, new_oid))

        return dl

    def diff_directories(self, old_dir, new_dir):
        """Return uniffied diff between two directories content.

        Function save two version's content of directory to temp
        files and treate them as casual diff between two files.
        """
        old_content = self._directory_content(old_dir)
        new_content = self._directory_content(new_dir)

        old_tmp = make_tempfile(content=old_content)
        new_tmp = make_tempfile(content=new_content)

        diff_cmd = ["diff", "-uN", old_tmp, new_tmp]
        dl = execute(diff_cmd,
                     extra_ignore_errors=(1, 2),
                     translate_newlines=False,
                     split_lines=True)

        # Replacing temporary filenames to
        # real directory names and add ids
        if dl:
            dl[0] = dl[0].replace(old_tmp, old_dir)
            dl[1] = dl[1].replace(new_tmp, new_dir)
            old_oid = execute(["cleartool", "describe", "-fmt", "%On",
                               old_dir])
            new_oid = execute(["cleartool", "describe", "-fmt", "%On",
                               new_dir])
            dl.insert(2, "==== %s %s ====\n" % (old_oid, new_oid))

        return dl

    def do_diff(self, changeset):
        """Generates a unified diff for all files in the changeset."""

        diff = []
        for old_file, new_file in changeset:
            dl = []
            if cpath.isdir(new_file):
                dl = self.diff_directories(old_file, new_file)
            elif cpath.exists(new_file):
                dl = self.diff_files(old_file, new_file)
            else:
                logging.error("File %s does not exist or access is denied."
                              % new_file)
                continue

            if dl:
                diff.append(''.join(dl))

        return (''.join(diff), None)


class ClearCaseRepositoryInfo(RepositoryInfo):
    """
    A representation of a ClearCase source code repository. This version knows
    how to find a matching repository on the server even if the URLs differ.
    """

    def __init__(self, path, base_path, vobstag, supports_parent_diffs=False):
        RepositoryInfo.__init__(self, path, base_path,
                                supports_parent_diffs=supports_parent_diffs)
        self.vobstag = vobstag

    def find_server_repository_info(self, server):
        """
        The point of this function is to find a repository on the server that
        matches self, even if the paths aren't the same. (For example, if self
        uses an 'http' path, but the server uses a 'file' path for the same
        repository.) It does this by comparing VOB's name. If the
        repositories use the same path, you'll get back self, otherwise you'll
        get a different ClearCaseRepositoryInfo object (with a different path).
        """

        # Find VOB's family uuid based on VOB's tag
        uuid = self._get_vobs_uuid(self.vobstag)
        logging.debug("Repository's %s uuid is %r" % (self.vobstag, uuid))

        repositories = server.get_repositories()
        for repository in repositories:
            if repository['tool'] != 'ClearCase':
                continue

            info = self._get_repository_info(server, repository)

            if not info or uuid != info['uuid']:
                continue

            logging.debug('Matching repository uuid:%s with path:%s' % (uuid,
                          info['repopath']))
            return ClearCaseRepositoryInfo(info['repopath'],
                    info['repopath'], uuid)

        # We didn't found uuid but if version is >= 1.5.3
        # we can try to use VOB's name hoping it is better
        # than current VOB's path.
        if server.rb_version >= '1.5.3':
            self.path = cpath.split(self.vobstag)[1]

        # We didn't find a matching repository on the server.
        # We'll just return self and hope for the best.
        return self

    def _get_vobs_uuid(self, vobstag):
        """Return family uuid of VOB."""

        property_lines = execute(["cleartool", "lsvob", "-long", vobstag],
                                 split_lines=True)
        for line  in property_lines:
            if line.startswith('Vob family uuid:'):
                return  line.split(' ')[-1].rstrip()

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
