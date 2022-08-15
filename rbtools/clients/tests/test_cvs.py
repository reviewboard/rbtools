"""Unit tests for CVSClient."""

from __future__ import unicode_literals

import kgb

from rbtools.clients import RepositoryInfo
from rbtools.clients.cvs import CVSClient
from rbtools.clients.tests import SCMClientTestCase


class CVSClientTests(kgb.SpyAgency, SCMClientTestCase):
    """Unit tests for CVSClient."""

    scmclient_cls = CVSClient

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
