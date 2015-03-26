import logging
import os
import re

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError)
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import die, execute


class PlasticClient(SCMClient):
    """
    A wrapper around the cm Plastic tool that fetches repository
    information and generates compatible diffs
    """
    name = 'Plastic'

    supports_patch_revert = True

    REVISION_CHANGESET_PREFIX = 'cs:'

    def __init__(self, **kwargs):
        super(PlasticClient, self).__init__(**kwargs)

    def get_repository_info(self):
        if not check_install(['cm', 'version']):
            logging.debug('Unable to execute "cm version": skipping Plastic')
            return None

        # Get the workspace directory, so we can strip it from the diff output
        self.workspacedir = execute(["cm", "gwp", ".", "--format={1}"],
                                    split_lines=False,
                                    ignore_errors=True).strip()

        logging.debug("Workspace is %s" % self.workspacedir)

        # Get the repository that the current directory is from
        split = execute(["cm", "ls", self.workspacedir, "--format={8}"],
                        split_lines=True, ignore_errors=True)

        # remove blank lines
        split = [x for x in split if x]

        m = re.search(r'^rep:(.+)$', split[0], re.M)

        if not m:
            return None

        path = m.group(1)

        return RepositoryInfo(path,
                              supports_changesets=True,
                              supports_parent_diffs=False)

    def parse_revision_spec(self, revisions=[]):
        """Parses the given revision spec.

        The 'revisions' argument is a list of revisions as specified by the
        user. Items in the list do not necessarily represent a single revision,
        since the user can use SCM-native syntaxes such as "r1..r2" or "r1:r2".
        SCMTool-specific overrides of this method are expected to deal with
        such syntaxes.

        This will return a dictionary with the following keys:
            'base': Always None.
            'tip':  A revision string representing either a changeset or a
                    branch.

        These will be used to generate the diffs to upload to Review Board (or
        print). The Plastic implementation requires that one and only one
        revision is passed in. The diff for review will include the changes in
        the given changeset or branch.
        """
        n_revisions = len(revisions)

        if n_revisions == 0:
            raise InvalidRevisionSpecError(
                'Either a changeset or a branch must be specified')
        elif n_revisions == 1:
            return {
                'base': None,
                'tip': revisions[0],
            }
        else:
            raise TooManyRevisionsError

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             extra_args=[]):
        """
        Performs a diff across all modified files in a Plastic workspace

        Parent diffs are not supported (the second value in the tuple).
        """
        # TODO: use 'files'
        changenum = None
        tip = revisions['tip']
        if tip.startswith(self.REVISION_CHANGESET_PREFIX):
            logging.debug('Doing a diff against changeset %s', tip)
            try:
                changenum = str(int(
                    tip[len(self.REVISION_CHANGESET_PREFIX):]))
            except ValueError:
                pass
        else:
            logging.debug('Doing a diff against branch %s', tip)
            if not getattr(self.options, 'branch', None):
                self.options.branch = tip

        diff_entries = execute(
            ['cm', 'diff', tip, '--format={status} {path} rev:revid:{revid} '
                                'rev:revid:{parentrevid} src:{srccmpath} '
                                'dst:{dstcmpath}{newline}'],
            split_lines=True)
        logging.debug('Got files: %s', diff_entries)

        diff = self._process_diffs(diff_entries)

        return {
            'diff': diff,
            'changenum': changenum,
        }

    def _process_diffs(self, my_diff_entries):
        # Diff generation based on perforce client
        diff_lines = []

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        for f in my_diff_entries:
            f = f.strip()

            if not f:
                continue

            m = re.search(r'(?P<type>[ACMD]) (?P<file>.*) '
                          r'(?P<revspec>rev:revid:[-\d]+) '
                          r'(?P<parentrevspec>rev:revid:[-\d]+) '
                          r'src:(?P<srcpath>.*) '
                          r'dst:(?P<dstpath>.*)$',
                          f)
            if not m:
                die("Could not parse 'cm log' response: %s" % f)

            changetype = m.group("type")
            filename = m.group("file")

            if changetype == "M":
                # Handle moved files as a delete followed by an add.
                # Clunky, but at least it works
                oldfilename = m.group("srcpath")
                oldspec = m.group("revspec")
                newfilename = m.group("dstpath")
                newspec = m.group("revspec")

                self._write_file(oldfilename, oldspec, tmp_diff_from_filename)
                dl = self._diff_files(tmp_diff_from_filename, empty_filename,
                                      oldfilename, "rev:revid:-1", oldspec,
                                      changetype)
                diff_lines += dl

                self._write_file(newfilename, newspec, tmp_diff_to_filename)
                dl = self._diff_files(empty_filename, tmp_diff_to_filename,
                                      newfilename, newspec, "rev:revid:-1",
                                      changetype)
                diff_lines += dl

            else:
                newrevspec = m.group("revspec")
                parentrevspec = m.group("parentrevspec")

                logging.debug("Type %s File %s Old %s New %s"
                              % (changetype, filename, parentrevspec,
                                 newrevspec))

                old_file = new_file = empty_filename

                if (changetype in ['A'] or
                    (changetype in ['C'] and parentrevspec == "rev:revid:-1")):
                    # There's only one content to show
                    self._write_file(filename, newrevspec,
                                     tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                elif changetype in ['C']:
                    self._write_file(filename, parentrevspec,
                                     tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                    self._write_file(filename, newrevspec,
                                     tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                elif changetype in ['D']:
                    self._write_file(filename, parentrevspec,
                                     tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                else:
                    die("Don't know how to handle change type '%s' for %s" %
                        (changetype, filename))

                dl = self._diff_files(old_file, new_file, filename,
                                      newrevspec, parentrevspec, changetype)
                diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)

        return ''.join(diff_lines)

    def _diff_files(self, old_file, new_file, filename, newrevspec,
                    parentrevspec, changetype):
        """
        Do the work of producing a diff for Plastic (based on the Perforce one)

        old_file - The absolute path to the "old" file.
        new_file - The absolute path to the "new" file.
        filename - The file in the Plastic workspace
        newrevspec - The revid spec of the changed file
        parentrevspecspec - The revision spec of the "old" file
        changetype - The change type as a single character string

        Returns a list of strings of diff lines.
        """
        if filename.startswith(self.workspacedir):
            filename = filename[len(self.workspacedir):]

        diff_cmd = ["diff", "-urN", old_file, new_file]
        # Diff returns "1" if differences were found.
        dl = execute(diff_cmd, extra_ignore_errors=(1, 2),
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
                return []

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

    def _write_file(self, filename, filespec, tmpfile):
        """ Grabs a file from Plastic and writes it to a temp file """
        logging.debug("Writing '%s' (rev %s) to '%s'"
                      % (filename, filespec, tmpfile))
        execute(["cm", "cat", filespec, "--file=" + tmpfile])
