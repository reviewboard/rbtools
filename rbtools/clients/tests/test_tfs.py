"""Unit tests for TFSClient."""

import argparse
import os
import re
from typing import Any, Dict, List

import kgb

from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    SCMError,
                                    TooManyRevisionsError)
from rbtools.clients.tests import SCMClientTestCase
from rbtools.clients.tfs import (BaseTFWrapper,
                                 TEEWrapper,
                                 TFExeWrapper,
                                 TFHelperWrapper,
                                 TFSClient)
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import chdir, make_tempdir
from rbtools.utils.process import run_process_exec


class TFExeWrapperTests(SCMClientTestCase):
    """Unit tests for TFExeWrapper."""

    scmclient_cls = TFSClient

    def make_vc_status_rule(
        self,
        changes: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Return a rule for fetching change history.

        Args:
            changes (list of dict):
                The list of changes and the attribute for each.

        Returns:
            dict:
            The rule to use for kgb.
        """
        payload_parts = [
            b'<?xml version="1.0" encoding="utf-8"?>\n'
            b'\n'
            b'<PendingSets>\n'
            b' <PendingSet>\n'
            b'  <PendingChanges>\n'
        ] + [
            b'   <PendingChange %s/>\n' % ' '.join([
                '%s="%s"' % _pair
                for _pair in _change.items()
            ]).encode('utf-8')
            for _change in changes
        ] + [
            b'  </PendingChanges>\n'
            b' </PendingSet>\n'
            b'</PendingSets>',
        ]

        return {
            'args': (['tf', 'vc', 'status', '/format:xml', '/noprompt'],),
            'op': kgb.SpyOpReturn((
                0,
                b''.join(payload_parts),
                b'',
            )),
        }

    def make_vc_view_rule(
        self,
        filename: str,
        revision: str,
        content: bytes,
    ) -> Dict[str, Any]:
        """Return a rule for fetching contents of a file.

        Args:
            filename (str):
                The filename to fetch.

            revision (str):
                The revision to fetch.

            content (bytes):
                The content to return.

        Returns:
            dict:
            The rule to use for kgb.
        """
        return {
            'args': ([
                'tf', 'vc', 'view', filename, '/version:%s' % revision,
                '/noprompt',
            ],),
            'op': kgb.SpyOpReturn((
                0,
                content,
                b'',
            )),
        }

    def make_diff_rule(
        self,
        *,
        client: TFSClient,
        orig_file: str,
        modified_file: str,
    ) -> Dict[str, Any]:
        """Return a rule for building a diff.

        Args:
            client (rbtools.clients.tfs.TFSClient):
                The client generating the diff.

            orig_file (str):
                The original file to diff against.

            modified_file (str):
                The modified file to diff against.

        Returns:
            dict:
            The rule to use for kgb.
        """
        diff_tool = client.get_diff_tool()
        assert diff_tool is not None

        return {
            'args': (
                diff_tool.make_run_diff_file_cmdline(
                    orig_path=orig_file,
                    modified_path=modified_file),
            ),
        }

    def test_check_dependencies_with_found(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe found"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Version Control Tool, Version 15\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()
        wrapper.check_dependencies()

        self.assertSpyCallCount(run_process_exec, 1)

    def test_check_dependencies_with_found_wrong_version(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe found but
        wrong version
        """
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Version Control Tool, Version 14\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(run_process_exec, 1)
        self.assertEqual(ctx.exception.missing_exes, ['tf'])

    def test_check_dependencies_with_not_found(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe not found"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'op': kgb.SpyOpRaise(FileNotFoundError),
            },
        ]))

        wrapper = TFExeWrapper()

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(run_process_exec, 1)
        self.assertEqual(ctx.exception.missing_exes, ['tf'])

    def test_parse_revision_spec_with_0_revisions(self):
        """Testing TFExeWrapper.parse_revision_spec with 0 revisions"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:W',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 123\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        self.assertEqual(
            wrapper.parse_revision_spec([]),
            {
                'base': '123',
                'tip': '--rbtools-working-copy',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_1_revision(self):
        """Testing TFExeWrapper.parse_revision_spec with 1 revision"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:Lrev',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 123\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev']),
            {
                'base': '122',
                'tip': '123',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_2_revisions(self):
        """Testing TFExeWrapper.parse_revision_spec with 2 revisions"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:Lrev1',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 123\n',
                    b'',
                )),
            },
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:124',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 124\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1', '124']),
            {
                'base': '123',
                'tip': '124',
            })

        self.assertSpyCallCount(run_process_exec, 2)

    def test_parse_revision_spec_with_3_revisions(self):
        """Testing TFExeWrapper.parse_revision_spec with 3 revisions"""
        wrapper = TFExeWrapper()

        with self.assertRaises(TooManyRevisionsError):
            wrapper.parse_revision_spec(['Lrev1', '124', '125'])

    def test_parse_revision_spec_with_r1_tilde_t2(self):
        """Testing TFExeWrapper.parse_revision_spec with r1~r2"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:Lrev1',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 123\n',
                    b'',
                )),
            },
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:Lrev2',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 456\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1~Lrev2']),
            {
                'base': '123',
                'tip': '456',
            })

        self.assertSpyCallCount(run_process_exec, 2)

    def test_parse_revision_spec_with_no_changeset_found(self):
        """Testing TFExeWrapper.parse_revision_spec with no changeset found"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:W',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        message = '"W" does not appear to be a valid versionspec'

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            wrapper.parse_revision_spec([])

    def test_diff_with_add(self):
        """Testing TFExeWrapper.diff with chg=Add"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        tmpfiles = self.precreate_tempfiles(4)

        self._run_diff_test(
            rules=[
                self.make_vc_status_rule(changes=[
                    {
                        'chg': 'Add',
                        'item': 'file1',
                        'local': 'file1',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Add',
                        'item': 'file2',
                        'local': 'file2',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Add',
                        'item': 'ignored-file',
                        'local': 'ignored-file',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Add',
                        'item': 'binary.bin',
                        'local': 'binary.bin',
                        'type': 'file',
                        'enc': '-1',
                    },
                ]),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[0],
                                    modified_file=tmpfiles[1]),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[2],
                                    modified_file=tmpfiles[3]),
            ],
            expected_diff_result={
                'base_commit_id': '123',
                'diff': (
                    b'--- /dev/null\t0\n'
                    b'+++ file1\t(pending)\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+file 1.\n'
                    b'--- /dev/null\t0\n'
                    b'+++ file2\t(pending)\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+file 2.\n'
                    b'--- /dev/null\t0\n'
                    b'+++ binary.bin\t(pending)\n'
                    b'Binary files binary.bin and binary.bin differ\n'
                ),
                'parent_diff': None,
            })

    def test_diff_with_delete(self):
        """Testing TFExeWrapper.diff with chg=Delete"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        tmpfiles = self.precreate_tempfiles(4)

        self._run_diff_test(
            rules=[
                self.make_vc_status_rule(changes=[
                    {
                        'chg': 'Delete',
                        'srcitem': 'file1',
                        'item': 'file1',
                        'local': 'file1',
                        'svrfm': '123',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Delete',
                        'srcitem': 'file2',
                        'item': 'file2',
                        'local': 'file2',
                        'svrfm': '456',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Delete',
                        'srcitem': 'ignored-file',
                        'item': 'ignored-file',
                        'local': 'ignored-file',
                        'svrfm': '999',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Delete',
                        'srcitem': 'binary.bin',
                        'item': 'binary.bin',
                        'local': 'binary.bin',
                        'svrfm': '789',
                        'type': 'file',
                        'enc': '-1',
                    },
                ]),
                self.make_vc_view_rule(
                    filename='file1',
                    revision='123',
                    content=b'old file 1.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[0],
                                    modified_file=tmpfiles[1]),
                self.make_vc_view_rule(
                    filename='file2',
                    revision='456',
                    content=b'old file 2.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[2],
                                    modified_file=tmpfiles[3]),
            ],
            expected_diff_result={
                'base_commit_id': '123',
                'diff': (
                    b'--- file1\t123\n'
                    b'+++ file1\t(deleted)\n'
                    b'@@ -1 +0,0 @@\n'
                    b'-old file 1.\n'
                    b'--- file2\t456\n'
                    b'+++ file2\t(deleted)\n'
                    b'@@ -1 +0,0 @@\n'
                    b'-old file 2.\n'
                    b'--- binary.bin\t789\n'
                    b'+++ binary.bin\t(deleted)\n'
                    b'Binary files binary.bin and binary.bin differ\n'
                ),
                'parent_diff': None,
            })

    def test_diff_with_edit(self):
        """Testing TFExeWrapper.diff with chg=Edit"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        tmpfiles = self.precreate_tempfiles(4)

        self._run_diff_test(
            rules=[
                self.make_vc_status_rule(changes=[
                    {
                        'chg': 'Edit',
                        'srcitem': 'file1',
                        'item': 'file1',
                        'local': 'file1',
                        'svrfm': '123',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Edit',
                        'srcitem': 'file2',
                        'item': 'renamed-file',
                        'local': 'renamed-file',
                        'svrfm': '456',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Edit',
                        'srcitem': 'ignored-file',
                        'item': 'ignored-file',
                        'local': 'ignored-file',
                        'svrfm': '999',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Edit',
                        'srcitem': 'binary.bin',
                        'item': 'binary.bin',
                        'local': 'binary.bin',
                        'svrfm': '789',
                        'type': 'file',
                        'enc': '-1',
                    },
                ]),
                self.make_vc_view_rule(
                    filename='file1',
                    revision='123',
                    content=b'old file 1.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[0],
                                    modified_file=tmpfiles[1]),
                self.make_vc_view_rule(
                    filename='file2',
                    revision='456',
                    content=b'old file 2.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[2],
                                    modified_file=tmpfiles[3]),
            ],
            expected_diff_result={
                'base_commit_id': '123',
                'diff': (
                    b'--- file1\t123\n'
                    b'+++ file1\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file 1.\n'
                    b'+file 1.\n'
                    b'--- file2\t456\n'
                    b'+++ renamed-file\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file 2.\n'
                    b'+renamed file.\n'
                    b'--- binary.bin\t789\n'
                    b'+++ binary.bin\t(pending)\n'
                    b'Binary files binary.bin and binary.bin differ\n'
                ),
                'parent_diff': None,
            })

    def test_diff_with_edit_branch(self):
        """Testing TFExeWrapper.diff with chg='Edit Branch'"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        tmpfiles = self.precreate_tempfiles(4)

        self._run_diff_test(
            rules=[
                self.make_vc_status_rule(changes=[
                    {
                        'chg': 'Edit Branch',
                        'srcitem': 'file1',
                        'item': 'file2',
                        'local': 'file2',
                        'svrfm': '123',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Edit',
                        'srcitem': 'ignored-file',
                        'item': 'ignored-file2',
                        'local': 'ignored-file2',
                        'svrfm': '999',
                        'type': 'file',
                        'enc': '0',
                    },
                    {
                        'chg': 'Edit Branch',
                        'srcitem': 'file2',
                        'item': 'renamed-file',
                        'local': 'renamed-file',
                        'svrfm': '456',
                        'type': 'file',
                        'enc': '0',
                    },
                ]),
                self.make_vc_view_rule(
                    filename='file1',
                    revision='123',
                    content=b'old file.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[0],
                                    modified_file=tmpfiles[1]),
                self.make_vc_view_rule(
                    filename='file2',
                    revision='456',
                    content=b'old file 2.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[2],
                                    modified_file=tmpfiles[3]),
            ],
            expected_diff_result={
                'base_commit_id': '123',
                'diff': (
                    b'Copied from: file1\n'
                    b'--- file1\t123\n'
                    b'+++ file2\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file.\n'
                    b'+file 2.\n'
                    b'Copied from: file2\n'
                    b'--- file2\t456\n'
                    b'+++ renamed-file\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file 2.\n'
                    b'+renamed file.\n'
                ),
                'parent_diff': None,
            })

    def test_diff_with_non_working_copy_tip(self):
        """Testing TFExeWrapper.diff with non-working copy tip"""
        client = self.build_client(allow_dep_checks=False)
        wrapper = TFExeWrapper()

        message = (
            'Posting committed changes is not yet supported for TFS when '
            'using the tf.exe wrapper.'
        )

        with self.assertRaisesMessage(SCMError, message):
            wrapper.diff(
                client=client,
                revisions={
                    'base': '123',
                    'tip': '124',
                },
                include_files=[],
                exclude_patterns=[])

    def _run_diff_test(
        self,
        *,
        rules: List[Dict[str, Any]],
        expected_diff_result: Dict[str, Any],
    ) -> None:
        """Run a test of TFExeWrapper.diff.

        This will set up some files in a directory and attempt to diff
        against them, using the simulated output from :command:`tf.exe`
        commands.

        Args:
            rules (list of dict):
                The list of kgb match rules for
                :py:func:`~rbtools.utils.process.run_process_exec` to run.

            expected_diff_result (dict):
                The expected diff result.

        Raises:
            AssertionError:
                An expectation failed.
        """
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder(rules))

        workdir = make_tempdir()

        with open(os.path.join(workdir, 'file1'), 'w') as fp:
            fp.write('file 1.\n')

        with open(os.path.join(workdir, 'file2'), 'w') as fp:
            fp.write('file 2.\n')

        with open(os.path.join(workdir, 'renamed-file'), 'w') as fp:
            fp.write('renamed file.\n')

        with open(os.path.join(workdir, 'ignored-file'), 'w') as fp:
            fp.write('ignored!\n')

        with open(os.path.join(workdir, 'ignored-file2'), 'w') as fp:
            fp.write('ignored!\n')

        with open(os.path.join(workdir, 'binary.bin'), 'wb') as fp:
            fp.write(b'\x00\x01\x02')

        wrapper = TFExeWrapper()

        with chdir(workdir):
            diff_result = wrapper.diff(
                client=client,
                revisions={
                    'base': '123',
                    'tip': TFExeWrapper.REVISION_WORKING_COPY,
                },
                include_files=[],
                exclude_patterns=['ignored*'])

        self.assertEqual(diff_result, expected_diff_result)
        self.assertSpyCallCount(run_process_exec, len(rules))


class TFHelperWrapperTests(SCMClientTestCase):
    """Unit tests for TFHelperWrapper."""

    scmclient_cls = TFSClient

    def test_check_dependencies_with_found(self):
        """Testing TFHelperWrapper.check_dependencies with java and helper
        found
        """
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['java'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = __file__
        wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)

    def test_check_dependencies_with_helper_path_not_found(self):
        """Testing TFHelperWrapper.check_dependencies with helper path not
        found
        """
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['java'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = __file__ + 'xxx'

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(ctx.exception.missing_exes, [wrapper.helper_path])

    def test_check_dependencies_with_java_not_found(self):
        """Testing TFHelperWrapper.check_dependencies with java not found"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['java'],),
                'op': kgb.SpyOpReturn(False),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = __file__

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(ctx.exception.missing_exes, ['java'])

    def test_check_dependencies_with_not_found(self):
        """Testing TFHelperWrapper.check_dependencies with no dependencies
        found
        """
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['java'],),
                'op': kgb.SpyOpReturn(False),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = __file__ + 'xxx'

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(ctx.exception.missing_exes,
                         [wrapper.helper_path, 'java'])

    def test_parse_revision_spec_with_0_revisions(self):
        """Testing TFHelperWrapper.parse_revision_spec with 0 revisions"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'123\n--rb-tfs-working-copy\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        self.assertEqual(
            wrapper.parse_revision_spec([]),
            {
                'base': '123',
                'tip': '--rb-tfs-working-copy',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_1_revision(self):
        """Testing TFHelperWrapper.parse_revision_spec with 1 revision"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision', 'Lrev',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'122\n123\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev']),
            {
                'base': '122',
                'tip': '123',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_2_revisions(self):
        """Testing TFHelperWrapper.parse_revision_spec with 2 revisions"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision', 'Lrev1', '124',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'123\n124\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1', '124']),
            {
                'base': '123',
                'tip': '124',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_3_revisions(self):
        """Testing TFHelperWrapper.parse_revision_spec with 3 revisions"""
        wrapper = TFHelperWrapper()

        with self.assertRaises(TooManyRevisionsError):
            wrapper.parse_revision_spec(['Lrev1', '124', '125'])

    def test_parse_revision_spec_with_r1_tilde_t2(self):
        """Testing TFHelperWrapper.parse_revision_spec with r1~r2"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision', 'Lrev1~Lrev2',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'123\n456\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1~Lrev2']),
            {
                'base': '123',
                'tip': '456',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_no_changeset_found(self):
        """Testing TFHelperWrapper.parse_revision_spec with no changeset
        found
        """
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision',
                ],),
                'op': kgb.SpyOpReturn((
                    1,
                    b'',
                    b'"W" does not appear to be a valid versionspec\n',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        message = '"W" does not appear to be a valid versionspec'

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            wrapper.parse_revision_spec([])

    def test_parse_revision_spec_with_no_changeset_found_no_error(self):
        """Testing TFHelperWrapper.parse_revision_spec with no changeset
        found and no error result
        """
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision', 'blah',
                ],),
                'op': kgb.SpyOpReturn((
                    1,
                    b'',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        message = "Unexpected error while parsing revision spec ['blah']"

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            wrapper.parse_revision_spec(['blah'])

    def test_diff(self):
        """Testing TFHelperWrapper.diff"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'diff', '--', '123', '--rbtools-working-copy',
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    b'--- file1\t123\n'
                    b'+++ file2\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file.\n'
                    b'+file 2.\n',

                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        diff_result = wrapper.diff(
            client=client,
            revisions={
                'base': '123',
                'tip': TEEWrapper.REVISION_WORKING_COPY,
            },
            include_files=[],
            exclude_patterns=['ignored*'])

        self.assertEqual(
            diff_result,
            {
                'base_commit_id': None,
                'diff': (
                    b'--- file1\t123\n'
                    b'+++ file2\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file.\n'
                    b'+file 2.\n'
                ),
                'parent_diff': None,
            })
        self.assertSpyCallCount(run_process_exec, 1)

    def test_diff_with_error_1(self):
        """Testing TFHelperWrapper.diff with exit code 1"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'diff', '--', '123', '--rbtools-working-copy',
                ],),
                'op': kgb.SpyOpReturn((
                    1,

                    b'',

                    b'Oh no.\n',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        with self.assertRaisesMessage(SCMError, 'Oh no.'):
            wrapper.diff(
                client=client,
                revisions={
                    'base': '123',
                    'tip': TEEWrapper.REVISION_WORKING_COPY,
                },
                include_files=[],
                exclude_patterns=['ignored*'])

        self.assertSpyCallCount(run_process_exec, 1)

    def test_diff_with_error_2(self):
        """Testing TFHelperWrapper.diff with exit code 2"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'diff', '--', '123', '--rbtools-working-copy',
                ],),
                'op': kgb.SpyOpReturn((
                    2,

                    b'--- file1\t123\n'
                    b'+++ file2\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file.\n'
                    b'+file 2.\n',

                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        with self.assertLogs(level='WARNING') as log_ctx:
            diff_result = wrapper.diff(
                client=client,
                revisions={
                    'base': '123',
                    'tip': TEEWrapper.REVISION_WORKING_COPY,
                },
                include_files=[],
                exclude_patterns=['ignored*'])

        self.assertEqual(
            diff_result,
            {
                'base_commit_id': None,
                'diff': (
                    b'--- file1\t123\n'
                    b'+++ file2\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file.\n'
                    b'+file 2.\n'
                ),
                'parent_diff': None,
            })
        self.assertSpyCallCount(run_process_exec, 1)

        self.assertEqual(
            log_ctx.output,
            [
                'WARNING:root:There are added or deleted files which have '
                'not been added to TFS. These will not be included in your '
                'review request.',
            ])


class TEEWrapperTests(SCMClientTestCase):
    """Unit tests for TEEWrapper."""

    scmclient_cls = TFSClient

    def make_status_rule(
        self,
        changes: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Return a rule for fetching change history.

        Args:
            changes (list of dict):
                The list of changes and the attribute for each.

        Returns:
            dict:
            The rule to use for kgb.
        """
        payload_parts = [
            b'<?xml version="1.0" encoding="utf-8"?>\n'
            b'\n'
            b'<root>\n'
            b' <pending-changes>\n'
        ] + [
            b'  <pending-change %s/>\n' % ' '.join([
                '%s="%s"' % _pair
                for _pair in _change.items()
            ]).encode('utf-8')
            for _change in changes
        ] + [
            b' </pending-changes>\n'
            b'</root>',
        ]

        return {
            'args': (['tf', '-noprompt', 'status', '-format:xml'],),
            'op': kgb.SpyOpReturn((
                0,
                b''.join(payload_parts),
                b'',
            )),
        }

    def make_vc_view_rule(
        self,
        filename: str,
        revision: str,
        content: bytes,
    ) -> Dict[str, Any]:
        """Return a rule for fetching contents of a file.

        Args:
            filename (str):
                The filename to fetch.

            revision (str):
                The revision to fetch.

            content (bytes):
                The content to return.

        Returns:
            dict:
            The rule to use for kgb.
        """
        return {
            'args': ([
                'tf', '-noprompt', 'print', '-version:%s' % revision,
                filename,
            ],),
            'op': kgb.SpyOpReturn((
                0,
                content,
                b'',
            )),
        }

    def make_get_source_revision_rule(
        self,
        path: str,
        revision: str,
    ) -> Dict[str, Any]:
        """Return history for a file.

        Args:
            path (str):
                The path to look up.

            revision (str):
                The resulting revision.

        Returns:
            dict:
            The rule to use for kgb.
        """
        return {
            'args': ([
                'tf', '-noprompt', 'history', '-stopafter:1',
                '-recursive', '-format:xml', path,
            ],),
            'op': kgb.SpyOpReturn((
                0,

                # NOTE: We are not sensitive to the root element name,
                #       and at the time of this writing, there is no
                #       public documentation (or local setup) capable
                #       of showing this. <changesets> is used as a
                #       possibility.
                b'<?xml version="1.0" encoding="utf-8"?>\n'
                b'\n'
                b'<changesets>\n'
                b' <changeset id="%s"/>\n'
                b'</changesets>\n'
                % revision.encode('utf-8'),

                b'',
            )),
        }

    def make_diff_rule(
        self,
        *,
        client: TFSClient,
        orig_file: str,
        modified_file: str,
    ) -> Dict[str, Any]:
        """Return a rule for building a diff.

        Args:
            client (rbtools.clients.tfs.TFSClient):
                The client generating the diff.

            orig_file (str):
                The original file to diff against.

            modified_file (str):
                The modified file to diff against.

        Returns:
            dict:
            The rule to use for kgb.
        """
        diff_tool = client.get_diff_tool()
        assert diff_tool is not None

        return {
            'args': (
                diff_tool.make_run_diff_file_cmdline(
                    orig_path=orig_file,
                    modified_path=modified_file),
            ),
        }


    def test_check_dependencies_with_found_on_windows(self):
        """Testing TEEWrapper.check_dependencies with found on Windows"""
        self.spy_on(
            TEEWrapper.get_default_tf_locations,
            op=kgb.SpyOpReturn(TEEWrapper.get_default_tf_locations('windows')))

        self.spy_on(check_install, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['tf.cmd', 'help'],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': ([
                    '%programfiles(x86)%\\Microsoft Visual Studio 12.0\\'
                    'Common7\\IDE\\tf.cmd',
                    'help',
                ],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': ([
                    '%programfiles%\\Microsoft Team Foundation Server 12.0\\'
                    'Tools\\tf.cmd',
                    'help',
                ],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 3)
        self.assertEqual(
            wrapper.tf,
            '%programfiles%\\Microsoft Team Foundation Server 12.0\\'
            'Tools\\tf.cmd')

    def test_check_dependencies_with_found_on_linux(self):
        """Testing TEEWrapper.check_dependencies with found on Linux"""
        self.spy_on(
            TEEWrapper.get_default_tf_locations,
            op=kgb.SpyOpReturn(TEEWrapper.get_default_tf_locations('linux')))

        self.spy_on(check_install, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['tf', 'help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(wrapper.tf, 'tf')

    def test_check_dependencies_with_found_with_custom(self):
        """Testing TEEWrapper.check_dependencies with found using custom
        path
        """
        self.spy_on(
            TEEWrapper.get_default_tf_locations,
            op=kgb.SpyOpReturn(TEEWrapper.get_default_tf_locations('linux')))

        self.spy_on(check_install, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['/path/to/my-tf', 'help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        options = argparse.Namespace()
        options.tf_cmd = '/path/to/my-tf'

        wrapper = TEEWrapper(options=options)
        wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(wrapper.tf, '/path/to/my-tf')

    def test_check_dependencies_with_not_found(self):
        """Testing TEEWrapper.check_dependencies with not found"""
        self.spy_on(
            TEEWrapper.get_default_tf_locations,
            op=kgb.SpyOpReturn(TEEWrapper.get_default_tf_locations('windows')))

        self.spy_on(check_install, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['/path/to/my-tf', 'help'],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': (['tf.cmd', 'help'],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': ([
                    '%programfiles(x86)%\\Microsoft Visual Studio 12.0\\'
                    'Common7\\IDE\\tf.cmd',
                    'help',
                ],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': ([
                    '%programfiles%\\Microsoft Team Foundation Server 12.0\\'
                    'Tools\\tf.cmd',
                    'help',
                ],),
                'op': kgb.SpyOpReturn(False),
            },
        ]))

        options = argparse.Namespace()
        options.tf_cmd = '/path/to/my-tf'

        wrapper = TEEWrapper(options=options)

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 4)
        self.assertEqual(
            ctx.exception.missing_exes,
            [(
                '/path/to/my-tf',
                'tf.cmd',
                ('%programfiles(x86)%\\Microsoft Visual Studio 12.0\\'
                 'Common7\\IDE\\tf.cmd'),
                ('%programfiles%\\Microsoft Team Foundation Server 12.0\\'
                 'Tools\\tf.cmd'),
            )])

    def test_parse_revision_spec_with_0_revisions(self):
        """Testing TEEWrapper.parse_revision_spec with 0 revisions"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="123"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        self.assertEqual(
            wrapper.parse_revision_spec([]),
            {
                'base': '123',
                'tip': '--rbtools-working-copy',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_1_revision(self):
        """Testing TEEWrapper.parse_revision_spec with 1 revision"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:Lrev', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="123"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev']),
            {
                'base': '122',
                'tip': '123',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_2_revisions(self):
        """Testing TEEWrapper.parse_revision_spec with 2 revisions"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:Lrev1', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="123"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:124', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="124"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1', '124']),
            {
                'base': '123',
                'tip': '124',
            })

        self.assertSpyCallCount(run_process_exec, 2)

    def test_parse_revision_spec_with_3_revisions(self):
        """Testing TEEWrapper.parse_revision_spec with 3 revisions"""
        wrapper = TEEWrapper()

        with self.assertRaises(TooManyRevisionsError):
            wrapper.parse_revision_spec(['Lrev1', '124', '125'])

    def test_parse_revision_spec_with_r1_tilde_t2(self):
        """Testing TEEWrapper.parse_revision_spec with r1~r2"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:Lrev1', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="123"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:Lrev2', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="456"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1~Lrev2']),
            {
                'base': '123',
                'tip': '456',
            })

        self.assertSpyCallCount(run_process_exec, 2)

    def test_parse_revision_spec_with_no_changeset_found(self):
        """Testing TEEWrapper.parse_revision_spec with no changeset found"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets/>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        message = '"W" does not appear to be a valid versionspec'

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            wrapper.parse_revision_spec([])

    def test_diff_with_add(self):
        """Testing TEEWrapper.diff with change-type=add"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        tmpfiles = self.precreate_tempfiles(4)

        self._run_diff_test(
            rules=[
                self.make_status_rule(changes=[
                    {
                        'change-type': 'add',
                        'server-item': 'file1',
                        'local-item': 'file1',
                        'file-type': 'file',
                        'version': '0',
                    },
                    {
                        'change-type': 'add',
                        'server-item': 'file2',
                        'local-item': 'file2',
                        'file-type': 'file',
                        'version': '0',
                    },
                    {
                        'change-type': 'add',
                        'server-item': 'ignored-file',
                        'local-item': 'ignored-file',
                        'file-type': 'file',
                        'version': '0',
                    },
                    {
                        'change-type': 'add',
                        'server-item': 'binary.bin',
                        'local-item': 'binary.bin',
                        'file-type': 'binary',
                        'version': '0',
                    },
                ]),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[0],
                                    modified_file=tmpfiles[1]),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[2],
                                    modified_file=tmpfiles[3]),
            ],
            expected_diff_result={
                'base_commit_id': '123',
                'diff': (
                    b'--- /dev/null\t0\n'
                    b'+++ file1\t(pending)\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+file 1.\n'
                    b'--- /dev/null\t0\n'
                    b'+++ file2\t(pending)\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+file 2.\n'
                    b'--- /dev/null\t0\n'
                    b'+++ binary.bin\t(pending)\n'
                    b'Binary files binary.bin and binary.bin differ\n'
                ),
                'parent_diff': None,
            })

    def test_diff_with_delete(self):
        """Testing TEEWrapper.diff with change-type=delete"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        tmpfiles = self.precreate_tempfiles(4)

        self._run_diff_test(
            rules=[
                self.make_status_rule(changes=[
                    {
                        'change-type': 'delete',
                        'server-item': 'file1',
                        'source-item': 'file1',
                        'local-item': 'file1',
                        'version': '123',
                        'file-type': 'file',
                    },
                    {
                        'change-type': 'delete',
                        'server-item': 'file2',
                        'source-item': 'file2',
                        'local-item': 'file2',
                        'version': '456',
                        'file-type': 'file',
                    },
                    {
                        'change-type': 'delete',
                        'server-item': 'ignored-file',
                        'source-item': 'ignored-file',
                        'local-item': 'ignored-file',
                        'version': '999',
                        'file-type': 'file',
                    },
                    {
                        'change-type': 'delete',
                        'server-item': 'binary.bin',
                        'source-item': 'binary.bin',
                        'local-item': 'binary.bin',
                        'version': '789',
                        'file-type': 'binary',
                    },
                ]),
                self.make_vc_view_rule(
                    filename='file1',
                    revision='123',
                    content=b'old file 1.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[0],
                                    modified_file=tmpfiles[1]),
                self.make_vc_view_rule(
                    filename='file2',
                    revision='456',
                    content=b'old file 2.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[2],
                                    modified_file=tmpfiles[3]),
            ],
            expected_diff_result={
                'base_commit_id': '123',
                'diff': (
                    b'--- file1\t123\n'
                    b'+++ file1\t(deleted)\n'
                    b'@@ -1 +0,0 @@\n'
                    b'-old file 1.\n'
                    b'--- file2\t456\n'
                    b'+++ file2\t(deleted)\n'
                    b'@@ -1 +0,0 @@\n'
                    b'-old file 2.\n'
                    b'--- binary.bin\t789\n'
                    b'+++ binary.bin\t(deleted)\n'
                    b'Binary files binary.bin and binary.bin differ\n'
                ),
                'parent_diff': None,
            })

    def test_diff_with_edit(self):
        """Testing TEEWrapper.diff with change-type=edit"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        tmpfiles = self.precreate_tempfiles(4)

        self._run_diff_test(
            rules=[
                self.make_status_rule(changes=[
                    {
                        'change-type': 'edit',
                        'server-item': 'file1',
                        'source-item': 'file1',
                        'local-item': 'file1',
                        'version': '123',
                        'file-type': 'file',
                    },
                    {
                        'change-type': 'edit, rename',
                        'server-item': 'renamed-file',
                        'source-item': 'file2',
                        'local-item': 'renamed-file',
                        'version': '456',
                        'file-type': 'file',
                    },
                    {
                        'change-type': 'edit',
                        'server-item': 'ignored-file',
                        'source-item': 'ignored-file',
                        'local-item': 'ignored-file',
                        'version': '999',
                        'file-type': 'file',
                    },
                    {
                        'change-type': 'edit',
                        'server-item': 'binary.bin',
                        'source-item': 'binary.bin',
                        'local-item': 'binary.bin',
                        'version': '789',
                        'file-type': 'binary',
                    },
                ]),
                self.make_vc_view_rule(
                    filename='file1',
                    revision='123',
                    content=b'old file 1.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[0],
                                    modified_file=tmpfiles[1]),
                self.make_vc_view_rule(
                    filename='file2',
                    revision='456',
                    content=b'old file 2.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[2],
                                    modified_file=tmpfiles[3]),
            ],
            expected_diff_result={
                'base_commit_id': '123',
                'diff': (
                    b'--- file1\t123\n'
                    b'+++ file1\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file 1.\n'
                    b'+file 1.\n'
                    b'--- file2\t456\n'
                    b'+++ renamed-file\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file 2.\n'
                    b'+renamed file.\n'
                    b'--- binary.bin\t789\n'
                    b'+++ binary.bin\t(pending)\n'
                    b'Binary files binary.bin and binary.bin differ\n'
                ),
                'parent_diff': None,
            })

    def test_diff_with_edit_branch(self):
        """Testing TEEWrapper.diff with change-type='edit, branch'"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        tmpfiles = self.precreate_tempfiles(4)

        self._run_diff_test(
            rules=[
                self.make_status_rule(changes=[
                    {
                        'change-type': 'edit, branch',
                        'source-item': 'file1',
                        'server-item': 'file2',
                        'local-item': 'file2',
                        'version': '123',
                        'file-type': 'file',
                    },
                    {
                        'change-type': 'edit, branch',
                        'source-item': 'ignored-file',
                        'server-item': 'ignored-file2',
                        'local-item': 'ignored-file2',
                        'version': '999',
                        'file-type': 'file',
                    },
                    {
                        'change-type': 'edit, branch',
                        'source-item': 'file2',
                        'server-item': 'renamed-file',
                        'local-item': 'renamed-file',
                        'version': '456',
                        'file-type': 'file',
                    },
                ]),
                self.make_get_source_revision_rule(
                    path='file1',
                    revision='123'),
                self.make_vc_view_rule(
                    filename='file1',
                    revision='123',
                    content=b'old file.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[0],
                                    modified_file=tmpfiles[1]),
                self.make_get_source_revision_rule(
                    path='file2',
                    revision='456'),
                self.make_vc_view_rule(
                    filename='file2',
                    revision='456',
                    content=b'old file 2.\n'),
                self.make_diff_rule(client=client,
                                    orig_file=tmpfiles[2],
                                    modified_file=tmpfiles[3]),
            ],
            expected_diff_result={
                'base_commit_id': '123',
                'diff': (
                    b'Copied from: file1\n'
                    b'--- file1\t123\n'
                    b'+++ file2\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file.\n'
                    b'+file 2.\n'
                    b'Copied from: file2\n'
                    b'--- file2\t456\n'
                    b'+++ renamed-file\t(pending)\n'
                    b'@@ -1 +1 @@\n'
                    b'-old file 2.\n'
                    b'+renamed file.\n'
                ),
                'parent_diff': None,
            })

    def test_diff_with_non_working_copy_tip(self):
        """Testing TEEWrapper.diff with non-working copy tip"""
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)
        wrapper = TEEWrapper()

        message = (
            'Posting committed changes is not yet supported for TFS when '
            'using the Team Explorer Everywhere wrapper.'
        )

        with self.assertRaisesMessage(SCMError, message):
            wrapper.diff(
                client=client,
                revisions={
                    'base': '123',
                    'tip': '124',
                },
                include_files=[],
                exclude_patterns=[])

    def _run_diff_test(
        self,
        *,
        rules: List[Dict[str, Any]],
        expected_diff_result: Dict[str, Any],
    ) -> None:
        """Run a test of TEEWrapper.diff.

        This will set up some files in a directory and attempt to diff
        against them, using the simulated output from :command:`tf.exe`
        commands.

        Args:
            rules (list of dict):
                The list of kgb match rules for
                :py:func:`~rbtools.utils.process.run_process_exec` to run.

            expected_diff_result (dict):
                The expected diff result.

        Raises:
            AssertionError:
                An expectation failed.
        """
        client = self.build_client(needs_diff=True,
                                   allow_dep_checks=False)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder(rules))

        workdir = make_tempdir()

        with open(os.path.join(workdir, 'file1'), 'w') as fp:
            fp.write('file 1.\n')

        with open(os.path.join(workdir, 'file2'), 'w') as fp:
            fp.write('file 2.\n')

        with open(os.path.join(workdir, 'renamed-file'), 'w') as fp:
            fp.write('renamed file.\n')

        with open(os.path.join(workdir, 'ignored-file'), 'w') as fp:
            fp.write('ignored!\n')

        with open(os.path.join(workdir, 'ignored-file2'), 'w') as fp:
            fp.write('ignored!\n')

        with open(os.path.join(workdir, 'binary.bin'), 'wb') as fp:
            fp.write(b'\x00\x01\x02')

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        with chdir(workdir):
            diff_result = wrapper.diff(
                client=client,
                revisions={
                    'base': '123',
                    'tip': TEEWrapper.REVISION_WORKING_COPY,
                },
                include_files=[],
                exclude_patterns=['ignored*'])

        self.assertEqual(diff_result, expected_diff_result)
        self.assertSpyCallCount(run_process_exec, len(rules))


class TFSClientTests(SCMClientTestCase):
    """Unit tests for TFSClient."""

    scmclient_cls = TFSClient

    def test_check_dependencies_with_tf_exe_found(self):
        """Testing TFSClient.check_dependencies with tf.exe found"""
        self.spy_on(TFExeWrapper.check_dependencies,
                    owner=TFExeWrapper,
                    op=kgb.SpyOpReturn(None))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertIsInstance(client.tf_wrapper, TFExeWrapper)

    def test_check_dependencies_with_tf_helper_found(self):
        """Testing TFSClient.check_dependencies with TF helper found"""
        self.spy_on(TFExeWrapper.check_dependencies,
                    owner=TFExeWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TFHelperWrapper.check_dependencies,
                    owner=TFHelperWrapper,
                    op=kgb.SpyOpReturn(None))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertIsInstance(client.tf_wrapper, TFHelperWrapper)

    def test_check_dependencies_with_tee_found(self):
        """Testing TFSClient.check_dependencies with TEE found"""
        self.spy_on(TFExeWrapper.check_dependencies,
                    owner=TFExeWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TFHelperWrapper.check_dependencies,
                    owner=TFHelperWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TEEWrapper.check_dependencies,
                    owner=TEEWrapper,
                    op=kgb.SpyOpReturn(None))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertIsInstance(client.tf_wrapper, TEEWrapper)

    def test_check_dependencies_with_not_found(self):
        """Testing TFSClient.check_dependencies with not found"""
        self.spy_on(TFExeWrapper.check_dependencies,
                    owner=TFExeWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TFHelperWrapper.check_dependencies,
                    owner=TFHelperWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TEEWrapper.check_dependencies,
                    owner=TEEWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))

        client = self.build_client(setup=False)

        with self.assertRaises(SCMClientDependencyError) as ctx:
            client.check_dependencies()

        self.assertEqual(
            ctx.exception.missing_exes,
            [(
                'VS2017+ tf',
                'Team Explorer Everywhere tf.cmd',
                'Our wrapper (rbt install tfs)',
            )])

        # This should be the fallback.
        self.assertIsInstance(client.tf_wrapper, TEEWrapper)

    def test_tf_wrapper_with_deps_missing(self):
        """Testing TFSClient.get_local_path with dependencies missing"""
        self.spy_on(BaseTFWrapper.check_dependencies,
                    owner=BaseTFWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_local_path(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        self.assertIsInstance(client.tf_wrapper, TEEWrapper)
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

    def test_tf_wrapper_with_deps_not_checked(self):
        """Testing TFSClient.get_local_path with dependencies not checked"""
        self.spy_on(BaseTFWrapper.check_dependencies,
                    owner=BaseTFWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either TFSClient.setup() or TFSClient.has_dependencies() must '
            'be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
            client.tf_wrapper
