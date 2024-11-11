"""Unit tests for rbtools.clients.base.scmclient.BaseSCMClient."""

from __future__ import annotations

import re
import warnings
from typing import TYPE_CHECKING

import kgb

from rbtools.clients import BaseSCMClient
from rbtools.clients.base.scmclient import _LegacyPatcher, SCMClientPatcher
from rbtools.clients.errors import SCMClientDependencyError
from rbtools.deprecation import (RemovedInRBTools50Warning,
                                 RemovedInRBTools70Warning)
from rbtools.diffs.errors import ApplyPatchError
from rbtools.diffs.patches import PatchResult
from rbtools.diffs.tools.backends.gnu import GNUDiffTool
from rbtools.diffs.tools.errors import MissingDiffToolError
from rbtools.diffs.tools.registry import diff_tools_registry
from rbtools.testing import TestCase

if TYPE_CHECKING:
    from rbtools.diffs.patches import Patch


class MySCMClient(BaseSCMClient):
    scmclient_id = 'my-client'
    name = 'My Client'


class MySCMClientWithDepErrors(MySCMClient):
    def check_dependencies(self) -> None:
        raise SCMClientDependencyError(missing_exes=['dep1', 'dep2'])


class BaseSCMClientTests(kgb.SpyAgency, TestCase):
    """Unit tests for BaseSCMClient."""

    def test_setup_with_no_errors(self):
        """Testing BaseSCMClient.setup with no errors"""
        client = MySCMClient()
        self.spy_on(client.check_dependencies)

        self.assertFalse(client.is_setup)
        self.assertIsNone(client._has_deps)

        # This should not raise any exceptions. If it does, we want to see
        # them.
        client.setup()

        self.assertTrue(client.is_setup)
        self.assertTrue(client._has_deps)

        # A second call should do nothing.
        client.setup()

        self.assertSpyCallCount(client.check_dependencies, 1)

    def test_setup_with_dep_errors(self):
        """Testing BaseSCMClient.setup with dependency errors"""
        client = MySCMClientWithDepErrors()
        self.spy_on(client.check_dependencies)

        self.assertFalse(client.is_setup)
        self.assertIsNone(client._has_deps)

        message = "Command line tools ('dep1', 'dep2') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError,
                                      message):
            client.setup()

        self.assertFalse(client.is_setup)
        self.assertFalse(client._has_deps)

        # A second call should repeat this.
        with self.assertRaisesMessage(SCMClientDependencyError,
                                      message):
            client.setup()

        self.assertSpyCallCount(client.check_dependencies, 2)

    def test_has_dependencies_with_found(self):
        """Testing BaseSCMClient.has_dependencies with found"""
        client = MySCMClient()
        self.spy_on(client.check_dependencies)
        self.spy_on(client.setup)

        self.assertFalse(client.is_setup)
        self.assertIsNone(client._has_deps)

        self.assertTrue(client.has_dependencies())

        self.assertTrue(client.is_setup)
        self.assertTrue(client._has_deps)

        # A second call should use cache.
        self.assertTrue(client.has_dependencies())

        self.assertSpyCallCount(client.check_dependencies, 1)
        self.assertSpyCallCount(client.setup, 1)

    def test_has_dependencies_with_not_found(self):
        """Testing BaseSCMClient.has_dependencies with not found"""
        client = MySCMClientWithDepErrors()
        self.spy_on(client.check_dependencies)
        self.spy_on(client.setup)

        self.assertFalse(client.is_setup)
        self.assertIsNone(client._has_deps)

        self.assertFalse(client.has_dependencies())

        self.assertFalse(client.is_setup)
        self.assertFalse(client._has_deps)

        # A second call should use cache.
        self.assertFalse(client.has_dependencies())

        self.assertSpyCallCount(client.check_dependencies, 1)
        self.assertSpyCallCount(client.setup, 1)

    def test_has_dependencies_with_expect_checked_and_not_checked(self):
        """Testing BaseSCMClient.has_dependencies with expect_checked=True and
        not checked
        """
        client = MySCMClient()

        message = re.escape(
            'Either MySCMClient.setup() or MySCMClient.has_dependencies() '
            'must be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
            self.assertTrue(client.has_dependencies(expect_checked=True))

    def test_has_dependencies_with_expect_checked_and_checked(self):
        """Testing BaseSCMClient.has_dependencies with expect_checked=True
        and checked
        """
        client = MySCMClient()
        client.setup()

        with warnings.catch_warnings(record=True) as w:
            self.assertTrue(client.has_dependencies(expect_checked=True))

        self.assertEqual(w, [])

    def test_has_dependencies_after_setup_with_found(self):
        """Testing BaseSCMClient.has_dependencies after setup() with found"""
        client = MySCMClient()
        self.spy_on(client.check_dependencies)
        self.spy_on(client.setup)

        client.setup()

        self.assertTrue(client.has_dependencies())

        # A second call should use cache.
        self.assertTrue(client.has_dependencies())

        self.assertSpyCallCount(client.check_dependencies, 1)
        self.assertSpyCallCount(client.setup, 1)

    def test_has_dependencies_after_setup_with_not_found(self):
        """Testing BaseSCMClient.has_dependencies after setup() with not found
        """
        client = MySCMClientWithDepErrors()
        self.spy_on(client.check_dependencies)
        self.spy_on(client.setup)

        message = "Command line tools ('dep1', 'dep2') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError,
                                      message):
            client.setup()

        self.assertFalse(client.has_dependencies())

        # A second call should use cache.
        self.assertFalse(client.has_dependencies())

        self.assertSpyCallCount(client.check_dependencies, 1)
        self.assertSpyCallCount(client.setup, 1)

    def test_get_diff_tool_with_requires_true(self):
        """Testing BaseSCMClient.get_diff_tool with requires_diff_tool=True"""
        class MySCMClient(BaseSCMClient):
            scmclient_id = 'my-client'
            name = 'My Client'
            requires_diff_tool = True

        client = MySCMClient()

        # Any tool is a successful result.
        self.assertIsNotNone(client.get_diff_tool())

    def test_get_diff_tool_with_requires_ids(self):
        """Testing BaseSCMClient.get_diff_tool with requires_diff_tool={id...}
        """
        class MySCMClient(BaseSCMClient):
            scmclient_id = 'my-client'
            name = 'My Client'
            requires_diff_tool = ['gnu']

        self.spy_on(GNUDiffTool.check_available,
                    owner=GNUDiffTool,
                    op=kgb.SpyOpReturn(True))

        try:
            client = MySCMClient()
            self.assertIsInstance(client.get_diff_tool(), GNUDiffTool)
        finally:
            diff_tools_registry.reset()

    def test_get_diff_tool_with_requires_false(self):
        """Testing BaseSCMClient.get_diff_tool with requires_diff_tool=False
        """
        class MySCMClient(BaseSCMClient):
            scmclient_id = 'my-client'
            name = 'My Client'
            requires_diff_tool = False

        client = MySCMClient()
        self.assertIsNone(client.get_diff_tool())

    def test_get_diff_tool_with_tool_missing(self):
        """Testing BaseSCMClient.get_diff_tool with no available tool"""
        class MySCMClient(BaseSCMClient):
            scmclient_id = 'my-client'
            name = 'My Client'
            requires_diff_tool = ['xxx']

        client = MySCMClient()

        with self.assertRaises(MissingDiffToolError):
            client.get_diff_tool()

    def test_get_patcher(self) -> None:
        """Testing BaseSCMClient.get_patcher"""
        client = MySCMClient()
        patcher = client.get_patcher(patches=[])

        self.assertIs(type(patcher), SCMClientPatcher)

    def test_get_patcher_with_legacy_apply_patch(self) -> None:
        """Testing BaseSCMClient.get_patcher with legacy custom apply_patch()
        """
        class LegacySCMClient(MySCMClient):
            def apply_patch(self, *args, **kwargs):
                pass

        client = LegacySCMClient()

        message = re.escape(
            'LegacySCMClient must be updated to set a custom patcher class '
            'as LegacySCMClient.patcher_cls. Support for apply_patch() will '
            'be removed in RBTools 7.'
        )

        with self.assertWarnsRegex(RemovedInRBTools70Warning, message):
            patcher = client.get_patcher(patches=[])

        self.assertIs(type(patcher), _LegacyPatcher)

    def test_get_patcher_with_legacy_apply_patch_and_custom_patcher(
        self,
    ) -> None:
        """Testing BaseSCMClient.get_patcher with legacy custom apply_patch()
        and custom patcher
        """
        class MyPatcher(SCMClientPatcher):
            pass

        class LegacySCMClient(MySCMClient):
            patcher_cls = MyPatcher

            def apply_patch(self, *args, **kwargs):
                pass

        client = LegacySCMClient()
        patcher = client.get_patcher(patches=[])

        self.assertIs(type(patcher), MyPatcher)

    def test_apply_patch(self) -> None:
        """Testing SCMClient.apply_patch"""
        class MyPatcher(SCMClientPatcher):
            def apply_single_patch(
                self,
                *,
                patch: Patch,
                patch_num: int,
            ) -> PatchResult:
                return PatchResult(applied=True,
                                   patch=patch,
                                   patch_range=(patch_num, patch_num))

        class MyPatcherSCMClient(MySCMClient):
            patcher_cls = MyPatcher

        client = MyPatcherSCMClient()
        result = client.apply_patch(patch_file='mypatch.diff',
                                    base_path='/',
                                    base_dir='/')

        self.assertIsInstance(result, PatchResult)
        self.assertTrue(result.applied)
        self.assertEqual(result.patch_range, (1, 1))

        patch = result.patch
        assert patch is not None
        self.assertEqual(str(patch.path), 'mypatch.diff')
        self.assertIsNone(patch.prefix_level)

    def test_apply_patch_with_patch_level(self) -> None:
        """Testing SCMClient.apply_patch with patch level"""
        class MyPatcher(SCMClientPatcher):
            def apply_single_patch(
                self,
                *,
                patch: Patch,
                patch_num: int,
            ) -> PatchResult:
                return PatchResult(applied=True,
                                   patch=patch,
                                   patch_range=(patch_num, patch_num))

        class MyPatcherSCMClient(MySCMClient):
            patcher_cls = MyPatcher

        client = MyPatcherSCMClient()
        result = client.apply_patch(patch_file='mypatch.diff',
                                    base_path='/',
                                    base_dir='/',
                                    p='2')

        self.assertIsInstance(result, PatchResult)
        self.assertTrue(result.applied)
        self.assertEqual(result.patch_range, (1, 1))

        patch = result.patch
        assert patch is not None
        self.assertEqual(str(patch.path), 'mypatch.diff')
        self.assertEqual(patch.prefix_level, 2)

    def test_apply_patch_with_patch_level_invalid(self) -> None:
        """Testing SCMClient.apply_patch with invalid patch level"""
        class MyPatcher(SCMClientPatcher):
            def apply_single_patch(
                self,
                *,
                patch: Patch,
                patch_num: int,
            ) -> PatchResult:
                return PatchResult(applied=True,
                                   patch=patch,
                                   patch_range=(patch_num, patch_num))

        class MyPatcherSCMClient(MySCMClient):
            patcher_cls = MyPatcher

        client = MyPatcherSCMClient()

        with self.assertLogs(level='WARNING') as ctx:
            result = client.apply_patch(patch_file='mypatch.diff',
                                        base_path='/',
                                        base_dir='/',
                                        p='XXX')

        self.assertEqual(ctx.records[0].msg,
                         'Invalid -p value: %s; assuming zero.')
        self.assertEqual(ctx.records[0].args, ('XXX',))

        self.assertIsInstance(result, PatchResult)
        self.assertTrue(result.applied)
        self.assertEqual(result.patch_range, (1, 1))

        patch = result.patch
        assert patch is not None
        self.assertEqual(str(patch.path), 'mypatch.diff')
        self.assertIsNone(patch.prefix_level)

    def test_apply_patch_with_patch_error(self) -> None:
        """Testing SCMClient.apply_patch with ApplyPatchError"""
        class MyPatcher(SCMClientPatcher):
            def apply_single_patch(
                self,
                *,
                patch: Patch,
                patch_num: int,
            ) -> PatchResult:
                raise ApplyPatchError(
                    'Something went wrong',
                    patcher=self,
                    failed_patch_result=PatchResult(
                        applied=False,
                        patch=patch,
                        patch_output=b'XXX Output',
                        patch_range=(patch_num, patch_num)))

        class MyPatcherSCMClient(MySCMClient):
            patcher_cls = MyPatcher

        client = MyPatcherSCMClient()
        result = client.apply_patch(patch_file='mypatch.diff',
                                    base_path='/',
                                    base_dir='/')

        self.assertIsInstance(result, PatchResult)
        self.assertFalse(result.applied)
        self.assertEqual(result.patch_range, (1, 1))

        patch = result.patch
        assert patch is not None
        self.assertEqual(str(patch.path), 'mypatch.diff')
        self.assertIsNone(patch.prefix_level)
