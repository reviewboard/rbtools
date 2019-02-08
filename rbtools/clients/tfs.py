"""A client for Team Foundation Server."""

from __future__ import unicode_literals

import logging
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

from six.moves.urllib.parse import unquote

from rbtools.clients import RepositoryInfo, SCMClient
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMError,
                                    TooManyRevisionsError)
from rbtools.utils.appdirs import user_data_dir
from rbtools.utils.checks import check_gnu_diff, check_install
from rbtools.utils.diffs import filename_match_any_patterns
from rbtools.utils.process import execute


class TFExeWrapper(object):
    """Implementation wrapper for using VS2017's tf.exe."""

    REVISION_WORKING_COPY = '--rbtools-working-copy'

    def __init__(self, config=None, options=None):
        """Initialize the wrapper.

        Args:
            config (dict, optional):
                The loaded configuration.

            options (argparse.Namespace, optional):
                The command line options.
        """
        self.config = config
        self.options = options

    def get_repository_info(self):
        """Determine and return the repository info.

        Returns:
            rbtools.clients.RepositoryInfo:
            The repository info object. If the current working directory does
            not correspond to a TFS checkout, this returns ``None``.
        """
        workfold = self._run_tf(['vc', 'workfold', os.getcwd()])

        m = re.search('^Collection: (.*)$', workfold, re.MULTILINE)

        if not m:
            logging.debug('Could not find the collection from "tf vc '
                          'workfold"')
            return None

        # Now that we know it's TFS, make sure we have GNU diff installed, and
        # error out if we don't.
        check_gnu_diff()

        path = unquote(m.group(1))

        return RepositoryInfo(path=path, local_path=path)

    def parse_revision_spec(self, revisions):
        """Parse the given revision spec.

        Args:
            revisions (list of unicode):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use the TFS-native syntax of ``r1~r2``. Versions passed in
                can be any versionspec, such as a changeset number,
                ``L``-prefixed label name, ``W`` (latest workspace version), or
                ``T`` (latest upstream version).

        Raises:
            rbtools.clients.errors.TooManyRevisionsError:
                Too many revisions were specified.

            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revision spec could not be parsed.

        Returns:
            dict:
            A dictionary with the following keys:

            ``base`` (:py:class:`unicode`):
                A revision to use as the base of the resulting diff.

            ``tip`` (:py:class:`unicode`):
                A revision to use as the tip of the resulting diff.

            ``parent_base`` (:py:class:`unicode`, optional):
                The revision to use as the base of a parent diff.

            These will be used to generate the diffs to upload to Review Board
            (or print). The diff for review will include the changes in (base,
            tip], and the parent diff (if necessary) will include (parent,
            base].

            If a single revision is passed in, this will return the parent of
            that revision for "base" and the passed-in revision for "tip".

            If zero revisions are passed in, this will return revisions
            relevant for the "current change" (changes in the work folder which
            have not yet been checked in).
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

    def _convert_symbolic_revision(self, revision, path=None):
        """Convert a symbolic revision into a numeric changeset.

        Args:
            revision (unicode):
                The TFS versionspec to convert.

            path (unicode, optional):
                The itemspec that the revision applies to.

        Returns:
            int:
            The changeset number corresponding to the versionspec.
        """
        # We pass results_unicode=False because that uses the filesystem
        # encoding to decode the output, but the XML results we get should
        # always be UTF-8, and are well-formed with the encoding specified. We
        # can therefore let ElementTree determine how to decode it.
        data = self._run_tf(['vc', 'history', '/stopafter:1', '/recursive',
                             '/format:detailed', '/version:%s' % revision,
                             path or os.getcwd()])

        m = re.search('^Changeset: (\d+)$', data, re.MULTILINE)

        if not m:
            logging.debug('Failed to parse output from "tf vc history":\n%s',
                          data)
            raise InvalidRevisionSpecError(
                '"%s" does not appear to be a valid versionspec' % revision)

    def diff(self, revisions, include_files, exclude_patterns):
        """Return the generated diff.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.

            ``base_commit_id` (:py:class:`unicode`, optional):
                The ID of the commit that the change is based on, if available.
                This is necessary for some hosting services that don't provide
                individual file access.
        """
        base = str(revisions['base'])
        tip = str(revisions['tip'])

        if tip == self.REVISION_WORKING_COPY:
            # TODO: support committed revisions
            return self._diff_working_copy(base, include_files,
                                           exclude_patterns)
        else:
            raise SCMError('Posting committed changes is not yet supported '
                           'for TFS when using the tf.exe wrapper.')

    def _diff_working_copy(self, base, include_files, exclude_patterns):
        """Return a diff of the working copy.

        Args:
            base (unicode):
                The base revision to diff against.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary containing ``diff``, ``parent_diff``, and
            ``base_commit_id`` keys. In the case of TFS, the parent diff key
            will always be ``None``.
        """
        # We pass results_unicode=False because that uses the filesystem
        # encoding, but the XML results we get should always be UTF-8, and are
        # well-formed with the encoding specified. We can therefore let
        # ElementTree determine how to decode it.
        status = self._run_tf(['vc', 'status', '/format:xml'],
                              results_unicode=False)
        root = ET.fromstring(status)

        diff = []

        for pending_change in root.findall(
                './PendingSet/PendingChanges/PendingChange'):
            action = pending_change.attrib['chg'].split(' ')
            old_filename = \
                pending_change.attrib.get('srcitem', '').encode('utf-8')
            new_filename = pending_change.attrib['item'].encode('utf-8')
            local_filename = pending_change.attrib['local']
            old_version = \
                pending_change.attrib.get('svrfm', '0').encode('utf-8')
            file_type = pending_change.attrib['type']
            encoding = pending_change.attrib['enc']
            new_version = b'(pending)'
            old_data = b''
            new_data = b''
            binary = (encoding == '-1')

            copied = 'Branch' in action

            if (not file_type or (not os.path.isfile(local_filename) and
                                  'Delete' not in action)):
                continue

            if (exclude_patterns and
                filename_match_any_patterns(local_filename,
                                            exclude_patterns,
                                            base_dir=None)):
                    continue

            if 'Add' in action:
                old_filename = b'/dev/null'

                if not binary:
                    with open(local_filename, 'rb') as f:
                        new_data = f.read()

                    old_data = b''
            elif 'Delete' in action:
                old_data = self._run_tf(
                    ['vc', 'view', '/version:%s' % old_version.decode('utf-8'),
                     old_filename.decode('utf-8')],
                    results_unicode=False)
                new_data = b''
                new_version = b'(deleted)'
            elif 'Edit' in action:
                if not binary:
                    old_data = self._run_tf(
                        ['vc', 'view', old_filename.decode('utf-8'),
                         '/version:%s' % old_version.decode('utf-8')],
                        results_unicode=False)

                    with open(local_filename, 'rb') as f:
                        new_data = f.read()

            old_label = b'%s\t%s' % (old_filename, old_version)
            new_label = b'%s\t%s' % (new_filename, new_version)

            if copied:
                diff.append(b'Copied from: %s\n' % old_filename)

            if binary:
                if 'Add' in action:
                    old_filename = new_filename

                diff.append(b'--- %s\n' % old_label)
                diff.append(b'+++ %s\n' % new_label)
                diff.append(b'Binary files %s and %s differ\n'
                            % (old_filename, new_filename))
            elif old_filename != new_filename and old_data == new_data:
                # Renamed file with no changes.
                diff.append(b'--- %s\n' % old_label)
                diff.append(b'+++ %s\n' % new_label)
            else:
                old_tmp = tempfile.NamedTemporaryFile(delete=False)
                old_tmp.write(old_data)
                old_tmp.close()

                new_tmp = tempfile.NamedTemporaryFile(delete=False)
                new_tmp.write(new_data)
                new_tmp.close()

                unified_diff = execute(
                    ['diff', '-u',
                     '--label', old_label.decode('utf-8'),
                     '--label', new_label.decode('utf-8'),
                     old_tmp.name, new_tmp.name],
                    extra_ignore_errors=(1,),
                    log_output_on_error=False,
                    results_unicode=False)

                diff.append(unified_diff)

                os.unlink(old_tmp.name)
                os.unlink(new_tmp.name)

        return {
            'diff': b''.join(diff),
            'parent_diff': None,
            'base_commit_id': base,
        }

    def _run_tf(self, args, **kwargs):
        """Run the "tf" command.

        Args:
            args (list):
                A list of arguments to pass to rb-tfs.

            **kwargs (dict):
                Additional keyword arguments for the :py:meth:`execute` call.

        Returns:
            unicode:
            The output of the command.
        """
        command = ['tf'] + args + ['/noprompt']

        if getattr(self.options, 'tfs_login', None):
            command.append('/login:%s' % self.options.tfs_login)

        return execute(command, ignore_errors=True, **kwargs)


class TEEWrapper(object):
    """Implementation wrapper for using Team Explorer Everywhere."""

    REVISION_WORKING_COPY = '--rbtools-working-copy'

    def __init__(self, config=None, options=None):
        """Initialize the wrapper.

        Args:
            config (dict, optional):
                The loaded configuration.

            options (argparse.Namespace, optional):
                The command line options.
        """
        self.config = config
        self.options = options

        self.tf = None
        tf_locations = []

        if options and getattr(options, 'tf_cmd', None):
            tf_locations.append(options.tf_cmd)

        if sys.platform.startswith('win'):
            # First check in the system path. If that doesn't work, look in the
            # two standard install locations.
            tf_locations.extend([
                'tf.cmd',
                (r'%programfiles(x86)%\Microsoft Visual Studio 12.0\Common7'
                 r'\IDE\tf.cmd'),
                (r'%programfiles%\Microsoft Team Foundation Server 12.0\Tools'
                 r'\tf.cmd'),
            ])
        else:
            tf_locations.append('tf')

        for location in tf_locations:
            location = os.path.expandvars(location)

            if check_install([location, 'help']):
                self.tf = location
                break

    def get_repository_info(self):
        """Determine and return the repository info.

        Returns:
            rbtools.clients.RepositoryInfo:
            The repository info object. If the current working directory does
            not correspond to a TFS checkout, this returns ``None``.
        """
        if self.tf is None:
            logging.debug('Unable to execute "tf help": skipping TFS')
            return None

        workfold = self._run_tf(['workfold', os.getcwd()])

        m = re.search('^Collection: (.*)$', workfold, re.MULTILINE)
        if not m:
            logging.debug('Could not find the collection from "tf workfold"')
            return None

        # Now that we know it's TFS, make sure we have GNU diff installed,
        # and error out if we don't.
        check_gnu_diff()

        path = unquote(m.group(1))

        return RepositoryInfo(path=path, local_path=path)

    def parse_revision_spec(self, revisions):
        """Parse the given revision spec.

        Args:
            revisions (list of unicode):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use the TFS-native syntax of ``r1~r2``. Versions passed in
                can be any versionspec, such as a changeset number,
                ``L``-prefixed label name, ``W`` (latest workspace version), or
                ``T`` (latest upstream version).

        Returns:
            dict:
            A dictionary with the following keys:

            ``base`` (:py:class:`unicode`):
                A revision to use as the base of the resulting diff.

            ``tip`` (:py:class:`unicode`):
                A revision to use as the tip of the resulting diff.

            ``parent_base`` (:py:class:`unicode`, optional):
                The revision to use as the base of a parent diff.

            These will be used to generate the diffs to upload to Review Board
            (or print). The diff for review will include the changes in (base,
            tip], and the parent diff (if necessary) will include (parent,
            base].

            If a single revision is passed in, this will return the parent of
            that revision for "base" and the passed-in revision for "tip".

            If zero revisions are passed in, this will return revisions
            relevant for the "current change" (changes in the work folder which
            have not yet been checked in).

        Raises:
            rbtools.clients.errors.TooManyRevisionsError:
                Too many revisions were specified.

            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revision spec could not be parsed.
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

    def _convert_symbolic_revision(self, revision, path=None):
        """Convert a symbolic revision into a numeric changeset.

        Args:
            revision (unicode):
                The TFS versionspec to convert.

            path (unicode, optional):
                The itemspec that the revision applies to.

        Returns:
            int:
            The changeset number corresponding to the versionspec.
        """
        args = ['history', '-stopafter:1', '-recursive', '-format:xml']

        # 'tf history -version:W'` doesn't seem to work (even though it's
        # supposed to). Luckily, W is the default when -version isn't passed,
        # so just elide it.
        if revision != 'W':
            args.append('-version:%s' % revision)

        args.append(path or os.getcwd())

        # We pass results_unicode=False because that uses the filesystem
        # encoding to decode the output, but the XML results we get should
        # always be UTF-8, and are well-formed with the encoding specified. We
        # can therefore let ElementTree determine how to decode it.
        data = self._run_tf(args, results_unicode=False)

        try:
            root = ET.fromstring(data)
            item = root.find('./changeset')

            if item is not None:
                return int(item.attrib['id'])
            else:
                raise Exception('No changesets found')
        except Exception as e:
            logging.debug('Failed to parse output from "tf history": %s\n%s',
                          e, data, exc_info=True)

            raise InvalidRevisionSpecError(
                '"%s" does not appear to be a valid versionspec' % revision)

    def diff(self, revisions, include_files, exclude_patterns):
        """Return the generated diff.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.

            ``base_commit_id` (:py:class:`unicode`, optional):
                The ID of the commit that the change is based on, if available.
                This is necessary for some hosting services that don't provide
                individual file access.
        """
        base = str(revisions['base'])
        tip = str(revisions['tip'])

        if tip == self.REVISION_WORKING_COPY:
            return self._diff_working_copy(base, include_files,
                                           exclude_patterns)
        else:
            raise SCMError('Posting committed changes is not yet supported '
                           'for TFS when using the Team Explorer Everywhere '
                           'wrapper.')

    def _diff_working_copy(self, base, include_files, exclude_patterns):
        """Return a diff of the working copy.

        Args:
            base (unicode):
                The base revision to diff against.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary containing ``diff``, ``parent_diff``, and
            ``base_commit_id`` keys. In the case of TFS, the parent diff key
            will always be ``None``.
        """
        # We pass results_unicode=False because that uses the filesystem
        # encoding, but the XML results we get should always be UTF-8, and are
        # well-formed with the encoding specified. We can therefore let
        # ElementTree determine how to decode it.
        status = self._run_tf(['status', '-format:xml'], results_unicode=False)
        root = ET.fromstring(status)

        diff = []

        for pending_change in root.findall('./pending-changes/pending-change'):
            action = pending_change.attrib['change-type'].split(', ')
            new_filename = pending_change.attrib['server-item'].encode('utf-8')
            local_filename = pending_change.attrib['local-item']
            old_version = pending_change.attrib['version'].encode('utf-8')
            file_type = pending_change.attrib.get('file-type')
            new_version = b'(pending)'
            old_data = b''
            new_data = b''
            copied = 'branch' in action

            if (not file_type or (not os.path.isfile(local_filename) and
                                  'delete' not in action)):
                continue

            if (exclude_patterns and
                filename_match_any_patterns(local_filename,
                                            exclude_patterns,
                                            base_dir=None)):
                continue

            if 'rename' in action:
                old_filename = \
                    pending_change.attrib['source-item'].encode('utf-8')
            else:
                old_filename = new_filename

            if copied:
                old_filename = \
                    pending_change.attrib['source-item'].encode('utf-8')
                old_version = (
                    '%d' % self._convert_symbolic_revision(
                        'W', old_filename.decode('utf-8')))

            if 'add' in action:
                old_filename = b'/dev/null'

                if file_type != 'binary':
                    with open(local_filename) as f:
                        new_data = f.read()
                old_data = b''
            elif 'delete' in action:
                old_data = self._run_tf(
                    ['print', '-version:%s' % old_version.decode('utf-8'),
                     old_filename.decode('utf-8')],
                    results_unicode=False)
                new_data = b''
                new_version = b'(deleted)'
            elif 'edit' in action:
                old_data = self._run_tf(
                    ['print', '-version:%s' % old_version.decode('utf-8'),
                     old_filename.decode('utf-8')],
                    results_unicode=False)

                with open(local_filename) as f:
                    new_data = f.read()

            old_label = b'%s\t%s' % (old_filename, old_version)
            new_label = b'%s\t%s' % (new_filename, new_version)

            if copied:
                diff.append(b'Copied from: %s\n' % old_filename)

            if file_type == 'binary':
                if 'add' in action:
                    old_filename = new_filename

                diff.append(b'--- %s\n' % old_label)
                diff.append(b'+++ %s\n' % new_label)
                diff.append(b'Binary files %s and %s differ\n'
                            % (old_filename, new_filename))
            elif old_filename != new_filename and old_data == new_data:
                # Renamed file with no changes
                diff.append(b'--- %s\n' % old_label)
                diff.append(b'+++ %s\n' % new_label)
            else:
                old_tmp = tempfile.NamedTemporaryFile(delete=False)
                old_tmp.write(old_data)
                old_tmp.close()

                new_tmp = tempfile.NamedTemporaryFile(delete=False)
                new_tmp.write(new_data)
                new_tmp.close()

                unified_diff = execute(
                    ['diff', '-u',
                     '--label', old_label.decode('utf-8'),
                     '--label', new_label.decode('utf-8'),
                     old_tmp.name, new_tmp.name],
                    extra_ignore_errors=(1,),
                    log_output_on_error=False,
                    results_unicode=False)

                diff.append(unified_diff)

                os.unlink(old_tmp.name)
                os.unlink(new_tmp.name)

        if len(root.findall('./candidate-pending-changes/pending-change')) > 0:
            logging.warning('There are added or deleted files which have not '
                            'been added to TFS. These will not be included '
                            'in your review request.')

        return {
            'diff': b''.join(diff),
            'parent_diff': None,
            'base_commit_id': base,
        }

    def _run_tf(self, args, **kwargs):
        """Run the "tf" command.

        Args:
            args (list):
                A list of arguments to pass to rb-tfs.

            **kwargs (dict):
                Additional keyword arguments for the :py:meth:`execute` call.

        Returns:
            unicode:
            The output of the command.
        """
        cmdline = [self.tf, '-noprompt']

        if getattr(self.options, 'tfs_login', None):
            cmdline.append('-login:%s' % self.options.tfs_login)

        cmdline += args

        # Use / style arguments when running on windows.
        if sys.platform.startswith('win'):
            for i, arg in enumerate(cmdline):
                if arg.startswith('-'):
                    cmdline[i] = '/' + arg[1:]

        return execute(cmdline, ignore_errors=True, **kwargs)


