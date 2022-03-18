"""Unit tests for CVSClient."""

from __future__ import unicode_literals

import kgb

from rbtools.clients import RepositoryInfo
from rbtools.clients.cvs import CVSClient
from rbtools.clients.tests import SCMClientTestCase


class CVSClientTests(kgb.SpyAgency, SCMClientTestCase):
    """Unit tests for CVSClient."""

    def setUp(self):
        super(CVSClientTests, self).setUp()

        self.client = CVSClient(options=self.options)

    def test_get_repository_info_with_found(self):
        """Testing CVSClient.get_repository_info with repository found"""
        self.spy_on(CVSClient.get_local_path,
                    op=kgb.SpyOpReturn('/path/to/cvsdir'))

        repository_info = self.client.get_repository_info()

        self.assertIsInstance(repository_info, RepositoryInfo)
        self.assertIsNone(repository_info.base_path)
        self.assertEqual(repository_info.path, '/path/to/cvsdir')
        self.assertEqual(repository_info.local_path, '/path/to/cvsdir')

    def test_get_repository_info_with_not_found(self):
        """Testing CVSClient.get_repository_info with repository not found"""
        self.spy_on(CVSClient.get_local_path,
                    op=kgb.SpyOpReturn(None))

        repository_info = self.client.get_repository_info()

        self.assertIsNone(repository_info)
