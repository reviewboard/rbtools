"""Unit tests for PerforceClient."""

from __future__ import annotations

import os
import re
import time
from subprocess import list2cmdline

import kgb

from rbtools.api.resource import FileAttachmentItemResource
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    SCMError,
                                    TooManyRevisionsError)
from rbtools.clients.perforce import PerforceClient, P4Wrapper
from rbtools.clients.tests import FOO1, SCMClientTestCase
from rbtools.diffs.patches import BinaryFilePatch, Patch
from rbtools.testing import TestCase
from rbtools.testing.api.transport import URLMapTransport
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_tempdir, make_tempfile
from rbtools.utils.process import RunProcessResult, run_process_exec


SAMPLE_CHANGEDESC_TEMPLATE_BASIC = (
    'Change:\t123\n'
    '\n'
    'Date:\t2023/05/06 01:02:03\n'
    '\n'
    'Client:\tTestClient\n'
    '\n'
    'User:\ttest-user\n'
    '\n'
    'Status:\tpending\n'
    '\n'
    'Type:\tpublic\n'
    '\n'
    '%s'
    '\n'
    'Files:\n'
    '\t//depot/main/test1\t# edit\n'
    '\t//depot/main/test2\t# edit\n'
)


class P4DiffTestWrapper(P4Wrapper):
    def __init__(self, options):
        super().__init__(options)

        self._timestamp = time.mktime(time.gmtime(0))

    def fstat(self, depot_path, fields=[]):
        assert depot_path in self.fstat_files

        fstat_info = self.fstat_files[depot_path]

        for field in fields:
            assert field in fstat_info

        return fstat_info

    def opened(self, changenum):
        return [info for info in self.repo_files
                if info['change'] == changenum]

    def print_file(self, depot_path, out_file):
        for info in self.repo_files:
            if depot_path == '%s#%s' % (info['depotFile'], info['rev']):
                fp = open(out_file, 'w')
                fp.write(info['text'])
                fp.close()
                return
        assert False

    def where(self, depot_path):
        assert depot_path in self.where_files

        return [{
            'path': self.where_files[depot_path],
        }]

    def change(self, changenum):
        return [{
            'Change': str(changenum),
            'Date': '2013/01/02 22:33:44',
            'User': 'joe@example.com',
            'Status': 'pending',
            'Description': 'This is a test.\n',
        }]

    def info(self):
        return {
            'Client root': '/',
        }

    def run_p4(self, *args, **kwargs):
        assert False


class P4WrapperTests(TestCase):
    """Unit tests for P4Wrapper."""

    def is_supported(self):
        return True

    def test_counters(self):
        """Testing P4Wrapper.counters"""
        class _TestWrapper(P4Wrapper):
            def run_p4(self, cmd, *args, **kwargs):
                return RunProcessResult(
                    command=list2cmdline(cmd),
                    stdout=(
                        b'a = 1\n'
                        b'b = 2\n'
                        b'c = 3\n'
                    )
                )

        p4 = _TestWrapper(None)
        info = p4.counters()

        self.assertEqual(
            info,
            {
                'a': '1',
                'b': '2',
                'c': '3',
            })

    def test_info(self):
        """Testing P4Wrapper.info"""
        class _TestWrapper(P4Wrapper):
            def run_p4(self, cmd, *args, **kwargs):
                return RunProcessResult(
                    command=list2cmdline(cmd),
                    stdout=(
                        b'User name: myuser\n'
                        b'Client name: myclient\n'
                        b'Client host: myclient.example.com\n'
                        b'Client root: /path/to/client\n'
                        b'Server uptime: 111:43:38\n'
                    )
                )

        p4 = _TestWrapper(None)
        info = p4.info()

        self.assertEqual(
            info,
            {
                'Client host': 'myclient.example.com',
                'Client name': 'myclient',
                'Client root': '/path/to/client',
                'Server uptime': '111:43:38',
                'User name': 'myuser',
            })


