"""A client for Plastic SCM."""

import logging
import os
import re
from typing import List, Optional

from rbtools.clients import RepositoryInfo
from rbtools.clients.base.scmclient import (BaseSCMClient,
                                            SCMClientDiffResult,
                                            SCMClientRevisionSpec)
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError,
                                    SCMClientDependencyError,
                                    SCMError)
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import execute


class PlasticClient(BaseSCMClient):
    """A client for Plastic SCM.

    This is a wrapper around the cm executable that fetches repository
    information and generates compatible diffs.
    """

    scmclient_id = 'plastic'
    name = 'Plastic'
    server_tool_names = 'Plastic SCM'
    supports_changesets = True
    supports_patch_revert = True

    REVISION_CHANGESET_PREFIX = 'cs:'

    def __init__(self, **kwargs):
        """Initialize the client.

        Args:
            **kwargs (dict):
                Keyword arguments to pass through to the superclass.
        """
        super(PlasticClient, self).__init__(**kwargs)

    def check_dependencies(self) -> None:
        """Check whether all base dependencies are available.

        This checks for the presence of :command:`cm` in the system path.

        Version Added:
            4.0

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                A :command:`cm` tool could not be found.
        """
        if not check_install(['cm', 'version']):
            raise SCMClientDependencyError(missing_exes=['cm'])

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        # NOTE: This can be removed once check_dependencies() is mandatory.
        if not self.has_dependencies(expect_checked=True):
            logging.debug('Unable to execute "cm version": skipping Plastic')
            return None

        # Get the workspace directory, so we can strip it from the diff output
        self.workspacedir = execute(['cm', 'gwp', '.', '--format={1}'],
                                    split_lines=False,
                                    ignore_errors=True).strip()

        logging.debug('Workspace is %s', self.workspacedir)

        # Get the repository that the current directory is from
        split = execute(['cm', 'ls', self.workspacedir, '--format={8}'],
                        split_lines=True, ignore_errors=True)

        # remove blank lines
        split = [x for x in split if x]

        m = re.search(r'^rep:(.+)$', split[0], re.M)

        if not m:
            return None

        return m.group(1)

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        local_path = self.get_local_path()

        if local_path:
            return RepositoryInfo(path=local_path,
                                  local_path=local_path)

        return None

    def parse_revision_spec(
        self,
        revisions: List[str] = [],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The Plastic implementation requires that one and only
        one revision is passed in. The diff for review will include the
        changes in the given changeset or branch.

        Args:
            revisions (list of str, optional):
                A list of revisions as specified by the user.

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates ``tip``.

            ``base`` will always be ``None``.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.
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

    def diff(
        self,
        revisions: SCMClientRevisionSpec,
        **kwargs,
    ) -> SCMClientDiffResult:
        """Perform a diff across all modified files in a Plastic workspace.

        Parent diffs are not supported.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary containing keys documented in
            :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`.
        """
        # TODO: use 'files'
        changenum = None
        tip = revisions['tip']
        assert tip

        if tip.startswith(self.REVISION_CHANGESET_PREFIX):
            logging.debug('Doing a diff against changeset %s', tip)

            try:
                changenum = str(int(
                    tip[len(self.REVISION_CHANGESET_PREFIX):]))
            except ValueError:
                pass
        else:
            logging.debug('Doing a diff against branch %s', tip)

            if self.options and not getattr(self.options, 'branch', None):
                self.options.branch = tip

        diff_entries = execute(
            ['cm', 'diff', tip, '--format={status} {path} rev:revid:{revid} '
                                'rev:revid:{parentrevid} src:{srccmpath} '
                                'dst:{dstcmpath}{newline}'],
            results_unicode=False,
            split_lines=True)

        diff = self._process_diffs(diff_entries)

        return {
            'diff': diff,
            'changenum': changenum,
        }

    def _process_diffs(self, diff_entries):
        """Process the given diff entries.

        Args:
            diff_entries (list):
                The list of diff entries.

        Returns:
            bytes:
            The processed diffs.
        """
        diff_lines = []

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        for f in diff_entries:
            f = f.strip()

            if not f:
                continue

            m = re.search(br'(?P<type>[ACMD]) (?P<file>.*) '
                          br'(?P<revspec>rev:revid:[-\d]+) '
                          br'(?P<parentrevspec>rev:revid:[-\d]+) '
                          br'src:(?P<srcpath>.*) '
                          br'dst:(?P<dstpath>.*)$',
                          f)
            if not m:
                raise SCMError('Could not parse "cm log" response: %s' % f)

            changetype = m.group('type')
            filename = m.group('file')

            if changetype == b'M':
                # Handle moved files as a delete followed by an add.
                # Clunky, but at least it works
                oldfilename = m.group('srcpath')
                oldspec = m.group('revspec')
                newfilename = m.group('dstpath')
                newspec = m.group('revspec')

                self._write_file(oldfilename, oldspec, tmp_diff_from_filename)
                dl = self._diff_files(tmp_diff_from_filename, empty_filename,
                                      oldfilename, 'rev:revid:-1', oldspec,
                                      changetype)
                diff_lines += dl

                self._write_file(newfilename, newspec, tmp_diff_to_filename)
                dl = self._diff_files(empty_filename, tmp_diff_to_filename,
                                      newfilename, newspec, 'rev:revid:-1',
                                      changetype)
                diff_lines += dl

            else:
                newrevspec = m.group('revspec')
                parentrevspec = m.group('parentrevspec')

                logging.debug('Type %s File %s Old %s New %s',
                              changetype, filename, parentrevspec, newrevspec)

                old_file = new_file = empty_filename

                if (changetype in [b'A'] or
                    (changetype in [b'C'] and
                     parentrevspec == b'rev:revid:-1')):
                    # There's only one content to show
                    self._write_file(filename, newrevspec,
                                     tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                elif changetype in [b'C']:
                    self._write_file(filename, parentrevspec,
                                     tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                    self._write_file(filename, newrevspec,
                                     tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                elif changetype in [b'D']:
                    self._write_file(filename, parentrevspec,
                                     tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                else:
                    raise SCMError('Unknown change type "%s" for %s'
                                   % (changetype, filename))

                dl = self._diff_files(old_file, new_file, filename,
                                      newrevspec, parentrevspec, changetype)
                diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)

        return b''.join(diff_lines)

    def _diff_files(self, old_file, new_file, filename, newrevspec,
                    parentrevspec, changetype):
        """Do the work of producing a diff for Plastic.

        Args:
            old_file (bytes):
                The absolute path to the old file.

            new_file (bytes):
                The absolute path to the new file.

            filename (bytes):
                The file in the Plastic workspace.

            newrevspec (bytes):
                The revid spec of the new file.

            parentrevspec (bytes):
                The revid spec of the old file.

            changetype (bytes):
                The change type as a single character string.

        Returns:
            list of bytes:
            The computed diff.
        """
        if filename.startswith(self.workspacedir):
            filename = filename[len(self.workspacedir):]

        # Diff returns "1" if differences were found.
        dl = execute(['diff', '-urN', old_file, new_file],
                     extra_ignore_errors=(1, 2),
                     results_unicode=False)

        # If the input file has ^M characters at end of line, lets ignore them.
        dl = dl.replace(b'\r\r\n', b'\r\n')
        dl = dl.splitlines(True)

        # Special handling for the output of the diff tool on binary files:
        #     diff outputs "Files a and b differ"
        # and the code below expects the output to start with
        #     "Binary files "
        if (len(dl) == 1 and
            dl[0].startswith(b'Files %s and %s differ'
                             % (old_file.encode('utf-8'),
                                new_file.encode('utf-8')))):
            dl = [b'Binary files %s and %s differ\n'
                  % (old_file.encode('utf-8'),
                     new_file.encode('utf-8'))]

        if dl == [] or dl[0].startswith(b'Binary files '):
            if dl == []:
                return []

            dl.insert(0, b'==== %s (%s) ==%s==\n'
                      % (filename, newrevspec, changetype))
            dl.append('\n')
        else:
            dl[0] = '--- %s\t%s\n' % (filename, parentrevspec)
            dl[1] = '+++ %s\t%s\n' % (filename, newrevspec)

            # Not everybody has files that end in a newline.  This ensures
            # that the resulting diff file isn't broken.
            if dl[-1][-1] != b'\n':
                dl.append(b'\n')

        return dl

    def _write_file(self, filename, filespec, tmpfile):
        """Retrieve a file from Plastic and write it to a temp file.

        Args:
            filename (bytes):
                The filename to fetch.

            filespec (bytes):
                The revision of the file to fetch.

            tmpfile (unicode):
                The name of the temporary file to write to.
        """
        logging.debug('Writing "%s" (rev %s) to "%s"',
                      filename.decode('utf-8'),
                      filespec.decode('utf-8'),
                      tmpfile)
        execute(['cm', 'cat', filespec, '--file=' + tmpfile])
