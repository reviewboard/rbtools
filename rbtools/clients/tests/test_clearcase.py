"""Unit tests for ClearCaseClient."""

from __future__ import unicode_literals

import os
import unittest

import kgb
import six

from rbtools.clients.clearcase import ClearCaseClient, ClearCaseRepositoryInfo
from rbtools.clients.errors import SCMError
from rbtools.clients.tests import SCMClientTestCase
from rbtools.utils.checks import check_gnu_diff, check_install
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


_LEGACY_DIFF = b"""--- vob/test2.py@@/main/1\t2022-05-23 20:10:38.578433000 +0000
+++ vob/test2.py\t2022-05-23 20:11:11.050410000 +0000
==== test2.py-fake-oid test2.py-fake-oid ====
@@ -0,0 +1,3 @@
+#!/usr/bin/env python
+
+print('Test')
==== test.pdf-fake-oid test.pdf-fake-oid ====
Binary files test.pdf@@/main/0 and test.pdf differ
--- vob/test.py@@/main/1\t2022-05-23 20:10:38.578433000 +0000
+++ vob/test.py\t2022-05-23 20:11:11.050410000 +0000
==== test.py-fake-oid test.py-fake-oid ====
@@ -1,3 +1,4 @@
#!/usr/bin/env python

print('Test 1')
+print('Added a line')
"""


_DIFFX_DIFF = b"""#diffx: encoding=utf-8, version=1.0
#.meta: format=json, length=143
{
    "stats": {
        "changes": 1,
        "deletions": 0,
        "files": 2,
        "insertions": 3,
        "lines changed": 3
    }
}
#.change:
#..meta: format=json, length=535
{
    "stats": {
        "deletions": 0,
        "files": 2,
        "insertions": 3,
        "lines changed": 3
    },
    "versionvault": {
        "os": {
            "long": null,
            "short": "posix"
        },
        "region": null,
        "scm": {
            "name": null,
            "version": null
        },
        "scope": {
            "name": "checkout",
            "type": "checkout"
        },
        "view": {
            "tag": null,
            "type": null,
            "ucm": false
        }
    }
}
#..file:
#...meta: format=json, length=670
{
    "op": "modify",
    "path": {
        "new": "test2.py",
        "old": "test2.py@@/main/1"
    },
    "revision": {
        "new": "test2.py-fake-version",
        "old": "test2.py-fake-version-old"
    },
    "stats": {
        "deletions": 0,
        "insertions": 3,
        "lines changed": 3
    },
    "type": "file",
    "versionvault": {
        "new": {
            "name": "test2.py",
            "oid": "test2.py-fake-oid",
            "path": "test2.py"
        },
        "old": {
            "name": "test2.py",
            "oid": "test2.py-fake-old-oid",
            "path": "test2.py@@/main/1"
        },
        "vob": "test2.py-vob-oid"
    }
}
#...diff: length=163, line_endings=unix, type=text
--- test2.py@@/main/1\t2022-05-23 20:10:38.578433000 +0000
+++ test2.py\t2022-05-23 20:11:11.050410000 +0000
@@ -0,0 +1,3 @@
+#!/usr/bin/env python
+
+print('Test')
#..file:
#...meta: format=json, length=572
{
    "op": "modify",
    "path": {
        "new": "test.pdf",
        "old": "test.pdf@@/main/0"
    },
    "revision": {
        "new": "test.pdf-fake-version",
        "old": "test.pdf-fake-version-old"
    },
    "type": "file",
    "versionvault": {
        "new": {
            "name": "test.pdf",
            "oid": "test.pdf-fake-oid",
            "path": "test.pdf"
        },
        "old": {
            "name": "test.pdf",
            "oid": "test.pdf-fake-old-oid",
            "path": "test.pdf@@/main/0"
        },
        "vob": "test.pdf-vob-oid"
    }
}
#...diff: length=51, line_endings=unix, type=binary
Binary files test.pdf@@/main/0 and test.pdf differ
"""


