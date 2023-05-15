"""Unit tests for ClearCaseClient."""

import os
import re

import kgb

from rbtools.clients.clearcase import ClearCaseClient, ClearCaseRepositoryInfo
from rbtools.clients.errors import SCMClientDependencyError, SCMError
from rbtools.clients.tests import SCMClientTestCase
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_gnu_diff, check_install
from rbtools.utils.process import run_process_exec


_SNAPSHOT_VIEW_INFO = (
    b'  snapshot-view-test\n'
    b'/home/user/stgloc_view1/user/snapshot-view-test.vws\n'
    b'Created 2021-06-18T18:10:32-04:00 by user.user@localhost.localdomain\n'
    b'Last modified 2021-06-24T17:01:39-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last accessed 2021-06-24T17:01:39-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last read of private data 2021-06-24T17:01:39-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last config spec update 2021-06-24T15:40:22-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last view private object update 2021-06-24T17:01:39-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Text mode: unix\n'
    b'Properties: snapshot readwrite\n'
    b'Owner: user            : rwx (all)\n'
    b'Group: user            : rwx (all)\n'
    b'Other:                  : r-x (read)\n'
    b'Additional groups: wheel\n'
)


_DYNAMIC_VIEW_INFO = (
    b'* test-view            /viewstore/test-view.vbs\n'
    b'Created 2021-06-10T01:49:46-04:00 by user.user@localhost.localdomain\n'
    b'Last modified 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last accessed 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last config spec update 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Text mode: unix\n'
    b'Properties: dynamic readwrite shareable_dos\n'
    b'Owner: user            : rwx (all)\n'
    b'Group: user            : rwx (all)\n'
    b'Other:                  : r-x (read)\n'
    b'Additional groups: wheel\n'
)


_UCM_VIEW_INFO = (
    b'* development-view            /viewstore/development-view.vbs\n'
    b'Created 2021-06-10T01:49:46-04:00 by user.user@localhost.localdomain\n'
    b'Last modified 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last accessed 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last config spec update 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Text mode: unix\n'
    b'Properties: dynamic ucmview readwrite shareable_dos\n'
    b'Owner: user            : rwx (all)\n'
    b'Group: user            : rwx (all)\n'
    b'Other:                  : r-x (read)\n'
    b'Additional groups: wheel\n'
)


_AUTOMATIC_VIEW_INFO = (
    b'* development-view            /viewstore/development-view.vbs\n'
    b'Created 2021-06-10T01:49:46-04:00 by user.user@localhost.localdomain\n'
    b'Last modified 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last accessed 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last config spec update 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Text mode: unix\n'
    b'Properties: automatic readwrite shareable_dos\n'
    b'Owner: user            : rwx (all)\n'
    b'Group: user            : rwx (all)\n'
    b'Other:                  : r-x (read)\n'
    b'Additional groups: wheel\n'
)


_WEBVIEW_VIEW_INFO = (
    b'* development-view            /viewstore/development-view.vbs\n'
    b'Created 2021-06-10T01:49:46-04:00 by user.user@localhost.localdomain\n'
    b'Last modified 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last accessed 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Last config spec update 2021-06-10T01:49:46-04:00 by '
    b'user.user@localhost.localdomain\n'
    b'Text mode: unix\n'
    b'Properties: webview readwrite shareable_dos\n'
    b'Owner: user            : rwx (all)\n'
    b'Group: user            : rwx (all)\n'
    b'Other:                  : r-x (read)\n'
    b'Additional groups: wheel\n'
)


