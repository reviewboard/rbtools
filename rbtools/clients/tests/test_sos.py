"""Unit tests for rbtools.clients.sos.

Version Added:
    3.1
"""

import os
import re
from typing import Any, Dict, List

import kgb

from rbtools.api.resource import ReviewRequestResource
from rbtools.api.tests.base import MockTransport
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    TooManyRevisionsError)
from rbtools.clients.tests import SCMClientTestCase
from rbtools.clients.sos import SOSClient
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_gnu_diff, check_install
from rbtools.utils.filesystem import make_tempdir
from rbtools.utils.process import run_process_exec


class BaseSOSTestCase(SCMClientTestCase):
    """Base class for SOS unit tests.

    This provides an initial SOS client setup, as well as convenience
    functions for generating spy matching rules for standard SOS operations.

    Version Added:
        3.1
    """

    scmclient_cls = SOSClient

    TEST_WORKAREA_ID = '1234567890'

    def setUp(self):
        super(BaseSOSTestCase, self).setUp()

        self.workarea_dir = make_tempdir()

    @property
    def rule_query_wa_root(self) -> Dict[str, Any]:
        """A spy match rule for querying the workarea root.

        Type:
            dict
        """
        return {
            'args': (['soscmd', 'query', 'wa_root'],),
            'op': kgb.SpyOpReturn((
                0,
                b'%s\n' % self.workarea_dir.encode('utf-8'),
                b'',
            )),
        }

    @property
    def rule_query_project(self):
        """A spy match rule for querying the current SOS project.

        Type:
            dict
        """
        return {
            'args': (['soscmd', 'query', 'project'],),
            'kwargs': {
                'cwd': os.getcwd(),
            },
            'op': kgb.SpyOpReturn((
                0,
                b'test-project\n',
                b'',
            )),
        }

    @property
    def rule_query_server(self) -> Dict[str, Any]:
        """A spy match rule for querying the current SOS server.

        Type:
            dict
        """
        return {
            'args': (['soscmd', 'query', 'server'],),
            'kwargs': {
                'cwd': os.getcwd(),
            },
            'op': kgb.SpyOpReturn((
                0,
                b'test-server\n',
                b'',
            )),
        }

    @property
    def rule_query_rso(self):
        """A spy match rule for querying the current SOS RSO.

        Type:
            dict
        """
        return {
            'args': (['soscmd', 'query', 'rso'],),
            'op': kgb.SpyOpReturn((
                0,
                b'main, test\n',
                b'',
            )),
        }

    def make_rule_stash_selection(
        self,
        result: List[bytes],
    ) -> Dict[str, Any]:
        """Return a spy match rule for stashing the current selection.

        Args:
            result (list of bytes):
                The list of selected file paths to simulate being stashed.
                These will be written to the stash temp file.

        Returns:
            dict:
            The match rule.
        """
        return {
            'args': (['soscmd', 'status', '-f%P'],),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'op': kgb.SpyOpReturn((
                0,
                b''.join(
                    b'%s\n' % _item
                    for _item in result
                ),
                b'',
            )),
        }

    def make_rule_restore_selection(
        self,
        filename: str,
    ) -> Dict[str, Any]:
        """Return a spy match rule for restoring the stashed selection.

        Args:
            filename (unicode):
                The expected path to the stash temp file.

        Returns:
            dict:
            The match rule.
        """
        return {
            'args': ([
                'soscmd', 'select', '-sall', '-sNr', '-sfile%s' % filename,
            ],),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'op': kgb.SpyOpReturn((
                0,
                b'',
                b'',
            )),
        }

    def make_rule_list_changelist(
        self,
        name: str,
        results: List[str],
    ) -> Dict[str, Any]:
        """A spy match rule for listing files in a SOS changelist.

        Args:
            name (str):
                The expected name of the changelist.

            results (list of str):
                A list of newline-terminated lines of simulated results from
                the changelist.

        Returns:
            dict:
            The match rule.
        """
        return {
            'args': (['soscmd', 'add', '-s', '-c', name],),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'op': kgb.SpyOpReturn((
                0,
                ''.join(results).encode('utf-8'),
                b'',
            )),
        }

    def make_rule_status(
        self,
        results: List[bytes],
        selection: List[str] = ['-scm'],
    ) -> Dict[str, Any]:
        """A spy match rule for fetching the current selection status.

        Args:
            results (list of bytes):
                Lines of simulated results from the status command.

            selection (list of unicode):
                The expected selection flags passed to the command.

        Returns:
            dict:
            The match rule.
        """
        return {
            'args': (
                (['soscmd', 'status', r'-f%T\t%S\t%C\t%P', '-Nhdr'] +
                 selection),
            ),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'op': kgb.SpyOpReturn((
                0,
                b''.join(
                    b'%s\n' % _item
                    for _item in results
                ),
                b'',
            )),
        }

    def make_rule_exportrev(
        self,
        sos_path: str,
        out_filename: str,
        content: bytes,
    ) -> Dict[str, Any]:
        """A spy match rule for exporting a file.

        This will write the provided contents to the path once the spy
        operation is called.

        Args:
            sos_path (unicode):
                The expected SOS path/revision to export.

            out_filename (unicode):
                The expected path the file will be written to.

            content (bytes):
                The simulated content to write to the file.

        Returns:
            dict:
            The match rule.
        """
        def _on_run_process(*args, **kwargs):
            self.write_workarea_file(out_filename, content)

            return 0, b'', b''

        return {
            'args': ([
                'soscmd', 'exportrev', sos_path, '-out%s' % out_filename,
            ],),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'call_fake': _on_run_process,
        }

    def make_rule_delete(
        self,
        sos_path: str,
    ) -> Dict[str, Any]:
        """A spy match rule for deleting a file.

        This will perform a standard filesystem delete once the spy operation
        is called.

        Args:
            sos_path (unicode):
                The expected SOS path to delete.

        Returns:
            dict:
            The match rule.
        """
        def _on_run_process(*args, **kwargs):
            os.unlink(os.path.join(
                self.workarea_dir,
                os.path.join(self.workarea_dir, sos_path)))

            return 0, b'', b''

        return {
            'args': (['soscmd', 'delete', sos_path],),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'call_fake': _on_run_process,
        }

    def make_rule_undelete(
        self,
        dirname: str,
        filename: str,
        content: bytes = b'old file content\n',
    ) -> Dict[str, Any]:
        """A spy match rule for undeleting a file.

        This will simulate the undelete by writing the specified file
        contents once the spy operation is called.

        Args:
            dirname (unicode):
                The expected path containing the file.

            filename (unicode):
                The expected filename within the directory.

            content (bytes, optional):
                The simulated contents of the old file, once undeleted.

        Returns:
            dict:
            The match rule.
        """
        def _on_run_process(*args, **kwargs):
            self.write_workarea_file(
                os.path.join(dirname, filename),
                content=content)

            return 0, b'', b''

        return {
            'args': (['soscmd', 'undelete', dirname, filename],),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'call_fake': _on_run_process,
        }

    def make_rule_nobjstatus(
        self,
        sos_paths: List[str],
        flags: List[str],
        results: List[str],
    ) -> Dict[str, Any]:
        """A spy match rule for fetching attributes for one or more files.

        Args:
            sos_paths (list of str):
                The expected list of file paths.

            flags (list of str):
                The expected list of attribute matcher flags.

            results (list of str):
                The simulated list of results from the command.

        Returns:
            dict:
            The match rule.
        """
        return {
            'args': (['soscmd', 'nobjstatus', '-ucl'] + flags + sos_paths,),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'op': kgb.SpyOpReturn((
                0,
                ''.join(
                    '%s\n' % _item
                    for _item in results
                ).encode('utf-8'),
                b'',
            )),
        }

    def make_rule_diff(
        self,
        client: SOSClient,
        old_filename: str,
        new_filename: str,
    ) -> Dict[str, Any]:
        """A spy match rule for diffing two files.

        This will perform an actual diff between the two files. The paths
        must exist at the time the spy operation is called.

        Args:
            client (rbtools.clients.sos.SOSClient):
                The SOS client being used for the test.

            old_filename (unicode):
                The old file to diff against, relative to the workarea.

            new_filename (unicode):
                The new file to diff against, relative to the workarea.

        Returns:
            dict:
            The match rule.
        """
        diff_tool = client.get_diff_tool()
        assert diff_tool is not None

        cmdline = diff_tool.make_run_diff_file_cmdline(
            orig_path=old_filename,
            modified_path=os.path.join(self.workarea_dir, new_filename))

        return {
            'args': (cmdline,),
        }

    def make_rule_diff_tree(
        self,
        sos_path: str,
        lines: List[str],
        dir_revision: str = '1',
    ) -> Dict[str, Any]:
        """A spy match rule for diffing pending file operations on a directory.

        Args:
            sos_path (unicode):
                The expected path to the directory to diff.

            lines (list of unicode):
                The simulated newline-terminated lines of results from the
                SOS diff operation.

            dir_revision (unicode, optional):
                The simulated directory revision.

        Returns:
            dict:
            The match rule.
        """
        # This won't actually be a real edit script diff, but it covers the
        # bare minimum for what SOSClient needs (the "<" and ">" lines).
        sep = '%s\n' % ('=' * 80)

        output = [
            "** The differences for '%s' have been written to file "
            "'./diff.out'.\n" % sos_path,
            sep,
            'Reference:     %s\n' % sos_path,
            'Compare:       %s\n' % sos_path,
            '< Revision:    %s\n' % dir_revision,
            '> Revision:    %s [In workarea]\n' % dir_revision,
            'Generated at:  2021/08/20 03:25:25\n',
            sep,
            '2a3\n',
        ] + lines + [
            sep,
        ]

        return {
            'args': (['soscmd', 'diff', sos_path],),
            'kwargs': {
                'cwd': self.workarea_dir,
            },
            'op': kgb.SpyOpReturn((
                0,
                ''.join(output).encode('utf-8'),
                b'',
            )),
        }

    def build_client(self, **kwargs):
        """Build a client for testing.

        Version Added:
            4.0

        Args:
            **kwargs (dict, optional):
                Additional keyword arguments to pass to the parent method.

        Returns:
            rbtools.clients.sos.SOClient:
            The client instance.
        """
        client = super(BaseSOSTestCase, self).build_client(**kwargs)
        client._cache['sos_version'] = (7, 20)
        client._cache['waid'] = self.TEST_WORKAREA_ID

        return client

    def write_workarea_file(
        self,
        out_filename: str,
        content: bytes,
    ) -> None:
        """Write a file to the workarea.

        This will create any paths as necessary.

        Args:
            out_filename (unicode):
                The file path to write to.

            content (bytes):
                The file content to write.
        """
        full_path = os.path.join(self.workarea_dir, out_filename)
        basedir = os.path.dirname(full_path)

        if not os.path.exists(basedir):
            os.makedirs(basedir, 0o755)

        with open(full_path, 'wb') as fp:
            fp.write(content)


