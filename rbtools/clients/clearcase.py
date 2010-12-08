import difflib
import os
import sys

try:
    from hashlib import md5
except ImportError:
    # Support Python versions before 2.5.
    from md5 import md5

# This specific import is necessary to handle the paths for
# cygwin enabled machines.
if (sys.platform.startswith('win')
    or sys.platform.startswith('cygwin')):
    import ntpath as cpath
else:
    import posixpath as cpath

from client import Client, Repository

class ClearCaseClient(Client):
    """A client for ClearCase repositories"""
    
    viewinfo = ""
    viewtype = "snapshot"

    def get_filename_hash(self, fname):
        # Hash the filename string so its easy to find the file later on.
        return md5(fname).hexdigest()

    def get_info(self):
        """Returns information about the repository
        
        This is an actual implementation that returns info about the CC repo
        """

        if not self.util.check_install('cleartool help'):
            return None

        # We must be running this from inside a view.
        # Otherwise it doesn't make sense.
        self.viewinfo = self.util.execute(["cleartool", "pwv", "-short"])

        if self.viewinfo.startswith('\*\* NONE'):
            return None

        # Returning the hardcoded clearcase root path to match the server
        #   respository path.
        # There is no reason to have a dynamic path unless you have
        #   multiple clearcase repositories. This should be implemented.
        return Repository(path=self.url,
                              base_path=self.url,
                              supports_parent_diffs=False)

    def get_previous_version(self, files):
        file = []
        curdir = os.getcwd()

        # Cygwin case must transform a linux-like path to windows like path
        #   including drive letter.
        if 'cygdrive' in curdir:
            where = curdir.index('cygdrive') + 9
            drive_letter = curdir[where:where+1]
            curdir = drive_letter + ":\\" + curdir[where+2:len(curdir)]

        for key in files:
            # Sometimes there is a quote in the filename. It must be removed.
            key = key.replace('\'', '')
            elem_path = cpath.normpath(os.path.join(curdir, key))

            # Removing anything before the last /vobs
            #   because it may be repeated.
            elem_path_idx = elem_path.rfind("/vobs")
            if elem_path_idx != -1:
                elem_path = elem_path[elem_path_idx:len(elem_path)].strip("\"")

            # Call cleartool to get this version and the previous version
            #   of the element.
            curr_version, pre_version = self.util.execute(
                ["cleartool", "desc", "-pre", elem_path], split_lines=True)
            curr_version = cpath.normpath(curr_version)
            pre_version = pre_version.split(':')[1].strip()

            # If a specific version was given, remove it from the path
            #   to avoid version duplication
            if "@@" in elem_path:
                elem_path = elem_path[:elem_path.rfind("@@")]
            file.append(elem_path + "@@" + pre_version)
            file.append(curr_version)

        # Determnine if the view type is snapshot or dynamic.
        if os.path.exists(file[0]):
            self.viewtype = "dynamic"

        return file

    def diff(self, files):
        """Creates a diff
        
        Performs a diff of the specified file and its previous version.
        """
        # We must be running this from inside a view.
        # Otherwise it doesn't make sense.
        return self.do_diff(self.get_extended_namespace(files))

    def do_diff(self, params):
        # Diff returns "1" if differences were found.
        # Add the view name and view type to the description
        o = []
        Feol = False

        while len(params) > 0:
            # Read both original and modified files.
            onam = params.pop(0)
            mnam = params.pop(0)

            file_data = []
            do_rem = False

            # If the filename length is greater than 254 char for windows,
            #   we copied the file to a temp file
            #   because the open will not work for path greater than 254.
            # This is valid for the original and
            #   modified files if the name size is > 254.
            for filenam in (onam, mnam):

                if cpath.exists(filenam) and self.viewtype == "dynamic":
                    do_rem = False
                    fn = filenam
                elif len(filenam) > 254 or self.viewtype == "snapshot":
                    fn = self.get_filename_hash(filenam)
                    fn = cpath.join(tempfile.gettempdir(), fn)
                    do_rem = True

                if cpath.isdir(filenam):
                    content = [
                        '%s\n' % s
                        for s in sorted(os.listdir(filenam))
                    ]
                    file_data.append(content)
                else:
                    fd = open(cpath.normpath(fn))
                    fdata = fd.readlines()
                    fd.close()
                    file_data.append(fdata)
                    # If the file was temp, it should be removed.
                    if do_rem:
                        os.remove(filenam)

            modi = file_data.pop()
            orig = file_data.pop()

            # For snapshot views, the local directories must be removed because
            #   they will break the diff on the server. Just replacing
            #   everything before the view name (including the view name) for
            #   vobs do the work.
            if (self.viewtype == "snapshot"
                and (sys.platform.startswith('win')
                  or sys.platform.startswith('cygwin'))):
                    vinfo = self.viewinfo.rstrip("\r\n")
                    mnam = "c:\\\\vobs" + mnam[mnam.rfind(vinfo) + len(vinfo):]
                    onam = "c:\\\\vobs" + onam[onam.rfind(vinfo) + len(vinfo):]

            # Call the diff lib to generate a diff.
            # The dates are bogus, since they don't natter anyway.
            # The only thing is that two spaces are needed to the server
            #   so it can identify the heades correctly.
            diff = difflib.unified_diff(orig, modi, onam, mnam,
               '  2002-02-21 23:30:39.942229878 -0800',
               '  2002-02-21 23:30:50.442260588 -0800', lineterm=' \n')
            # Transform the generator output into a string output
            #   Use a comprehension instead of a generator,
            #   so 2.3.x doesn't fail to interpret.
            diffstr = ''.join([str(l) for l in diff])

            # Workaround for the difflib no new line at end of file
            #   problem.
            if not diffstr.endswith('\n'):
                diffstr = diffstr + ("\n\\ No newline at end of file\n")

            o.append(diffstr)

        ostr = ''.join(o)
        return (ostr, None)  # diff, parent_diff (not supported)

    def get_extended_namespace(self, files):
        """
        Parses the file path to get the extended namespace
        """
        versions = self.get_previous_version(files)

        evfiles = []
        hlist = []

        for vkey in versions:
            # Verify if it is a checkedout file.
            if "CHECKEDOUT" in vkey:
                # For checkedout files just add it to the file list
                #   since it cannot be accessed outside the view.
                splversions = vkey[:vkey.rfind("@@")]
                evfiles.append(splversions)
            else:
                # For checkedin files.
                ext_path = []
                ver = []
                fname = ""      # fname holds the file name without the version.
                (bpath, fpath) = cpath.splitdrive(vkey)
                if bpath :
                    # Windows.
                    # The version (if specified like file.c@@/main/1)
                    #   should be kept as a single string
                    #   so split the path and concat the file name
                    #   and version in the last position of the list.
                    ver = fpath.split("@@")
                    splversions = fpath[:vkey.rfind("@@")].split("\\")
                    fname = splversions.pop()
                    splversions.append(fname + ver[1])
                else :
                    # Linux.
                    if vkey.rfind("vobs") != -1 :
                        bpath = vkey[:vkey.rfind("vobs")+4]
                        fpath = vkey[vkey.rfind("vobs")+5:]
                    else :
                       bpath = vkey[:0]
                       fpath = vkey[1:]
                    ver = fpath.split("@@")
                    splversions =  ver[0][:vkey.rfind("@@")].split("/")
                    fname = splversions.pop()
                    splversions.append(fname + ver[1])

                filename = splversions.pop()
                bpath = cpath.normpath(bpath + "/")
                elem_path = bpath

                for key in splversions:
                    # For each element (directory) in the path,
                    #   get its version from clearcase.
                    elem_path = cpath.join(elem_path, key)

                    # This is the version to be appended to the extended
                    #   path list.
                    this_version = self.util.execute(
                        ["cleartool", "desc", "-fmt", "%Vn",
                        cpath.normpath(elem_path)])
                    if this_version:
                        ext_path.append(key + "/@@" + this_version + "/")
                    else:
                        ext_path.append(key + "/")

                # This must be done in case we haven't specified
                #   the version on the command line.
                ext_path.append(cpath.normpath(fname + "/@@" +
                    vkey[vkey.rfind("@@")+2:len(vkey)]))
                epstr = cpath.join(bpath, cpath.normpath(''.join(ext_path)))
                evfiles.append(epstr)

                """
                In windows, there is a problem with long names(> 254).
                In this case, we hash the string and copy the unextended
                  filename to a temp file whose name is the hash.
                This way we can get the file later on for diff.
                The same problem applies to snapshot views where the
                  extended name isn't available.
                The previous file must be copied from the CC server
                  to a local dir.
                """
                if cpath.exists(epstr) :
                    pass
                else:
                    if len(epstr) > 254 or self.viewtype == "snapshot":
                        name = self.get_filename_hash(epstr)
                        # Check if this hash is already in the list
                        try:
                            i = hlist.index(name)
                            die("ERROR: duplicate value %s : %s" %
                                (name, epstr))
                        except ValueError:
                            hlist.append(name)

                        normkey = cpath.normpath(vkey)
                        td = tempfile.gettempdir()
                        # Cygwin case must transform a linux-like path to
                        # windows like path including drive letter
                        if 'cygdrive' in td:
                            where = td.index('cygdrive') + 9
                            drive_letter = td[where:where+1] + ":"
                            td = cpath.join(drive_letter, td[where+1:])
                        tf = cpath.normpath(cpath.join(td, name))
                        if cpath.exists(tf):
                            debug("WARNING: FILE EXISTS")
                            os.unlink(tf)
                        self.util.execute(["cleartool", "get", "-to", tf, normkey])
                    else:
                        die("ERROR: FILE NOT FOUND : %s" % epstr)

        return evfiles