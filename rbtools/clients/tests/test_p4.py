"""Unit tests for PerforceClient."""

from __future__ import unicode_literals

import os
import re
import time
from hashlib import md5

from rbtools.api.capabilities import Capabilities
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError)
from rbtools.clients.perforce import PerforceClient, P4Wrapper
from rbtools.clients.tests import SCMClientTests
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.testbase import RBTestBase


class P4WrapperTests(RBTestBase):
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

        self.assertEqual(len(info), 3)
        self.assertEqual(info['a'], '1')
        self.assertEqual(info['b'], '2')
        self.assertEqual(info['c'], '3')

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

        self.assertEqual(len(info), 5)
        self.assertEqual(info['User name'], 'myuser')
        self.assertEqual(info['Client name'], 'myclient')
        self.assertEqual(info['Client host'], 'myclient.example.com')
        self.assertEqual(info['Client root'], '/path/to/client')
        self.assertEqual(info['Server uptime'], '111:43:38')


class PerforceClientTests(SCMClientTests):
    """Unit tests for PerforceClient."""

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

    def test_scan_for_server_counter_with_reviewboard_url(self):
        """Testing PerforceClient.scan_for_server_counter with
        reviewboard.url"""
        RB_URL = 'http://reviewboard.example.com/'

        class TestWrapper(P4Wrapper):
            def counters(self):
                return {
                    'reviewboard.url': RB_URL,
                    'foo': 'bar',
                }

        client = PerforceClient(TestWrapper)
        url = client.scan_for_server_counter(None)

        self.assertEqual(url, RB_URL)

    def test_repository_info(self):
        """Testing PerforceClient.get_repository_info"""
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def is_supported(self):
                return True

            def info(self):
                return {
                    'Client root': os.getcwd(),
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = PerforceClient(TestWrapper)
        info = client.get_repository_info()

        self.assertNotEqual(info, None)
        self.assertEqual(info.path, SERVER_PATH)
        self.assertEqual(client.p4d_version, (2012, 2))

    def test_repository_info_outside_client_root(self):
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

        client = PerforceClient(TestWrapper)
        info = client.get_repository_info()

        self.assertEqual(info, None)

    def test_scan_for_server_counter_with_reviewboard_url_encoded(self):
        """Testing PerforceClient.scan_for_server_counter with encoded
        reviewboard.url.http:||"""
        URL_KEY = 'reviewboard.url.http:||reviewboard.example.com/'
        RB_URL = 'http://reviewboard.example.com/'

        class TestWrapper(P4Wrapper):
            def counters(self):
                return {
                    URL_KEY: '1',
                    'foo': 'bar',
                }

        client = PerforceClient(TestWrapper)
        url = client.scan_for_server_counter(None)

        self.assertEqual(url, RB_URL)

    def test_diff_with_pending_changelist(self):
        """Testing PerforceClient.diff with a pending changelist"""
        client = self._build_client()
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
        diff = client.diff(revisions)
        self._compare_diff(diff, '07aa18ff67f9aa615fcda7ecddcb354e')

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

        client = PerforceClient(TestWrapper)
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
        diff = client.diff(revisions)
        self._compare_diff(diff, '8af5576f5192ca87731673030efb5f39',
                           expect_changenum=False)

    def test_diff_with_moved_files_cap_on(self):
        """Testing PerforceClient.diff with moved files and capability on"""
        self._test_diff_with_moved_files(
            '5926515eaf4cf6d8257a52f7d9f0e530',
            caps={
                'scmtools': {
                    'perforce': {
                        'moved_files': True
                    }
                }
            })

    def test_diff_with_moved_files_cap_off(self):
        """Testing PerforceClient.diff with moved files and capability off"""
        self._test_diff_with_moved_files('20e5ab395e170dce1b062a796e6c2c13')

    def _test_diff_with_moved_files(self, expected_diff_hash, caps={}):
        client = self._build_client()
        client.capabilities = Capabilities(caps)
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
        diff = client.diff(revisions)
        self._compare_diff(diff, expected_diff_hash)

    def _build_client(self):
        self.options.p4_client = 'myclient'
        self.options.p4_port = 'perforce.example.com:1666'
        self.options.p4_passwd = ''
        client = PerforceClient(self.P4DiffTestWrapper, options=self.options)
        client.p4d_version = (2012, 2)
        return client

    def _compare_diff(self, diff_info, expected_diff_hash,
                      expect_changenum=True):
        self.assertTrue(isinstance(diff_info, dict))
        self.assertTrue('diff' in diff_info)
        if expect_changenum:
            self.assertTrue('changenum' in diff_info)

        diff_content = re.sub(br'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                              br'1970-01-01 00:00:00',
                              diff_info['diff'])
        self.assertEqual(md5(diff_content).hexdigest(), expected_diff_hash)

    def test_parse_revision_spec_no_args(self):
        """Testing PerforceClient.parse_revision_spec with no specified
        revisions"""
        client = self._build_client()

        revisions = client.parse_revision_spec()
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertEqual(
            revisions['base'], PerforceClient.REVISION_CURRENT_SYNC)
        self.assertEqual(
            revisions['tip'],
            PerforceClient.REVISION_PENDING_CLN_PREFIX + 'default')

    def test_parse_revision_spec_pending_cln(self):
        """Testing PerforceClient.parse_revision_spec with a pending
        changelist"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'pending',
                    'Description': 'My change description\n',
                }]
        client = PerforceClient(TestWrapper)

        revisions = client.parse_revision_spec(['12345'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(
            revisions['base'], PerforceClient.REVISION_CURRENT_SYNC)
        self.assertEqual(
            revisions['tip'],
            PerforceClient.REVISION_PENDING_CLN_PREFIX + '12345')

    def test_parse_revision_spec_submitted_cln(self):
        """Testing PerforceClient.parse_revision_spec with a submitted
        changelist"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'submitted',
                    'Description': 'My change description\n',
                }]

        client = PerforceClient(TestWrapper)

        revisions = client.parse_revision_spec(['12345'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], '12344')
        self.assertEqual(revisions['tip'], '12345')

    def test_parse_revision_spec_shelved_cln(self):
        """Testing PerforceClient.parse_revision_spec with a shelved
        changelist"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'shelved',
                    'Description': 'My change description\n',
                }]
        client = PerforceClient(TestWrapper)

        revisions = client.parse_revision_spec(['12345'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(
            revisions['base'], PerforceClient.REVISION_CURRENT_SYNC)
        self.assertEqual(
            revisions['tip'],
            PerforceClient.REVISION_PENDING_CLN_PREFIX + '12345')

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

        client = PerforceClient(TestWrapper)

        revisions = client.parse_revision_spec(['99', '100'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], '99')
        self.assertEqual(revisions['tip'], '100')

        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['99', '101'])
        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['99', '102'])
        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['101', '100'])
        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['102', '100'])
        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['102', '10284'])

    def test_parse_revision_spec_invalid_spec(self):
        """Testing PerforceClient.parse_revision_spec with invalid
        specifications"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return []

        client = PerforceClient(TestWrapper)

        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['aoeu'])

        self.assertRaises(TooManyRevisionsError,
                          client.parse_revision_spec,
                          ['1', '2', '3'])

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

        client = PerforceClient(ExcludeWrapper)

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