_LEGACY_DIFF = b"""\
--- vob/test2.py@@/main/1\t2022-01-02 12:34:56.000000 +0000
+++ vob/test2.py\t2022-01-02 12:34:56.000000 +0000
==== test2.py-fake-oid test2.py-fake-oid ====
@@ -0,0 +1,3 @@
+#!/usr/bin/env python
+
+print('Test')
==== test.pdf-fake-oid test.pdf-fake-oid ====
Binary files test.pdf@@/main/0 and test.pdf differ
--- vob/test.py@@/main/1\t2022-01-02 12:34:56.000000 +0000
+++ vob/test.py\t2022-01-02 12:34:56.000000 +0000
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
--- test2.py@@/main/1\t2022-01-02 12:34:56.000000 +0000
+++ test2.py\t2022-01-02 12:34:56.000000 +0000
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


_LEGACY_DIRECTORY_DIFF = b"""\
--- test-dir@@/main/0\t2022-01-02 12:34:56.000000 +0000
+++ test-dir\t2022-01-02 12:34:56.000000 +0000
==== test-dir-old-oid test-dir-new-oid ====
@@ -0,0 +1 @@
+empty-dir
"""


_DIFFX_DIRECTORY_DIFF = b"""\
#diffx: encoding=utf-8, version=1.0
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
--- test-dir@@/main/0	2022-01-02 12:34:56.000000 +0000
+++ test-dir	2022-01-02 12:34:56.000000 +0000
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


