import logging
import os
import re

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import die, execute


class PlasticClient(SCMClient):
    """
    A wrapper around the cm Plastic tool that fetches repository
    information and generates compatible diffs
    """
    def __init__(self, **kwargs):
        super(PlasticClient, self).__init__(**kwargs)

    def get_repository_info(self):
        if not check_install('cm version'):
            return None

        # Get the repository that the current directory is from.  If there
        # is more than one repository mounted in the current directory,
        # bail out for now (in future, should probably enter a review
        # request per each repository.)
        split = execute(["cm", "ls", "--format={8}"], split_lines=True,
                        ignore_errors=True)
        m = re.search(r'^rep:(.+)$', split[0], re.M)

        if not m:
            return None

        # Make sure the repository list contains only one unique entry
        if len(split) != split.count(split[0]):
            # Not unique!
            die('Directory contains more than one mounted repository')

        path = m.group(1)

        # Get the workspace directory, so we can strip it from the diff output
        self.workspacedir = execute(["cm", "gwp", ".", "--format={1}"],
                                    split_lines=False,
                                    ignore_errors=True).strip()

        logging.debug("Workspace is %s" % self.workspacedir)

        return RepositoryInfo(path,
                              supports_changesets=True,
                              supports_parent_diffs=False)

    def get_changenum(self, args):
        """ Extract the integer value from a changeset ID (cs:1234) """
        if len(args) == 1 and args[0].startswith("cs:"):
                try:
                    return str(int(args[0][3:]))
                except ValueError:
                    pass

        return None

    def sanitize_changenum(self, changenum):
        """ Return a "sanitized" change number.  Currently a no-op """
        return changenum

    def diff(self, args):
        """
        Performs a diff across all modified files in a Plastic workspace

        Parent diffs are not supported (the second value in the tuple).
        """
        changenum = self.get_changenum(args)

        if changenum is None:
            return self.branch_diff(args), None
        else:
            return self.changenum_diff(changenum), None

    def diff_between_revisions(self, revision_range, args, repository_info):
        """
        Performs a diff between 2 revisions of a Plastic repository.

        Assume revision_range is a branch specification (br:/main/task001)
        and hand over to branch_diff
        """
        return (self.branch_diff(revision_range), None)

    def changenum_diff(self, changenum):
        logging.debug("changenum_diff: %s" % (changenum))
        files = execute(["cm", "log", "cs:" + changenum,
                         "--csFormat={items}",
                         "--itemFormat={shortstatus} {path} "
                         "rev:revid:{revid} rev:revid:{parentrevid} "
                         "src:{srccmpath} rev:revid:{srcdirrevid} "
                         "dst:{dstcmpath} rev:revid:{dstdirrevid}{newline}"],
                        split_lines = True)

        logging.debug("got files: %s" % (files))

        # Diff generation based on perforce client
        diff_lines = []

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        for f in files:
            f = f.strip()

            if not f:
                continue

            m = re.search(r'(?P<type>[ACIMR]) (?P<file>.*) '
                          r'(?P<revspec>rev:revid:[-\d]+) '
                          r'(?P<parentrevspec>rev:revid:[-\d]+) '
                          r'src:(?P<srcpath>.*) '
                          r'(?P<srcrevspec>rev:revid:[-\d]+) '
                          r'dst:(?P<dstpath>.*) '
                          r'(?P<dstrevspec>rev:revid:[-\d]+)$',
                          f)
            if not m:
                die("Could not parse 'cm log' response: %s" % f)

            changetype = m.group("type")
            filename = m.group("file")

            if changetype == "M":
                # Handle moved files as a delete followed by an add.
                # Clunky, but at least it works
                oldfilename = m.group("srcpath")
                oldspec = m.group("srcrevspec")
                newfilename = m.group("dstpath")
                newspec = m.group("dstrevspec")

                self.write_file(oldfilename, oldspec, tmp_diff_from_filename)
                dl = self.diff_files(tmp_diff_from_filename, empty_filename,
                                     oldfilename, "rev:revid:-1", oldspec,
                                     changetype)
                diff_lines += dl

                self.write_file(newfilename, newspec, tmp_diff_to_filename)
                dl = self.diff_files(empty_filename, tmp_diff_to_filename,
                                     newfilename, newspec, "rev:revid:-1",
                                     changetype)
                diff_lines += dl
            else:
                newrevspec = m.group("revspec")
                parentrevspec = m.group("parentrevspec")

                logging.debug("Type %s File %s Old %s New %s" % (changetype,
                                                         filename,
                                                         parentrevspec,
                                                         newrevspec))

                old_file = new_file = empty_filename

                if (changetype in ['A'] or
                    (changetype in ['C', 'I'] and
                     parentrevspec == "rev:revid:-1")):
                    # File was Added, or a Change or Merge (type I) and there
                    # is no parent revision
                    self.write_file(filename, newrevspec, tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                elif changetype in ['C', 'I']:
                    # File was Changed or Merged (type I)
                    self.write_file(filename, parentrevspec,
                                    tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                    self.write_file(filename, newrevspec, tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                elif changetype in ['R']:
                    # File was Removed
                    self.write_file(filename, parentrevspec,
                                    tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                else:
                    die("Don't know how to handle change type '%s' for %s" %
                        (changetype, filename))

                dl = self.diff_files(old_file, new_file, filename,
                                     newrevspec, parentrevspec, changetype)
                diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)

        return ''.join(diff_lines)

    def branch_diff(self, args):
        logging.debug("branch diff: %s" % (args))

        if len(args) > 0:
            branch = args[0]
        else:
            branch = args

        if not branch.startswith("br:"):
            return None

        if not self.options.branch:
            self.options.branch = branch

        files = execute(["cm", "fbc", branch, "--format={3} {4}"],
                        split_lines = True)
        logging.debug("got files: %s" % (files))

        diff_lines = []

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        for f in files:
            f = f.strip()

            if not f:
                continue

            m = re.search(r'^(?P<branch>.*)#(?P<revno>\d+) (?P<file>.*)$', f)

            if not m:
                die("Could not parse 'cm fbc' response: %s" % f)

            filename = m.group("file")
            branch = m.group("branch")
            revno = m.group("revno")

            # Get the base revision with a cm find
            basefiles = execute(["cm", "find", "revs", "where",
                                 "item='" + filename + "'", "and",
                                 "branch='" + branch + "'", "and",
                                 "revno=" + revno,
                                 "--format={item} rev:revid:{id} "
                                 "rev:revid:{parent}", "--nototal"],
                                split_lines = True)

            # We only care about the first line
            m = re.search(r'^(?P<filename>.*) '
                              r'(?P<revspec>rev:revid:[-\d]+) '
                              r'(?P<parentrevspec>rev:revid:[-\d]+)$',
                              basefiles[0])
            basefilename = m.group("filename")
            newrevspec = m.group("revspec")
            parentrevspec = m.group("parentrevspec")

            # Cope with adds/removes
            changetype = "C"

            if parentrevspec == "rev:revid:-1":
                changetype = "A"
            elif newrevspec == "rev:revid:-1":
                changetype = "R"

            logging.debug("Type %s File %s Old %s New %s" % (changetype,
                                                     basefilename,
                                                     parentrevspec,
                                                     newrevspec))

            old_file = new_file = empty_filename

            if changetype == "A":
                # File Added
                self.write_file(basefilename, newrevspec,
                                tmp_diff_to_filename)
                new_file = tmp_diff_to_filename
            elif changetype == "R":
                # File Removed
                self.write_file(basefilename, parentrevspec,
                                tmp_diff_from_filename)
                old_file = tmp_diff_from_filename
            else:
                self.write_file(basefilename, parentrevspec,
                                tmp_diff_from_filename)
                old_file = tmp_diff_from_filename

                self.write_file(basefilename, newrevspec,
                                tmp_diff_to_filename)
                new_file = tmp_diff_to_filename

            dl = self.diff_files(old_file, new_file, basefilename,
                                 newrevspec, parentrevspec, changetype)
            diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)

        return ''.join(diff_lines)

    def diff_files(self, old_file, new_file, filename, newrevspec,
                   parentrevspec, changetype, ignore_unmodified=False):
        """
        Do the work of producing a diff for Plastic (based on the Perforce one)

        old_file - The absolute path to the "old" file.
        new_file - The absolute path to the "new" file.
        filename - The file in the Plastic workspace
        newrevspec - The revid spec of the changed file
        parentrevspecspec - The revision spec of the "old" file
        changetype - The change type as a single character string
        ignore_unmodified - If true, will return an empty list if the file
            is not changed.

        Returns a list of strings of diff lines.
        """
        if filename.startswith(self.workspacedir):
            filename = filename[len(self.workspacedir):]

        diff_cmd = ["diff", "-urN", old_file, new_file]
        # Diff returns "1" if differences were found.
        dl = execute(diff_cmd, extra_ignore_errors=(1,2),
                     translate_newlines = False)

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

        if dl == [] or dl[0].startswith("Binary files "):
            if dl == []:
                if ignore_unmodified:
                    return []
                else:
                    print "Warning: %s in your changeset is unmodified" % \
                          filename

            dl.insert(0, "==== %s (%s) ==%s==\n" % (filename, newrevspec,
                                                    changetype))
            dl.append('\n')
        else:
            dl[0] = "--- %s\t%s\n" % (filename, parentrevspec)
            dl[1] = "+++ %s\t%s\n" % (filename, newrevspec)

            # Not everybody has files that end in a newline.  This ensures
            # that the resulting diff file isn't broken.
            if dl[-1][-1] != '\n':
                dl.append('\n')

        return dl

    def write_file(self, filename, filespec, tmpfile):
        """ Grabs a file from Plastic and writes it to a temp file """
        logging.debug("Writing '%s' (rev %s) to '%s'" % (filename, filespec, tmpfile))
        execute(["cm", "cat", filespec, "--file=" + tmpfile])
