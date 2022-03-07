"""Unit tests for ClearCaseClient."""

from __future__ import unicode_literals

import os
import unittest

import kgb
import six

from rbtools.clients.clearcase import ClearCaseClient, ClearCaseRepositoryInfo
from rbtools.clients.errors import SCMError
from rbtools.clients.tests import SCMClientTestCase
from rbtools.utils.checks import check_gnu_diff
from rbtools.utils.filesystem import is_exe_in_path
from rbtools.utils.process import execute


_SNAPSHOT_VIEW_INFO = [
    '  snapshot-view-test',
    '/home/user/stgloc_view1/user/snapshot-view-test.vws',
    'Created 2021-06-18T18:10:32-04:00 by user.user@localhost.localdomain',
    ('Last modified 2021-06-24T17:01:39-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last accessed 2021-06-24T17:01:39-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last read of private data 2021-06-24T17:01:39-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last config spec update 2021-06-24T15:40:22-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last view private object update 2021-06-24T17:01:39-04:00 by '
     'user.user@localhost.localdomain'),
    'Text mode: unix',
    'Properties: snapshot readwrite',
    'Owner: user            : rwx (all)',
    'Group: user            : rwx (all)',
    'Other:                  : r-x (read)',
    'Additional groups: wheel',
]


_DYNAMIC_VIEW_INFO = [
    '* test-view            /viewstore/test-view.vbs',
    'Created 2021-06-10T01:49:46-04:00 by user.user@localhost.localdomain',
    ('Last modified 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last accessed 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last config spec update 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    'Text mode: unix',
    'Properties: dynamic readwrite shareable_dos',
    'Owner: user            : rwx (all)',
    'Group: user            : rwx (all)',
    'Other:                  : r-x (read)',
    'Additional groups: wheel',
]


_UCM_VIEW_INFO = [
    '* development-view            /viewstore/development-view.vbs',
    'Created 2021-06-10T01:49:46-04:00 by user.user@localhost.localdomain',
    ('Last modified 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last accessed 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last config spec update 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    'Text mode: unix',
    'Properties: dynamic ucmview readwrite shareable_dos',
    'Owner: user            : rwx (all)',
    'Group: user            : rwx (all)',
    'Other:                  : r-x (read)',
    'Additional groups: wheel',
]


_AUTOMATIC_VIEW_INFO = [
    '* development-view            /viewstore/development-view.vbs',
    'Created 2021-06-10T01:49:46-04:00 by user.user@localhost.localdomain',
    ('Last modified 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last accessed 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last config spec update 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    'Text mode: unix',
    'Properties: automatic readwrite shareable_dos',
    'Owner: user            : rwx (all)',
    'Group: user            : rwx (all)',
    'Other:                  : r-x (read)',
    'Additional groups: wheel',
]


_WEBVIEW_VIEW_INFO = [
    '* development-view            /viewstore/development-view.vbs',
    'Created 2021-06-10T01:49:46-04:00 by user.user@localhost.localdomain',
    ('Last modified 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last accessed 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    ('Last config spec update 2021-06-10T01:49:46-04:00 by '
     'user.user@localhost.localdomain'),
    'Text mode: unix',
    'Properties: webview readwrite shareable_dos',
    'Owner: user            : rwx (all)',
    'Group: user            : rwx (all)',
    'Other:                  : r-x (read)',
    'Additional groups: wheel',
]


class ClearCaseClientTests(kgb.SpyAgency, SCMClientTestCase):
    """Unit tests for ClearCaseClient."""

    @unittest.skipIf(not is_exe_in_path('cleartool'),
                     'cleartool not found in path')
    def setUp(self):
        super(ClearCaseClientTests, self).setUp()

        self.set_user_home(
            os.path.join(self.testdata_dir, 'homedir'))
        self.client = ClearCaseClient(options=self.options)

    def test_get_local_path_outside_view(self):
        """Testing ClearCaseClient.get_local_path outside of view"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn('** NONE **'),
            },
        ]))

        self.assertEqual(self.client.get_local_path(), None)

    def test_get_local_path_inside_view(self):
        """Testing ClearCaseClient.get_local_path inside view"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn('test-view'),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn('/test/view'),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn('vob'),
            },
        ]))

        self.assertEqual(self.client.get_local_path(), '/test/view/vob')

    def test_get_repository_info_snapshot(self):
        """Testing ClearCaseClient.get_repository_info with snapshot view"""
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn('test-view'),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn('/test/view'),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn('vob'),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn(_SNAPSHOT_VIEW_INFO),
            },
        ]))

        repository_info = self.client.get_repository_info()
        self.assertEqual(repository_info.path, '/test/view/vob')
        self.assertEqual(repository_info.vobtag, 'vob')
        self.assertEqual(repository_info.vob_tags, {'vob'})

        # Initial state that gets populated later by update_from_remote
        self.assertEqual(repository_info.uuid_to_tags, {})
        self.assertEqual(repository_info.is_legacy, True)

        self.assertEqual(self.client.viewtype, 'snapshot')
        self.assertEqual(self.client.is_ucm, False)

    def test_get_repository_info_dynamic(self):
        """Testing ClearCaseClient.get_repository_info with dynamic view and
        base ClearCase
        """
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn('test-view'),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn('/test/view'),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn('vob'),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn(_DYNAMIC_VIEW_INFO),
            },
        ]))

        repository_info = self.client.get_repository_info()
        self.assertEqual(repository_info.path, '/test/view/vob')
        self.assertEqual(repository_info.vobtag, 'vob')
        self.assertEqual(repository_info.vob_tags, {'vob'})

        # Initial state that gets populated later by update_from_remote
        self.assertEqual(repository_info.uuid_to_tags, {})
        self.assertEqual(repository_info.is_legacy, True)

        self.assertEqual(self.client.viewtype, 'dynamic')
        self.assertEqual(self.client.is_ucm, False)

    def test_get_repository_info_dynamic_UCM(self):
        """Testing ClearCaseClient.get_repository_info with dynamic view and UCM
        """
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn('test-view'),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn('/test/view'),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn('vob'),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn(_UCM_VIEW_INFO),
            },
        ]))

        repository_info = self.client.get_repository_info()
        self.assertEqual(repository_info.path, '/test/view/vob')
        self.assertEqual(repository_info.vobtag, 'vob')
        self.assertEqual(repository_info.vob_tags, {'vob'})

        # Initial state that gets populated later by update_from_remote
        self.assertEqual(repository_info.uuid_to_tags, {})
        self.assertEqual(repository_info.is_legacy, True)

        self.assertEqual(self.client.viewtype, 'dynamic')
        self.assertEqual(self.client.is_ucm, True)

    def test_get_repository_info_automatic(self):
        """Testing ClearCaseClient.get_repository_info with automatic view"""
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn('test-view'),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn('/test/view'),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn('vob'),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn(_AUTOMATIC_VIEW_INFO),
            },
        ]))

        try:
            self.client.get_repository_info()
        except SCMError as e:
            self.assertEqual(six.text_type(e),
                             'Webviews and automatic views are not currently '
                             'supported. RBTools commands can only be used in '
                             'dynamic or snapshot views.')
        else:
            self.fail('get_repository_info did not raise SCMError')

    def test_get_repository_info_webview(self):
        """Testing ClearCaseClient.get_repository_info with webview"""
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn('test-view'),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn('/test/view'),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn('vob'),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn(_WEBVIEW_VIEW_INFO),
            },
        ]))

        try:
            self.client.get_repository_info()
        except SCMError as e:
            self.assertEqual(six.text_type(e),
                             'Webviews and automatic views are not currently '
                             'supported. RBTools commands can only be used in '
                             'dynamic or snapshot views.')
        else:
            self.fail('get_repository_info did not raise SCMError')

    def test_repository_info_update_from_remote_clearcase(self):
        """Testing ClearCaseRepositoryInfo.update_from_remote with ClearCase
        remote
        """
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'lsregion'],),
                'op': kgb.SpyOpReturn(['region']),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn('vob1'),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          'b520a815.c9af11eb.986f.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn('vob2'),
            },
        ]))

        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.update_from_remote({}, {
            'repopath': '/view/server-view',
            'uuids': [
                '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                'b520a815.c9af11eb.986f.52:54:00:7f:63:a5',
            ],
        })

        self.assertEqual(repository_info.uuid_to_tags, {
            '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5': ['vob1'],
            'b520a815.c9af11eb.986f.52:54:00:7f:63:a5': ['vob2'],
        })
        self.assertEqual(repository_info.is_legacy, False)

    def test_repository_info_update_from_remote_versionvault(self):
        """Testing ClearCaseRepositoryInfo.update_from_remote with
        VersionVault remote
        """
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'lsregion'],),
                'op': kgb.SpyOpReturn(['region']),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn('vob'),
            },
        ]))

        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.update_from_remote({}, {
            'repopath': '/view/server-view',
            'uuid': '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
        })

        self.assertEqual(repository_info.uuid_to_tags, {
            '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5': ['vob'],
        })
        self.assertEqual(repository_info.is_legacy, True)

    def test_get_vobtag_success(self):
        """Testing ClearCaseClient._get_vobtag inside view"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn('/vob\n'),
            },
        ]))

        self.assertEqual(self.client._get_vobtag(), '/vob')

    def test_get_vobtag_error(self):
        """Testing ClearCaseClient._get_vobtag outside view"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn(
                    'cleartool: Error: Unable to determine VOB for '
                    'pathname ".".\n'
                ),
            },
        ]))

        with self.assertRaises(SCMError):
            self.client._get_vobtag()

    def test_parse_revision_spec(self):
        """Testing ClearCaseClient.parse_revision_spec"""
        cases = [
            (
                [],
                '--rbtools-checkedout-base',
                '--rbtools-checkedout-changeset',
            ),
            (
                ['activity:bugfix123'],
                '--rbtools-activity-base',
                'bugfix123',
            ),
            (
                ['baseline:test@/vob'],
                '--rbtools-baseline-base',
                ['test@/vob'],
            ),
            (
                ['brtype:bugfix123'],
                '--rbtools-branch-base',
                'bugfix123',
            ),
            (
                ['lbtype:bugfix123'],
                '--rbtools-label-base',
                ['bugfix123'],
            ),
            (
                ['stream:bugfix123@/vob'],
                '--rbtools-stream-base',
                'bugfix123@/vob',
            ),
            (
                ['baseline:dev@/vob', 'baseline:bugfix123@/vob'],
                '--rbtools-baseline-base',
                ['dev@/vob', 'bugfix123@/vob'],
            ),
            (
                ['lbtype:dev', 'lbtype:bugfix123'],
                '--rbtools-label-base',
                ['dev', 'bugfix123'],
            ),
            (
                [
                    'vob1/file@@/main/0:vob1/file@@/main/4',
                    'vob2/file2@@/dev/3:vob2/file2@@/main/9',
                ],
                '--rbtools-files',
                [
                    ['vob1/file@@/main/0', 'vob1/file@@/main/4'],
                    ['vob2/file2@@/dev/3', 'vob2/file2@@/main/9'],
                ],
            ),
        ]

        # Fake a dynamic view, which is required for revision specs with two
        # revisions.
        self.client.viewtype = 'dynamic'

        for spec, base, tip in cases:
            self.assertEqual(
                self.client.parse_revision_spec(spec),
                {'base': base, 'tip': tip})

    def test_checkedout_changeset(self):
        """Testing ClearCaseClient._get_checkedout_changeset"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'lsregion'],),
                'op': kgb.SpyOpReturn(['region']),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn('vob'),
            },
            {
                'args': (['cleartool', 'lscheckout', '-avobs', '-cview',
                          '-me', '-fmt', r'%En\t%PVn\t%Vn\n'],),
                'op': kgb.SpyOpReturn(
                    'test2.py\t/main/1\t/main/CHECKEDOUT\n'
                    'test.pdf\t/main/0\t/main/CHECKEDOUT\n'
                    'test.py\t/main/1\t/main/CHECKEDOUT\n'
                ),
            },
        ]))

        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.update_from_remote({}, {
            'repopath': '/view/server-view',
            'uuid': '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
        })

        changeset = self.client._get_checkedout_changeset(repository_info)

        self.assertEqual(changeset, [
            ('test2.py@@/main/1', 'test2.py'),
            ('test.pdf@@/main/0', 'test.pdf'),
            ('test.py@@/main/1', 'test.py'),
        ])

    def test_activity_changeset(self):
        """Testing ClearCaseClient._get_activity_changeset"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'lsregion'],),
                'op': kgb.SpyOpReturn(['region']),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn('/vobs/els'),
            },
            {
                'args': (['cleartool', 'lsactivity', '-fmt', '%[versions]Qp',
                          'activity-name'],),
                'op': kgb.SpyOpReturn(
                    '"/view/x/vobs/els/.@@/main/int/CHECKEDOUT.78" '
                    '"/view/x/vobs/els/test.pdf@@/main/int/CHECKEDOUT.77" '
                    '"/view/x/vobs/els/new.py@@/main/int/CHECKEDOUT.71" '
                    '"/view/x/vobs/els/test.py@@/main/int/CHECKEDOUT.64" '
                    '"/view/x/vobs/els/.@@/main/int/2" '
                    '"/view/x/vobs/els/test.py@@/main/int/3" '
                    '"/view/x/vobs/els/test.py@@/main/int/2"'
                ),
            },
            {
                'args': (['cleartool', 'desc', '-fmt',
                          '%[version_predecessor]p',
                          '/view/x/vobs/els/.@@/main/int/2'],),
                'op': kgb.SpyOpReturn('/main/int/1'),
            },
            {
                'args': (['cleartool', 'desc', '-fmt',
                          '%[version_predecessor]p',
                          '/view/x/vobs/els/test.py@@/main/int/2'],),
                'op': kgb.SpyOpReturn('/main/int/1'),
            },
        ]))

        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.update_from_remote({}, {
            'repopath': '/view/server-view',
            'uuid': '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
        })

        changeset = self.client._get_activity_changeset('activity-name',
                                                        repository_info)

        self.assertEqual(changeset, [
            ('/view/x/vobs/els/.@@/main/int/1',
             '/view/x/vobs/els/.'),
            ('/view/x/vobs/els/test.pdf@@/main/int/0',
             '/view/x/vobs/els/test.pdf'),
            ('/view/x/vobs/els/new.py@@/main/int/0',
             '/view/x/vobs/els/new.py'),
            ('/view/x/vobs/els/test.py@@/main/int/1',
             '/view/x/vobs/els/test.py'),
        ])

    def test_diff_directory(self):
        """Testing ClearCaseClient._diff_directory"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'diff', '-ser',
                          '.@@/main/1', '.@@/main/CHECKEDOUT'],),
                'op': kgb.SpyOpReturn([
                    '********************************',
                    '<<< directory 1: .@@/main/test-project_integration/2',
                    '>>> directory 2:',
                    '.@@/main/test-project_integration/CHECKEDOUT',
                    '********************************',
                    '-----[ renamed to ]-----',
                    '< test2.py  --06-29T17:26 david',
                    '---',
                    '> renamed-file.py  --06-29T17:26 david',
                    '-----[ deleted ]-----',
                    '< test3.py  --07-28T00:30 david',
                    '-----[ added ]-----',
                    '> test4.py  --07-28T18:27 david',
                ]),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          '.@@/main/1/test2.py'],),
                'op': kgb.SpyOpReturn('test2.py-fake-oid'),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          '.@@/main/CHECKEDOUT/renamed-file.py'],),
                'op': kgb.SpyOpReturn('renamed-file.py-fake-oid'),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          '.@@/main/1/test3.py'],),
                'op': kgb.SpyOpReturn('test3.py-fake-oid'),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          '.@@/main/CHECKEDOUT/test4.py'],),
                'op': kgb.SpyOpReturn('test4.py-fake-oid'),
            },
        ]))

        self.assertEqual(
            self.client._diff_directory('.@@/main/1', '.@@/main/CHECKEDOUT'),
            {
                'added': {('.@@/main/CHECKEDOUT/test4.py',
                           'test4.py-fake-oid')},
                'deleted': {('.@@/main/1/test3.py', 'test3.py-fake-oid')},
                'renamed': {('.@@/main/1/test2.py', 'test2.py-fake-oid',
                             '.@@/main/CHECKEDOUT/renamed-file.py',
                             'renamed-file.py-fake-oid')},
            })
