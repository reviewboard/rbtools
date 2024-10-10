"""Unit tests for rbtools.diffs.errors.ApplyPatchError.

Version Added:
    5.1
"""

from __future__ import annotations

from rbtools.diffs.errors import ApplyPatchError
from rbtools.diffs.patches import Patch, PatchResult
from rbtools.diffs.patcher import Patcher
from rbtools.testing import TestCase


class ApplyPatchErrorTests(TestCase):
    """Unit tests for rbtools.diffs.errors.ApplyPatchError.

    Version Added:
        5.1
    """

    def test_without_failed_patch_result(self) -> None:
        """Testing ApplyPatchError without failed patch result"""
        patcher = Patcher(patches=[
            Patch(content=b'...'),
            Patch(content=b'...'),
            Patch(content=b'...'),
        ])

        e = ApplyPatchError(
            message='%(total_patches)s',
            patcher=patcher)

        self.assertEqual(str(e), '3')

    def test_with_failed_patch_result_one_patch(self) -> None:
        """Testing ApplyPatchError with failed patch result and one patch"""
        patcher = Patcher(patches=[
            Patch(content=b'...'),
        ])

        e = ApplyPatchError(
            message='%(patch_num)s:%(patch_subject)s:%(total_patches)s',
            patcher=patcher,
            failed_patch_result=PatchResult(
                applied=False,
                patch_range=(1, 1)))

        self.assertEqual(str(e), '1:patch 1 of 1:1')

    def test_with_failed_patch_result_multiple_patches(self) -> None:
        """Testing ApplyPatchError with failed patch result and multiple
        patches
        """
        patcher = Patcher(patches=[
            Patch(content=b'...'),
            Patch(content=b'...'),
            Patch(content=b'...'),
        ])

        e = ApplyPatchError(
            message='%(patch_num)s:%(patch_subject)s:%(total_patches)s',
            patcher=patcher,
            failed_patch_result=PatchResult(
                applied=False,
                patch_range=(1, 3)))

        self.assertEqual(str(e), '1-3:patches 1-3 of 3:3')

    def test_with_failed_patch_result_no_patc_range(self) -> None:
        """Testing ApplyPatchError with failed patch result and no patch
        range information
        """
        patcher = Patcher(patches=[
            Patch(content=b'...'),
            Patch(content=b'...'),
        ])

        e = ApplyPatchError(
            message='%(patch_num)s:%(patch_subject)s:%(total_patches)s',
            patcher=patcher,
            failed_patch_result=PatchResult(applied=False))

        self.assertEqual(str(e), '1:patch 1 of 2:2')
