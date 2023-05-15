"""A client for Team Foundation Server."""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, cast
from urllib.parse import unquote

from rbtools.clients import BaseSCMClient, RepositoryInfo
from rbtools.clients.base.scmclient import (SCMClientDiffResult,
                                            SCMClientRevisionSpec)
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    SCMError,
                                    TooManyRevisionsError)
from rbtools.deprecation import (RemovedInRBTools50Warning,
                                 deprecate_non_keyword_only_args)
from rbtools.diffs.writers import UnifiedDiffWriter
from rbtools.utils.appdirs import user_data_dir
from rbtools.utils.checks import check_install
from rbtools.utils.diffs import filename_match_any_patterns
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import (RunProcessError,
                                   RunProcessResult,
                                   run_process)


class BaseTFWrapper:
    """Base class for TF wrappers.

    Version Added:
        4.0
    """

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
        options: Optional[argparse.Namespace] = None,
    ) -> None:
        """Initialize the wrapper.

        Args:
            config (dict, optional):
                The loaded configuration.

            options (argparse.Namespace, optional):
                The command line options.
        """
        self.config = config
        self.options = options

    def check_dependencies(self) -> None:
        """Check whether all dependencies for the client are available.

        By default, no dependencies are checked.
        """
        pass

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        raise NotImplementedError

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        raise NotImplementedError

    def parse_revision_spec(
        self,
        revisions: List[str],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The diff for review will include the changes in (base,
        tip], and the parent diff (if necessary) will include (parent,
        base].

        If a single revision is passed in, this will return the parent of
        that revision for "base" and the passed-in revision for "tip".

        If zero revisions are passed in, this will return revisions
        relevant for the "current change" (changes in the work folder which
        have not yet been checked in).

        Args:
            revisions (list of str):
                A list of revisions as specified by the user.

                Items in the list do not necessarily represent a single
                revision, since the user can use the TFS-native syntax of
                ``r1~r2``. Versions passed in can be any versionspec, such as a
                changeset number, ``L``-prefixed label name, ``W`` (latest
                workspace version), or ``T`` (latest upstream version).

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates ``base`` and ``tip``.

        Raises:
            rbtools.clients.errors.TooManyRevisionsError:
                Too many revisions were specified.

            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revision spec could not be parsed.
        """
        raise NotImplementedError

    def diff(
        self,
        *,
        client: TFSClient,
        revisions: SCMClientRevisionSpec,
        include_files: List[str],
        exclude_patterns: List[str],
    ) -> SCMClientDiffResult:
        """Return the generated diff.

        Args:
            client (TFSClient):
                The client performing the diff.

            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary of diff results.

            See :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`
            for the format of this dictionary.
        """
        raise NotImplementedError


class TFExeWrapper(BaseTFWrapper):
    """Implementation wrapper for using VS2017's tf.exe."""

    REVISION_WORKING_COPY = '--rbtools-working-copy'

    def check_dependencies(self) -> None:
        """Check whether all dependencies for the client are available.

        This will check for ``tf.exe``.

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                A :command:`tf` tool could not be found.
        """
        tf_vc_output: bytes

        try:
            tf_vc_output = (
                run_process(['tf', 'vc', 'help'])
                .stdout_bytes
                .read()
            )
        except Exception:
            tf_vc_output = b''

        # VS2015 has a tf.exe but it's not good enough.
        if (not tf_vc_output or
            b'Version Control Tool, Version 15' not in tf_vc_output):
            raise SCMClientDependencyError(missing_exes=['tf'])

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        workfold = (
            self._run_tf(['vc', 'workfold', os.getcwd()])
            .stdout
            .read()
        )

        m = re.search('^Collection: (.*)$', workfold, re.MULTILINE)

        if m:
            return unquote(m.group(1))

        logging.debug('Could not find the collection from "tf vc workfold"')
        return None

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        path = self.get_local_path()

        if path:
            return RepositoryInfo(path=path, local_path=path)

        return None

    def parse_revision_spec(
        self,
        revisions: List[str],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The diff for review will include the changes in (base,
        tip], and the parent diff (if necessary) will include (parent,
        base].

        If a single revision is passed in, this will return the parent of
        that revision for "base" and the passed-in revision for "tip".

        If zero revisions are passed in, this will return revisions
        relevant for the "current change" (changes in the work folder which
        have not yet been checked in).

        Versions passed in can be any versionspec, such as a changeset number,
        ``L``-prefixed label name, ``W`` (latest workspace version), or ``T``
        (latest upstream version).

        Args:
            revisions (list of str):
                A list of revisions as specified by the user.

                Items in the list do not necessarily represent a single
                revision, since the user can use the TFS-native syntax of
                ``r1~r2``. Versions passed in can be any versionspec, such as a
                changeset number, ``L``-prefixed label name, ``W`` (latest
                workspace version), or ``T`` (latest upstream version).

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates ``base`` and ``tip``.

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
                'base': str(self._convert_symbolic_revision('W')),
                'tip': self.REVISION_WORKING_COPY,
            }
        elif n_revisions == 1:
            # Either a numeric revision (n-1:n) or a changelist
            revision = self._convert_symbolic_revision(revisions[0])

            return {
                'base': str(revision - 1),
                'tip': str(revision),
            }
        elif n_revisions == 2:
            # Diff between two numeric revisions
            return {
                'base': str(self._convert_symbolic_revision(revisions[0])),
                'tip': str(self._convert_symbolic_revision(revisions[1])),
            }
        else:
            raise TooManyRevisionsError

    def _convert_symbolic_revision(
        self,
        revision: str,
        path: Optional[str] = None,
    ) -> int:
        """Convert a symbolic revision into a numeric changeset.

        Args:
            revision (str):
                The TFS versionspec to convert.

            path (str, optional):
                The itemspec that the revision applies to.

        Returns:
            int:
            The changeset number corresponding to the versionspec.
        """
        data = (
            self._run_tf([
                'vc',
                'history',
                '/stopafter:1',
                '/recursive',
                '/format:detailed',
                '/version:%s' % revision,
                path or os.getcwd(),
            ])
            .stdout_bytes
            .read()
        )

        m = re.search(br'^Changeset: (\d+)$', data, re.MULTILINE)

        if not m:
            logging.debug('Failed to parse output from "tf vc history":\n%s',
                          data)
            raise InvalidRevisionSpecError(
                '"%s" does not appear to be a valid versionspec' % revision)

        return int(m.group(1))

    def diff(
        self,
        *,
        client: TFSClient,
        revisions: SCMClientRevisionSpec,
        include_files: List[str],
        exclude_patterns: List[str],
    ) -> SCMClientDiffResult:
        """Return the generated diff.

        Args:
            client (TFSClient):
                The client performing the diff.

            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary of diff results.

            See :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`
            for the format of this dictionary.
        """
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        if tip == self.REVISION_WORKING_COPY:
            # TODO: support committed revisions
            return self._diff_working_copy(client=client,
                                           base=base,
                                           include_files=include_files,
                                           exclude_patterns=exclude_patterns)

        raise SCMError('Posting committed changes is not yet supported '
                       'for TFS when using the tf.exe wrapper.')

    def _diff_working_copy(
        self,
        *,
        client: TFSClient,
        base: str,
        include_files: List[str],
        exclude_patterns: List[str],
    ) -> SCMClientDiffResult:
        """Return a diff of the working copy.

        Args:
            client (TFSClient):
                The client performing the diff.

            base (str):
                The base revision to diff against.

            include_files (list of str, unused):
                A list of file paths to include in the diff.

            exclude_patterns (list of str):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary of diff results.

            See :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`
            for the format of this dictionary.

            ``parent_diff`` will always be ``None``.
        """
        diff_tool = client.get_diff_tool()
        assert diff_tool is not None

        status = (
            self._run_tf(['vc', 'status', '/format:xml'])
            .stdout_bytes
            .read()
        )
        root = ET.fromstring(status)

        stream = io.BytesIO()
        diff_writer = UnifiedDiffWriter(stream)

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
                                            exclude_patterns)):
                continue

            if 'Add' in action:
                old_filename = b'/dev/null'

                if not binary:
                    with open(local_filename, 'rb') as f:
                        new_data = f.read()

                    old_data = b''
            elif 'Delete' in action:
                if not binary:
                    old_data = (
                        self._run_tf([
                            'vc',
                            'view',
                            old_filename.decode('utf-8'),
                            '/version:%s' % old_version.decode('utf-8'),
                        ])
                        .stdout_bytes
                        .read()
                    )

                new_data = b''
                new_version = b'(deleted)'
            elif 'Edit' in action:
                if not binary:
                    old_data = (
                        self._run_tf([
                            'vc',
                            'view',
                            old_filename.decode('utf-8'),
                            '/version:%s' % old_version.decode('utf-8'),
                        ])
                        .stdout_bytes
                        .read()
                    )

                    with open(local_filename, 'rb') as f:
                        new_data = f.read()

            if copied:
                diff_writer.write_line(b'Copied from: %s' % old_filename)

            if binary:
                diff_writer.write_file_headers(
                    orig_path=old_filename,
                    orig_extra=old_version,
                    modified_path=new_filename,
                    modified_extra=new_version)

                if 'Add' in action:
                    old_filename = new_filename

                diff_writer.write_binary_files_differ(
                    orig_path=old_filename,
                    modified_path=new_filename)
            elif old_filename != new_filename and old_data == new_data:
                # Renamed file with no changes.
                diff_writer.write_file_headers(
                    orig_path=old_filename,
                    orig_extra=old_version,
                    modified_path=new_filename,
                    modified_extra=new_version)
            else:
                old_tmp = make_tempfile(content=old_data)
                new_tmp = make_tempfile(content=new_data)

                diff_result = diff_tool.run_diff_file(
                    orig_path=old_tmp,
                    modified_path=new_tmp)

                if diff_result.has_text_differences:
                    diff_writer.write_file_headers(
                        orig_path=old_filename,
                        orig_extra=old_version,
                        modified_path=new_filename,
                        modified_extra=new_version)
                    diff_writer.write_diff_file_result_hunks(diff_result)

                os.unlink(old_tmp)
                os.unlink(new_tmp)

        return {
            'diff': stream.getvalue(),
            'parent_diff': None,
            'base_commit_id': base,
        }

    def _run_tf(
        self,
        args: List[str],
    ) -> RunProcessResult:
        """Run the "tf" command.

        Args:
            args (list of str):
                A list of arguments to pass to rb-tfs.

        Returns:
            rbtools.utils.process.RunProcessResult:
            The result of the command.
        """
        command = ['tf'] + args + ['/noprompt']

        tfs_login = getattr(self.options, 'tfs_login', None)

        if tfs_login:
            command.append('/login:%s' % tfs_login)

        return run_process(command, ignore_errors=True)


class TEEWrapper(BaseTFWrapper):
    """Implementation wrapper for using Team Explorer Everywhere."""

    REVISION_WORKING_COPY = '--rbtools-working-copy'

    @classmethod
    def get_default_tf_locations(
        cls,
        target_platform: str = sys.platform
    ) -> List[str]:
        """Return default locations for tf.cmd for the given platform.

        Version Added:
            4.0

        Args:
            target_platform (str):
                The platform to return paths for.

        Returns:
            list of str:
            The list of possible platforms.
        """
        tf_locations: List[str] = []

        if target_platform.startswith('win'):
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

        return tf_locations

    def __init__(self, **kwargs) -> None:
        """Initialize the wrapper.

        Args:
            **kwargs (dict):
                Keyword arguments to pass to the parent class.
        """
        super().__init__(**kwargs)

        self.tf: Optional[str] = None

    def check_dependencies(self) -> None:
        """Check whether all dependencies for the client are available.

        This checks for the presence of :command:`tf` or :command:`tf.cmd`
        in known locations and in the system path.

        It will also include the :option:`--tf-cmd` location, if provided.

        Version Added:
            4.0

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                A :command:`tf` tool could not be found.
        """
        options = self.options
        tf_locations = []

        if options and getattr(options, 'tf_cmd', None):
            tf_locations.append(options.tf_cmd)

        tf_locations += self.get_default_tf_locations()

        for location in tf_locations:
            location = os.path.expandvars(location)

            if check_install([location, 'help']):
                self.tf = location
                return

        # To help with debugging, we'll include the full path on each.
        raise SCMClientDependencyError(missing_exes=[tuple(tf_locations)])

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        assert self.tf is not None

        workfold = (
            self._run_tf(['workfold', os.getcwd()])
            .stdout
            .read()
        )

        m = re.search('^Collection: (.*)$', workfold, re.MULTILINE)

        if m:
            return unquote(m.group(1))

        logging.debug('Could not find the collection from "tf workfold"')
        return None

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        path = self.get_local_path()

        if path:
            return RepositoryInfo(path=path, local_path=path)

        return None

    def parse_revision_spec(
        self,
        revisions: List[str],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The diff for review will include the changes in (base,
        tip], and the parent diff (if necessary) will include (parent,
        base].

        If a single revision is passed in, this will return the parent of
        that revision for "base" and the passed-in revision for "tip".

        If zero revisions are passed in, this will return revisions
        relevant for the "current change" (changes in the work folder which
        have not yet been checked in).

        Args:
            revisions (list of str):
                A list of revisions as specified by the user.

                Items in the list do not necessarily represent a single
                revision, since the user can use the TFS-native syntax of
                ``r1~r2``. Versions passed in can be any versionspec, such as a
                changeset number, ``L``-prefixed label name, ``W`` (latest
                workspace version), or ``T`` (latest upstream version).

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates ``base`` and ``tip``.

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
                'base': str(self._convert_symbolic_revision('W')),
                'tip': self.REVISION_WORKING_COPY,
            }
        elif n_revisions == 1:
            # Either a numeric revision (n-1:n) or a changelist
            revision = self._convert_symbolic_revision(revisions[0])

            return {
                'base': str(revision - 1),
                'tip': str(revision),
            }
        elif n_revisions == 2:
            # Diff between two numeric revisions
            return {
                'base': str(self._convert_symbolic_revision(revisions[0])),
                'tip': str(self._convert_symbolic_revision(revisions[1])),
            }
        else:
            raise TooManyRevisionsError

    def _convert_symbolic_revision(
        self,
        revision: str,
        path: Optional[str] = None,
    ) -> int:
        """Convert a symbolic revision into a numeric changeset.

        Args:
            revision (str):
                The TFS versionspec to convert.

            path (str, optional):
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

        # We access stdout_bytes, even though the XML results we get should
        # always be UTF-8. They are well-formed with the encoding specified,
        # so we can let ElementTree determine how to decode it.
        data = (
            self._run_tf(args)
            .stdout_bytes
            .read()
        )

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

    def diff(
        self,
        *,
        client: TFSClient,
        revisions: SCMClientRevisionSpec,
        include_files: List[str],
        exclude_patterns: List[str],
    ) -> SCMClientDiffResult:
        """Return the generated diff.

        Args:
            client (TFSClient):
                The client performing the diff.

            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary of diff results.

            See :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`
            for the format of this dictionary.

            ``parent_diff`` will always be ``None``.
        """
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        if tip == self.REVISION_WORKING_COPY:
            return self._diff_working_copy(client=client,
                                           base=base,
                                           include_files=include_files,
                                           exclude_patterns=exclude_patterns)

        raise SCMError('Posting committed changes is not yet supported '
                       'for TFS when using the Team Explorer Everywhere '
                       'wrapper.')

    def _diff_working_copy(
        self,
        *,
        client: TFSClient,
        base: str,
        include_files: List[str],
        exclude_patterns: List[str],
    ) -> SCMClientDiffResult:
        """Return a diff of the working copy.

        Args:
            client (TFSClient):
                The client performing the diff.

            base (str):
                The base revision to diff against.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary of diff results.

            See :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`
            for the format of this dictionary.

            ``parent_diff`` will always be ``None``.
        """
        diff_tool = client.get_diff_tool()
        assert diff_tool is not None

        # We access stdout_bytes, even though the XML results we get should
        # always be UTF-8. They are well-formed with the encoding specified,
        # so we can let ElementTree determine how to decode it.
        status = (
            self._run_tf(['status', '-format:xml'])
            .stdout_bytes
            .read()
        )
        root = ET.fromstring(status)

        stream = io.BytesIO()
        diff_writer = UnifiedDiffWriter(stream)

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
                                            exclude_patterns)):
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
                        'W', old_filename.decode('utf-8'))).encode('utf-8')

            if 'add' in action:
                old_filename = b'/dev/null'

                if file_type != 'binary':
                    with open(local_filename, 'rb') as f:
                        new_data = f.read()

                old_data = b''
            elif 'delete' in action:
                if file_type != 'binary':
                    old_data = (
                        self._run_tf([
                            'print',
                            '-version:%s' % old_version.decode('utf-8'),
                            old_filename.decode('utf-8'),
                        ])
                        .stdout_bytes
                        .read()
                    )

                new_data = b''
                new_version = b'(deleted)'
            elif 'edit' in action:
                if file_type != 'binary':
                    old_data = (
                        self._run_tf([
                            'print',
                            '-version:%s' % old_version.decode('utf-8'),
                            old_filename.decode('utf-8'),
                        ])
                        .stdout_bytes
                        .read()
                    )

                    with open(local_filename, 'rb') as f:
                        new_data = f.read()

            if copied:
                diff_writer.write_line(b'Copied from: %s' % old_filename)

            if file_type == 'binary':
                diff_writer.write_file_headers(
                    orig_path=old_filename,
                    orig_extra=old_version,
                    modified_path=new_filename,
                    modified_extra=new_version)

                if 'add' in action:
                    old_filename = new_filename

                diff_writer.write_binary_files_differ(
                    orig_path=old_filename,
                    modified_path=new_filename)
            elif old_filename != new_filename and old_data == new_data:
                # Renamed file with no changes
                diff_writer.write_file_headers(
                    orig_path=old_filename,
                    orig_extra=old_version,
                    modified_path=new_filename,
                    modified_extra=new_version)
            else:
                old_tmp = make_tempfile(content=old_data)
                new_tmp = make_tempfile(content=new_data)

                diff_result = diff_tool.run_diff_file(
                    orig_path=old_tmp,
                    modified_path=new_tmp)

                if diff_result.has_text_differences:
                    diff_writer.write_file_headers(
                        orig_path=old_filename,
                        orig_extra=old_version,
                        modified_path=new_filename,
                        modified_extra=new_version)
                    diff_writer.write_diff_file_result_hunks(diff_result)

                os.unlink(old_tmp)
                os.unlink(new_tmp)

        if len(root.findall('./candidate-pending-changes/pending-change')) > 0:
            logging.warning('There are added or deleted files which have not '
                            'been added to TFS. These will not be included '
                            'in your review request.')

        return {
            'diff': stream.getvalue(),
            'parent_diff': None,
            'base_commit_id': base,
        }

    def _run_tf(
        self,
        args: List[str],
    ) -> RunProcessResult:
        """Run the "tf" command.

        Args:
            args (list of str):
                A list of arguments to pass to rb-tfs.

        Returns:
            rbtools.utils.process.RunProcessResult
            The result of the command.
        """
        assert self.tf is not None

        cmdline: List[str] = [self.tf, '-noprompt']

        tfs_login = getattr(self.options, 'tfs_login', None)

        if tfs_login:
            cmdline.append('-login:%s' % tfs_login)

        cmdline += args

        # Use / style arguments when running on windows.
        if sys.platform.startswith('win'):
            for i, arg in enumerate(cmdline):
                if arg.startswith('-'):
                    cmdline[i] = '/' + arg[1:]

        return run_process(cmdline, ignore_errors=True)


class TFHelperWrapper(BaseTFWrapper):
    """Implementation wrapper using our own helper."""

    def __init__(self, **kwargs) -> None:
        """Initialize the wrapper.

        Args:
            **kwargs (dict):
                Keyword arguments to pass to the parent class.
        """
        super().__init__(**kwargs)

        self.helper_path = os.path.join(
            user_data_dir('rbtools'), 'packages', 'tfs', 'rb-tfs.jar')

    def check_dependencies(self) -> None:
        """Check whether all dependencies for the client are available.

        This will check that :command:`java` is installed, so the provided
        JAR file can be used.

        Version Added:
            4.0

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                :command:`java` could not be found.
        """
        missing_exes: SCMClientDependencyError.MissingList = []

        if not os.path.exists(self.helper_path):
            missing_exes.append(self.helper_path)

        if not check_install(['java']):
            missing_exes.append('java')

        if missing_exes:
            raise SCMClientDependencyError(missing_exes=missing_exes)

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        try:
            return (
                self._run_helper(['get-collection'])
                .stdout
                .read()
                .strip()
            )
        except Exception:
            return None

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        path = self.get_local_path()

        if path:
            return RepositoryInfo(path=path, local_path=path)

        return None

    def parse_revision_spec(
        self,
        revisions: List[str],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The diff for review will include the changes in (base,
        tip], and the parent diff (if necessary) will include (parent,
        base].

        If a single revision is passed in, this will return the parent of
        that revision for "base" and the passed-in revision for "tip".

        If zero revisions are passed in, this will return revisions
        relevant for the "current change" (changes in the work folder which
        have not yet been checked in).

        Args:
            revisions (list of str):
                A list of revisions as specified by the user.

                Items in the list do not necessarily represent a single
                revision, since the user can use the TFS-native syntax of
                ``r1~r2``. Versions passed in can be any versionspec, such as a
                changeset number, ``L``-prefixed label name, ``W`` (latest
                workspace version), or ``T`` (latest upstream version).

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates ``base`` and ``tip``.

        Raises:
            rbtools.clients.errors.TooManyRevisionsError:
                Too many revisions were specified.

            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revision spec could not be parsed.
        """
        if len(revisions) > 2:
            raise TooManyRevisionsError

        try:
            result = self._run_helper(['parse-revision'] + revisions)
        except Exception as e:
            if isinstance(e, RunProcessError):
                errors = e.result.stderr.read().strip()
            else:
                errors = ''

            if not errors:
                errors = ('Unexpected error while parsing revision spec %r'
                          % (revisions,))

            raise InvalidRevisionSpecError(errors)

        parsed_revisions = result.stdout.readlines()

        return {
            'base': parsed_revisions[0].strip(),
            'tip': parsed_revisions[1].strip(),
        }

    def diff(
        self,
        *,
        client: TFSClient,
        revisions: SCMClientRevisionSpec,
        include_files: List[str],
        exclude_patterns: List[str],
    ) -> SCMClientDiffResult:
        """Return the generated diff.

        Args:
            client (TFSClient):
                The client performing the diff.

            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list):
                A list of file paths to include in the diff.

            exclude_patterns (list):
                A list of file paths to exclude from the diff.

        Returns:
            dict:
            A dictionary of diff results.

            See :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`
            for the format of this dictionary.

        Raises:
            rbtools.clients.errors.SCMError:
                Something failed when creating the diff.
        """
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        result = self._run_helper(['diff', '--', base, tip],
                                  ignore_errors=True,
                                  log_debug_output_on_error=False)

        if result.exit_code in (0, 2):
            if result.exit_code == 2:
                # Magic return code that means success, but there were
                # un-tracked files in the working directory.
                logging.warning('There are added or deleted files which have '
                                'not been added to TFS. These will not be '
                                'included in your review request.')

            return {
                'diff': result.stdout_bytes.read(),
                'parent_diff': None,
                'base_commit_id': None,
            }
        else:
            raise SCMError(result.stderr.read().strip())

    def _run_helper(
        self,
        args: List[str],
        **kwargs,
    ) -> RunProcessResult:
        """Run the rb-tfs binary.

        Args:
            args (list):
                A list of arguments to pass to rb-tfs.

            **kwargs (dict):
                Additional keyword arguments for the
                :py:func:`~rbtools.utils.process.run_process` call.

        Returns:
            rbtools.utils.process.RunProcessResult:
            The result of the command.
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

        return run_process(cmdline, **kwargs)


class TFSClient(BaseSCMClient):
    """A client for Team Foundation Server."""

    scmclient_id = 'tfs'
    name = 'Team Foundation Server'
    server_tool_names = 'Team Foundation Server'

    requires_diff_tool = True

    supports_diff_exclude_patterns = True
    supports_patch_revert = True

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the client.

        Args:
            *args (tuple):
                Positional arguments to pass to the parent class.

            **kwargs (dict):
                Keyword arguments to pass to the parent class.
        """
        super(TFSClient, self).__init__(*args, **kwargs)

        self._tf_wrapper: Optional[BaseTFWrapper] = None

    @property
    def tf_wrapper(self) -> BaseTFWrapper:
        """The wrapper used to communicate with a TF tool.

        Type:
            BaseTFWrapper
        """
        if self._tf_wrapper is None:
            # This will log a deprecation warning if checking dependencies for
            # the first time.
            self.has_dependencies(expect_checked=True)

        return cast(BaseTFWrapper, self._tf_wrapper)

    def check_dependencies(self) -> None:
        """Check whether all dependencies for the client are available.

        There are three different backends that can be used to access the
        underlying TFS repository. We try them in this order:

        * VS2017+ :command:`tf.exe`
        * Our custom rb-tfs wrapper, built on the TFS Java SDK
        * Team Explorer Everywhere's :command:`tf` command

        This checks for each, setting underlying wrappers to communicate with
        whichever tool is found.

        If no tool is found, the raised exception will present the high-level
        possibilities.

        Version Added:
            4.0

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                No suitable dependencies could be found.
        """
        wrapper_kwargs = {
            'config': self.config,
            'options': self.options,
        }

        wrapper = None
        found = False

        for wrapper_cls in (TFExeWrapper, TFHelperWrapper, TEEWrapper):
            wrapper = wrapper_cls(**wrapper_kwargs)

            try:
                wrapper.check_dependencies()

                found = True
                break
            except SCMClientDependencyError:
                # Skip this one. Go to the next.
                continue

        # Regardless of any failures above, we'll want a default wrapper set.
        # We'll use the last one we tried.
        assert wrapper is not None
        self._tf_wrapper = wrapper

        if not found:
            # We'll provide a general version of all the options. The last
            # entry isn't the name of the executable, but should help people
            # figure out what to install.
            raise SCMClientDependencyError(missing_exes=[(
                'VS2017+ tf',
                'Team Explorer Everywhere tf.cmd',
                'Our wrapper (rbt install tfs)',
            )])

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        return self.tf_wrapper.get_local_path()

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        return self.tf_wrapper.get_repository_info()

    def parse_revision_spec(
        self,
        revisions: List[str] = [],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The diff for review will include the changes in (base,
        tip], and the parent diff (if necessary) will include (parent,
        base].

        If a single revision is passed in, this will return the parent of
        that revision for "base" and the passed-in revision for "tip".

        If zero revisions are passed in, this will return revisions
        relevant for the "current change" (changes in the work folder which
        have not yet been checked in).

        Args:
            revisions (list of str, optional):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use the TFS-native syntax of ``r1~r2``. Versions passed in
                can be any versionspec, such as a changeset number,
                ``L``-prefixed label name, ``W`` (latest workspace version), or
                ``T`` (latest upstream version).

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates ``base`` and ``tip``.

        Raises:
            rbtools.clients.errors.TooManyRevisionsError:
                Too many revisions were specified.

            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revision spec could not be parsed.
        """
        return self.tf_wrapper.parse_revision_spec(revisions)

    @deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
    def diff(
        self,
        revisions: SCMClientRevisionSpec,
        *,
        include_files: List[str] = [],
        exclude_patterns: List[str] = [],
        **kwargs,
    ) -> SCMClientDiffResult:
        """Return the generated diff.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

            include_files (list, optional):
                A list of file paths to include in the diff.

            exclude_patterns (list, optional):
                A list of file paths to exclude from the diff.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary of diff results.

            See :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`
            for the format of this dictionary.
        """
        return self.tf_wrapper.diff(
            client=self,
            revisions=revisions,
            include_files=include_files,
            exclude_patterns=exclude_patterns)
