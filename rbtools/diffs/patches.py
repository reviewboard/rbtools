"""Patch information and support for applying patches.

Version Added:
    5.1:
    :py:class:`PatchAuthor` and :py:class:`PatchResult` were moved from
    :py:mod:`rbtools.scmclients.base.patch`.
"""

from __future__ import annotations

from contextlib import contextmanager
from gettext import gettext as _
from pathlib import Path
from typing import Iterator, Optional

from housekeeping import deprecate_non_keyword_only_args

from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.utils.filesystem import make_tempfile


class PatchAuthor:
    """The author of a patch or commit.

    This wraps the full name and e-mail address of a commit or patch's
    author primarily for use in :py:meth:`BaseSCMClient.apply_patch()
    <rbtools.clients.base.scmclient.BaseSCMClient.apply_patch>`.

    Version Changed:
        5.1:
        * Moved from :py:mod:`rbtools.clients.base.patch`. That module
          will provide compatibility imports until RBTools 7.

    Version Changed:
        4.0:
        * Moved from :py:mod:`rbtools.clients`. That module still provides
          compatibility imports until RBTools 7.
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


class Patch:
    """A patch to a repository that can be applied.

    This consolidates metadata on the patch (the author and description)
    along with information needed to apply a patch (the base directory
    within the repository in which to apply the patch, the patch level,
    and the patch contents).

    Version Added:
        5.1
    """

    ######################
    # Instance variables #
    ######################

    #: The author of the patch.
    #:
    #: This will generally be available if generating a patch from an
    #: existing commit.
    author: Optional[PatchAuthor]

    #: The base directory in the repository where the patch was generated.
    #:
    #: This is dependent on the SCM and the method used to generate the
    #: patch.
    base_dir: Optional[str]

    #: The commit message describing the patch.
    #:
    #: This will generally be available if generating a patch from an
    #: existing commit.
    message: Optional[str]

    #: The path prefix stripping level to use when applying the patch.
    #:
    #: This is the number of path components to strip from the beginning of
    #: each filename in the patch. It's the equivalent of
    #: :command:`patch -p<X>`.
    prefix_level: Optional[int]

    #: The cached contents of the patch.
    _content: Optional[bytes]

    #: Whether the patch is opened for reading.
    _opened: bool

    #: The cached file path for the patch.
    _path: Optional[Path]

    def __init__(
        self,
        *,
        author: Optional[PatchAuthor] = None,
        base_dir: Optional[str] = None,
        content: Optional[bytes] = None,
        message: Optional[str] = None,
        path: Optional[Path] = None,
        prefix_level: Optional[int] = 0,
    ) -> None:
        """Initialize the patch.

        Args:
            author (PatchAuthor, optional):
                The author of the patch.

            base_dir (str, optional):
                The directory in the repository where the patch was generated.

                This is dependent on the SCM and the method used to generate
                the patch.

            content (bytes, optional):
                The contents of the patch.

                Either this or ``path`` must be provided.

            message (str, optional):
                The commit message describing the patch.

            path (pathlib.Path, optional):
                The file path where the patch resides.

                Either this or ``content`` must be provided.

            prefix_level (int, optional):
                The path prefix stripping level to use when applying the
                patch.

                This is the number of path components to strip from the
                beginning of each filename in the patch. It's the equivalent
                of :command:`patch -p<X>`.

                If not provided, the patching code will determine a default.
                This default may not be correct for the patch.

        Raises:
            ValueError:
                One or more parameters or parameter combinations were invalid.
        """
        if not content and not path:
            raise ValueError(_('Either content= or path= must be provided.'))

        self.author = author
        self.base_dir = base_dir
        self.message = message
        self.prefix_level = prefix_level
        self._content = content
        self._path = path
        self._opened = False

    @contextmanager
    def open(self) -> Iterator[None]:
        """Open the patch for reading.

        Once upon, either the content or the file path can be directly read.
        Any temporary state will be cleaned up once the patch is no longer
        open.

        This must be called before accessing :py:attr;`content` or
        :py:attr:`path`.

        Context:
            The patch will be available for reading.
        """
        had_content = (self._content is not None)
        had_path = (self._path is not None)

        self._opened = True

        try:
            yield
        finally:
            if not had_content:
                self._content = None

            if not had_path:
                path = self._path

                if path:
                    path.unlink()
                    self._path = None

    @property
    def content(self) -> bytes:
        """The raw content of the patch.

        The patch must be :py:meth:`opened <open>` before this is called.

        Returns:
            bytes:
            The raw patch contents.

        Raises:
            IOError:
                The patch was not opened for reading or could not be read
                from disk.
        """
        self._validate_open()

        content = self._content

        if content is None:
            path = self._path
            assert path is not None

            with open(path, 'rb') as fp:
                content = fp.read()

            self._content = content

        return content

    @property
    def path(self) -> Path:
        """A path to the patch content.

        The returned path may be a temporary file path, which would be
        automatically deleted once the patch is closed for reading.

        The patch must be :py:meth:`opened <open>` before this is called.

        Returns:
            bytes:
            The raw patch contents.

        Raises:
            IOError:
                The patch was not opened for reading or a temporary file
                could not be written to disk.
        """
        self._validate_open()

        path = self._path

        if path is None:
            content = self._content
            assert content is not None

            path = Path(make_tempfile(content=content))
            self._path = path

        return path

    def _validate_open(self) -> None:
        """Validate that the patch is opened for reading.

        Raises:
            IOError:
                The patch was not opened for reading.
        """
        if not self._opened:
            raise IOError(_('Patch objects must be opened before being read.'))


class PatchResult:
    """The result of a patch operation.

    This stores state on whether the patch could be applied (fully or
    partially), whether there are conflicts that can be resolved (as in
    conflict markers, not reject files), which files conflicted, and the
    patch output.

    Version Changed:
        5.1:
        * Moved from :py:mod:`rbtools.clients.base.patch`. That module
          will provide compatibility imports until RBTools 7.

    Version Changed:
        4.0:
        * Moved from :py:mod:`rbtools.clients`. That module will provide
          compatibility imports until RBTools 7.
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

    #: The patch that was being applied.
    #:
    #: This may be ``None``, depending on the method used to apply the patch.
    #:
    #: Version Added:
    #:     5.1
    patch: Optional[Patch]

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
        patch: Optional[Patch] = None,
    ) -> None:
        """Initialize the object.

        Version Changed:
            5.1:
            * This now requires keyword-only arguments. Support for positional
              arguments will be removed in RBTools 7.

            * Added the ``patch`` argument.

        Args:
            applied (bool):
                Whether the patch was applied.

            has_conflicts (bool, optional):
                Whether the applied patch included conflicts.

            conflicting_files (list of str, optional):
                A list of the filenames containing conflicts.

            patch_output (bytes, optional):
                The output of the patch command.

            patch (Patch, optional):
                The patch that was being applied, if available.

                Version Added:
                    5.1
        """
        self.applied = applied
        self.conflicting_files = conflicting_files
        self.has_conflicts = has_conflicts
        self.patch = patch
        self.patch_output = patch_output

    @property
    def success(self) -> bool:
        return self.applied and not self.has_conflicts