class SOSClientTests(BaseSOSTestCase):
    """Unit tests for rbtools.clients.sos.SOSClient."""

    def setUp(self):
        super().setUp()

        # Our unit tests simulate results for soscmd, so we don't actually
        # need it installed. Instead, fake that it's installed so tests
        # aren't skipped.
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['soscmd', 'version'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

    def test_check_dependencies_with_found(self):
        """Testing SOSClient.check_dependencies with soscmd found"""
        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['soscmd', 'version'])

    def test_check_dependencies_with_missing(self):
        """Testing SOSClient.check_dependencies with dependencies
        missing
        """
        check_install.unspy()
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools ('soscmd') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['soscmd', 'version'])

    def test_get_local_path(self):
        """Testing SOSClient.get_local_path"""
        client = self.build_client()
        del client._cache['sos_version']

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
        ]))

        self.assertEqual(client.get_local_path(), self.workarea_dir)

    def test_get_local_path_with_deps_missing(self):
        """Testing SOSClient.get_local_path with dependencies missing"""
        check_install.unspy()
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_local_path(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            local_path = client.get_local_path()

        self.assertIsNone(local_path)

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "soscmd version"; skipping SOS')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['soscmd', 'version'])

    def test_get_local_path_with_deps_not_checked(self):
        """Testing MercurialClient.get_local_path with dependencies not
        checked
        """
        # A False value is used just to ensure get_local_path() bails early,
        # and to minimize side-effects.
        check_install.unspy()
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either SOSClient.setup() or SOSClient.has_dependencies() must '
            'be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_local_path()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "soscmd version"; skipping SOS')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['soscmd', 'version'])

    def test_get_repository_info(self):
        """Testing SOSClient.get_repository_info"""
        client = self.build_client()
        del client._cache['sos_version']

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.rule_query_project,
            self.rule_query_server,
        ]))
        self.spy_on(check_gnu_diff, call_original=False)

        repo_info = client.get_repository_info()
        self.assertEqual(repo_info.path, 'SOS:test-server:test-project')
        self.assertEqual(repo_info.local_path, self.workarea_dir)

    def test_parse_revision_spec_with_0_args(self):
        """Testing SOSClient.parse_revision_spec with 0 args"""
        client = self.build_client()

        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': None,
                'extra': {
                    'sos_selection': ['-scm'],
                    'has_explicit_selection': False,
                },
                'tip': None,
            })

    def test_parse_revision_spec_with_1_arg_select(self):
        """Testing SOSClient.parse_revision_spec with select:* argument"""
        client = self.build_client()

        self.assertEqual(
            client.parse_revision_spec(['select:-scm -sor -sunm']),
            {
                'base': None,
                'extra': {
                    'sos_selection': ['-scm', '-sor', '-sunm'],
                    'has_explicit_selection': True,
                },
                'tip': None,
            })

    def test_parse_revision_spec_with_1_arg_changelist_supported(self):
        """Testing SOSClient.parse_revision_spec with 1 argument (changelist)
        and changelists supported
        """
        client = self.build_client()

        self.assertEqual(
            client.parse_revision_spec(['my_changelist']),
            {
                'base': None,
                'extra': {
                    'sos_changelist': 'my_changelist',
                },
                'tip': None,
            })

    def test_parse_revision_spec_with_1_arg_changelist_not_supported(self):
        """Testing SOSClient.parse_revision_spec with 1 argument (changelist)
        and changelists not supported
        """
        message = (
            'SOS requires a revision argument to be a selection in the form '
            'of: "select:<selection>". For example: select:-scm'
        )

        client = self.build_client()
        client._cache['supports_changelists'] = False

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            client.parse_revision_spec(['123'])

    def test_parse_revision_spec_with_multiple_args(self):
        """Testing SOSClient.parse_revision_spec with multiple arguments"""
        client = self.build_client()

        with self.assertRaises(TooManyRevisionsError):
            client.parse_revision_spec(['123', '456'])

    def test_get_tree_matches_review_request_with_match(self):
        """Testing SOSClient.get_tree_matches_review_request with match"""
        review_request = ReviewRequestResource(
            transport=MockTransport(),
            payload={
                'id': 123,
                'extra_data': {
                    'sos_changelist': 'my_changelist',
                    'sos_project': 'my_project',
                    'sos_server': 'my_server',
                    'sos_workarea': self.TEST_WORKAREA_ID,
                },
            },
            url='https://reviews.example.com/api/review-requests/123/')

        client = self.build_client()
        client._cache['project'] = 'my_project'
        client._cache['server'] = 'my_server'

        self.assertTrue(client.get_tree_matches_review_request(
            review_request=review_request,
            revisions={
                'base': None,
                'extra': {
                    'sos_changelist': 'my_changelist',
                },
                'tip': None,
            }))

    def test_get_tree_matches_review_request_without_match(self):
        """Testing SOSClient.get_tree_matches_review_request without match"""
        review_request = ReviewRequestResource(
            transport=MockTransport(),
            payload={
                'id': 123,
                'extra_data': {
                    'sos_changelist': 'my_changelist',
                    'sos_project': 'other_project',
                    'sos_server': 'my_server',
                    'sos_workarea': self.TEST_WORKAREA_ID,
                },
            },
            url='https://reviews.example.com/api/review-requests/123/')

        client = self.build_client()
        client._cache['project'] = 'my_project'
        client._cache['server'] = 'my_server'

        self.assertFalse(client.get_tree_matches_review_request(
            review_request=review_request,
            revisions={
                'base': None,
                'extra': {
                    'sos_changelist': 'my_changelist',
                },
                'tip': None,
            }))

    def test_get_tree_matches_review_request_without_sos(self):
        """Testing SOSClient.get_tree_matches_review_request without SOS
        state
        """
        review_request = ReviewRequestResource(
            transport=MockTransport(),
            payload={
                'id': 123,
                'extra_data': {},
            },
            url='https://reviews.example.com/api/review-requests/123/')

        client = self.build_client()
        client._cache['project'] = 'my_project'
        client._cache['server'] = 'my_server'

        self.assertFalse(client.get_tree_matches_review_request(
            review_request=review_request,
            revisions={
                'base': None,
                'extra': {
                    'sos_changelist': 'my_changelist',
                },
                'tip': None,
            }))

    def test_diff_with_changelist(self):
        """Testing SOSClient.diff with changelist"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(4)

        self.write_workarea_file('README', b'new line\n')
        self.write_workarea_file(os.path.join('src', 'main.c'),
                                 b'new content\n')
        self.write_workarea_file('newfile', b'new file!\n')
        self.write_workarea_file(os.path.join('doc', 'index.md'),
                                 b'# new header line\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_list_changelist(
                name='my_changelist',
                results=[
                    'Modifying ./README\n',
                    'Modifying ./src/main.c\n',
                    'Adding ./newfile\n',
                    'Deleting ./delfile\n',
                ]),
            self.make_rule_status(
                [
                    b'F\tO\tM\t./README',
                    b'F\tO\tM\t./src/main.c',
                    b'F\t-\t-\t./ignore-me',
                    b'F\t?\t?\t./newfile',
                    b'F\t!\t-\t./delfile',
                ],
                selection=['-sor', '-scm', '-sunm', '-sne']),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './README',
                    './src/main.c',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './README',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '1',
                    '5',
                    '!Record!',
                    './src/main.c',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '3',
                    'RevId',
                    '2',
                    '26',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./README/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old line\n'),
            self.make_rule_diff(client, tmpfiles[1], 'README'),
            self.make_rule_diff(client, tmpfiles[2], 'newfile'),
            self.make_rule_exportrev(sos_path='./src/main.c/#/3',
                                     out_filename=tmpfiles[3],
                                     content=b'old content\n'),
            self.make_rule_diff(client, tmpfiles[3],
                                os.path.join('src', 'main.c')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_changelist': 'my_changelist',
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=354\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "changelist": "my_changelist",\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=258\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 5\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=54, line_endings=unix\n'
            b'--- README\n'
            b'+++ README\n'
            b'@@ -1 +1 @@\n'
            b'-old line\n'
            b'+new line\n'
            b'#..file:\n'
            b'#...meta: format=json, length=144\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "newfile",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=51, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ newfile\n'
            b'@@ -0,0 +1 @@\n'
            b'+new file!\n'
            b'#..file:\n'
            b'#...meta: format=json, length=263\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "src/main.c",\n'
            b'    "revision": {\n'
            b'        "old": "3"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 26\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=68, line_endings=unix\n'
            b'--- src/main.c\n'
            b'+++ src/main.c\n'
            b'@@ -1 +1 @@\n'
            b'-old content\n'
            b'+new content\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_changelist': 'my_changelist',
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_changelist_added_files(self):
        """Testing SOSClient.diff with changelist and added files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(3)

        self.write_workarea_file('newfile1', b'new file!\n')
        self.write_workarea_file(os.path.join('src', 'newfile2'),
                                 b'another new file!\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_list_changelist(
                name='my_changelist',
                results=[
                    'Adding ./newfile1\n',
                    'Adding ./src/newfile2\n',
                ]),
            self.make_rule_status(
                [
                    b'F\t?\t?\t./newfile1',
                    b'F\t?\t?\t./src/newfile2',
                ],
                selection=['-sor', '-scm', '-sunm', '-sne']),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_diff(client, tmpfiles[1], 'newfile1'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('src', 'newfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_changelist': 'my_changelist',
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=354\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "changelist": "my_changelist",\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 0,\n'
            b'        "files": 2,\n'
            b'        "insertions": 2,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "files": 2,\n'
            b'        "insertions": 2,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=145\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "newfile1",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=52, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ newfile1\n'
            b'@@ -0,0 +1 @@\n'
            b'+new file!\n'
            b'#..file:\n'
            b'#...meta: format=json, length=149\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "src/newfile2",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=64, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ src/newfile2\n'
            b'@@ -0,0 +1 @@\n'
            b'+another new file!\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_changelist': 'my_changelist',
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_changelist_deleted_files(self):
        """Testing SOSClient.diff with changelist and deleted files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(3)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_list_changelist(
                name='my_changelist',
                results=[
                    'Deleting ./oldfile1\n',
                    'Deleting ./src/oldfile2\n',
                ]),
            self.make_rule_status(
                [
                    b'F\tW\t!\t./oldfile1',
                    b'F\tW\t!\t./src/oldfile2',
                ],
                selection=['-sor', '-scm', '-sunm', '-sne']),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './oldfile1',
                    './src/oldfile2',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './oldfile1',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '1',
                    '5',
                    '!Record!',
                    './src/oldfile2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '3',
                    'RevId',
                    '2',
                    '26',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./oldfile1/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old line\n'),
            self.make_rule_diff(client, tmpfiles[1], 'oldfile1'),
            self.make_rule_exportrev(sos_path='./src/oldfile2/#/3',
                                     out_filename=tmpfiles[2],
                                     content=b'old line\n'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('src', 'oldfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_changelist': 'my_changelist',
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=354\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "changelist": "my_changelist",\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 2,\n'
            b'        "files": 2,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 2,\n'
            b'        "files": 2,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=260\n'
            b'{\n'
            b'    "op": "delete",\n'
            b'    "path": "oldfile1",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 5\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=51, line_endings=unix\n'
            b'--- oldfile1\n'
            b'+++ /dev/null\n'
            b'@@ -1 +0,0 @@\n'
            b'-old line\n'
            b'#..file:\n'
            b'#...meta: format=json, length=265\n'
            b'{\n'
            b'    "op": "delete",\n'
            b'    "path": "src/oldfile2",\n'
            b'    "revision": {\n'
            b'        "old": "3"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 26\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=55, line_endings=unix\n'
            b'--- src/oldfile2\n'
            b'+++ /dev/null\n'
            b'@@ -1 +0,0 @@\n'
            b'-old line\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_changelist': 'my_changelist',
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_changelist_and_renamed_files_soscmd_rename(self):
        """Testing SOSClient.diff with changelist and renamed files using
        `soscmd rename`
        """
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(4)

        self.write_workarea_file('newfile1', b'new content 1\n')
        self.write_workarea_file('newfile2', b'unchanged content\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_list_changelist(
                name='my_changelist',
                results=[
                    'Adding ./newfile1\n',
                    'Adding ./newfile2\n',
                    'Deleting ./oldfile1\n',
                    'Deleting ./oldfile2\n',
                ]),
            self.make_rule_status(
                [
                    b'd\tO\tM\t.',
                ],
                selection=['-sor', '-scm', '-sunm', '-sne']),
            self.make_rule_diff_tree('.', [
                '< F:    oldfile1   1\n',
                '< F:    oldfile2   3\n',
                '---\n',
                '> F:    newfile1   1\n',
                '> F:    newfile2   3\n',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './newfile1',
                    './newfile2',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './newfile1',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '1',
                    '5',
                    '!Record!',
                    './newfile2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '3',
                    'RevId',
                    '2',
                    '26',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./newfile1/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old content 1\n'),
            self.make_rule_diff(client, tmpfiles[1], 'newfile1'),
            self.make_rule_exportrev(sos_path='./newfile2/#/3',
                                     out_filename=tmpfiles[2],
                                     content=b'unchanged content\n'),
            self.make_rule_diff(client, tmpfiles[2], 'newfile2'),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_changelist': 'my_changelist',
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=354\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "changelist": "my_changelist",\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 1,\n'
            b'        "files": 2,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "files": 2,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=315\n'
            b'{\n'
            b'    "op": "move-modify",\n'
            b'    "path": {\n'
            b'        "new": "newfile1",\n'
            b'        "old": "oldfile1"\n'
            b'    },\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 5\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=68, line_endings=unix\n'
            b'--- oldfile1\n'
            b'+++ newfile1\n'
            b'@@ -1 +1 @@\n'
            b'-old content 1\n'
            b'+new content 1\n'
            b'#..file:\n'
            b'#...meta: format=json, length=211\n'
            b'{\n'
            b'    "op": "move",\n'
            b'    "path": {\n'
            b'        "new": "newfile2",\n'
            b'        "old": "oldfile2"\n'
            b'    },\n'
            b'    "revision": {\n'
            b'        "old": "3"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 26\n'
            b'        }\n'
            b'    }\n'
            b'}\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_changelist': 'my_changelist',
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_changelist_and_binary_files(self):
        """Testing SOSClient.diff with changelist and binary files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(4)

        self.write_workarea_file('test.bin', b'\x00\x01\x02')
        self.write_workarea_file(os.path.join('images', 'image.png'),
                                 b'\x00\x04\x05')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_list_changelist(
                name='my_changelist',
                results=[
                    'Adding ./test.bin\n',
                    'Modifying ./images/image.png\n',
                    'Deleting ./trash/old.bin\n',
                ]),
            self.make_rule_status(
                [
                    b'F\tO\tM\t./images/image.png',
                    b'F\t?\t?\t./test.bin',
                    b'F\tW\t!\t./trash/old.bin',
                ],
                selection=['-sor', '-scm', '-sunm', '-sne']),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './images/image.png',
                    './trash/old.bin',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './images/image.png',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '1',
                    '5',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_diff(client, tmpfiles[1], 'test.bin'),
            self.make_rule_exportrev(sos_path='./images/image.png/#/1',
                                     out_filename=tmpfiles[2],
                                     content=b'\x00\x01'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('images', 'image.png')),
            self.make_rule_diff(client, tmpfiles[3],
                                os.path.join('trash', 'old.bin')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_changelist': 'my_changelist',
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=354\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "changelist": "my_changelist",\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 0,\n'
            b'        "files": 3,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 0\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "files": 3,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 0\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=47\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "test.bin"\n'
            b'}\n'
            b'#...diff: length=43, line_endings=unix, type=binary\n'
            b'Binary files /dev/null and test.bin differ\n'
            b'#..file:\n'
            b'#...meta: format=json, length=170\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "images/image.png",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 5\n'
            b'        }\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=58, line_endings=unix, type=binary\n'
            b'Binary files images/image.png and images/image.png differ\n'
            b'#..file:\n'
            b'#...meta: format=json, length=52\n'
            b'{\n'
            b'    "op": "delete",\n'
            b'    "path": "trash/old.bin"\n'
            b'}\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_changelist': 'my_changelist',
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_changelist_complex(self):
        """Testing SOSClient.diff with changelist containing complex set
        of changes
        """
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(6)

        self.write_workarea_file('README', b'new line\n')
        self.write_workarea_file(os.path.join('src', 'main.c'),
                                 b'new content\n')
        self.write_workarea_file('newfile', b'new file!\n')
        self.write_workarea_file(os.path.join('doc', 'index.md'),
                                 b'# new header line\n')
        self.write_workarea_file('new-name1', b'new content\n')
        self.write_workarea_file(os.path.join('src', 'new-name2'),
                                 b'unchanged content\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_list_changelist(
                name='my_changelist',
                results=[
                    'Modifying ./README\n',
                    'Modifying ./src/main.c\n',
                    'Adding ./newfile\n',
                    'Adding ./new-name1\n',
                    'Adding ./src/new-name2\n',
                    'Deleting ./delfile\n',
                    'Deleting ./old-name1\n',
                    'Deleting ./src/old-name2\n',
                ]),
            self.make_rule_status(
                [
                    b'F\tO\tM\t./src/main.c',
                    b'F\t!\t-\t./src/new-name2',
                    b'F\tO\tM\t./README',
                    b'F\t!\t-\t./delfile',
                    b'F\t-\t-\t./ignore-me',
                    b'F\t?\t?\t./newfile',
                    b'F\t!\t-\t./new-name1',
                    b'd\tO\tM\t.',
                    b'd\tO\tM\t./src',
                ],
                selection=['-sor', '-scm', '-sunm', '-sne']),
            self.make_rule_diff_tree('.', [
                '< F:    old-name1   1\n',
                '---\n',
                '> F:    new-name1   1\n',
            ]),
            self.make_rule_diff_tree('./src', [
                '< F:    old-name2   3\n',
                '---\n',
                '> F:    new-name2   3\n',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './README',
                    './new-name1',
                    './src/main.c',
                    './src/new-name2',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './README',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '1',
                    '5',
                    '!Record!',
                    './src/main.c',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '3',
                    'RevId',
                    '2',
                    '26',
                    '!Record!',
                    './new-name1',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '2',
                    '31',
                    '!Record!',
                    './src/new-name2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '3',
                    'RevId',
                    '2',
                    '42',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./README/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old line\n'),
            self.make_rule_diff(client, tmpfiles[1], 'README'),
            self.make_rule_exportrev(sos_path='./new-name1/#/1',
                                     out_filename=tmpfiles[2],
                                     content=b'old content\n'),
            self.make_rule_diff(client, tmpfiles[2], 'new-name1'),
            self.make_rule_diff(client, tmpfiles[3], 'newfile'),
            self.make_rule_exportrev(sos_path='./src/main.c/#/3',
                                     out_filename=tmpfiles[4],
                                     content=b'old content\n'),
            self.make_rule_diff(client, tmpfiles[4],
                                os.path.join('src', 'main.c')),
            self.make_rule_exportrev(sos_path='./src/new-name2/#/3',
                                     out_filename=tmpfiles[5],
                                     content=b'unchanged content\n'),
            self.make_rule_diff(client, tmpfiles[5],
                                os.path.join('src', 'new-name2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_changelist': 'my_changelist',
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=354\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "changelist": "my_changelist",\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 3,\n'
            b'        "files": 5,\n'
            b'        "insertions": 4,\n'
            b'        "lines changed": 7\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 3,\n'
            b'        "files": 5,\n'
            b'        "insertions": 4,\n'
            b'        "lines changed": 7\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=258\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 5\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=54, line_endings=unix\n'
            b'--- README\n'
            b'+++ README\n'
            b'@@ -1 +1 @@\n'
            b'-old line\n'
            b'+new line\n'

            b'#..file:\n'
            b'#...meta: format=json, length=318\n'
            b'{\n'
            b'    "op": "move-modify",\n'
            b'    "path": {\n'
            b'        "new": "new-name1",\n'
            b'        "old": "old-name1"\n'
            b'    },\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 31\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=66, line_endings=unix\n'
            b'--- old-name1\n'
            b'+++ new-name1\n'
            b'@@ -1 +1 @@\n'
            b'-old content\n'
            b'+new content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=144\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "newfile",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=51, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ newfile\n'
            b'@@ -0,0 +1 @@\n'
            b'+new file!\n'
            b'#..file:\n'
            b'#...meta: format=json, length=263\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "src/main.c",\n'
            b'    "revision": {\n'
            b'        "old": "3"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 26\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=68, line_endings=unix\n'
            b'--- src/main.c\n'
            b'+++ src/main.c\n'
            b'@@ -1 +1 @@\n'
            b'-old content\n'
            b'+new content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=221\n'
            b'{\n'
            b'    "op": "move",\n'
            b'    "path": {\n'
            b'        "new": "src/new-name2",\n'
            b'        "old": "src/old-name2"\n'
            b'    },\n'
            b'    "revision": {\n'
            b'        "old": "3"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 42\n'
            b'        }\n'
            b'    }\n'
            b'}\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_changelist': 'my_changelist',
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_changelist_and_include_files(self):
        """Testing SOSClient.diff with changelist and include_files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(4)

        self.write_workarea_file('README', b'new README content\n')
        self.write_workarea_file('README2', b'new README2 content\n')
        self.write_workarea_file(os.path.join('doc', 'index.md'),
                                 b'# new index.md line\n')

        self.write_workarea_file('newfile1', b'new file!\n')
        self.write_workarea_file(os.path.join('src', 'newfile2'),
                                 b'another new file!\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_list_changelist(
                name='my_changelist',
                results=[
                    'Modifying ./README\n',
                    'Modifying ./README2\n',
                    'Modifying ./doc/index.md\n',
                    'Adding ./newfile1\n',
                    'Adding ./src/newfile2\n',
                ]),
            self.make_rule_status(
                [
                    b'd\tO\tM\t.',
                    b'F\tO\tM\t./README',
                    b'F\tO\tM\t./README2',
                    b'F\t-\t-\t./ignore-me',
                    b'F\t?\t?\t./newfile1',
                    b'F\tO\tM\t./doc/index.md',
                    b'd\tO\tM\t./src',
                ],
                selection=['-sor', '-scm', '-sunm', '-sne']),
            self.make_rule_diff_tree('.', [
                '> F:    newfile1   1\n',
            ]),
            self.make_rule_diff_tree('./src', [
                '> F:    newfile2   1\n',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './README',
                    './README2',
                    './doc/index.md',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './README',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '2',
                    '19',
                    '!Record!',
                    './README2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '5',
                    'RevId',
                    '2',
                    '20',
                    '!Record!',
                    './doc/index.md',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '2',
                    'RevId',
                    '2',
                    '21',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./README/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old README content\n'),
            self.make_rule_diff(client, tmpfiles[1], 'README'),
            self.make_rule_exportrev(sos_path='./README2/#/5',
                                     out_filename=tmpfiles[2],
                                     content=b'old README2 content\n'),
            self.make_rule_diff(client, tmpfiles[2], 'README2'),
            self.make_rule_diff(client, tmpfiles[3],
                                os.path.join('src', 'newfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(
            revisions={
                'base': None,
                'extra': {
                    'sos_changelist': 'my_changelist',
                },
                'tip': None,
            },
            include_files=[
                'README',
                './README2',
                'src/newfile2',
            ])

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=354\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "changelist": "my_changelist",\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=259\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 19\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=74, line_endings=unix\n'
            b'--- README\n'
            b'+++ README\n'
            b'@@ -1 +1 @@\n'
            b'-old README content\n'
            b'+new README content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=260\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README2",\n'
            b'    "revision": {\n'
            b'        "old": "5"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 20\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=78, line_endings=unix\n'
            b'--- README2\n'
            b'+++ README2\n'
            b'@@ -1 +1 @@\n'
            b'-old README2 content\n'
            b'+new README2 content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=149\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "src/newfile2",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=64, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ src/newfile2\n'
            b'@@ -0,0 +1 @@\n'
            b'+another new file!\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_changelist': 'my_changelist',
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_changelist_and_exclude_patterns(self):
        """Testing SOSClient.diff with changelist and exclude_patterns"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(5)

        self.write_workarea_file('README', b'new README content\n')
        self.write_workarea_file('README2', b'new README2 content\n')
        self.write_workarea_file(os.path.join('doc', 'index.md'),
                                 b'# new index.md line\n')

        self.write_workarea_file('newfile1', b'new file!\n')
        self.write_workarea_file(os.path.join('src', 'newfile2'),
                                 b'another new file!\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_list_changelist(
                name='my_changelist',
                results=[
                    'Modifying ./README\n',
                    'Modifying ./README2\n',
                    'Modifying ./doc/index.md\n',
                    'Adding ./newfile1\n',
                    'Adding ./src/newfile2\n',
                ]),
            self.make_rule_status(
                [
                    b'd\tO\tM\t.',
                    b'F\tO\tM\t./README',
                    b'F\tO\tM\t./README2',
                    b'F\t-\t-\t./ignore-me',
                    b'F\t?\t?\t./newfile1',
                    b'F\tO\tM\t./doc/index.md',
                    b'd\tO\tM\t./src',
                ],
                selection=['-sor', '-scm', '-sunm', '-sne']),
            self.make_rule_diff_tree('.', [
                '> F:    newfile1   1\n',
            ]),
            self.make_rule_diff_tree('./src', [
                '> F:    newfile2   1\n',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './README',
                    './README2',
                    './doc/index.md',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './README',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '2',
                    '19',
                    '!Record!',
                    './README2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '5',
                    'RevId',
                    '2',
                    '20',
                    '!Record!',
                    './doc/index.md',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '2',
                    'RevId',
                    '2',
                    '21',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./README/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old README content\n'),
            self.make_rule_diff(client, tmpfiles[1], 'README'),
            self.make_rule_exportrev(sos_path='./README2/#/5',
                                     out_filename=tmpfiles[2],
                                     content=b'old README2 content\n'),
            self.make_rule_diff(client, tmpfiles[2], 'README2'),
            self.make_rule_diff(client, tmpfiles[3],
                                os.path.join('src', 'newfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(
            revisions={
                'base': None,
                'extra': {
                    'sos_changelist': 'my_changelist',
                },
                'tip': None,
            },
            exclude_patterns=[
                '*.md',
                'docs/*',
                'newfile1',
            ])

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=354\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "changelist": "my_changelist",\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=259\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 19\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=74, line_endings=unix\n'
            b'--- README\n'
            b'+++ README\n'
            b'@@ -1 +1 @@\n'
            b'-old README content\n'
            b'+new README content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=260\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README2",\n'
            b'    "revision": {\n'
            b'        "old": "5"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 20\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=78, line_endings=unix\n'
            b'--- README2\n'
            b'+++ README2\n'
            b'@@ -1 +1 @@\n'
            b'-old README2 content\n'
            b'+new README2 content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=149\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "src/newfile2",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=64, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ src/newfile2\n'
            b'@@ -0,0 +1 @@\n'
            b'+another new file!\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_changelist': 'my_changelist',
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_selection(self):
        """Testing SOSClient.diff with selection"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(3)

        self.write_workarea_file('README', b'new line\n')
        self.write_workarea_file(os.path.join('doc', 'index.md'),
                                 b'# new header line\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_status([
                b'F\tO\tM\t./README',
                b'F\t-\t-\t./ignore-me',
                b'F\tO\tM\t./doc/index.md',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './README',
                    './doc/index.md',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './README',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '1',
                    '5',
                    '!Record!',
                    './doc/index.md',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '3',
                    'RevId',
                    '2',
                    '26',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./README/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old line\n'),
            self.make_rule_diff(client, tmpfiles[1], 'README'),
            self.make_rule_exportrev(sos_path='./doc/index.md/#/3',
                                     out_filename=tmpfiles[2],
                                     content=b'# old header line\n'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('doc', 'index.md')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_selection': ['-scm'],
                'has_explicit_selection': False,
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=315\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 2,\n'
            b'        "files": 2,\n'
            b'        "insertions": 2,\n'
            b'        "lines changed": 4\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 2,\n'
            b'        "files": 2,\n'
            b'        "insertions": 2,\n'
            b'        "lines changed": 4\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=258\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 5\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=54, line_endings=unix\n'
            b'--- README\n'
            b'+++ README\n'
            b'@@ -1 +1 @@\n'
            b'-old line\n'
            b'+new line\n'
            b'#..file:\n'
            b'#...meta: format=json, length=265\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "doc/index.md",\n'
            b'    "revision": {\n'
            b'        "old": "3"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 26\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=84, line_endings=unix\n'
            b'--- doc/index.md\n'
            b'+++ doc/index.md\n'
            b'@@ -1 +1 @@\n'
            b'-# old header line\n'
            b'+# new header line\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_selection_added_files(self):
        """Testing SOSClient.diff with selection and added files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(3)

        self.write_workarea_file('newfile1', b'new file!\n')
        self.write_workarea_file(os.path.join('src', 'newfile2'),
                                 b'another new file!\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_status([
                b'd\tO\tM\t.',
                b'd\tO\tM\t./src',
            ]),
            self.make_rule_diff_tree('.', [
                '> F:    newfile1   1\n',
            ]),
            self.make_rule_diff_tree('./src', [
                '> F:    newfile2   1\n',
            ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_diff(client, tmpfiles[1], 'newfile1'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('src', 'newfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_selection': ['-scm'],
                'has_explicit_selection': False,
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=315\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 0,\n'
            b'        "files": 2,\n'
            b'        "insertions": 2,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "files": 2,\n'
            b'        "insertions": 2,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=145\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "newfile1",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=52, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ newfile1\n'
            b'@@ -0,0 +1 @@\n'
            b'+new file!\n'
            b'#..file:\n'
            b'#...meta: format=json, length=149\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "src/newfile2",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=64, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ src/newfile2\n'
            b'@@ -0,0 +1 @@\n'
            b'+another new file!\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_selection_deleted_files(self):
        """Testing SOSClient.diff with selection and deleted files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(3)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_status([
                b'd\tO\tM\t.',
                b'd\tO\tM\t./src',
            ]),
            self.make_rule_diff_tree('.', [
                '< F:    oldfile1   1\n',
            ]),
            self.make_rule_diff_tree('./src', [
                '< F:    oldfile2   1\n',
            ]),
            self.make_rule_undelete('.', 'oldfile1'),
            self.make_rule_nobjstatus(
                sos_paths=['./oldfile1'],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './oldfile1',
                    '3',
                    '1',
                    'Revision',
                    '2',
                    '10',
                    'RevId',
                    '2',
                    '27',
                ]),
            self.make_rule_delete('./oldfile1'),
            self.make_rule_undelete('./src', 'oldfile2'),
            self.make_rule_nobjstatus(
                sos_paths=['./src/oldfile2'],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './src/oldfile2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '7',
                    'RevId',
                    '1',
                    '9',
                ]),
            self.make_rule_delete('./src/oldfile2'),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_diff(client, tmpfiles[1], 'oldfile1'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('src', 'oldfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_selection': ['-scm'],
                'has_explicit_selection': False,
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=315\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 2,\n'
            b'        "files": 2,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 2,\n'
            b'        "files": 2,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=262\n'
            b'{\n'
            b'    "op": "delete",\n'
            b'    "path": "oldfile1",\n'
            b'    "revision": {\n'
            b'        "old": "10"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 27\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=59, line_endings=unix\n'
            b'--- oldfile1\n'
            b'+++ /dev/null\n'
            b'@@ -1 +0,0 @@\n'
            b'-old file content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=264\n'
            b'{\n'
            b'    "op": "delete",\n'
            b'    "path": "src/oldfile2",\n'
            b'    "revision": {\n'
            b'        "old": "7"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 9\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=63, line_endings=unix\n'
            b'--- src/oldfile2\n'
            b'+++ /dev/null\n'
            b'@@ -1 +0,0 @@\n'
            b'-old file content\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_selection_renamed_files(self):
        """Testing SOSClient.diff with selection and renamed files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(3)

        self.write_workarea_file('newfile1', b'new content\n')
        self.write_workarea_file(os.path.join('src', 'newfile2'),
                                 b'unchanged content\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_status([
                b'd\tO\tM\t./src',
                b'd\tO\tM\t.',
            ]),
            self.make_rule_diff_tree('./src', [
                '< F:    oldfile2   2\n',
                '---\n',
                '> F:    newfile2   2\n',
            ]),
            self.make_rule_diff_tree('.', [
                '< F:    oldfile1   1\n',
                '---\n',
                '> F:    newfile1   1\n',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './newfile1',
                    './src/newfile2',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './newfile1',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '2',
                    '19',
                    '!Record!',
                    './src/newfile2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '2',
                    'RevId',
                    '2',
                    '21',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./newfile1/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old content\n'),
            self.make_rule_diff(client, tmpfiles[1], 'newfile1'),
            self.make_rule_exportrev(sos_path='./src/newfile2/#/2',
                                     out_filename=tmpfiles[2],
                                     content=b'unchanged content\n'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('src', 'newfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_selection': ['-scm'],
                'has_explicit_selection': False,
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=315\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 1,\n'
            b'        "files": 2,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "files": 2,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=316\n'
            b'{\n'
            b'    "op": "move-modify",\n'
            b'    "path": {\n'
            b'        "new": "newfile1",\n'
            b'        "old": "oldfile1"\n'
            b'    },\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 19\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=64, line_endings=unix\n'
            b'--- oldfile1\n'
            b'+++ newfile1\n'
            b'@@ -1 +1 @@\n'
            b'-old content\n'
            b'+new content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=219\n'
            b'{\n'
            b'    "op": "move",\n'
            b'    "path": {\n'
            b'        "new": "src/newfile2",\n'
            b'        "old": "src/oldfile2"\n'
            b'    },\n'
            b'    "revision": {\n'
            b'        "old": "2"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 21\n'
            b'        }\n'
            b'    }\n'
            b'}\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_selection_renamed_dirs(self):
        """Testing SOSClient.diff with selection and renamed directories"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(3)

        self.write_workarea_file(os.path.join('src2', 'testfile1'),
                                 b'new content 1\n')
        self.write_workarea_file(os.path.join('src2', 'subdir', 'testfile2'),
                                 b'content 2\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_status([
                b'd\tO\tM\t.',
            ]),
            self.make_rule_diff_tree('.', [
                '< D:    src    2\n',
                '---\n',
                '> D:    src2   2\n',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './src2/subdir/testfile2',
                    './src2/testfile1',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './src2/subdir/testfile2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '2',
                    '19',
                    '!Record!',
                    './src2/testfile1',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '2',
                    'RevId',
                    '2',
                    '21',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./src2/testfile1/#/2',
                                     out_filename=tmpfiles[1],
                                     content=b'old content 1\n'),
            self.make_rule_diff(client, tmpfiles[1],
                                os.path.join('src2', 'testfile1')),
            self.make_rule_exportrev(sos_path='./src2/subdir/testfile2/#/1',
                                     out_filename=tmpfiles[2],
                                     content=b'content 2\n'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('src2', 'subdir', 'testfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_selection': ['-scm'],
                'has_explicit_selection': False,
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=315\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 1,\n'
            b'        "files": 2,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "files": 2,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=327\n'
            b'{\n'
            b'    "op": "move-modify",\n'
            b'    "path": {\n'
            b'        "new": "src2/testfile1",\n'
            b'        "old": "src/testfile1"\n'
            b'    },\n'
            b'    "revision": {\n'
            b'        "old": "2"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 21\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=79, line_endings=unix\n'
            b'--- src/testfile1\n'
            b'+++ src2/testfile1\n'
            b'@@ -1 +1 @@\n'
            b'-old content 1\n'
            b'+new content 1\n'
            b'#..file:\n'
            b'#...meta: format=json, length=236\n'
            b'{\n'
            b'    "op": "move",\n'
            b'    "path": {\n'
            b'        "new": "src2/subdir/testfile2",\n'
            b'        "old": "src/subdir/testfile2"\n'
            b'    },\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 19\n'
            b'        }\n'
            b'    }\n'
            b'}\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_selection_and_binary_files(self):
        """Testing SOSClient.diff with selection and binary files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(3)

        self.write_workarea_file('test.bin', b'\x00\x01\x02')
        self.write_workarea_file(os.path.join('images', 'image.png'),
                                 b'\x03\x04\x05')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_status([
                b'F\tO\tM\t./test.bin',
                b'F\tO\tM\t./images/image.png',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './images/image.png',
                    './test.bin',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './test.bin',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '1',
                    '5',
                    '!Record!',
                    './images/image.png',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '3',
                    'RevId',
                    '2',
                    '26',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./test.bin/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'\x00\x01'),
            self.make_rule_diff(client, tmpfiles[1], 'test.bin'),
            self.make_rule_exportrev(sos_path='./images/image.png/#/3',
                                     out_filename=tmpfiles[2],
                                     content=b'\x00\x03'),
            self.make_rule_diff(client, tmpfiles[2],
                                os.path.join('images', 'image.png')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(revisions={
            'base': None,
            'extra': {
                'sos_selection': ['-scm'],
                'has_explicit_selection': False,
            },
            'tip': None,
        })

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=315\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 0,\n'
            b'        "files": 2,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 0\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "files": 2,\n'
            b'        "insertions": 0,\n'
            b'        "lines changed": 0\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=162\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "test.bin",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 5\n'
            b'        }\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=42, line_endings=unix, type=binary\n'
            b'Binary files test.bin and test.bin differ\n'
            b'#..file:\n'
            b'#...meta: format=json, length=171\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "images/image.png",\n'
            b'    "revision": {\n'
            b'        "old": "3"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 26\n'
            b'        }\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=58, line_endings=unix, type=binary\n'
            b'Binary files images/image.png and images/image.png differ\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_selection_and_include_files(self):
        """Testing SOSClient.diff with selection and include_files"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(4)

        self.write_workarea_file('README', b'new README content\n')
        self.write_workarea_file('README2', b'new README2 content\n')
        self.write_workarea_file(os.path.join('doc', 'index.md'),
                                 b'# new index.md line\n')

        self.write_workarea_file('newfile1', b'new file!\n')
        self.write_workarea_file(os.path.join('src', 'newfile2'),
                                 b'another new file!\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_status(
                [
                    b'd\tO\tM\t.',
                    b'F\tO\tM\t./README',
                    b'F\tO\tM\t./README2',
                    b'F\t-\t-\t./ignore-me',
                    b'F\tO\tM\t./doc/index.md',
                    b'd\tO\tM\t./src',
                ],
                selection=[
                    '-sor', '-sfo', '-sdo', '-sunm',
                    'README',
                    './README2',
                    'src/newfile2',
                ]
            ),
            self.make_rule_diff_tree('.', [
                '> F:    newfile1   1\n',
            ]),
            self.make_rule_diff_tree('./src', [
                '> F:    newfile2   1\n',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './README',
                    './README2',
                    './doc/index.md',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './README',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '2',
                    '19',
                    '!Record!',
                    './README2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '5',
                    'RevId',
                    '2',
                    '20',
                    '!Record!',
                    './doc/index.md',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '2',
                    'RevId',
                    '2',
                    '21',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./README/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old README content\n'),
            self.make_rule_diff(client, tmpfiles[1], 'README'),
            self.make_rule_exportrev(sos_path='./README2/#/5',
                                     out_filename=tmpfiles[2],
                                     content=b'old README2 content\n'),
            self.make_rule_diff(client, tmpfiles[2], 'README2'),
            self.make_rule_diff(client, tmpfiles[3],
                                os.path.join('src', 'newfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(
            revisions={
                'base': None,
                'extra': {
                    'sos_selection': ['-scm'],
                    'has_explicit_selection': False,
                },
                'tip': None,
            },
            include_files=[
                'README',
                './README2',
                'src/newfile2',
            ])

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=315\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=259\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 19\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=74, line_endings=unix\n'
            b'--- README\n'
            b'+++ README\n'
            b'@@ -1 +1 @@\n'
            b'-old README content\n'
            b'+new README content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=260\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README2",\n'
            b'    "revision": {\n'
            b'        "old": "5"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 20\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=78, line_endings=unix\n'
            b'--- README2\n'
            b'+++ README2\n'
            b'@@ -1 +1 @@\n'
            b'-old README2 content\n'
            b'+new README2 content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=149\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "src/newfile2",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=64, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ src/newfile2\n'
            b'@@ -0,0 +1 @@\n'
            b'+another new file!\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_diff_with_selection_and_exclude_patterns(self):
        """Testing SOSClient.diff with selection and exclude_patterns"""
        client = self.build_client(needs_diff=True)
        tmpfiles = self.precreate_tempfiles(5)

        self.write_workarea_file('README', b'new README content\n')
        self.write_workarea_file('README2', b'new README2 content\n')
        self.write_workarea_file(os.path.join('doc', 'index.md'),
                                 b'# new index.md line\n')

        self.write_workarea_file('newfile1', b'new file!\n')
        self.write_workarea_file(os.path.join('src', 'newfile2'),
                                 b'another new file!\n')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            self.rule_query_wa_root,
            self.make_rule_stash_selection([
                b'README',
                b'src/main.c',
                b'doc/index.md',
            ]),
            self.make_rule_status([
                b'd\tO\tM\t.',
                b'F\tO\tM\t./README',
                b'F\tO\tM\t./README2',
                b'F\t-\t-\t./ignore-me',
                b'F\tO\tM\t./doc/index.md',
                b'd\tO\tM\t./src',
            ]),
            self.make_rule_diff_tree('.', [
                '> F:    newfile1   1\n',
            ]),
            self.make_rule_diff_tree('./src', [
                '> F:    newfile2   1\n',
            ]),
            self.make_rule_nobjstatus(
                sos_paths=[
                    './README',
                    './README2',
                    './doc/index.md',
                ],
                flags=['-gaRevision', '-gaRevId'],
                results=[
                    '!nObjStatus! 1',
                    '!Record!',
                    './README',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '1',
                    'RevId',
                    '2',
                    '19',
                    '!Record!',
                    './README2',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '5',
                    'RevId',
                    '2',
                    '20',
                    '!Record!',
                    './doc/index.md',
                    '3',
                    '1',
                    'Revision',
                    '1',
                    '2',
                    'RevId',
                    '2',
                    '21',
                ]),
            self.rule_query_project,
            self.rule_query_server,
            self.rule_query_rso,
            self.make_rule_exportrev(sos_path='./README/#/1',
                                     out_filename=tmpfiles[1],
                                     content=b'old README content\n'),
            self.make_rule_diff(client, tmpfiles[1], 'README'),
            self.make_rule_exportrev(sos_path='./README2/#/5',
                                     out_filename=tmpfiles[2],
                                     content=b'old README2 content\n'),
            self.make_rule_diff(client, tmpfiles[2], 'README2'),
            self.make_rule_diff(client, tmpfiles[3],
                                os.path.join('src', 'newfile2')),
            self.make_rule_restore_selection(tmpfiles[0]),
        ]))

        result = client.diff(
            revisions={
                'base': None,
                'extra': {
                    'sos_selection': ['-scm'],
                    'has_explicit_selection': False,
                },
                'tip': None,
            },
            exclude_patterns=[
                '*.md',
                'docs/*',
                'newfile1',
            ])

        self.assertDiffEqual(
            result['diff'],
            b'#diffx: encoding=utf-8, version=1.0\n'
            b'#.meta: format=json, length=315\n'
            b'{\n'
            b'    "scm": "sos",\n'
            b'    "sos": {\n'
            b'        "project": "test-project",\n'
            b'        "rso": [\n'
            b'            "main",\n'
            b'            "test"\n'
            b'        ],\n'
            b'        "server": "test-server"\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "changes": 1,\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#.change:\n'
            b'#..meta: format=json, length=121\n'
            b'{\n'
            b'    "stats": {\n'
            b'        "deletions": 2,\n'
            b'        "files": 3,\n'
            b'        "insertions": 3,\n'
            b'        "lines changed": 5\n'
            b'    }\n'
            b'}\n'
            b'#..file:\n'
            b'#...meta: format=json, length=259\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README",\n'
            b'    "revision": {\n'
            b'        "old": "1"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 19\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=74, line_endings=unix\n'
            b'--- README\n'
            b'+++ README\n'
            b'@@ -1 +1 @@\n'
            b'-old README content\n'
            b'+new README content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=260\n'
            b'{\n'
            b'    "op": "modify",\n'
            b'    "path": "README2",\n'
            b'    "revision": {\n'
            b'        "old": "5"\n'
            b'    },\n'
            b'    "sos": {\n'
            b'        "rev_id": {\n'
            b'            "old": 20\n'
            b'        }\n'
            b'    },\n'
            b'    "stats": {\n'
            b'        "deletions": 1,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 2\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=78, line_endings=unix\n'
            b'--- README2\n'
            b'+++ README2\n'
            b'@@ -1 +1 @@\n'
            b'-old README2 content\n'
            b'+new README2 content\n'
            b'#..file:\n'
            b'#...meta: format=json, length=149\n'
            b'{\n'
            b'    "op": "create",\n'
            b'    "path": "src/newfile2",\n'
            b'    "stats": {\n'
            b'        "deletions": 0,\n'
            b'        "insertions": 1,\n'
            b'        "lines changed": 1\n'
            b'    }\n'
            b'}\n'
            b'#...diff: length=64, line_endings=unix\n'
            b'--- /dev/null\n'
            b'+++ src/newfile2\n'
            b'@@ -0,0 +1 @@\n'
            b'+another new file!\n')

        self.assertEqual(result.get('review_request_extra_data'), {
            'sos_project': 'test-project',
            'sos_server': 'test-server',
            'sos_workarea': '1234567890',
        })

    def test_normalize_sos_path_with_sos_path(self):
        """Testing SOSClient._normalize_sos_path with leading ./"""
        client = self.build_client()

        self.assertEqual(
            client._normalize_sos_path('./dir/file'),
            'dir/file')

    def test_normalize_sos_path_with_non_sos_path(self):
        """Testing SOSClient._normalize_sos_path without leading ./"""
        client = self.build_client()

        self.assertEqual(
            client._normalize_sos_path('dir/file'),
            'dir/file')

    def test_normalize_sos_path_with_none(self):
        """Testing SOSClient._normalize_sos_path with None"""
        client = self.build_client()

        self.assertIsNone(client._normalize_sos_path(None))

    def test_make_sos_path(self):
        """Testing SOSClient._make_sos_path"""
        client = self.build_client()

        self.assertEqual(
            client._make_sos_path(os.path.join('dir', '', 'file'),
                                  self.workarea_dir),
            './dir/file')

    def test_make_sos_path_with_abs_path(self):
        """Testing SOSClient._make_sos_path with absolute path"""
        client = self.build_client()

        self.assertEqual(
            client._make_sos_path(
                os.path.join(self.workarea_dir, 'dir', 'file'),
                self.workarea_dir),
            './dir/file')

    def test_make_sos_path_with_dot_slash(self):
        """Testing SOSClient._make_sos_path with "./"-prefixed relative path"""
        client = self.build_client()

        self.assertEqual(
            client._make_sos_path(os.path.join('.', 'dir', 'file'),
                                  self.workarea_dir),
            './dir/file')
