"""Unit tests for CVSClient."""

import os
import re
from typing import Optional

import kgb

from rbtools.clients import RepositoryInfo
from rbtools.clients.cvs import CVSClient
from rbtools.clients.errors import SCMClientDependencyError
from rbtools.clients.tests import SCMClientTestCase
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_install
from rbtools.utils.process import run_process


class CVSClientTests(SCMClientTestCase):
    """Unit tests for CVSClient."""

    scmclient_cls = CVSClient

    @classmethod
    def setup_checkout(
        cls,
        checkout_dir: str,
    ) -> Optional[str]:
        """Populate a CVS checkout.

        This will create a checkout of the sample CVS repository stored
        in the :file:`testdata` directory.

        Args:
            checkout_dir (str):
                The top-level directory in which the clones will be placed.

        Returns:
            str:
            The main checkout directory, or ``None`` if :command:`cvs` isn't
            in the path.
        """
        if not CVSClient().has_dependencies():
            return None

        cls.cvs_repo_dir = os.path.join(cls.testdata_dir, 'cvs-repo')
        cls.cvs_project_repo_dir = os.path.join(cls.cvs_repo_dir,
                                                'test-project')

        run_process([
            'cvs', '-d', cls.cvs_repo_dir, 'co', '-d', checkout_dir,
            'test-project',
        ])

        return checkout_dir

    def test_check_dependencies_with_found(self):
        """Testing CVSClient.check_dependencies with dependencies found"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['cvs'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cvs'])

    def test_check_dependencies_with_missing(self):
        """Testing CVSClient.check_dependencies with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools ('cvs') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cvs'])

    def test_get_local_path_with_deps_missing(self):
        """Testing CVSClient.get_local_path with dependencies missing"""
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
                         'Unable to execute "cvs": skipping CVS')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cvs'])

    def test_get_local_path_with_deps_not_checked(self):
        """Testing CVSClient.get_local_path with dependencies not checked"""
        # A False value is used just to ensure get_local_path() bails early,
        # and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)
        message = re.escape(
            'Either CVSClient.setup() or CVSClient.has_dependencies() must '
            'be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_local_path()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "cvs": skipping CVS')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cvs'])

    def test_get_repository_info_with_found(self):
        """Testing CVSClient.get_repository_info with repository found"""
        client = self.build_client()

        self.spy_on(client.get_local_path,
                    op=kgb.SpyOpReturn('/path/to/cvsdir'))

        repository_info = client.get_repository_info()

        self.assertIsInstance(repository_info, RepositoryInfo)
        self.assertIsNone(repository_info.base_path)
        self.assertEqual(repository_info.path, '/path/to/cvsdir')
        self.assertEqual(repository_info.local_path, '/path/to/cvsdir')

    def test_get_repository_info_with_not_found(self):
        """Testing CVSClient.get_repository_info with repository not found"""
        client = self.build_client()

        self.spy_on(client.get_local_path,
                    op=kgb.SpyOpReturn(None))

        repository_info = client.get_repository_info()

        self.assertIsNone(repository_info)

    def test_get_repository_info_with_deps_missing(self):
        """Testing CVSClient.get_repository_info with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_repository_info(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            repository_info = client.get_repository_info()

        self.assertIsNone(repository_info)

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "cvs": skipping CVS')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cvs'])

    def test_get_repository_info_with_deps_not_checked(self):
        """Testing CVSClient.get_repository_info with dependencies not checked
        """
        # A False value is used just to ensure get_repository_info() bails
        # early, and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either CVSClient.setup() or CVSClient.has_dependencies() must '
            'be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_repository_info()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "cvs": skipping CVS')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cvs'])

    def test_diff(self):
        """Testing CVSClient.diff"""
        client = self.build_client(needs_diff=True)

        with open('file1', 'w') as fp:
            fp.write('new content!\n')

        with open('file3', 'w') as fp:
            fp.write('even more new content!\n')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            self.normalize_diff_result(
                client.diff(revisions),
                date_format='%d %b %Y %H:%M:%S -000'),
            {
                'diff': (
                    b'Index: file1\n'
                    b'==================================================='
                    b'================\n'
                    b'RCS file: %(checkout_dir)s/file1,v\n'
                    b'retrieving revision 1.1\n'
                    b'diff -u -r1.1 file1\n'
                    b'--- file1\t02 Jan 2022 12:34:56 -0000\t1.1\n'
                    b'+++ file1\t02 Jan 2022 12:34:56 -0000\n'
                    b'@@ -1 +1 @@\n'
                    b'-Oh hi there.\n'
                    b'+new content!\n'
                    b'Index: file3\n'
                    b'==================================================='
                    b'================\n'
                    b'RCS file: %(checkout_dir)s/file3,v\n'
                    b'retrieving revision 1.1\n'
                    b'diff -u -r1.1 file3\n'
                    b'--- file3\t02 Jan 2022 12:34:56 -0000\t1.1\n'
                    b'+++ file3\t02 Jan 2022 12:34:56 -0000\n'
                    b'@@ -1 +1 @@\n'
                    b'-Where even am I right now.\n'
                    b'+even more new content!\n'
                    % {
                        b'checkout_dir':
                            self.cvs_project_repo_dir.encode('utf-8'),
                    }
                ),
            })

    def test_diff_with_include_files(self):
        """Testing CVSClient.diff with include_files="""
        client = self.build_client(needs_diff=True)

        with open('file1', 'w') as fp:
            fp.write('new content!\n')

        with open('file3', 'w') as fp:
            fp.write('even more new content!\n')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            self.normalize_diff_result(
                client.diff(revisions,
                            include_files=['file1']),
                date_format='%d %b %Y %H:%M:%S -000'),
            {
                'diff': (
                    b'Index: file1\n'
                    b'==================================================='
                    b'================\n'
                    b'RCS file: %(checkout_dir)s/file1,v\n'
                    b'retrieving revision 1.1\n'
                    b'diff -u -r1.1 file1\n'
                    b'--- file1\t02 Jan 2022 12:34:56 -0000\t1.1\n'
                    b'+++ file1\t02 Jan 2022 12:34:56 -0000\n'
                    b'@@ -1 +1 @@\n'
                    b'-Oh hi there.\n'
                    b'+new content!\n'
                    % {
                        b'checkout_dir':
                            self.cvs_project_repo_dir.encode('utf-8'),
                    }
                ),
            })

    def test_diff_with_exclude_patterns(self):
        """Testing CVSClient.diff with exclude_patterns="""
        client = self.build_client(needs_diff=True)

        with open('file1', 'w') as fp:
            fp.write('new content!\n')

        with open('file3', 'w') as fp:
            fp.write('even more new content!\n')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            self.normalize_diff_result(
                client.diff(revisions,
                            exclude_patterns=['*1']),
                date_format='%d %b %Y %H:%M:%S -000'),
            {
                'diff': (
                    b'Index: file3\n'
                    b'==================================================='
                    b'================\n'
                    b'RCS file: %(checkout_dir)s/file3,v\n'
                    b'retrieving revision 1.1\n'
                    b'diff -u -r1.1 file3\n'
                    b'--- file3\t02 Jan 2022 12:34:56 -0000\t1.1\n'
                    b'+++ file3\t02 Jan 2022 12:34:56 -0000\n'
                    b'@@ -1 +1 @@\n'
                    b'-Where even am I right now.\n'
                    b'+even more new content!\n'
                    % {
                        b'checkout_dir':
                            self.cvs_project_repo_dir.encode('utf-8'),
                    }
                ),
            })