class TFHelperWrapper(object):
    """Implementation wrapper using our own helper."""

    def __init__(self, helper_path, config=None, options=None):
        """Initialize the wrapper.

        Args:
            helper_path (unicode):
                The path to the helper binary.

            config (dict, optional):
                The loaded configuration.

            options (argparse.Namespace, optional):
                The command line options.
        """
        self.helper_path = helper_path
        self.config = config
        self.options = options

    def get_repository_info(self):
        """Determine and return the repository info.

        Returns:
            rbtools.clients.RepositoryInfo:
            The repository info object. If the current working directory does
            not correspond to a TFS checkout, this returns ``None``.
        """
        rc, path, errors = self._run_helper(['get-collection'],
                                            ignore_errors=True)

        if rc == 0:
            return RepositoryInfo(path.strip())
        else:
            return None

    def parse_revision_spec(self, revisions):
        """Parse the given revision spec.

        Args:
            revisions (list of unicode):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use the TFS-native syntax of ``r1~r2``. Versions passed in
                can be any versionspec, such as a changeset number,
                ``L``-prefixed label name, ``W`` (latest workspace version), or
                ``T`` (latest upstream version).

        Returns:
            dict:
            A dictionary with the following keys:

            ``base`` (:py:class:`unicode`):
                A revision to use as the base of the resulting diff.

            ``tip`` (:py:class:`unicode`):
                A revision to use as the tip of the resulting diff.

            ``parent_base`` (:py:class:`unicode`, optional):
                The revision to use as the base of a parent diff.

            These will be used to generate the diffs to upload to Review Board
            (or print). The diff for review will include the changes in (base,
            tip], and the parent diff (if necessary) will include (parent,
            base].

            If a single revision is passed in, this will return the parent of
            that revision for "base" and the passed-in revision for "tip".

            If zero revisions are passed in, this will return revisions
            relevant for the "current change" (changes in the work folder which
            have not yet been checked in).

        Raises:
            rbtools.clients.errors.TooManyRevisionsError:
                Too many revisions were specified.

            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revision spec could not be parsed.
        """
        if len(revisions) > 2:
            raise TooManyRevisionsError

        rc, revisions, errors = self._run_helper(
            ['parse-revision'] + revisions, split_lines=True)

        if rc == 0:
            return {
                'base': revisions[0].strip(),
                'tip': revisions[1].strip()
            }
        else:
            raise InvalidRevisionSpecError('\n'.join(errors))

    def diff(self, revisions, include_files, exclude_patterns):
        """Return the generated diff.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.

            ``base_commit_id` (:py:class:`unicode`, optional):
                The ID of the commit that the change is based on, if available.
                This is necessary for some hosting services that don't provide
                individual file access.

        Raises:
            rbtools.clients.errors.SCMError:
                Something failed when creating the diff.
        """
        base = revisions['base']
        tip = revisions['tip']

        rc, diff, errors = self._run_helper(['diff', '--', base, tip],
                                            ignore_errors=True,
                                            results_unicode=False,
                                            log_output_on_error=False)

        if rc in (0, 2):
            if rc == 2:
                # Magic return code that means success, but there were
                # un-tracked files in the working directory.
                logging.warning('There are added or deleted files which have '
                                'not been added to TFS. These will not be '
                                'included in your review request.')

            return {
                'diff': diff,
                'parent_diff': None,
                'base_commit_id': None,
            }
        else:
            raise SCMError(errors.strip())

    def _run_helper(self, args, **kwargs):
        """Run the rb-tfs binary.

        Args:
            args (list):
                A list of arguments to pass to rb-tfs.

            **kwargs (dict):
                Additional keyword arguments for the :py:meth:`execute` call.

        Returns:
            tuple:
            A 3-tuple of return code, output, and error output. The output and
            error output may be lists depending on the contents of ``kwargs``.
        """
        if len(args) == 0:
            raise ValueError('_run_helper called without any arguments')

        cmdline = ['java']
        cmdline += getattr(self.config, 'JAVA_OPTS', ['-Xmx2048M'])
        cmdline += ['-jar', self.helper_path]

        cmdline.append(args[0])

        if self.options:
            if self.options.debug:
                cmdline.append('--debug')

            if getattr(self.options, 'tfs_shelveset_owner', None):
                cmdline += ['--shelveset-owner',
                            self.options.tfs_shelveset_owner]

            if getattr(self.options, 'tfs_login', None):
                cmdline += ['--login', self.options.tfs_login]

        cmdline += args[1:]

        return execute(cmdline,
                       with_errors=False,
                       results_unicode=False,
                       return_error_code=True,
                       return_errors=True,
                       **kwargs)


