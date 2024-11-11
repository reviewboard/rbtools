"""Unit tests for rbtools.clients.base.scmclient._LegacyPatcher.

Version Added:
    5.1
"""

from __future__ import annotations

import kgb

from rbtools.clients import BaseSCMClient
from rbtools.clients.base.repository import RepositoryInfo
from rbtools.clients.base.scmclient import _LegacyPatcher
from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.diffs.patches import Patch, PatchAuthor, PatchResult
from rbtools.testing import TestCase
from rbtools.utils.filesystem import make_tempfile


class LegacySCMClient(BaseSCMClient):
    scmclient_id = 'legacy-client'
    name = 'Legacy Client'

    def apply_patch(self, *args, **kwargs):
        return PatchResult(applied=True)


class LegacyPatcherTests(kgb.SpyAgency, TestCase):
    """Unit tests for _LegacyPatcher.

    Version Added:
        5.1
    """

    def test_init(self) -> None:
        """Testing _LegacyPatch.__init__"""
        client = LegacySCMClient()

        with self.assertWarns(RemovedInRBTools70Warning):
            patcher = client.get_patcher(patches=[])

        assert isinstance(patcher, _LegacyPatcher)
        self.assertIs(patcher.scmclient, client)
        self.assertFalse(patcher.can_patch_empty_files)
        self.assertFalse(patcher.can_commit)

    def test_init_with_can_patch_empty_files(self) -> None:
        """Testing _LegacyPatch.__init__ with supports_empty_files"""
        class MyLegacySCMClient(LegacySCMClient):
            def supports_empty_files(self) -> bool:
                return True

        client = MyLegacySCMClient()

        with self.assertWarns(RemovedInRBTools70Warning):
            patcher = client.get_patcher(patches=[])

        assert isinstance(patcher, _LegacyPatcher)
        self.assertIs(patcher.scmclient, client)
        self.assertTrue(patcher.can_patch_empty_files)
        self.assertFalse(patcher.can_commit)

    def test_init_with_can_commit(self) -> None:
        """Testing _LegacyPatch.__init__ with can_commit"""
        class MyLegacySCMClient(LegacySCMClient):
            def create_commit(self, *args, **kwargs):
                pass

        client = MyLegacySCMClient()

        with self.assertWarns(RemovedInRBTools70Warning):
            patcher = client.get_patcher(patches=[])

        assert isinstance(patcher, _LegacyPatcher)
        self.assertIs(patcher.scmclient, client)
        self.assertFalse(patcher.can_patch_empty_files)
        self.assertTrue(patcher.can_commit)

    def test_patch(self) -> None:
        """Testing _LegacyPatch.patch"""
        client = LegacySCMClient()

        with self.assertWarns(RemovedInRBTools70Warning):
            patcher = client.get_patcher(
                patches=[
                    Patch(content=b'...'),
                ],
                repository_info=RepositoryInfo())

        self.spy_on(client.apply_patch)
        self.spy_on(make_tempfile)

        results = list(patcher.patch())

        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertIsInstance(result, PatchResult)
        self.assertTrue(result.applied)

        self.assertSpyCalledWith(
            client.apply_patch,
            base_dir='',
            base_path=None,
            p=None,
            patch_file=make_tempfile.calls[0].return_value,
            revert=False)

    def test_patch_with_commit(self) -> None:
        """Testing _LegacyPatch.patch with commit"""
        class MyLegacySCMClient(LegacySCMClient):
            def create_commit(self, *args, **kwargs):
                pass

        client = MyLegacySCMClient()

        with self.assertWarns(RemovedInRBTools70Warning):
            patcher = client.get_patcher(
                patches=[
                    Patch(content=b'...'),
                ],
                repository_info=RepositoryInfo())

        self.assertTrue(patcher.can_commit)

        self.spy_on(client.apply_patch)
        self.spy_on(make_tempfile)

        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Test commit')
        results = list(patcher.patch())

        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertIsInstance(result, PatchResult)
        self.assertTrue(result.applied)

        self.assertSpyCalledWith(
            client.apply_patch,
            base_dir='',
            base_path=None,
            p=None,
            patch_file=make_tempfile.calls[0].return_value,
            revert=False)
