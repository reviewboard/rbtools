"""Classes for representing patch results in SCM clients.

Version Added:
    4.0
"""

from __future__ import annotations

from typing import Optional

from housekeeping import deprecate_non_keyword_only_args

from rbtools.deprecation import RemovedInRBTools70Warning


class PatchAuthor:
    """The author of a patch or commit.

    This wraps the full name and e-mail address of a commit or patch's
    author primarily for use in :py:meth:`BaseSCMClient.apply_patch
    <rbtools.clients.base.scmclient.BaseSCMClient.apply_patch>`.

    Version Changed:
        4.0:
        * Moved from :py:mod:`rbtools.clients`. That module still provides
          compatibility imports.
    """

    ######################
    # Instance variables #
    ######################

    #: The e-mail address of the author.
    email: str

    #: The full name of the author.
    fullname: str

    @deprecate_non_keyword_only_args(RemovedInRBTools70Warning)
    def __init__(
        self,
        *,
        full_name: str,
        email: str,
    ) -> None:
        """Initialize the author information.

        Version Changed:
            5.1:
            This now requires keyword-only arguments. Support for positional
            arguments will be removed in RBTools 7.

        Args:
            full_name (str):
                The full name of the author.

            email (str):
                The e-mail address of the author.
        """
        self.fullname = full_name
        self.email = email


class PatchResult:
    """The result of a patch operation.

    This stores state on whether the patch could be applied (fully or
    partially), whether there are conflicts that can be resolved (as in
    conflict markers, not reject files), which files conflicted, and the
    patch output.

    Version Changed:
        4.0:
        * Moved from :py:mod:`rbtools.clients`. That module still provides
          compatibility imports.
    """

    ######################
    # Instance variables #
    ######################

    #: Whether the patch was applied.
    applied: bool

    #: A list of the filenames containing conflicts.
    conflicting_files: list[str]

    #: Whether the applied patch included conflicts.
    has_conflicts: bool

    #: The output of the patch command.
    patch_output: Optional[bytes]

    @deprecate_non_keyword_only_args(RemovedInRBTools70Warning)
    def __init__(
        self,
        *,
        applied: bool,
        has_conflicts: bool = False,
        conflicting_files: list[str] = [],
        patch_output: Optional[bytes] = None,
    ) -> None:
        """Initialize the object.

        Version Changed:
            5.1:
            This now requires keyword-only arguments. Support for positional
            arguments will be removed in RBTools 7.

        Args:
            applied (bool):
                Whether the patch was applied.

            has_conflicts (bool, optional):
                Whether the applied patch included conflicts.

            conflicting_files (list of str, optional):
                A list of the filenames containing conflicts.

            patch_output (str, optional):
                The output of the patch command.
        """
        self.applied = applied
        self.has_conflicts = has_conflicts
        self.conflicting_files = conflicting_files
        self.patch_output = patch_output