class TFSClient(SCMClient):
    """A client for Team Foundation Server."""

    name = 'Team Foundation Server'
    supports_diff_exclude_patterns = True
    supports_patch_revert = True

    def __init__(self, config=None, options=None):
        """Initialize the client.

        Args:
            config (dict, optional):
                The loaded configuration.

            options (argparse.Namespace, optional):
                The command line options.
        """
        super(TFSClient, self).__init__(config, options)

        # There are three different backends that can be used to access the
        # underlying TFS repository. We try them in this order:
        #     - VS2017+ tf.exe
        #     - Our custom rb-tfs wrapper, built on the TFS Java SDK
        #     - Team Explorer Everywhere's tf command
        use_tf_exe = False

        try:
            tf_vc_output = execute(['tf', 'vc', 'help'], ignore_errors=True,
                                   none_on_ignored_error=True)

            # VS2015 has a tf.exe but it's not good enough.
            if (tf_vc_output and
                'Version Control Tool, Version 15' in tf_vc_output):
                use_tf_exe = True
        except OSError:
            pass

        helper_path = os.path.join(user_data_dir('rbtools'), 'packages', 'tfs',
                                   'rb-tfs.jar')

        if use_tf_exe:
            self.tf_wrapper = TFExeWrapper(config, options)
        elif os.path.exists(helper_path):
            self.tf_wrapper = TFHelperWrapper(helper_path, config, options)
        else:
            self.tf_wrapper = TEEWrapper(config, options)

    def get_repository_info(self):
        """Determine and return the repository info.

        Returns:
            rbtools.clients.RepositoryInfo:
            The repository info object. If the current working directory does
            not correspond to a TFS checkout, this returns ``None``.
        """
        return self.tf_wrapper.get_repository_info()

    def parse_revision_spec(self, revisions):
        """Parse the given revision spec.

        Args:
            revisions (list of unicode):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use the TFS-native syntax of ``r1~r2``. Versions passed in
                can be any versionspec, such as a changeset number,
                ``L``-prefixed label name, ``W`` (latest workspace version), or
                ``T`` (latest upstream version).

        Returns:
            dict:
            A dictionary with the following keys:

            ``base`` (:py:class:`unicode`):
                A revision to use as the base of the resulting diff.

            ``tip`` (:py:class:`unicode`):
                A revision to use as the tip of the resulting diff.

            ``parent_base`` (:py:class:`unicode`, optional):
                The revision to use as the base of a parent diff.

            These will be used to generate the diffs to upload to Review Board
            (or print). The diff for review will include the changes in (base,
            tip], and the parent diff (if necessary) will include (parent,
            base].

            If a single revision is passed in, this will return the parent of
            that revision for "base" and the passed-in revision for "tip".

            If zero revisions are passed in, this will return revisions
            relevant for the "current change" (changes in the work folder which
            have not yet been checked in).

        Raises:
            rbtools.clients.errors.TooManyRevisionsError:
                Too many revisions were specified.

            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revision spec could not be parsed.
        """
        return self.tf_wrapper.parse_revision_spec(revisions)

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             no_renames=False, extra_args=[]):
        """Return the generated diff.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list, optional):
                A list of file paths to include in the diff.

            exclude_patterns (list, optional):
                A list of file paths to exclude from the diff.

            extra_args (list, optional):
                Unused.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.

            ``base_commit_id` (:py:class:`unicode`, optional):
                The ID of the commit that the change is based on, if available.
                This is necessary for some hosting services that don't provide
                individual file access.
        """
        return self.tf_wrapper.diff(revisions, include_files, exclude_patterns)
