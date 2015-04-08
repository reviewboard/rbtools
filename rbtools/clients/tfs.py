from __future__ import unicode_literals

import difflib
import logging
import os
import re
import sys
import urllib2
import xml.etree.ElementTree as ET

from rbtools.clients import RepositoryInfo, SCMClient
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError)
from rbtools.utils.checks import check_install
from rbtools.utils.process import die, execute


class TFSClient(SCMClient):
    """A client for Team Foundation Server.

    This wraps the 'tf' command-line tool to get repository information and
    create diffs.
    """
    name = 'TFS'

    supports_patch_revert = True

    REVISION_WORKING_COPY = '--rbtools-working-copy'

    def __init__(self, config=None, options=None):
        super(TFSClient, self).__init__(config, options)

        self.tf = None

        if sys.platform.startswith('win'):
            # First check in the system path. If that doesn't work, look in the
            # two standard install locations.
            tf_locations = [
                'tf.cmd',
                'tf.exe',
                r'%programfiles(x86)%\Microsoft Visual Studio 12.0\Common7\IDE\tf.cmd',
                r'%programfiles(x86)%\Microsoft Visual Studio 12.0\Common7\IDE\tf.exe',
                r'%programfiles%\Microsoft Team Foundation Server 12.0\Tools\tf.cmd',
            ]

            for location in tf_locations:
                if check_install([location, 'help']):
                    self.tf = location
                    break
        elif check_install(['tf', 'help']):
            self.tf = 'tf'

    def get_repository_info(self):
        if self.tf is None:
            logging.debug('Unable to execute "tf help": skipping TFS')
            return None

        workfold = self._run_tf(['workfold', os.getcwd()])

        m = re.search('^Collection: (.*)$', workfold, re.MULTILINE)
        if not m:
            logging.debug('Could not find the collection from "tf workfold"')
            return None

        path = urllib2.unquote(m.group(1))

        mappings = dict([
            (group[0], group[2])
            for group in
            re.findall(r' (\$(.+))\: (.+)$', workfold, re.MULTILINE)
        ])

        return TFSRepositoryInfo(path, mappings=mappings)

    def parse_revision_spec(self, revisions=[]):
        """Parses the given revision spec.

        The 'revisions' argument is a list of revisions as specified by the
        user. Items in the list do not necessarily represent a single revision,
        since the user can use the TFS-native syntax of "r1~r2". Versions
        passed in can be any versionspec, such as a changeset number,
        L-prefixed label name, 'W' (latest workspace version), or 'T' (latest
        upstream version).

        This will return a dictionary with the following keys:
            'base':        A revision to use as the base of the resulting diff.
            'tip':         A revision to use as the tip of the resulting diff.
            'parent_base': (optional) The revision to use as the base of a
                           parent diff.

        These will be used to generate the diffs to upload to Review Board (or
        print). The diff for review will include the changes in (base, tip],
        and the parent diff (if necessary) will include (parent, base].

        If a single revision is passed in, this will return the parent of that
        revision for 'base' and the passed-in revision for 'tip'.

        If zero revisions are passed in, this will return revisions relevant
        for the "current change" (changes in the work folder which have not yet
        been checked in).
        """
        n_revisions = len(revisions)

        if n_revisions == 1 and '~' in revisions[0]:
            revisions = revisions[0].split('~')
            n_revisions = len(revisions)

        if n_revisions == 0:
            # Most recent checked-out revision -- working copy
            return {
                'base': self._convert_symbolic_revision('W'),
                'tip': self.REVISION_WORKING_COPY,
            }
        elif n_revisions == 1:
            # Either a numeric revision (n-1:n) or a changelist
            revision = self._convert_symbolic_revision(revisions[0])

            return {
                'base': revision - 1,
                'tip': revision,
            }
        elif n_revisions == 2:
            # Diff between two numeric revisions
            return {
                'base': self._convert_symbolic_revision(revisions[0]),
                'tip': self._convert_symbolic_revision(revisions[1]),
            }
        else:
            raise TooManyRevisionsError

        return {
            'base': None,
            'tip': None,
        }

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             extra_args=[]):
        """Returns the generated diff and optional parent diff.

        The return value must be a dictionary, and must have, at a minimum,
        a 'diff' field. A 'parent_diff' can also be provided.

        It may also return 'base_commit_id', representing the revision/ID of
        the commit that the diff or parent diff is based on. This exists
        because in some diff formats, this may different from what's provided
        in the diff.
        """
        base = str(revisions['base'])
        tip = str(revisions['tip'])

        if tip == self.REVISION_WORKING_COPY:
            return self._diff_working_copy(base, include_files,
                                           exclude_patterns)
        else:
            return self._diff_committed_changes(
                base, tip, include_files, exclude_patterns)

    def _diff_working_copy(self, base, include_files, exclude_patterns):
        status = self._run_tf(['status', '-format:xml'])
        root = ET.fromstring(status)

        diff = []

        for pending_change in root.findall('./pending-changes/pending-change'):
            action = pending_change.attrib['change-type'].split(', ')
            new_filename = pending_change.attrib['server-item']
            local_filename = pending_change.attrib['local-item']
            old_version = pending_change.attrib['version']
            file_type = pending_change.attrib['file-type']
            new_version = '(pending)'
            old_data = ''
            new_data = ''

            if 'rename' in action:
                old_filename = pending_change.attrib['source-item']
            else:
                old_filename = new_filename

            if 'add' in action:
                old_filename = '/dev/null'

                if file_type != 'binary':
                    with open(local_filename) as f:
                        new_data = f.read()
                old_data = ''
            elif 'delete' in action:
                old_data = self._run_tf(['print', '-version:%s' % old_version,
                                         old_filename])
                new_data = ''
                new_version = '(deleted)'
            elif 'edit' in action:
                old_data = self._run_tf(['print', '-version:%s' % old_version,
                                         old_filename])

                with open(local_filename) as f:
                    new_data = f.read()

            if file_type == 'binary':
                if 'add' in action:
                    old_filename = new_filename

                diff.append('--- %s\t%s\n' % (old_filename, old_version))
                diff.append('+++ %s\t%s\n' % (new_filename, new_version))
                diff.append('Binary files %s and %s differ\n'
                            % (old_filename, new_filename))
            elif old_filename != new_filename and old_data == new_data:
                # Renamed file with no changes (difflib will completely skip
                # these, so do it by hand).
                diff.append('--- %s\t%s\n' % (old_filename, old_version))
                diff.append('+++ %s\t%s\n' % (new_filename, new_version))
            else:
                diff.append(''.join(difflib.unified_diff(
                    old_data.splitlines(True), new_data.splitlines(True),
                    old_filename, new_filename,
                    old_version, new_version)))

        if len(root.findall('./candidate-pending-changes/pending-change')) > 0:
            logging.warning('There are added or deleted files which have not '
                            'been added to TFS. These will not be included '
                            'in your review request.')

        return {
            'diff': ''.join(diff),
            'parent_diff': None,
            'base_commit_id': base,
        }

    def _diff_committed_changes(self, base, tip, include_files,
                                exclude_patterns):
        """Compute the changes across files given a range of commits.

        This will look at the history of all changes within the given range and
        compute the full set of changes contained therein. Just looking at the
        two trees isn't enough, since files may have moved around and we want
        to include that information.
        """
        # XXX: the code below is a work in progress, but I haven't yet figured
        # out a way to match up rename and source rename entries in the history
        # when multiple files were renamed within a single changeset. For now,
        # just bail out.
        #
        # Probably we can at least try our best and support this for most
        # cases, and die only if we encounter multiple renames.
        die('Posting committed changes is not yet supported for TFS.')

        # We expect to generate a diff for (base, tip], but 'tf history' gives
        # us [base, tip]. Increment the base to avoid this.
        real_base = str(int(base) + 1)

        history = self._run_tf(['history', '-version:%s~%s' % (real_base, tip),
                                '-recursive', '-format:xml', os.getcwd()])

        changesets = {}

        try:
            root = ET.fromstring(history)

            for changeset in root.findall('./changeset'):
                cln = changeset.attrib['id']

                for item in changeset.findall('./item'):
                    action = item.attrib['change-type']
                    server_file = item.attrib['server-item']

                    if 'source rename' in action:
                        filetype = ''
                    else:
                        info = self._run_tf(['info', '-version:%s' % cln,
                                             server_file])
                        m = re.search(r'Type:\W*(.*)$', info, re.MULTILINE)
                        if not m:
                            logging.error("Couldn't find file type for %s in "
                                          "changeset %s (%s)",
                                          server_file, cln, action)
                            continue

                        filetype = m.group(1)

                    if filetype != 'folder':
                        changesets.setdefault(cln, {})[server_file] = {
                            'action': action,
                            'server_file': server_file,
                            'filetype': filetype,
                        }
        except Exception as e:
            logging.debug('Failed to parse output from "tf history": %s',
                          e, exc_info=True)
            logging.debug(history)

    def _run_tf(self, args):
        cmdline = [self.tf, '-noprompt']

        if getattr(self.options, 'tfs_login', None):
            cmdline.append('-login:%s' % self.options.tfs_login)

        cmdline += args

        # Use / style arguments when running on windows
        if sys.platform.startswith('win'):
            for i, arg in enumerate(cmdline):
                if arg.startswith('-'):
                    cmdline[i] = '/' + arg[1:]

        return execute(cmdline, ignore_errors=True)

    def _convert_symbolic_revision(self, revision):
        """Convert a symbolic revision into a numeric changeset."""
        args = ['history', '-stopafter:1', '-recursive', '-format:xml']

        # 'tf history -version:W' doesn't seem to work (even though it's
        # supposed to). Luckily, W is the default when -version isn't passed,
        # so just elide it.
        if revision != 'W':
            args.append('-version:%s' % revision)

        args.append(os.getcwd())

        data = self._run_tf(args)
        try:
            root = ET.fromstring(data)
            item = root.find('./changeset')
            if item is not None:
                return int(item.attrib['id'])
            else:
                raise Exception('No changesets found')
        except Exception as e:
            logging.debug('Failed to parse output from "tf history": %s',
                          e, exc_info=True)
            logging.debug(data)
            raise InvalidRevisionSpecError(
                '"%s" does not appear to be a valid versionspec'
                % revision)


class TFSRepositoryInfo(RepositoryInfo):
    def __init__(self, path=None, base_path=None, supports_changesets=False,
                 supports_parent_diffs=False, mappings=None):
        super(TFSRepositoryInfo, self).__init__(
            path, base_path, supports_changesets, supports_parent_diffs)

        self.mappings = mappings
