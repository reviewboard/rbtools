"""Errors for diff and patch operations.

Version Added:
    5.1
"""

from __future__ import annotations

from gettext import gettext as _
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rbtools.diffs.patcher import Patcher
    from rbtools.diffs.patches import PatchResult


class ApplyPatchError(Exception):
    """An error occurring during the patching process.

    Version Added:
        5.1
    """

    ######################
    # Instance variables #
    ######################

    #: The patch result indicating the failed patch.
    #:
    #: This will be set if the failure was during a patch operation. If it
    #: occurred before any files were patched, it will be ``None``.
    failed_patch_result: Optional[PatchResult]

    #: The patcher responsible for applying this patch.
    patcher: Patcher

    def __init__(
        self,
        message: str,
        *,
        patcher: Patcher,
        failed_patch_result: Optional[PatchResult] = None,
    ) -> None:
        """Initialize the error.

        The message supports a couple of standard ``%``-based formatting
        variables:

        ``%(patch_num)s``:
            The patch number, or batched patch range, the error pertains to.

            This is only available if ``failed_patch_result`` is set.

        ``%(patch_subject)s``:
            A descriptive label for the patch being applied.

            This will be in the form of ``patch %(patch_num)s of
            %(total_patches)s`` or ``patches %(patch_num)s of
            %(total_patches)s``.

            This is only available if ``failed_patch_result`` is set.

        ``%(total_patches)s``:
            The total number of patches being applied.

        Args:
            message (str):
                The error message to display.

            patcher (rbtools.diffs.patcher.Patcher):
                The patcher that generated the error.

            failed_patch_result (rbtools.diffs.patches.PatchResult, optional):
                The patch result indicating the failed patch.

                This must be set if the failure was during a patch operation.
                If it occurred before any files were patched, it must be
                ``None``
        """
        error_vars: dict[str, Any] = {
            'total_patches': len(patcher.patches),
        }

        if failed_patch_result is not None:
            patch_range = failed_patch_result.patch_range

            if patch_range is not None:
                start_patch_num, end_patch_num = patch_range
            else:
                # This is an older implementation. We'll have to assume
                # 1 higher than the previous patch.
                #
                # TODO [DEPRECATED]: This can go away with RBTools 7.
                start_patch_num = len(patcher.applied_patch_results) + 1
                end_patch_num = start_patch_num

            if start_patch_num == end_patch_num:
                error_vars['patch_num'] = start_patch_num
                patch_subject = \
                    _('patch %(patch_num)s of %(total_patches)s')
            else:
                error_vars['patch_num'] = f'{start_patch_num}-{end_patch_num}'
                patch_subject = \
                    _('patches %(patch_num)s of %(total_patches)s')

            error_vars['patch_subject'] = patch_subject % error_vars

        super().__init__(message % error_vars)

        self.failed_patch_result = failed_patch_result
        self.patcher = patcher