class PerforceSCMClientTestCase(SCMClientTestCase[PerforceClient]):
    scmclient_cls = PerforceClient

    default_scmclient_caps = {
        'scmtools': {
            'perforce': {
                'empty_files': True,
            },
        },
    }
    default_scmclient_options = {
        'p4_client': 'myclient',
        'p4_passwd': '',
        'p4_port': 'perforce.example.com:1666',
    }

    def setUp(self) -> None:
        """Set up the state for a test."""
        super().setUp()

        # Our unit tests simulate results for p4, so we don't actually
        # need it installed. Instead, fake that it's installed so tests
        # aren't skipped.
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['p4', 'help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

    def build_client(
        self,
        wrapper_cls: type[P4Wrapper] = P4DiffTestWrapper,
        **kwargs,
    ) -> PerforceClient:
        """Build a client for testing.

        THis will set default command line options for the client and
        server, and allow for specifying a custom Perforce wrapper class.

        Version Added:
            4.0:
            This was part of :py:class:`PerforceClientTests`.

        Args:
            wrapper_cls (type, optional):
                The P4 wrapper class to pass to the client.

            **kwargs (dict, optional):
                Additional keyword arguments to pass to the parent method.

        Returns:
            rbtools.clients.perforce.PerforceClient:
            The client instance.
        """
        return super().build_client(
            client_kwargs={
                'p4_class': wrapper_cls,
            },
            **kwargs)


class PerforceClientTests(PerforceSCMClientTestCase):
    """Unit tests for PerforceClient."""

    def test_check_dependencies_with_found(self):
        """Testing PerforceClient.check_dependencies with p4 found"""
        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['p4', 'help'])

    def test_check_dependencies_with_missing(self):
        """Testing PerforceClient.check_dependencies with dependencies
        missing
        """
        check_install.unspy()
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools ('p4') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['p4', 'help'])

    def test_get_local_path_with_deps_missing(self) -> None:
        """Testing PerforceClient.get_local_path with dependencies missing"""
        check_install.unspy()
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_local_path(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            local_path = client.get_local_path()

        self.assertIsNone(local_path)

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "p4 help": skipping Perforce')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['p4', 'help'])

    def test_get_local_path_with_deps_not_checked(self) -> None:
        """Testing PerforceClient.get_local_path with dependencies not
        checked
        """
        # A False value is used just to ensure get_local_path() bails early,
        # and to minimize side-effects.
        check_install.unspy()
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either PerforceClient.setup() or '
            'PerforceClient.has_dependencies() must be called before other '
            'functions are used.'
        )

        with self.assertRaisesRegex(SCMError, message):
            client.get_local_path()

    def test_scan_for_server_with_reviewboard_url(self):
        """Testing PerforceClient.scan_for_server with reviewboard.url"""
        RB_URL = 'http://reviewboard.example.com/'

        class TestWrapper(P4Wrapper):
            def counters(self):
                return {
                    'reviewboard.url': RB_URL,
                    'foo': 'bar',
                }

        client = self.build_client(wrapper_cls=TestWrapper)
        url = client.scan_for_server(None)

        self.assertEqual(url, RB_URL)

    def test_get_repository_info_with_server_address(self):
        """Testing PerforceClient.get_repository_info with server address"""
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def is_supported(self):
                return True

            def counters(self):
                return {}

            def info(self):
                return {
                    'Client root': os.getcwd(),
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = self.build_client(wrapper_cls=TestWrapper)
        info = client.get_repository_info()

        self.assertIsNotNone(info)
        self.assertEqual(info.path, SERVER_PATH)
        self.assertEqual(client.p4d_version, (2012, 2))

    def test_get_repository_info_with_broker_address(self):
        """Testing PerforceClient.get_repository_info with broker address"""
        BROKER_PATH = 'broker.example.com:1666'
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def is_supported(self):
                return True

            def counters(self):
                return {}

            def info(self):
                return {
                    'Client root': os.getcwd(),
                    'Broker address': BROKER_PATH,
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = self.build_client(wrapper_cls=TestWrapper)
        info = client.get_repository_info()

        self.assertIsNotNone(info)
        self.assertEqual(info.path, BROKER_PATH)
        self.assertEqual(client.p4d_version, (2012, 2))

    def test_get_repository_info_with_server_address_and_encrypted(self):
        """Testing PerforceClient.get_repository_info with server address
        and broker encryption"""
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def is_supported(self):
                return True

            def counters(self):
                return {}

            def info(self):
                return {
                    'Client root': os.getcwd(),
                    'Server address': SERVER_PATH,
                    'Server encryption': 'encrypted',
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = self.build_client(wrapper_cls=TestWrapper)
        info = client.get_repository_info()

        self.assertIsNotNone(info)
        self.assertEqual(info.path, [
            'ssl:%s' % SERVER_PATH,
            SERVER_PATH,
        ])
        self.assertEqual(client.p4d_version, (2012, 2))

    def test_get_repository_info_with_broker_address_and_encrypted(self):
        """Testing PerforceClient.get_repository_info with broker address
        and broker encryption"""
        BROKER_PATH = 'broker.example.com:1666'
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def is_supported(self):
                return True

            def counters(self):
                return {}

            def info(self):
                return {
                    'Client root': os.getcwd(),
                    'Broker address': BROKER_PATH,
                    'Broker encryption': 'encrypted',
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = self.build_client(wrapper_cls=TestWrapper)
        info = client.get_repository_info()

        self.assertIsNotNone(info)
        self.assertEqual(info.path, [
            'ssl:%s' % BROKER_PATH,
            BROKER_PATH,
        ])
        self.assertEqual(client.p4d_version, (2012, 2))

    def test_get_repository_info_with_repository_name_counter(self):
        """Testing PerforceClient.get_repository_info with repository name
        counter
        """
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def is_supported(self):
                return True

            def counters(self):
                return {
                    'reviewboard.repository_name': 'myrepo',
                }

            def info(self):
                return {
                    'Client root': os.getcwd(),
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = self.build_client(wrapper_cls=TestWrapper)
        info = client.get_repository_info()

        self.assertIsNotNone(info)
        self.assertEqual(info.path, SERVER_PATH)
        self.assertEqual(client.p4d_version, (2012, 2))

        self.assertEqual(client.get_repository_name(), 'myrepo')

    def test_get_repository_info_outside_client_root(self):
        """Testing PerforceClient.get_repository_info outside client root"""
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def is_supported(self):
                return True

            def info(self):
                return {
                    'Client root': '/',
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = self.build_client(wrapper_cls=TestWrapper)
        info = client.get_repository_info()

        self.assertIsNone(info)

    def test_scan_for_server_with_reviewboard_url_encoded(self):
        """Testing PerforceClient.scan_for_server with encoded
        reviewboard.url.http:||
        """
        URL_KEY = 'reviewboard.url.http:||reviewboard.example.com/'
        RB_URL = 'http://reviewboard.example.com/'

        class TestWrapper(P4Wrapper):
            def counters(self):
                return {
                    URL_KEY: '1',
                    'foo': 'bar',
                }

        client = self.build_client(wrapper_cls=TestWrapper)
        url = client.scan_for_server(None)

        self.assertEqual(url, RB_URL)

    def test_diff_with_pending_changelist(self):
        """Testing PerforceClient.diff with a pending changelist"""
        client = self.build_client(needs_diff=True)
        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': 'This is a mess.\n',
            },
            {
                'depotFile': '//mydepot/test/COPYING',
                'rev': '1',
                'action': 'add',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
            {
                'depotFile': '//mydepot/test/Makefile',
                'rev': '3',
                'action': 'delete',
                'change': '12345',
                'text': 'all: all\n',
            },
        ]

        readme_file = make_tempfile()
        copying_file = make_tempfile()
        makefile_file = make_tempfile()
        client.p4.print_file('//mydepot/test/README#3', readme_file)
        client.p4.print_file('//mydepot/test/COPYING#1', copying_file)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/COPYING': copying_file,
            '//mydepot/test/Makefile': makefile_file,
        }

        revisions = client.parse_revision_spec(['12345'])

        self.assertEqual(
            self.normalize_diff_result(client.diff(revisions)),
            {
                'changenum': '12345',
                'diff': (
                    b'--- //mydepot/test/README\t//mydepot/test/README#2\n'
                    b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
                    b'@@ -1 +1 @@\n'
                    b'-This is a test.\n'
                    b'+This is a mess.\n'
                    b'--- //mydepot/test/COPYING\t//mydepot/test/COPYING#0\n'
                    b'+++ //mydepot/test/COPYING\t2022-01-02 12:34:56\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+Copyright 2013 Joe User.\n'
                    b'--- //mydepot/test/Makefile\t//mydepot/test/Makefile#3\n'
                    b'+++ //mydepot/test/Makefile\t2022-01-02 12:34:56\n'
                    b'@@ -1 +0,0 @@\n'
                    b'-all: all\n'
                ),
            })

    def test_diff_for_submitted_changelist(self):
        """Testing PerforceClient.diff with a submitted changelist"""
        class TestWrapper(P4DiffTestWrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'submitted',
                    'Description': 'My change description\n',
                }]

            def filelog(self, path):
                return [
                    {
                        'change0': '12345',
                        'action0': 'edit',
                        'rev0': '3',
                        'depotFile': '//mydepot/test/README',
                    }
                ]

        client = self.build_client(wrapper_cls=TestWrapper,
                                   needs_diff=True)
        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': 'This is a mess.\n',
            },
        ]

        readme_file = make_tempfile()
        client.p4.print_file('//mydepot/test/README#3', readme_file)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
        }
        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': 'This is a mess.\n',
            },
        ]

        revisions = client.parse_revision_spec(['12345'])

        self.assertEqual(
            self.normalize_diff_result(client.diff(revisions)),
            {
                'commit_id': '12345',
                'diff': (
                    b'--- //mydepot/test/README\t//mydepot/test/README#2\n'
                    b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
                    b'@@ -1 +1 @@\n'
                    b'-This is a test.\n'
                    b'+This is a mess.\n'
                ),
            })

    def test_diff_with_moved_files_cap_on(self):
        """Testing PerforceClient.diff with moved files and capability on"""
        self._test_diff_with_moved_files(
            expected_diff=(
                b'Moved from: //mydepot/test/README\n'
                b'Moved to: //mydepot/test/README-new\n'
                b'--- //mydepot/test/README\t//mydepot/test/README#2\n'
                b'+++ //mydepot/test/README-new\t2022-01-02 12:34:56\n'
                b'@@ -1 +1 @@\n'
                b'-This is a test.\n'
                b'+This is a mess.\n'
                b'==== //mydepot/test/COPYING#2 ==MV== '
                b'//mydepot/test/COPYING-new ====\n'
                b'\n'
            ),
            caps={
                'scmtools': {
                    'perforce': {
                        'moved_files': True
                    }
                }
            })

    def test_diff_with_moved_files_cap_off(self):
        """Testing PerforceClient.diff with moved files and capability off"""
        self._test_diff_with_moved_files(expected_diff=(
            b'--- //mydepot/test/README\t//mydepot/test/README#2\n'
            b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
            b'@@ -1 +0,0 @@\n'
            b'-This is a test.\n'
            b'--- //mydepot/test/README-new\t//mydepot/test/README-new#0\n'
            b'+++ //mydepot/test/README-new\t2022-01-02 12:34:56\n'
            b'@@ -0,0 +1 @@\n'
            b'+This is a mess.\n'
            b'--- //mydepot/test/COPYING\t//mydepot/test/COPYING#2\n'
            b'+++ //mydepot/test/COPYING\t2022-01-02 12:34:56\n'
            b'@@ -1 +0,0 @@\n'
            b'-Copyright 2013 Joe User.\n'
            b'--- //mydepot/test/COPYING-new\t//mydepot/test/COPYING-new#0\n'
            b'+++ //mydepot/test/COPYING-new\t2022-01-02 12:34:56\n'
            b'@@ -0,0 +1 @@\n'
            b'+Copyright 2013 Joe User.\n'
        ))

    def _test_diff_with_moved_files(self, expected_diff, caps={}):
        client = self.build_client(needs_diff=True,
                                   caps=caps)
        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'move/delete',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README-new',
                'rev': '1',
                'action': 'move/add',
                'change': '12345',
                'text': 'This is a mess.\n',
            },
            {
                'depotFile': '//mydepot/test/COPYING',
                'rev': '2',
                'action': 'move/delete',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
            {
                'depotFile': '//mydepot/test/COPYING-new',
                'rev': '1',
                'action': 'move/add',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
        ]

        readme_file = make_tempfile()
        copying_file = make_tempfile()
        readme_file_new = make_tempfile()
        copying_file_new = make_tempfile()
        client.p4.print_file('//mydepot/test/README#2', readme_file)
        client.p4.print_file('//mydepot/test/COPYING#2', copying_file)
        client.p4.print_file('//mydepot/test/README-new#1', readme_file_new)
        client.p4.print_file('//mydepot/test/COPYING-new#1', copying_file_new)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/COPYING': copying_file,
            '//mydepot/test/README-new': readme_file_new,
            '//mydepot/test/COPYING-new': copying_file_new,
        }

        client.p4.fstat_files = {
            '//mydepot/test/README': {
                'clientFile': readme_file,
                'movedFile': '//mydepot/test/README-new',
            },
            '//mydepot/test/README-new': {
                'clientFile': readme_file_new,
                'depotFile': '//mydepot/test/README-new',
            },
            '//mydepot/test/COPYING': {
                'clientFile': copying_file,
                'movedFile': '//mydepot/test/COPYING-new',
            },
            '//mydepot/test/COPYING-new': {
                'clientFile': copying_file_new,
                'depotFile': '//mydepot/test/COPYING-new',
            },
        }

        revisions = client.parse_revision_spec(['12345'])

        self.assertEqual(
            self.normalize_diff_result(client.diff(revisions)),
            {
                'changenum': '12345',
                'diff': expected_diff,
            })

    def test_parse_revision_spec_no_args(self):
        """Testing PerforceClient.parse_revision_spec with no specified
        revisions
        """
        client = self.build_client()

        self.assertEqual(
            client.parse_revision_spec([]),
            {
                'base': PerforceClient.REVISION_CURRENT_SYNC,
                'tip': ('%sdefault'
                        % PerforceClient.REVISION_PENDING_CLN_PREFIX),
            })

    def test_parse_revision_spec_pending_cln(self):
        """Testing PerforceClient.parse_revision_spec with a pending
        changelist
        """
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'pending',
                    'Description': 'My change description\n',
                }]

        client = self.build_client(wrapper_cls=TestWrapper)

        self.assertEqual(
            client.parse_revision_spec(['12345']),
            {
                'base': PerforceClient.REVISION_CURRENT_SYNC,
                'tip': '%s12345' % PerforceClient.REVISION_PENDING_CLN_PREFIX,
            })

    def test_parse_revision_spec_submitted_cln(self):
        """Testing PerforceClient.parse_revision_spec with a submitted
        changelist
        """
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'submitted',
                    'Description': 'My change description\n',
                }]

        client = self.build_client(wrapper_cls=TestWrapper)

        self.assertEqual(
            client.parse_revision_spec(['12345']),
            {
                'base': '12344',
                'tip': '12345',
            })

    def test_parse_revision_spec_shelved_cln(self):
        """Testing PerforceClient.parse_revision_spec with a shelved
        changelist
        """
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'shelved',
                    'Description': 'My change description\n',
                }]

        client = self.build_client(wrapper_cls=TestWrapper)

        self.assertEqual(
            client.parse_revision_spec(['12345']),
            {
                'base': PerforceClient.REVISION_CURRENT_SYNC,
                'tip': '%s12345' % PerforceClient.REVISION_PENDING_CLN_PREFIX,
            })

    def test_parse_revision_spec_two_args(self):
        """Testing PerforceClient.parse_revision_spec with two changelists"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                change = {
                    'Change': str(changelist),
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Description': 'My change description\n',
                }

                if changelist == '99' or changelist == '100':
                    change['Status'] = 'submitted'
                elif changelist == '101':
                    change['Status'] = 'pending'
                elif changelist == '102':
                    change['Status'] = 'shelved'
                else:
                    assert False

                return [change]

        client = self.build_client(wrapper_cls=TestWrapper)

        self.assertEqual(
            client.parse_revision_spec(['99', '100']),
            {
                'base': '99',
                'tip': '100',
            })

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['99', '101'])

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['99', '102'])

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['101', '100'])

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['102', '100'])

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['102', '10284'])

    def test_parse_revision_spec_invalid_spec(self):
        """Testing PerforceClient.parse_revision_spec with invalid
        specifications
        """
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return []

        client = self.build_client(wrapper_cls=TestWrapper)

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['aoeu'])

        with self.assertRaises(TooManyRevisionsError):
            client.parse_revision_spec(['1', '2', '3'])

    def test_diff_exclude(self):
        """Testing PerforceClient.normalize_exclude_patterns"""
        repo_root = self.chdir_tmp()
        os.mkdir('subdir')
        cwd = os.getcwd()

        class ExcludeWrapper(P4Wrapper):
            def info(self):
                return {
                    'Client root': repo_root,
                }

        client = self.build_client(wrapper_cls=ExcludeWrapper)

        patterns = [
            '//depot/path',
            os.path.join(os.path.sep, 'foo'),
            'foo',
        ]

        normalized_patterns = [
            # Depot paths should remain unchanged.
            patterns[0],
            # "Absolute" paths (i.e., ones that begin with a path separator)
            # should be relative to the repository root.
            os.path.join(repo_root, patterns[1][1:]),
            # Relative paths should be relative to the current working
            # directory.
            os.path.join(cwd, patterns[2]),
        ]

        result = client.normalize_exclude_patterns(patterns)

        self.assertEqual(result, normalized_patterns)

    def test_replace_changeset_description(self) -> None:
        """Testing PerforceClient._replace_changeset_description"""
        client = self.build_client()

        old_changedesc = SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\tHere is the original description.\n'
            '\t\n'
            '\tWith multiple...\n'
            '\t...lines.\n'
        )

        new_changedesc = client._replace_changeset_description(
            old_changedesc,
            'Here is the original description.\n'
            '\n'
            'With multiple...\n'
            '...lines.\n'
            '\n'
            'Reviewed at https://reviews.example.com/r/123/\n'
        )

        self.assertEqual(new_changedesc, SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\tHere is the original description.\n'
            '\t\n'
            '\tWith multiple...\n'
            '\t...lines.\n'
            '\t\n'
            '\tReviewed at https://reviews.example.com/r/123/\n'
        ))

    def test_replace_changeset_description_with_summary(self) -> None:
        """Testing PerforceClient._replace_changeset_description with existing
        summary only
        """
        client = self.build_client()

        old_changedesc = SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\tHere is the original description.\n'
        )

        new_changedesc = client._replace_changeset_description(
            old_changedesc,
            'Here is the original description.\n'
            '\n'
            'Reviewed at https://reviews.example.com/r/123/\n'
        )

        self.assertEqual(new_changedesc, SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\tHere is the original description.\n'
            '\t\n'
            '\tReviewed at https://reviews.example.com/r/123/\n'
        ))

    def test_replace_changeset_description_with_single(self) -> None:
        """Testing PerforceClient._replace_changeset_description with single
        line
        """
        client = self.build_client()

        old_changedesc = SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\tHere is the original description.\n'
        )

        new_changedesc = client._replace_changeset_description(
            old_changedesc,
            'Here is the original description.\n'
            '\n'
            'Reviewed at https://reviews.example.com/r/123/\n'
        )

        self.assertEqual(new_changedesc, SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\tHere is the original description.\n'
            '\t\n'
            '\tReviewed at https://reviews.example.com/r/123/\n'
        ))

    def test_replace_changeset_description_with_spaces(self) -> None:
        """Testing PerforceClient._replace_changeset_description with spaces
        """
        client = self.build_client()

        old_changedesc = SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '    Here is the original description.\n'
        )

        new_changedesc = client._replace_changeset_description(
            old_changedesc,
            'Here is the original description.\n'
            '\n'
            'Reviewed at https://reviews.example.com/r/123/\n'
        )

        self.assertEqual(new_changedesc, SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\tHere is the original description.\n'
            '\t\n'
            '\tReviewed at https://reviews.example.com/r/123/\n'
        ))

    def test_replace_changeset_description_with_indents(self) -> None:
        """Testing PerforceClient._replace_changeset_description with indents
        within body
        """
        client = self.build_client()

        old_changedesc = SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\tHere is the original description.\n'
            '\n'
            '\t    And we indent here.\n'
            '\n'
            '\tAnd back to normal.\n'
        )

        new_changedesc = client._replace_changeset_description(
            old_changedesc,
            'Here is the original description.\n'
            '\n'
            '    And we indent here.\n'
            '\n'
            'And back to normal.\n'
            '\n'
            'Reviewed at https://reviews.example.com/r/123/\n'
        )

        self.assertEqual(new_changedesc, SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\tHere is the original description.\n'
            '\t\n'
            '\t    And we indent here.\n'
            '\t\n'
            '\tAnd back to normal.\n'
            '\t\n'
            '\tReviewed at https://reviews.example.com/r/123/\n'
        ))

    def test_replace_changeset_description_with_empty(self) -> None:
        """Testing PerforceClient._replace_changeset_description with empty
        description
        """
        client = self.build_client()

        old_changedesc = SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
        )

        new_changedesc = client._replace_changeset_description(
            old_changedesc,
            '\n'
            'Reviewed at https://reviews.example.com/r/123/\n'
        )

        self.assertEqual(new_changedesc, SAMPLE_CHANGEDESC_TEMPLATE_BASIC % (
            'Description:\n'
            '\t\n'
            '\tReviewed at https://reviews.example.com/r/123/\n'
        ))

    def test_get_file_content_pending_changelist(self) -> None:
        """Testing PerforceClient.get_file_content with a pending changelist"""
        client = self.build_client()
        readme_file = make_tempfile(content=FOO1)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
        }

        content = client.get_file_content(
            filename='//mydepot/test/README',
            revision='')

        self.assertEqual(content, FOO1)

    def test_get_file_content_pending_changelist_invalid_file(self) -> None:
        """Testing PerforceClient.get_file_content with a pending changelist
        and an invalid filename
        """
        client = self.build_client()
        readme_file = make_tempfile(content=FOO1)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
        }

        with self.assertRaises(SCMError):
            client.get_file_content(
                filename='//mydepot/test/README2',
                revision='')

    def test_get_file_content_submitted_changelist(self) -> None:
        """Testing PerforceClient.get_file_content with a submitted changelist
        """
        client = self.build_client()

        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': FOO1.decode(),
            },
        ]

        content = client.get_file_content(
            filename='//mydepot/test/README',
            revision='3')

        self.assertEqual(content, FOO1)

    def test_get_file_content_submitted_changelist_invalid_file(self) -> None:
        """Testing PerforceClient.get_file_content with a sibmutted changelist
        and invalid filename/revision
        """
        client = self.build_client()

        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': FOO1.decode(),
            },
        ]

        with self.assertRaises(SCMError):
            client.get_file_content(
                filename='//mydepot/test/README2',
                revision='3')

    def test_get_file_size_pending_changelist(self) -> None:
        """Testing PerforceClient.get_file_size with a pending changelist"""
        client = self.build_client()
        readme_file = make_tempfile(content=FOO1)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
        }

        size = client.get_file_size(
            filename='//mydepot/test/README',
            revision='')

        self.assertEqual(size, len(FOO1))

    def test_get_file_size_pending_changelist_invalid_file(self) -> None:
        """Testing PerforceClient.get_file_size with a pending changelist and
        an invalid filename/revision
        """
        client = self.build_client()
        readme_file = make_tempfile(content=FOO1)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
        }

        with self.assertRaises(SCMError):
            client.get_file_size(
                filename='//mydepot/test/README2',
                revision='')

    def test_get_file_size_submitted_changelist(self) -> None:
        """Testing PerforceClient.get_file_size with a submitted changelist"""
        client = self.build_client()

        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': FOO1.decode(),
            },
        ]
        client.p4.fstat_files = {
            '//mydepot/test/README#3': {
                'fileSize': len(FOO1),
            },
        }

        size = client.get_file_size(
            filename='//mydepot/test/README',
            revision='3')

        self.assertEqual(size, len(FOO1))

    def test_get_file_size_submitted_changelist_invalid_file(self) -> None:
        """Testing PerforceClient.get_file_size with a submitted changelist and
        invalid filename/revision
        """
        client = self.build_client()

        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': FOO1.decode(),
            },
        ]

        with self.assertRaises(SCMError):
            client.get_file_size(
                filename='//mydepot/test/README2',
                revision='3')


class PerforcePatcherTests(PerforceSCMClientTestCase):
    """Unit tests for PerforcePatcher.

    Version Added:
        5.1
    """

    def test_patch(self) -> None:
        """Testing PerforcePatcher.patch"""
        client = self.build_client()
        repository_info = client.get_repository_info()
        tempfiles = self.precreate_tempfiles(1)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[
                Patch(content=(
                    b'--- //mydepot/test/README\t//mydepot/test/README#2\n'
                    b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
                    b'@@ -1 +1 @@\n'
                    b'-This is a test.\n'
                    b'+This is a mess.\n'
                    b'--- //mydepot/test/COPYING\t//mydepot/test/COPYING#0\n'
                    b'+++ //mydepot/test/COPYING\t2022-01-02 12:34:56\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+Copyright 2013 Joe User.\n'
                    b'--- //mydepot/test/Makefile\t//mydepot/test/Makefile#3\n'
                    b'+++ //mydepot/test/Makefile\t2022-01-02 12:34:56\n'
                    b'@@ -1 +0,0 @@\n'
                    b'-all: all\n'
                )),
            ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        self.assertSpyCallCount(run_process_exec, 2)

    def test_patch_with_prefix_level(self) -> None:
        """Testing PerforcePatcher.patch with Patch.prefix_level="""
        client = self.build_client()
        repository_info = client.get_repository_info()
        tempfiles = self.precreate_tempfiles(1)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-p3', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[
                Patch(
                    prefix_level=3,
                    content=(
                        b'--- //mydepot/test/README\t//mydepot/test/README#2\n'
                        b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
                        b'@@ -1 +1 @@\n'
                        b'-This is a test.\n'
                        b'+This is a mess.\n'
                        b'--- //mydepot/test/COPYING\t//mydepot/test/COPYING#0'
                        b'\n'
                        b'+++ //mydepot/test/COPYING\t2022-01-02 12:34:56\n'
                        b'@@ -0,0 +1 @@\n'
                        b'+Copyright 2013 Joe User.\n'
                        b'--- //mydepot/test/Makefile\t//mydepot/test/Makefile'
                        b'#3\n'
                        b'+++ //mydepot/test/Makefile\t2022-01-02 12:34:56\n'
                        b'@@ -1 +0,0 @@\n'
                        b'-all: all\n'
                    )),
            ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        self.assertSpyCallCount(run_process_exec, 2)

    def test_patch_with_revert(self) -> None:
        """Testing PerforcePatcher.patch with revert=True"""
        client = self.build_client()
        repository_info = client.get_repository_info()
        tempfiles = self.precreate_tempfiles(1)

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-R', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        patcher = client.get_patcher(
            repository_info=repository_info,
            revert=True,
            patches=[
                Patch(content=(
                    b'--- //mydepot/test/README\t//mydepot/test/README#2\n'
                    b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
                    b'@@ -1 +1 @@\n'
                    b'-This is a test.\n'
                    b'+This is a mess.\n'
                    b'--- //mydepot/test/COPYING\t//mydepot/test/COPYING#0\n'
                    b'+++ //mydepot/test/COPYING\t2022-01-02 12:34:56\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+Copyright 2013 Joe User.\n'
                    b'--- //mydepot/test/Makefile\t//mydepot/test/Makefile#3\n'
                    b'+++ //mydepot/test/Makefile\t2022-01-02 12:34:56\n'
                    b'@@ -1 +0,0 @@\n'
                    b'-all: all\n'
                )),
            ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        self.assertSpyCallCount(run_process_exec, 2)

    def test_patch_with_empty_files(self) -> None:
        """Testing PerforcePatcher.patch with empty files"""
        client = self.build_client(caps={
            'scmtools': {
                'perforce': {
                    'empty_files': True,
                },
            },
        })
        repository_info = client.get_repository_info()

        tempfiles = self.precreate_tempfiles(1)
        tempdir = make_tempdir()
        readme_file = os.path.join(tempdir, 'README')
        new_file = os.path.join(tempdir, 'NEWFILE')

        with open(readme_file, mode='w', encoding='utf-8'):
            pass

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/NEWFILE': new_file,
        }

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((
                    2,
                    b"  I can't seem to find a patch in there anywhere.\n",
                    b'',
                )),
            },
            {
                'args': (['p4', 'add', new_file],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'delete', readme_file],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[
                Patch(content=(
                    b'==== //mydepot/test/README#1 ==D=='
                    b' //mydepot/test/README#1 ====\n'
                    b'==== //mydepot/test/NEWFILE#1 ==A=='
                    b' //mydepot/test/NEWFILE#1 ====\n'
                )),
            ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        self.assertSpyCallCount(run_process_exec, 4)

        self.assertTrue(os.path.exists(new_file))

    def test_patch_binary_file_add(self) -> None:
        """Testing PerforcePatcher.patch with an added binary file"""
        client = self.build_client()
        repository_info = client.get_repository_info()
        tempdir = make_tempdir()

        test_content = b'Binary file content'
        test_path = '//mydepot/test/new_binary_file.bin'
        local_path = os.path.join(tempdir, 'new_binary_file.bin')

        client.p4.where_files = {
            test_path: local_path,
        }

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 123,
                'absolute_url': 'https://example.com/r/1/file/123/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/123/'
        )

        binary_file = self.make_binary_file_patch(
            old_path=None,
            new_path=test_path,
            status='added',
            file_attachment=attachment,
            content=test_content,
        )

        tempfiles = self.precreate_tempfiles(1)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'edit', local_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'add', local_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        patch_content = (
            b'==== //mydepot/test/new_binary_file.bin#0 ==A== '
            b'//mydepot/test/new_binary_file.bin ====\n'
        )
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], local_path)

        self.assertTrue(os.path.exists(local_path))

        with open(local_path, 'rb') as f:
            self.assertEqual(f.read(), test_content)

        self.assertSpyCallCount(run_process_exec, 4)

    def test_patch_binary_file_modify(self) -> None:
        """Testing PerforcePatcher.patch with a modified binary file"""
        client = self.build_client()
        repository_info = client.get_repository_info()
        tempdir = make_tempdir()

        old_content = b'Old binary content'
        new_content = b'New binary content'
        test_path = '//mydepot/test/modified_file.bin'
        local_path = os.path.join(tempdir, 'modified_file.bin')

        with open(local_path, 'wb') as f:
            f.write(old_content)

        client.p4.where_files = {
            test_path: local_path,
        }

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 124,
                'absolute_url': 'https://example.com/r/1/file/124/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/124/'
        )

        binary_file = self.make_binary_file_patch(
            old_path=test_path,
            new_path=test_path,
            status='modified',
            file_attachment=attachment,
            content=new_content,
        )

        tempfiles = self.precreate_tempfiles(1)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'edit', local_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        temp1 = os.path.join(tempdir, 'temp1')
        temp2 = os.path.join(tempdir, 'temp2')
        patch_content = (
            f'==== //mydepot/test/modified_file.bin#1 ==M== '
            f'//mydepot/test/modified_file.bin ====\n'
            f'Binary files {temp1} and {temp2} differ\n'
        ).encode()
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], local_path)

        self.assertTrue(os.path.exists(local_path))

        with open(local_path, 'rb') as f:
            self.assertEqual(f.read(), new_content)

        self.assertSpyCallCount(run_process_exec, 3)

    def test_patch_binary_file_move(self) -> None:
        """Testing PerforcePatcher.patch with a moved binary file"""
        client = self.build_client()
        repository_info = client.get_repository_info()
        tempdir = make_tempdir()

        old_path = '//mydepot/test/old_file.bin'
        new_path = '//mydepot/test/new_file.bin'
        local_old_path = os.path.join(tempdir, 'old_file.bin')
        local_new_path = os.path.join(tempdir, 'new_file.bin')
        test_content = b'Binary file content'
        temp1 = os.path.join(tempdir, 'temp1')
        temp2 = os.path.join(tempdir, 'temp2')

        with open(local_old_path, 'wb') as f:
            f.write(b'Old file content')

        client.p4.where_files = {
            old_path: local_old_path,
            new_path: local_new_path,
        }

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 125,
                'absolute_url': 'https://example.com/r/1/file/125/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/125/'
        )

        binary_file = self.make_binary_file_patch(
            old_path=old_path,
            new_path=new_path,
            status='moved',
            file_attachment=attachment,
            content=test_content,
        )

        tempfiles = self.precreate_tempfiles(1)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'edit', local_old_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'move', local_old_path, local_new_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'edit', local_new_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        patch_content = (
            b'Moved from: //mydepot/test/old_file.bin\n'
            b'Moved to: //mydepot/test/new_file.bin\n'
            b'==== //mydepot/test/old_file.bin#1 ==MV== '
            b'//mydepot/test/new_file.bin ====\n'
            b'Binary files %s and %s differ\n'
            % (temp1.encode('utf-8'), temp2.encode('utf-8'))
        )
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], local_new_path)

        self.assertTrue(os.path.exists(local_new_path))

        with open(local_new_path, 'rb') as f:
            self.assertEqual(f.read(), test_content)

        self.assertSpyCallCount(run_process_exec, 5)

    def test_patch_binary_file_remove(self) -> None:
        """Testing PerforcePatcher.patch with a removed binary file"""
        client = self.build_client()
        repository_info = client.get_repository_info()
        tempdir = make_tempdir()

        test_path = '//mydepot/test/file_to_remove.bin'
        local_path = os.path.join(tempdir, 'file_to_remove.bin')
        test_content = b'Binary file content'

        with open(local_path, 'wb') as f:
            f.write(test_content)

        client.p4.where_files = {
            test_path: local_path,
        }

        binary_file = BinaryFilePatch(
            old_path=test_path,
            new_path=None,
            status='deleted',
            file_attachment=None,
        )

        tempfiles = self.precreate_tempfiles(1)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'delete', local_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        temp1 = os.path.join(tempdir, 'temp1')
        temp2 = os.path.join(tempdir, 'temp2')
        patch_content = (
            f'==== //mydepot/test/file_to_remove.bin#1 ==D== '
            f'//mydepot/test/file_to_remove.bin ====\n'
            f'Binary files {temp1} and {temp2} differ\n'
        ).encode()
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], local_path)

        self.assertSpyCallCount(run_process_exec, 3)

    def test_patch_with_regular_and_empty_files(self) -> None:
        """Testing PerforcePatcher.patch with regular and empty files."""
        client = self.build_client(caps={
            'scmtools': {
                'perforce': {
                    'empty_files': True,
                },
            },
        })
        repository_info = client.get_repository_info()

        tempfiles = self.precreate_tempfiles(1)
        tempdir = make_tempdir()
        readme_file = os.path.join(tempdir, 'README')
        empty_file = os.path.join(tempdir, 'EMPTYFILE')
        deleted_empty_file = os.path.join(tempdir, 'DELETED_EMPTY')

        with open(deleted_empty_file, mode='w', encoding='utf-8'):
            pass

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/EMPTYFILE': empty_file,
            '//mydepot/test/DELETED_EMPTY': deleted_empty_file,
        }

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'add', empty_file],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'delete', deleted_empty_file],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[
                Patch(content=(
                    b'--- //mydepot/test/README\t//mydepot/test/README#2\n'
                    b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
                    b'@@ -1 +1 @@\n'
                    b'-This is a test.\n'
                    b'+This is updated.\n'
                    b'==== //mydepot/test/EMPTYFILE#1 ==A== '
                    b'//mydepot/test/EMPTYFILE#1 ====\n'
                    b'==== //mydepot/test/DELETED_EMPTY#1 ==D== '
                    b'//mydepot/test/DELETED_EMPTY#1 ====\n'
                )),
            ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        self.assertSpyCallCount(run_process_exec, 4)
        self.assertTrue(os.path.exists(empty_file))

    def test_patch_with_regular_and_binary_files(self) -> None:
        """Testing PerforcePatcher.patch with regular and binary files."""
        client = self.build_client()
        repository_info = client.get_repository_info()
        tempdir = make_tempdir()

        readme_file = os.path.join(tempdir, 'README')
        binary_file_path = '//mydepot/test/image.png'
        local_binary_path = os.path.join(tempdir, 'image.png')
        modified_binary_path = '//mydepot/test/document.pdf'
        local_modified_binary = os.path.join(tempdir, 'document.pdf')

        old_binary_content = b'\x89PNG old content'
        with open(local_modified_binary, 'wb') as f:
            f.write(old_binary_content)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            binary_file_path: local_binary_path,
            modified_binary_path: local_modified_binary,
        }

        attachment_new = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 200,
                'absolute_url': 'https://example.com/r/1/file/200/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/200/'
        )

        attachment_modified = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 201,
                'absolute_url': 'https://example.com/r/1/file/201/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/201/'
        )

        new_binary_content = b'\x89PNG new image content'
        modified_binary_content = b'%PDF modified content'

        binary_file_new = self.make_binary_file_patch(
            old_path=None,
            new_path=binary_file_path,
            status='added',
            file_attachment=attachment_new,
            content=new_binary_content,
        )

        binary_file_modified = self.make_binary_file_patch(
            old_path=modified_binary_path,
            new_path=modified_binary_path,
            status='modified',
            file_attachment=attachment_modified,
            content=modified_binary_content,
        )

        tempfiles = self.precreate_tempfiles(1)
        temp1 = os.path.join(tempdir, 'temp1')
        temp2 = os.path.join(tempdir, 'temp2')

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['patch', '-f', '-i', tempfiles[0]],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'edit', local_binary_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'add', local_binary_path],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'edit', local_modified_binary],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
            {
                'args': (['p4', 'reconcile'],),
                'op': kgb.SpyOpReturn((0, b'', b'')),
            },
        ]))

        patch_content = (
            b'--- //mydepot/test/README\t//mydepot/test/README#5\n'
            b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
            b'@@ -1,3 +1,4 @@\n'
            b' Line 1\n'
            b'-Line 2\n'
            b'+Line 2 modified\n'
            b'+Line 2.5 added\n'
            b' Line 3\n'
            b'==== //mydepot/test/image.png#0 ==A== '
            b'//mydepot/test/image.png ====\n'
            b'==== //mydepot/test/document.pdf#1 ==M== '
            b'//mydepot/test/document.pdf ====\n'
            b'Binary files %s and %s differ\n'
            % (temp1.encode('utf-8'), temp2.encode('utf-8'))
        )

        patch = Patch(
            content=patch_content,
            binary_files=[binary_file_new, binary_file_modified]
        )
        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 2)
        self.assertIn(local_binary_path, result.binary_applied)
        self.assertIn(local_modified_binary, result.binary_applied)

        self.assertTrue(os.path.exists(local_binary_path))
        with open(local_binary_path, 'rb') as f:
            self.assertEqual(f.read(), new_binary_content)

        self.assertTrue(os.path.exists(local_modified_binary))
        with open(local_modified_binary, 'rb') as f:
            self.assertEqual(f.read(), modified_binary_content)

        self.assertSpyCallCount(run_process_exec, 5)

    def test_patch_with_empty_and_binary_files(self) -> None:
        """Testing PerforcePatcher.patch with empty and binary files."""
        client = self.build_client(caps={
            'scmtools': {
                'perforce': {
                    'empty_files': True,
                },
            },
        })
        repository_info = client.get_repository_info()
        tempdir = make_tempdir()

        empty_added = os.path.join(tempdir, 'EMPTY_ADDED')
        empty_deleted = os.path.join(tempdir, 'EMPTY_DELETED')
        binary_path = '//mydepot/test/archive.zip'
        local_binary = os.path.join(tempdir, 'archive.zip')

        with open(empty_deleted, mode='w', encoding='utf-8') as f:
            pass

        client.p4.where_files = {
            '//mydepot/test/EMPTY_ADDED': empty_added,
            '//mydepot/test/EMPTY_DELETED': empty_deleted,
            binary_path: local_binary,
        }

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 300,
                'absolute_url': 'https://example.com/r/1/file/300/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/300/'
        )

        binary_content = b'PK\x03\x04 zip file content'
        binary_file = self.make_binary_file_patch(
            old_path=None,
            new_path=binary_path,
            status='added',
            file_attachment=attachment,
            content=binary_content,
        )

        self.spy_on(run_process_exec, op=kgb.SpyOpReturn((0, b'', b'')))

        patch_content = (
            b'==== //mydepot/test/EMPTY_ADDED#1 ==A== '
            b'//mydepot/test/EMPTY_ADDED#1 ====\n'
            b'==== //mydepot/test/EMPTY_DELETED#1 ==D== '
            b'//mydepot/test/EMPTY_DELETED#1 ====\n'
            b'==== //mydepot/test/archive.zip#0 ==A== '
            b'//mydepot/test/archive.zip ====\n'
        )

        patch = Patch(
            content=patch_content,
            binary_files=[binary_file]
        )
        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], local_binary)

        self.assertTrue(os.path.exists(empty_added))
        self.assertTrue(os.path.exists(local_binary))

        with open(local_binary, 'rb') as f:
            self.assertEqual(f.read(), binary_content)

        self.assertSpyCalledWith(
            run_process_exec,
            ['p4', 'reconcile'])

    def test_patch_with_mixed_operations(self) -> None:
        """Testing PerforcePatcher.patch with all file types and operations.

        This test combines regular files, empty files, and binary files with
        various operations (add, modify, delete, move) in a single patch.
        """
        client = self.build_client(caps={
            'scmtools': {
                'perforce': {
                    'empty_files': True,
                },
            },
        })
        repository_info = client.get_repository_info()
        tempdir = make_tempdir()

        readme_file = os.path.join(tempdir, 'README')
        makefile = os.path.join(tempdir, 'Makefile')

        empty_added = os.path.join(tempdir, 'EMPTY_NEW')
        empty_deleted = os.path.join(tempdir, 'EMPTY_OLD')

        binary_new_path = '//mydepot/test/icon.png'
        local_binary_new = os.path.join(tempdir, 'icon.png')
        binary_modified_path = '//mydepot/test/data.bin'
        local_binary_modified = os.path.join(tempdir, 'data.bin')
        binary_deleted_path = '//mydepot/test/old.exe'
        local_binary_deleted = os.path.join(tempdir, 'old.exe')
        binary_moved_old_path = '//mydepot/test/old_name.dll'
        binary_moved_new_path = '//mydepot/test/new_name.dll'
        local_binary_moved_old = os.path.join(tempdir, 'old_name.dll')
        local_binary_moved_new = os.path.join(tempdir, 'new_name.dll')

        with open(empty_deleted, mode='w', encoding='utf-8') as f:
            pass

        with open(local_binary_modified, 'wb') as f:
            f.write(b'\x00\x01\x02 old data')

        with open(local_binary_deleted, 'wb') as f:
            f.write(b'exe content to delete')

        with open(local_binary_moved_old, 'wb') as f:
            f.write(b'dll to move')

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/Makefile': makefile,
            '//mydepot/test/EMPTY_NEW': empty_added,
            '//mydepot/test/EMPTY_OLD': empty_deleted,
            binary_new_path: local_binary_new,
            binary_modified_path: local_binary_modified,
            binary_deleted_path: local_binary_deleted,
            binary_moved_old_path: local_binary_moved_old,
            binary_moved_new_path: local_binary_moved_new,
        }

        attachment_new = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 400,
                'absolute_url': 'https://example.com/r/1/file/400/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/400/'
        )

        attachment_modified = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 401,
                'absolute_url': 'https://example.com/r/1/file/401/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/401/'
        )

        attachment_moved = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 402,
                'absolute_url': 'https://example.com/r/1/file/402/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/402/'
        )

        binary_new_content = b'\x89PNG new icon'
        binary_modified_content = b'\x00\x01\x02 new data'
        binary_moved_content = b'dll moved content'

        binary_file_new = self.make_binary_file_patch(
            old_path=None,
            new_path=binary_new_path,
            status='added',
            file_attachment=attachment_new,
            content=binary_new_content,
        )

        binary_file_modified = self.make_binary_file_patch(
            old_path=binary_modified_path,
            new_path=binary_modified_path,
            status='modified',
            file_attachment=attachment_modified,
            content=binary_modified_content,
        )

        binary_file_deleted = BinaryFilePatch(
            old_path=binary_deleted_path,
            new_path=None,
            status='deleted',
            file_attachment=None,
        )

        binary_file_moved = self.make_binary_file_patch(
            old_path=binary_moved_old_path,
            new_path=binary_moved_new_path,
            status='moved',
            file_attachment=attachment_moved,
            content=binary_moved_content,
        )

        temp1 = os.path.join(tempdir, 'temp1')
        temp2 = os.path.join(tempdir, 'temp2')

        self.spy_on(run_process_exec, op=kgb.SpyOpReturn((0, b'', b'')))

        patch_content = (
            b'--- //mydepot/test/README\t//mydepot/test/README#3\n'
            b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
            b'@@ -1,2 +1,3 @@\n'
            b' README content\n'
            b'-Version 1\n'
            b'+Version 2\n'
            b'+New line\n'
            b'--- //mydepot/test/Makefile\t//mydepot/test/Makefile#1\n'
            b'+++ //mydepot/test/Makefile\t2022-01-02 12:34:56\n'
            b'@@ -1 +0,0 @@\n'
            b'-all: test\n'
            b'==== //mydepot/test/EMPTY_NEW#1 ==A== '
            b'//mydepot/test/EMPTY_NEW#1 ====\n'
            b'==== //mydepot/test/EMPTY_OLD#1 ==D== '
            b'//mydepot/test/EMPTY_OLD#1 ====\n'
            b'==== //mydepot/test/icon.png#0 ==A== '
            b'//mydepot/test/icon.png ====\n'
            b'==== //mydepot/test/data.bin#2 ==M== '
            b'//mydepot/test/data.bin ====\n'
            b'Binary files %s and %s differ\n'
            b'==== //mydepot/test/old.exe#5 ==D== '
            b'//mydepot/test/old.exe ====\n'
            b'Binary files %s and %s differ\n'
            b'Moved from: //mydepot/test/old_name.dll\n'
            b'Moved to: //mydepot/test/new_name.dll\n'
            b'==== //mydepot/test/old_name.dll#1 ==MV== '
            b'//mydepot/test/new_name.dll ====\n'
            b'Binary files %s and %s differ\n'
            % (temp1.encode('utf-8'), temp2.encode('utf-8'),
               temp1.encode('utf-8'), temp2.encode('utf-8'),
               temp1.encode('utf-8'), temp2.encode('utf-8'))
        )

        patch = Patch(
            content=patch_content,
            binary_files=[
                binary_file_new,
                binary_file_modified,
                binary_file_deleted,
                binary_file_moved,
            ]
        )
        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 4)

        self.assertIn(local_binary_new, result.binary_applied)
        self.assertIn(local_binary_modified, result.binary_applied)
        self.assertIn(local_binary_deleted, result.binary_applied)
        self.assertIn(local_binary_moved_new, result.binary_applied)

        self.assertTrue(os.path.exists(local_binary_new))
        with open(local_binary_new, 'rb') as f:
            self.assertEqual(f.read(), binary_new_content)

        self.assertTrue(os.path.exists(local_binary_modified))
        with open(local_binary_modified, 'rb') as f:
            self.assertEqual(f.read(), binary_modified_content)

        self.assertTrue(os.path.exists(local_binary_moved_new))
        with open(local_binary_moved_new, 'rb') as f:
            self.assertEqual(f.read(), binary_moved_content)

        self.assertTrue(os.path.exists(empty_added))

        self.assertSpyCalledWith(
            run_process_exec,
            ['p4', 'reconcile'])

    def test_patch_with_mixed_files_and_patch_failure(self) -> None:
        """Testing PerforcePatcher.patch with mixed files when patch fails.

        This tests the scenario where the patch command fails on regular
        files but empty and binary files should still be processed correctly.
        """
        client = self.build_client(caps={
            'scmtools': {
                'perforce': {
                    'empty_files': True,
                },
            },
        })
        repository_info = client.get_repository_info()
        tempdir = make_tempdir()

        readme_file = os.path.join(tempdir, 'README')
        empty_file = os.path.join(tempdir, 'EMPTY')
        binary_path = '//mydepot/test/file.bin'
        local_binary = os.path.join(tempdir, 'file.bin')

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/EMPTY': empty_file,
            binary_path: local_binary,
        }

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 500,
                'absolute_url': 'https://example.com/r/1/file/500/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/500/'
        )

        binary_content = b'binary content'
        binary_file = self.make_binary_file_patch(
            old_path=None,
            new_path=binary_path,
            status='added',
            file_attachment=attachment,
            content=binary_content,
        )

        def process_spy(*args, **kwargs) -> tuple[int, bytes, bytes]:
            cmd = args[0] if args else kwargs.get('command', [])

            if cmd and cmd[0] == 'patch':
                return (1, b'', b'patch: **** malformed patch\n')

            return (0, b'', b'')

        self.spy_on(run_process_exec, call_fake=process_spy)

        patch_content = (
            b'--- //mydepot/test/README\t//mydepot/test/README#1\n'
            b'+++ //mydepot/test/README\t2022-01-02 12:34:56\n'
            b'@@ -1 +1 @@\n'
            b'malformed content\n'
            b'==== //mydepot/test/EMPTY#1 ==A== '
            b'//mydepot/test/EMPTY#1 ====\n'
            b'==== //mydepot/test/file.bin#0 ==A== '
            b'//mydepot/test/file.bin ====\n'
        )

        patch = Patch(
            content=patch_content,
            binary_files=[binary_file]
        )
        patcher = client.get_patcher(
            repository_info=repository_info,
            patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]

        # The patch may still succeed overall even if patch command fails,
        # as long as empty and binary files are applied correctly.
        # We mainly care that binary files were still applied.
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], local_binary)

        self.assertTrue(os.path.exists(local_binary))
        with open(local_binary, 'rb') as f:
            self.assertEqual(f.read(), binary_content)

        self.assertTrue(os.path.exists(empty_file))
