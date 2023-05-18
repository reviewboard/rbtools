"""Unit tests for PerforceClient."""

import os
import re
import time
from typing import Type

import kgb

from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    TooManyRevisionsError)
from rbtools.clients.perforce import PerforceClient, P4Wrapper
from rbtools.clients.tests import SCMClientTestCase
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.testing import TestCase
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_tempfile


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


class P4WrapperTests(TestCase):
    """Unit tests for P4Wrapper."""

    def is_supported(self):
        return True

    def test_counters(self):
        """Testing P4Wrapper.counters"""
        class TestWrapper(P4Wrapper):
            def run_p4(self, cmd, *args, **kwargs):
                return [
                    'a = 1\n',
                    'b = 2\n',
                    'c = 3\n',
                ]

        p4 = TestWrapper(None)
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
        class TestWrapper(P4Wrapper):
            def run_p4(self, cmd, *args, **kwargs):
                return [
                    'User name: myuser\n',
                    'Client name: myclient\n',
                    'Client host: myclient.example.com\n',
                    'Client root: /path/to/client\n',
                    'Server uptime: 111:43:38\n',
                ]

        p4 = TestWrapper(None)
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


class PerforceClientTests(SCMClientTestCase):
    """Unit tests for PerforceClient."""

    scmclient_cls = PerforceClient

    default_scmclient_options = {
        'p4_client': 'myclient',
        'p4_passwd': '',
        'p4_port': 'perforce.example.com:1666',
    }

    class P4DiffTestWrapper(P4Wrapper):
        def __init__(self, options):
            super(
                PerforceClientTests.P4DiffTestWrapper, self).__init__(options)

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

    def setUp(self):
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
        wrapper_cls: Type[P4Wrapper] = P4DiffTestWrapper,
        **kwargs,
    ) -> PerforceClient:
        """Build a client for testing.

        THis will set default command line options for the client and
        server, and allow for specifying a custom Perforce wrapper class.

        Version Added:
            4.0

        Args:
            wrapper_cls (type, optional):
                The P4 wrapper class to pass to the client.

            **kwargs (dict, optional):
                Additional keyword arguments to pass to the parent method.

        Returns:
            rbtools.clients.perforce.PerforceClient:
            The client instance.
        """
        return super(PerforceClientTests, self).build_client(
            client_kwargs={
                'p4_class': wrapper_cls,
            },
            **kwargs)

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

    def test_get_local_path_with_deps_missing(self):
        """Testing PerforceClient.get_local_path with dependencies missing"""
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
                         'Unable to execute "p4 help": skipping Perforce')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['p4', 'help'])

    def test_get_local_path_with_deps_not_checked(self):
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
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_local_path()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "p4 help": skipping Perforce')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['p4', 'help'])

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
        class TestWrapper(self.P4DiffTestWrapper):
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
            client.parse_revision_spec(),
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