_LEGACY_DIRECTORY_DIFF = b"""--- test-dir@@/main/0\t2022-09-05 23:49:05.000000000 -0600
+++ test-dir\t2022-09-05 23:49:09.000000000 -0600
==== test-dir-old-oid test-dir-new-oid ====
@@ -0,0 +1 @@
+empty-dir
"""


_DIFFX_DIRECTORY_DIFF = b"""#diffx: encoding=utf-8, version=1.0
#.meta: format=json, length=143
{
    "stats": {
        "changes": 1,
        "deletions": 0,
        "files": 2,
        "insertions": 1,
        "lines changed": 1
    }
}
#.change:
#..meta: format=json, length=535
{
    "stats": {
        "deletions": 0,
        "files": 2,
        "insertions": 1,
        "lines changed": 1
    },
    "versionvault": {
        "os": {
            "long": null,
            "short": "posix"
        },
        "region": null,
        "scm": {
            "name": null,
            "version": null
        },
        "scope": {
            "name": "checkout",
            "type": "checkout"
        },
        "view": {
            "tag": null,
            "type": null,
            "ucm": false
        }
    }
}
#..file:
#...meta: format=json, length=709
{
    "op": "modify",
    "path": {
        "new": "test-dir",
        "old": "test-dir@@/main/0"
    },
    "revision": {
        "new": "test-dir-new-version",
        "old": "test-dir-old-version"
    },
    "stats": {
        "deletions": 0,
        "insertions": 1,
        "lines changed": 1
    },
    "type": "directory",
    "versionvault": {
        "directory-diff": "legacy-filenames",
        "new": {
            "name": "test-dir",
            "oid": "test-dir-new-oid",
            "path": "test-dir"
        },
        "old": {
            "name": "test-dir",
            "oid": "test-dir-old-oid",
            "path": "test-dir@@/main/0"
        },
        "vob": "test-dir-vob-oid"
    }
}
#...diff: length=132, line_endings=unix, type=text
--- test-dir@@/main/0	2022-09-05 23:49:05.000000000 -0600
+++ test-dir	2022-09-05 23:49:09.000000000 -0600
@@ -0,0 +1 @@
+empty-dir
#..file:
#...meta: format=json, length=398
{
    "op": "create",
    "path": "test-dir/empty-dir",
    "revision": {
        "new": "empty-dir-new-version"
    },
    "type": "directory",
    "versionvault": {
        "directory-diff": "legacy-filenames",
        "new": {
            "name": "empty-dir",
            "oid": "empty-dir-new-oid",
            "path": "test-dir/empty-dir"
        },
        "vob": "empty-dir-vob-oid"
    }
}
"""


