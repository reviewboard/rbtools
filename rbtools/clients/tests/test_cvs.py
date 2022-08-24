"""Unit tests for CVSClient."""

from __future__ import unicode_literals

import re

import kgb

from rbtools.clients import RepositoryInfo
from rbtools.clients.cvs import CVSClient
from rbtools.clients.errors import SCMClientDependencyError
from rbtools.clients.tests import SCMClientTestCase
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_install


class CVSClientTests(SCMClientTestCase):
    """Unit tests for CVSClient."""

    scmclient_cls = CVSClient

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