class ClearCaseClientTests(SCMClientTestCase):
    """Unit tests for ClearCaseClient."""

    scmclient_cls = ClearCaseClient

    @classmethod
    def setup_checkout(
        cls,
        checkout_dir: str,
    ) -> str:
        """Populate a ClearCase checkout.

        This will create a few files and directories needed to test diffing.

        Args:
            checkout_dir (str):
                The top-level directory in which the checkout will be placed.

        Returns:
            str:
            The checkout directory.
        """
        # Write some files that will be diffed.
        test2_py_path = os.path.join(checkout_dir, 'test2.py@@', 'main')
        test_pdf_path = os.path.join(checkout_dir, 'test.pdf@@', 'main')

        os.makedirs(test2_py_path)
        os.makedirs(test_pdf_path)

        with open(os.path.join(test2_py_path, '1'), 'w'):
            pass

        with open(os.path.join(checkout_dir, 'test2.py'), 'w') as fp:
            fp.write(
                "#!/usr/bin/env python\n"
                "\n"
                "print('Test')\n"
            )

        with open(os.path.join(test_pdf_path, '0'), 'wb') as fp:
            fp.write(b'\0\1\2')

        with open(os.path.join(checkout_dir, 'test.pdf'), 'wb') as fp:
            fp.write(b'\1\2\3')

        return checkout_dir

    def setUp(self):
        super(ClearCaseClientTests, self).setUp()

        self.set_user_home(os.path.join(self.testdata_dir, 'homedir'))

    def test_check_dependencies_with_found(self):
        """Testing ClearCaseClient.check_dependencies with found"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['cleartool', 'help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cleartool', 'help'])

    def test_check_dependencies_with_missing(self):
        """Testing ClearCaseClient.check_dependencies with dependencies
        missing
        """
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools ('cleartool') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cleartool', 'help'])

    def test_host_properties_with_deps_missing(self):
        """Testing ClearCaseClient.host_properties with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # host_properties(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            props = client.host_properties

        self.assertIsNone(props)

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "cleartool help": skipping ClearCase')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cleartool', 'help'])

    def test_host_properties_with_deps_not_checked(self):
        """Testing ClearCaseClient.host_properties with dependencies not
        checked
        """
        # A False value is used just to ensure host_properties() bails early,
        # and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either ClearCaseClient.setup() or '
            'ClearCaseClient.has_dependencies() must be called before other '
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.host_properties

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "cleartool help": skipping ClearCase')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cleartool', 'help'])

    def test_get_local_path_with_deps_missing(self):
        """Testing ClearCaseClient.get_local_path with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_local_path(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            local_path = client.get_local_path()

        self.assertIsNone(local_path)

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "cleartool help": skipping ClearCase')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cleartool', 'help'])

    def test_get_local_path_with_deps_not_checked(self):
        """Testing ClearCaseClient.get_local_path with dependencies not
        checked
        """
        # A False value is used just to ensure get_local_path() bails early,
        # and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either ClearCaseClient.setup() or '
            'ClearCaseClient.has_dependencies() must be called before other '
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_local_path()

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "cleartool help": skipping ClearCase')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cleartool', 'help'])

    def test_get_repository_info_with_deps_missing(self):
        """Testing ClearCaseClient.get_repository_info with dependencies
        missing
        """
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_repository_info(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            repository_info = client.get_repository_info()

        self.assertIsNone(repository_info)

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "cleartool help": skipping ClearCase')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cleartool', 'help'])

    def test_get_repository_info_with_deps_not_checked(self):
        """Testing ClearCaseClient.get_repository_info with dependencies
        not checked
        """
        # A False value is used just to ensure get_repository_info() bails
        # early, and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either ClearCaseClient.setup() or '
            'ClearCaseClient.has_dependencies() must be called before other '
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_repository_info()

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "cleartool help": skipping ClearCase')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cleartool', 'help'])


    def test_get_local_path_outside_view(self):
        """Testing ClearCaseClient.get_local_path outside of view"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'** NONE \n**',
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        self.assertIsNone(client.get_local_path())

    def test_get_local_path_inside_view(self):
        """Testing ClearCaseClient.get_local_path inside view"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/test/view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob\n',
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        self.assertEqual(client.get_local_path(), '/test/view/vob')

    def test_get_repository_info_snapshot(self):
        """Testing ClearCaseClient.get_repository_info with snapshot view"""
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/test/view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn((
                    0,
                    _SNAPSHOT_VIEW_INFO,
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        repository_info = client.get_repository_info()
        self.assertEqual(repository_info.path, '/test/view/vob')
        self.assertEqual(repository_info.vobtag, 'vob')
        self.assertEqual(repository_info.vob_tags, {'vob'})

        # Initial state that gets populated later by update_from_remote
        self.assertEqual(repository_info.uuid_to_tags, {})
        self.assertTrue(repository_info.is_legacy)

        self.assertEqual(client.viewtype, 'snapshot')
        self.assertFalse(client.is_ucm)

    def test_get_repository_info_dynamic(self):
        """Testing ClearCaseClient.get_repository_info with dynamic view and
        base ClearCase
        """
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/test/view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn((
                    0,
                    _DYNAMIC_VIEW_INFO,
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        repository_info = client.get_repository_info()
        self.assertEqual(repository_info.path, '/test/view/vob')
        self.assertEqual(repository_info.vobtag, 'vob')
        self.assertEqual(repository_info.vob_tags, {'vob'})

        # Initial state that gets populated later by update_from_remote
        self.assertEqual(repository_info.uuid_to_tags, {})
        self.assertTrue(repository_info.is_legacy)

        self.assertEqual(client.viewtype, 'dynamic')
        self.assertFalse(client.is_ucm)

    def test_get_repository_info_dynamic_UCM(self):
        """Testing ClearCaseClient.get_repository_info with dynamic view and
        UCM
        """
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/test/view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn((
                    0,
                    _UCM_VIEW_INFO,
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        repository_info = client.get_repository_info()
        self.assertEqual(repository_info.path, '/test/view/vob')
        self.assertEqual(repository_info.vobtag, 'vob')
        self.assertEqual(repository_info.vob_tags, {'vob'})

        # Initial state that gets populated later by update_from_remote
        self.assertEqual(repository_info.uuid_to_tags, {})
        self.assertTrue(repository_info.is_legacy)

        self.assertEqual(client.viewtype, 'dynamic')
        self.assertTrue(client.is_ucm)

    def test_get_repository_info_automatic(self):
        """Testing ClearCaseClient.get_repository_info with automatic view"""
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/test/view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn((
                    0,
                    _AUTOMATIC_VIEW_INFO,
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        try:
            client.get_repository_info()
        except SCMError as e:
            self.assertEqual(str(e),
                             'Webviews and automatic views are not currently '
                             'supported. RBTools commands can only be used in '
                             'dynamic or snapshot views.')
        else:
            self.fail('get_repository_info did not raise SCMError')

    def test_get_repository_info_webview(self):
        """Testing ClearCaseClient.get_repository_info with webview"""
        self.spy_on(check_gnu_diff, call_original=False)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'pwv', '-short'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'pwv', '-root'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/test/view\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsview', '-full', '-properties',
                          '-cview'],),
                'op': kgb.SpyOpReturn((
                    0,
                    _WEBVIEW_VIEW_INFO,
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        try:
            client.get_repository_info()
        except SCMError as e:
            self.assertEqual(str(e),
                             'Webviews and automatic views are not currently '
                             'supported. RBTools commands can only be used in '
                             'dynamic or snapshot views.')
        else:
            self.fail('get_repository_info did not raise SCMError')

    def test_repository_info_update_from_remote_clearcase(self):
        """Testing ClearCaseRepositoryInfo.update_from_remote with ClearCase
        remote
        """
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'lsregion'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'region\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob1\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          'b520a815.c9af11eb.986f.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob2\n',
                    b'',
                )),
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
        self.assertFalse(repository_info.is_legacy)

    def test_repository_info_update_from_remote_versionvault(self):
        """Testing ClearCaseRepositoryInfo.update_from_remote with
        VersionVault remote
        """
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'lsregion'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'region\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob\n',
                    b'',
                )),
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
        self.assertTrue(repository_info.is_legacy)

    def test_get_vobtag_success(self):
        """Testing ClearCaseClient._get_vobtag inside view"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/vob\n',
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        self.assertEqual(client._get_vobtag(), '/vob')

    def test_get_vobtag_error(self):
        """Testing ClearCaseClient._get_vobtag outside view"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-short', 'vob:.'],),
                'kwargs': {
                    'redirect_stderr': True,
                },
                'op': kgb.SpyOpReturn((
                    1,
                    (b'cleartool: Error: Unable to determine VOB for '
                     b'pathname ".".\n'),
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        with self.assertRaises(SCMError):
            client._get_vobtag()

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
        client = self.build_client(allow_dep_checks=False)
        client.viewtype = 'dynamic'

        for spec, base, tip in cases:
            self.assertEqual(
                client.parse_revision_spec(spec),
                {'base': base, 'tip': tip})

    def test_checkedout_changeset(self):
        """Testing ClearCaseClient._get_checkedout_changeset"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'lsregion'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'region\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'vob\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lscheckout', '-avobs', '-cview',
                          '-me', '-fmt', r'%En\t%PVn\t%Vn\n'],),
                'op': kgb.SpyOpReturn((
                    0,
                    (b'test2.py\t/main/1\t/main/CHECKEDOUT\n'
                     b'test.pdf\t/main/0\t/main/CHECKEDOUT\n'
                     b'test.py\t/main/1\t/main/CHECKEDOUT\n'),
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.update_from_remote({}, {
            'repopath': '/view/server-view',
            'uuid': '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
        })

        changeset = client._get_checkedout_changeset(repository_info)

        self.assertEqual(changeset, [
            ('test2.py@@/main/1', 'test2.py'),
            ('test.pdf@@/main/0', 'test.pdf'),
            ('test.py@@/main/1', 'test.py'),
        ])

    def test_activity_changeset(self):
        """Testing ClearCaseClient._get_activity_changeset"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'lsregion'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'region\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsvob', '-s', '-family',
                          '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
                          '-region', 'region'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/vobs/els\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'lsactivity', '-fmt', '%[versions]Qp',
                          'activity-name'],),
                'op': kgb.SpyOpReturn((
                    0,
                    (b'"/view/x/vobs/els/.@@/main/int/CHECKEDOUT.78" '
                     b'"/view/x/vobs/els/test.pdf@@/main/int/CHECKEDOUT.77" '
                     b'"/view/x/vobs/els/new.py@@/main/int/CHECKEDOUT.71" '
                     b'"/view/x/vobs/els/test.py@@/main/int/CHECKEDOUT.64" '
                     b'"/view/x/vobs/els/.@@/main/int/2" '
                     b'"/view/x/vobs/els/test.py@@/main/int/3" '
                     b'"/view/x/vobs/els/test.py@@/main/int/2"\n'),
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'desc', '-fmt',
                          '%[version_predecessor]p',
                          '/view/x/vobs/els/.@@/main/int/2'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/main/int/1\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'desc', '-fmt',
                          '%[version_predecessor]p',
                          '/view/x/vobs/els/test.py@@/main/int/2'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'/main/int/1\n',
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.update_from_remote({}, {
            'repopath': '/view/server-view',
            'uuid': '9ac6856f.c9af11eb.9851.52:54:00:7f:63:a5',
        })

        changeset = client._get_activity_changeset('activity-name',
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
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'diff', '-ser',
                          '.@@/main/1', '.@@/main/CHECKEDOUT'],),
                'op': kgb.SpyOpReturn((
                    1,

                    b'********************************\n'
                    b'<<< directory 1: .@@/main/test-project_integration/2\n'
                    b'>>> directory 2:\n'
                    b'.@@/main/test-project_integration/CHECKEDOUT\n'
                    b'********************************\n'
                    b'-----[ renamed to ]-----\n'
                    b'< test2.py  --06-29T17:26 david\n'
                    b'---\n'
                    b'> renamed-file.py  --06-29T17:26 david\n'
                    b'-----[ deleted ]-----\n'
                    b'< test3.py  --07-28T00:30 david\n'
                    b'-----[ added ]-----\n'
                    b'> test4.py  --07-28T18:27 david\n',

                    b'',
                )),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          '.@@/main/1/test2.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-fake-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          '.@@/main/CHECKEDOUT/renamed-file.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'renamed-file.py-fake-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          '.@@/main/1/test3.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test3.py-fake-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          '.@@/main/CHECKEDOUT/test4.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test4.py-fake-oid',
                    b'',
                )),
            },
        ]))

        client = self.build_client(allow_dep_checks=False)

        self.assertEqual(
            client._get_file_changes_from_directories(
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
        client = self.build_client(allow_dep_checks=False,
                                   needs_diff=True)
        diff_tool = client.get_diff_tool()

        self.spy_on(ClearCaseClient._get_host_info,
                    op=kgb.SpyOpReturn({}),
                    owner=ClearCaseClient)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test2.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'file',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test.pdf'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'file',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'file',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path='test2.py@@/main/1',
                        modified_path='test2.py'),
                ),
                'op': kgb.SpyOpReturn((
                    1,

                    b'--- test2.py@@/main/1\t2022-05-23 '
                    b'20:10:38.578433000 +0000\n'
                    b'+++ test2.py\t2022-05-23 '
                    b'20:11:11.050410000 +0000\n'
                    b'@@ -0,0 +1,3 @@\n'
                    b'+#!/usr/bin/env python\n'
                    b'+\n'
                    b'+print(\'Test\')\n',

                    b''
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test2.py@@/main/1'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-fake-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test2.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-fake-oid',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path='test.pdf@@/main/0',
                        modified_path='test.pdf'),
                ),
                'op': kgb.SpyOpReturn((
                    2,
                    b'Binary files test.pdf@@/main/0 and test.pdf differ\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.pdf@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf-fake-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.pdf'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf-fake-oid',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path='test.py@@/main/1',
                        modified_path='test.py'),
                ),
                'op': kgb.SpyOpReturn((
                    1,

                    b'--- test.py@@/main/1\t2022-05-23 '
                    b'20:10:38.578433000 +0000\n'
                    b'+++ test.py\t2022-05-23 '
                    b'20:11:11.050410000 +0000\n'
                    b'@@ -1,3 +1,4 @@\n'
                    b'#!/usr/bin/env python\n'
                    b'\n'
                    b'print(\'Test 1\')\n'
                    b'+print(\'Added a line\')\n',

                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.py@@/main/1'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.py-fake-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.py-fake-oid',
                    b'',
                )),
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

        client.root_path = os.getcwd()
        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        metadata = client._get_diff_metadata({
            'base': '--rbtools-checkedout-base',
            'tip': '--rbtools-checkedout-changeset',
        })

        diff = client._do_diff(changeset, repository_info, metadata)

        self.assertEqual(
            self.normalize_diff_result(diff,
                                       date_format='%Y-%m-%d %H:%M:%S.%f %z'),
            {
                'diff': _LEGACY_DIFF,
            })

    def test_diff_diffx(self):
        """Testing ClearCaseClient._do_diff in diffx mode"""
        client = self.build_client(allow_dep_checks=False,
                                   needs_diff=True)
        diff_tool = client.get_diff_tool()

        self.spy_on(ClearCaseClient._get_host_info,
                    op=kgb.SpyOpReturn({}),
                    owner=ClearCaseClient)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test2.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'file',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test.pdf'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'file',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path='test2.py@@/main/1',
                        modified_path='test2.py'),
                ),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test2.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-vob-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test2.py@@/main/1'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-fake-old-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test2.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-fake-vob-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test2.py-fake-old-oid@vobuuid:test2.py-fake-vob-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-fake-version-old',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test2.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-fake-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test2.py-fake-oid@vobuuid:test2.py-fake-vob-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py-fake-version',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test2.py@@/main/1'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test2.py'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test2.py',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path='test.pdf@@/main/0',
                        modified_path='test.pdf'),
                ),
                'op': kgb.SpyOpReturn((
                    2,
                    b'Binary files test.pdf@@/main/0 and test.pdf differ\n',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test.pdf'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf-vob-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.pdf@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf-fake-old-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test.pdf'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf-vob-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test.pdf-fake-old-oid@vobuuid:test.pdf-vob-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf-fake-version-old',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test.pdf'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf-fake-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test.pdf-fake-oid@vobuuid:test.pdf-vob-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf-fake-version',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test.pdf@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test.pdf'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test.pdf',
                    b'',
                )),
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

        client.root_path = os.getcwd()
        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.is_legacy = False
        metadata = client._get_diff_metadata({
            'base': '--rbtools-checkedout-base',
            'tip': '--rbtools-checkedout-changeset',
        })

        diff = client._do_diff(changeset, repository_info, metadata)

        print(diff['diff'].decode('utf-8'))
        self.assertEqual(
            self.normalize_diff_result(diff,
                                       date_format='%Y-%m-%d %H:%M:%S.%f %z'),
            {
                'diff': _DIFFX_DIFF,
            })

    def test_diff_directory_legacy(self):
        """Testing ClearCaseClient._do_diff with a changed directory in legacy
        mode
        """
        client = self.build_client(allow_dep_checks=False,
                                   needs_diff=True)
        diff_tool = client.get_diff_tool()

        tmpfiles = self.precreate_tempfiles(4)
        self.spy_on(ClearCaseClient._get_host_info,
                    op=kgb.SpyOpReturn({}),
                    owner=ClearCaseClient)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'directory',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'directory',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'diff', '-ser', 'test-dir@@/main/0',
                          'test-dir'],),
                'op': kgb.SpyOpReturn((
                    1,

                    b'********************************\n'
                    b'<<< directory 1: test-dir@@/main/0\n'
                    b'>>> directory 2: test-dir\n'
                    b'********************************\n'
                    b'-----[ added ]-----\n'
                    b'> empty-dir/ --08-30T23:13 user\n',

                    b'',
                )),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          'test-dir/empty-dir/'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-new-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir-new-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-new-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'diff', '-ser',
                          'test-dir/empty-dir@@/main/0',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Directories are identical',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path=tmpfiles[0],
                        modified_path=tmpfiles[1]),
                ),
                'op': kgb.SpyOpReturn((
                    1,

                    b'--- %s\t2022-09-05 23:49:05.000000000 -0600\n'
                    b'+++ %s\t2022-09-05 23:49:09.000000000 -0600\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+empty-dir\n'
                    % (tmpfiles[0].encode('utf-8'),
                       tmpfiles[1].encode('utf-8')),

                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir-old-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path=tmpfiles[2],
                        modified_path=tmpfiles[3]),
                ),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir-new-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-old-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-new-oid',
                    b'',
                )),
            },
        ]))

        changeset = [
            ('test-dir@@/main/0', 'test-dir'),
            ('test-dir/empty-dir@@/main/0', 'test-dir/empty-dir'),
        ]

        client.root_path = os.getcwd()
        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        metadata = client._get_diff_metadata({
            'base': '--rbtools-checkedout-base',
            'tip': '--rbtools-checkedout-changeset',
        })

        diff = client._do_diff(changeset, repository_info, metadata)

        self.assertEqual(
            self.normalize_diff_result(diff,
                                       date_format='%Y-%m-%d %H:%M:%S.%f %z'),
            {
                'diff': _LEGACY_DIRECTORY_DIFF,
            })

    def test_diff_directory_diffx(self):
        """Testing ClearCaseClient._do_diff with a changed directory in diffx
        mode
        """
        client = self.build_client(allow_dep_checks=False,
                                   needs_diff=True)
        diff_tool = client.get_diff_tool()

        tmpfiles = self.precreate_tempfiles(4)
        self.spy_on(ClearCaseClient._get_host_info,
                    op=kgb.SpyOpReturn({}),
                    owner=ClearCaseClient)
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['cleartool', 'describe', '-fmt', '%m', 'test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'directory',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%m',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'directory',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'diff', '-ser', 'test-dir@@/main/0',
                          'test-dir'],),
                'op': kgb.SpyOpReturn((
                    1,

                    b'********************************\n'
                    b'<<< directory 1: test-dir@@/main/0\n'
                    b'>>> directory 2: test-dir\n'
                    b'********************************\n'
                    b'-----[ added ]-----\n'
                    b'> empty-dir/ --08-30T23:13 user\n',

                    b'',
                )),
            },
            {
                'args': (['cleartool', 'desc', '-fmt', '%On',
                          'test-dir/empty-dir/'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-new-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir-new-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-new-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'diff', '-ser',
                          'test-dir/empty-dir@@/main/0',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Directories are identical',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path=tmpfiles[0],
                        modified_path=tmpfiles[1]),
                ),
                'op': kgb.SpyOpReturn((
                    1,

                    b'--- %s\t2022-09-05 23:49:05.000000000 -0600\n'
                    b'+++ %s\t2022-09-05 23:49:09.000000000 -0600\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+empty-dir\n'
                    % (tmpfiles[0].encode('utf-8'),
                       tmpfiles[1].encode('utf-8')),

                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir-vob-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir-old-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test-dir-old-oid@vobuuid:test-dir-vob-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir-old-version',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:test-dir-new-oid@vobuuid:test-dir-vob-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir-new-version',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'test-dir',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (
                    diff_tool.make_run_diff_file_cmdline(
                        orig_path=tmpfiles[2],
                        modified_path=tmpfiles[3]),
                ),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'vob:test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-vob-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:empty-dir-new-oid@vobuuid:empty-dir-vob-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-new-version',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-old-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:empty-dir-old-oid@vobuuid:empty-dir-vob-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-old-version',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%On',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-new-oid',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%Vn',
                          'oid:empty-dir-new-oid'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir-new-version',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir/empty-dir@@/main/0'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir',
                    b'',
                )),
            },
            {
                'args': (['cleartool', 'describe', '-fmt', '%En',
                          'test-dir/empty-dir'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'empty-dir',
                    b'',
                )),
            },
        ]))

        changeset = [
            ('test-dir@@/main/0', 'test-dir'),
            ('test-dir/empty-dir@@/main/0', 'test-dir/empty-dir'),
        ]

        client.root_path = os.getcwd()
        repository_info = ClearCaseRepositoryInfo('/view/test/vob', 'vob')
        repository_info.is_legacy = False
        metadata = client._get_diff_metadata({
            'base': '--rbtools-checkedout-base',
            'tip': '--rbtools-checkedout-changeset',
        })

        diff = client._do_diff(changeset, repository_info, metadata)

        self.assertEqual(
            self.normalize_diff_result(diff,
                                       date_format='%Y-%m-%d %H:%M:%S.%f %z'),
            {
                'diff': _DIFFX_DIRECTORY_DIFF,
            })