class ClearCaseClientTests(kgb.SpyAgency, SCMClientTestCase):
    """Unit tests for ClearCaseClient."""

    def setUp(self):
        super(ClearCaseClientTests, self).setUp()

        self.set_user_home(
            os.path.join(self.testdata_dir, 'homedir'))

        self.spy_on(check_install, op=kgb.SpyOpReturn(True))
        self.spy_on(ClearCaseClient._get_host_info,
                    op=kgb.SpyOpReturn({}),
                    owner=ClearCaseClient)

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

    def test_file_changes_from_directories(self):
        """Testing ClearCaseClient._get_file_changes_from_directories"""
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
            self.client._get_file_changes_from_directories(
                '.@@/main/1', '.@@/main/CHECKEDOUT'),
            {
                'added': {('.@@/main/CHECKEDOUT/test4.py',
                           'test4.py-fake-oid')},
                'deleted': {('.@@/main/1/test3.py', 'test3.py-fake-oid')},
                'renamed': {('.@@/main/1/test2.py', 'test2.py-fake-oid',
                             '.@@/main/CHECKEDOUT/renamed-file.py',
                             'renamed-file.py-fake-oid')},
            })

    def test_diff_legacy(self):
        """Testing ClearCaseClient._do_diff in legacy mode"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test2.py'],),
                'op': kgb.SpyOpReturn('file'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test.pdf'],),
                'op': kgb.SpyOpReturn('file'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test.py'],),
                'op': kgb.SpyOpReturn('file'),
            },
            {
                'args': (['diff', '-uN', 'test2.py@@/main/1', 'test2.py'],),
                'op': kgb.SpyOpReturn(
                    b'--- test2.py@@/main/1\t2022-05-23 '
                    b'20:10:38.578433000 +0000\n'
                    b'+++ test2.py\t2022-05-23 '
                    b'20:11:11.050410000 +0000\n'
                    b'@@ -0,0 +1,3 @@\n'
                    b'+#!/usr/bin/env python\n'
                    b'+\n'
                    b'+print(\'Test\')\n'
                ),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test2.py@@/main/1'],),
                'op': kgb.SpyOpReturn('test2.py-fake-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test2.py'],),
                'op': kgb.SpyOpReturn('test2.py-fake-oid'),
            },
            {
                'args': (['diff', '-uN', 'test.pdf@@/main/0', 'test.pdf'],),
                'op': kgb.SpyOpReturn(
                    b'Binary files test.pdf@@/main/0 and test.pdf differ\n'
                ),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.pdf@@/main/0'],),
                'op': kgb.SpyOpReturn('test.pdf-fake-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.pdf'],),
                'op': kgb.SpyOpReturn('test.pdf-fake-oid'),
            },
            {
                'args': (['diff', '-uN', 'test.py@@/main/1', 'test.py'],),
                'op': kgb.SpyOpReturn(
                    b'--- test.py@@/main/1\t2022-05-23 '
                    b'20:10:38.578433000 +0000\n'
                    b'+++ test.py\t2022-05-23 '
                    b'20:11:11.050410000 +0000\n'
                    b'@@ -1,3 +1,4 @@\n'
                    b'#!/usr/bin/env python\n'
                    b'\n'
                    b'print(\'Test 1\')\n'
                    b'+print(\'Added a line\')\n'
                ),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.py@@/main/1'],),
                'op': kgb.SpyOpReturn('test.py-fake-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.py'],),
                'op': kgb.SpyOpReturn('test.py-fake-oid'),
            },
        ]))

        self.spy_on(os.path.exists, op=kgb.SpyOpMatchInOrder([
            {
                'args': ('test2.py',),
                'op': kgb.SpyOpReturn(True)
            },
            {
                'args': ('test.pdf',),
                'op': kgb.SpyOpReturn(True)
            },
            {
                'args': ('test.py',),
                'op': kgb.SpyOpReturn(True)
            },
        ]))

        changeset = [
            ('test2.py@@/main/1', 'test2.py'),
            ('test.pdf@@/main/0', 'test.pdf'),
            ('test.py@@/main/1', 'test.py'),
        ]

        self.client.root_path = os.getcwd()
        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        metadata = self.client._get_diff_metadata({
            'base': '--rbtools-checkedout-base',
            'tip': '--rbtools-checkedout-changeset',
        })

        diff = self.client._do_diff(changeset, repository_info, metadata)

        self.assertEqual(diff['diff'], _LEGACY_DIFF)

    def test_diff_diffx(self):
        """Testing ClearCaseClient._do_diff in diffx mode"""
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test2.py'],),
                'op': kgb.SpyOpReturn('file'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test.pdf'],),
                'op': kgb.SpyOpReturn('file'),
            },
            {
                'args': (['diff', '-uN', 'test2.py@@/main/1', 'test2.py'],),
                'op': kgb.SpyOpReturn(
                    b'--- test2.py@@/main/1\t2022-05-23 '
                    b'20:10:38.578433000 +0000\n'
                    b'+++ test2.py\t2022-05-23 '
                    b'20:11:11.050410000 +0000\n'
                    b'@@ -0,0 +1,3 @@\n'
                    b'+#!/usr/bin/env python\n'
                    b'+\n'
                    b'+print(\'Test\')\n'
                ),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test2.py'],),
                'op': kgb.SpyOpReturn('test2.py-vob-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test2.py@@/main/1'],),
                'op': kgb.SpyOpReturn('test2.py-fake-old-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test2.py-fake-old-oid'],),
                'op': kgb.SpyOpReturn('test2.py-fake-version-old'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test2.py'],),
                'op': kgb.SpyOpReturn('test2.py-fake-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test2.py-fake-oid'],),
                'op': kgb.SpyOpReturn('test2.py-fake-version'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test2.py@@/main/1'],),
                'op': kgb.SpyOpReturn('test2.py'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test2.py'],),
                'op': kgb.SpyOpReturn('test2.py'),
            },
            {
                'args': (['diff', '-uN', 'test.pdf@@/main/0', 'test.pdf'],),
                'op': kgb.SpyOpReturn(
                    b'Binary files test.pdf@@/main/0 and test.pdf differ\n'
                ),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test.pdf'],),
                'op': kgb.SpyOpReturn('test.pdf-vob-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.pdf@@/main/0'],),
                'op': kgb.SpyOpReturn('test.pdf-fake-old-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test.pdf-fake-old-oid'],),
                'op': kgb.SpyOpReturn('test.pdf-fake-version-old'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.pdf'],),
                'op': kgb.SpyOpReturn('test.pdf-fake-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test.pdf-fake-oid'],),
                'op': kgb.SpyOpReturn('test.pdf-fake-version'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test.pdf@@/main/0'],),
                'op': kgb.SpyOpReturn('test.pdf'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test.pdf'],),
                'op': kgb.SpyOpReturn('test.pdf'),
            },
        ]))

        self.spy_on(os.path.exists, op=kgb.SpyOpMatchInOrder([
            {
                'args': ('test2.py',),
                'op': kgb.SpyOpReturn(True)
            },
            {
                'args': ('test.pdf',),
                'op': kgb.SpyOpReturn(True)
            },
        ]))

        changeset = [
            ('test2.py@@/main/1', 'test2.py'),
            ('test.pdf@@/main/0', 'test.pdf'),
        ]

        self.client.root_path = os.getcwd()
        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.is_legacy = False
        metadata = self.client._get_diff_metadata({
            'base': '--rbtools-checkedout-base',
            'tip': '--rbtools-checkedout-changeset',
        })

        diff = self.client._do_diff(changeset, repository_info, metadata)

        self.assertEqual(diff['diff'], _DIFFX_DIFF)

    def test_diff_directory_legacy(self):
        """Testing ClearCaseClient._do_diff with a changed directory in legacy
        mode
        """
        tmpfiles = self.precreate_tempfiles(4)
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test-dir'],),
                'op': kgb.SpyOpReturn('directory'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('directory'),
            },
            {
                'args': (['cleartool', 'diff', '-ser', 'test-dir@@/main/0',
                          'test-dir'],),
                'op': kgb.SpyOpReturn([
                    '********************************',
                    '<<< directory 1: test-dir@@/main/0',
                    '>>> directory 2: test-dir',
                    '********************************',
                    '-----[ added ]-----',
                    '> empty-dir/ --08-30T23:13 user',
                ]),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          'test-dir/empty-dir/'],),
                'op': kgb.SpyOpReturn('empty-dir-new-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir'],),
                'op': kgb.SpyOpReturn('test-dir-new-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('empty-dir-new-oid'),
            },
            {
                'args': (['cleartool', 'diff', '-ser',
                          'test-dir/empty-dir@@/main/0',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn(['Directories are identical'])
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn([]),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir'],),
                'op': kgb.SpyOpReturn([b'empty-dir']),
            },
            {
                'args': (['diff', '-uN', tmpfiles[0], tmpfiles[1]],),
                'op': kgb.SpyOpReturn([
                    (b'--- %s\t2022-09-05 23:49:05.000000000 -0600\n'
                     % tmpfiles[0].encode('utf-8')),
                    (b'+++ %s\t2022-09-05 23:49:09.000000000 -0600\n'
                     % tmpfiles[1].encode('utf-8')),
                    b'@@ -0,0 +1 @@\n',
                    b'+empty-dir\n',
                ]),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn('test-dir-old-oid'),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn([]),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn([]),
            },
            {
                'args': (['diff', '-uN', tmpfiles[2], tmpfiles[3]],),
                'op': kgb.SpyOpReturn(b''),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir'],),
                'op': kgb.SpyOpReturn('test-dir-new-oid'),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn([]),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn([]),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn('empty-dir-old-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('empty-dir-new-oid'),
            },
        ]))

        changeset = [
            ('test-dir@@/main/0', 'test-dir'),
            ('test-dir/empty-dir@@/main/0', 'test-dir/empty-dir'),
        ]

        self.client.root_path = os.getcwd()
        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        metadata = self.client._get_diff_metadata({
            'base': '--rbtools-checkedout-base',
            'tip': '--rbtools-checkedout-changeset',
        })

        diff = self.client._do_diff(changeset, repository_info, metadata)

        self.assertEqual(diff['diff'], _LEGACY_DIRECTORY_DIFF)

    def test_diff_directory_diffx(self):
        """Testing ClearCaseClient._do_diff with a changed directory in diffx
        mode
        """
        tmpfiles = self.precreate_tempfiles(4)
        self.spy_on(execute, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test-dir'],),
                'op': kgb.SpyOpReturn('directory'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('directory'),
            },
            {
                'args': (['cleartool', 'diff', '-ser', 'test-dir@@/main/0',
                          'test-dir'],),
                'op': kgb.SpyOpReturn([
                    '********************************',
                    '<<< directory 1: test-dir@@/main/0',
                    '>>> directory 2: test-dir',
                    '********************************',
                    '-----[ added ]-----',
                    '> empty-dir/ --08-30T23:13 user',
                ]),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          'test-dir/empty-dir/'],),
                'op': kgb.SpyOpReturn('empty-dir-new-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir'],),
                'op': kgb.SpyOpReturn('test-dir-new-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('empty-dir-new-oid'),
            },
            {
                'args': (['cleartool', 'diff', '-ser',
                          'test-dir/empty-dir@@/main/0',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn(['Directories are identical'])
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn([]),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir'],),
                'op': kgb.SpyOpReturn([b'empty-dir']),
            },
            {
                'args': (['diff', '-uN', tmpfiles[0], tmpfiles[1]],),
                'op': kgb.SpyOpReturn([
                    (b'--- %s\t2022-09-05 23:49:05.000000000 -0600\n'
                     % tmpfiles[0].encode('utf-8')),
                    (b'+++ %s\t2022-09-05 23:49:09.000000000 -0600\n'
                     % tmpfiles[1].encode('utf-8')),
                    b'@@ -0,0 +1 @@\n',
                    b'+empty-dir\n',
                ]),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test-dir'],),
                'op': kgb.SpyOpReturn('test-dir-vob-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn('test-dir-old-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test-dir-old-oid'],),
                'op': kgb.SpyOpReturn('test-dir-old-version'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test-dir-new-oid'],),
                'op': kgb.SpyOpReturn('test-dir-new-version'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn('test-dir'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir'],),
                'op': kgb.SpyOpReturn('test-dir'),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn([]),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn([]),
            },
            {
                'args': (['diff', '-uN', tmpfiles[2], tmpfiles[3]],),
                'op': kgb.SpyOpReturn(b''),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('empty-dir-vob-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:empty-dir-new-oid'],),
                'op': kgb.SpyOpReturn('empty-dir-new-version'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('empty-dir'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn('empty-dir-old-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:empty-dir-old-oid'],),
                'op': kgb.SpyOpReturn('empty-dir-old-version'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('empty-dir-new-oid'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:empty-dir-new-oid'],),
                'op': kgb.SpyOpReturn('empty-dir-new-version'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn('empty-dir'),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn('empty-dir'),
            },
        ]))

        changeset = [
            ('test-dir@@/main/0', 'test-dir'),
            ('test-dir/empty-dir@@/main/0', 'test-dir/empty-dir'),
        ]

        self.client.root_path = os.getcwd()
        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.is_legacy = False
        metadata = self.client._get_diff_metadata({
            'base': '--rbtools-checkedout-base',
            'tip': '--rbtools-checkedout-changeset',
        })

        diff = self.client._do_diff(changeset, repository_info, metadata)

        self.assertEqual(diff['diff'], _DIFFX_DIRECTORY_DIFF)
