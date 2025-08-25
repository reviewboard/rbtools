"""Patch information and support for applying patches.

Version Added:
    5.1:
    :py:class:`PatchAuthor` and :py:class:`PatchResult` were moved from
    :py:mod:`rbtools.scmclients.base.patch`.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from gettext import gettext as _
from pathlib import Path
from typing import Literal, TYPE_CHECKING
from urllib.error import URLError
from urllib.request import urlopen

from housekeeping import deprecate_non_keyword_only_args
from typelets.runtime import raise_invalid_type

from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.utils.filesystem import make_tempfile

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from typing_extensions import TypeAlias

    from rbtools.api.resource import FileAttachmentItemResource


logger = logging.getLogger(__name__)


#: Type for the status of a binary file change.
#:
#: Version Added:
#:     6.0
BinaryFileStatus: TypeAlias = Literal[
    'added',
    'deleted',
    'modified',
    'moved',
]


class BinaryFilePatch:
    """Represents a binary file in a patch with lazy content loading.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: Download error if any.
    download_error: str | None

    #: Modified file path relative to the repository root.
    new_path: str | None

    #: Original file path relative to the repository root.
    old_path: str | None

    #: File operation.
    status: BinaryFileStatus

    #: Source for downloading content.
    _attachment: FileAttachmentItemResource | None

    #: Cached binary content.
    _content: bytes | None

    #: Whether download was attempted.
    _content_loaded: bool

    def __init__(
        self,
        *,
        old_path: str | None,
        new_path: str | None,
        status: BinaryFileStatus,
        file_attachment: FileAttachmentItemResource | None,
    ) -> None:
        """Initialize the binary file.

        Args:
            old_path (str):
                Original file path relative to the repository root.

            new_path (str):
                Modified file path relative to the repository root.

            status (str):
                File operation ('added', 'deleted', 'modified', or 'moved').

            file_attachment (rbtools.api.resource.FileAttachmentItemResource):
                Source for downloading content.
        """
        self.download_error = None
        self.old_path = old_path
        self.new_path = new_path
        self.status = status
        self._attachment = file_attachment
        self._content = None
        self._content_loaded = False

    @property
    def path(self) -> str:
        """The path of the file, for display purposes."""
        path = self.new_path or self.old_path
        assert path is not None

        return path

    @property
    def content(self) -> bytes | None:
        """Lazy-loaded binary content."""
        if not self._content_loaded:
            self._download_content()

        return self._content

    def _download_content(self) -> None:
        """Download binary content from the API."""
        if self._content_loaded:
            return

        if self.status == 'deleted':
            # For deleted files, we don't need anything.
            self._content_loaded = True
        elif not self._attachment:
            self.download_error = _('No attachment available')
            self._content_loaded = True
        else:
            try:
                url = self._attachment.absolute_url

                logger.debug('Downloading binary file for %s from %s',
                             self.path, url)

                with urlopen(url) as rsp:
                    self._content = rsp.read()
            except URLError as e:
                self.download_error = str(e)

            self._content_loaded = True

    def __repr__(self) -> str:
        """Return a string representation of the object.

        Returns:
            str:
            The string representation.
        """
        return (
            f'<BinaryFilePatch(old_path={self.old_path!r}, '
            f'new_path={self.new_path!r}, status={self.status!r}, '
            f'loaded={self._content_loaded})>'
        )


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
    #:
    #: Version Added:
    #:     5.1:
    #:     This was added as a replacement for :py:attr:`fullname`.
    full_name: str

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
        self.full_name = full_name
        self.email = email

    @property
    def fullname(self) -> str:
        """The full name  of this author.

        Deprecated:
            5.1:
            This is deprecated in favor of :py:attr:`full_name`. It will be
            removed in RBTools 7.

        Returns:
            bool:
            The full name of the author.
        """
        RemovedInRBTools70Warning.warn(
            'PatchAuthor.fullname is deprecated. Please use '
            'PatchAuthor.full_name instead. This will be removed in '
            'RBTools 7.')

        return self.full_name

    def __eq__(
        self,
        other: object,
    ) -> bool:
        """Return whether this author is equal to another.

        Args:
            other (object):
                The other object to compare to.

        Returns:
            bool:
            ``True`` if the other object is equal to this one.
            ``False`` if it is not.
        """
        return (isinstance(other, PatchAuthor) and
                self.email == other.email and
                self.full_name == other.full_name)

    def __hash__(self) -> int:
        """Return a hash of the object.

        Returns:
            int:
            A hash for the object.
        """
        return hash(f'{self.full_name}:{self.email}')

    def __repr__(self) -> str:
        """Return a string representation of this object.

        Version Added:
            5.1

        Returns:
            str:
            The string representation.
        """
        return (f'<PatchAuthor(email={self.email!r},'
                f' full_name={self.full_name!r})>')


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
    author: PatchAuthor | None

    #: The base directory in the repository where the patch was generated.
    #:
    #: This is dependent on the SCM and the method used to generate the
    #: patch.
    base_dir: str | None

    #: The commit message describing the patch.
    #:
    #: This will generally be available if generating a patch from an
    #: existing commit.
    message: str | None

    #: The path prefix stripping level to use when applying the patch.
    #:
    #: This is the number of path components to strip from the beginning of
    #: each filename in the patch. It's the equivalent of
    #: :command:`patch -p<X>`.
    prefix_level: int | None

    #: List of binary files in this patch.
    #:
    #: Version Added:
    #:     6.0
    binary_files: Sequence[BinaryFilePatch]

    #: The cached contents of the patch.
    _content: bytes | None

    #: Whether the patch is opened for reading.
    _opened: bool

    #: The cached file path for the patch.
    _path: Path | None

    def __init__(
        self,
        *,
        author: (PatchAuthor | None) = None,
        base_dir: (str | None) = None,
        content: (bytes | None) = None,
        message: (str | None) = None,
        path: (Path | None) = None,
        prefix_level: (int | None) = None,
        binary_files: (Sequence[BinaryFilePatch] | None) = None,
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

            binary_files (list of BinaryFilePatch, optional):
                List of binary files associated with this patch.

                Version Added:
                    6.0

        Raises:
            ValueError:
                One or more parameters or parameter combinations were invalid.
        """
        if not content and not path:
            raise ValueError(_('Either content= or path= must be provided.'))

        if isinstance(prefix_level, str):
            RemovedInRBTools70Warning.warn(
                'prefix_level must be an integer, not a string. Support '
                'for string prefix levels will be removed in RBTools 7.')

            try:
                prefix_level = int(prefix_level)
            except ValueError:
                # We'll cover this below.
                pass

        if prefix_level is not None and not isinstance(prefix_level, int):
            raise_invalid_type(
                prefix_level,
                f'prefix_level must be an integer, not {prefix_level!r}.')

        self.author = author
        self.base_dir = base_dir
        self.message = message
        self.prefix_level = prefix_level
        self.binary_files = binary_files or []
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
            OSError:
                The patch was not opened for reading.
        """
        if not self._opened:
            raise OSError(_('Patch objects must be opened before being read.'))

    def __repr__(self) -> str:
        """Return a string representation of the object.

        Returns:
            str:
            The string representation.
        """
        if self._path is not None:
            path = repr(self._path)
        else:
            path = '<PENDING>'

        if self._content is not None:
            content = repr(b'%s[...]' % self._content[:30])
        else:
            content = '<PENDING>'

        return (
            f'<Patch(path={path}, base_dir={self.base_dir!r},'
            f' prefix_level={self.prefix_level!r}, author={self.author!r},'
            f' content={content})>'
        )


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
    #:
    #: This will be ``True`` whether the patch was fully applied without
    #: issues, or partially applied. Callers sohuld check :py:attr:`success`
    #: to check for a successful application, and :py:attr:`has_conflicts`
    #: to check for conflicts.
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
    patch: Patch | None

    #: The range of patches represented by this result.
    #:
    #: This is in the form of:
    #:
    #: Tuple:
    #:     0 (int):
    #:         The 1-based starting patch number.
    #:
    #:     1 (int):
    #:         The 1-based ending patch number.
    #:
    #: Version Added:
    #:     5.1
    patch_range: tuple[int, int] | None

    #: The output of the patch command.
    patch_output: bytes | None

    #: Binary files that were successfully applied.
    #:
    #: Version Added:
    #:     6.0
    binary_applied: Sequence[str]

    #: Binary files that failed to apply, mapped to failure reason.
    #:
    #: Version Added:
    #:     6.0
    binary_failed: Mapping[str, str]

    @deprecate_non_keyword_only_args(RemovedInRBTools70Warning)
    def __init__(
        self,
        *,
        applied: bool,
        has_conflicts: bool = False,
        conflicting_files: (list[str] | None) = None,
        patch_output: (bytes | None) = None,
        patch: (Patch | None) = None,
        patch_range: (tuple[int, int] | None) = None,
        binary_applied: (Sequence[str] | None) = None,
        binary_failed: (Mapping[str, str] | None) = None,
    ) -> None:
        """Initialize the object.

        Version Changed:
            5.1:
            * This now requires keyword-only arguments. Support for positional
              arguments will be removed in RBTools 7.

            * Added the ``patch`` and ``patch_range`` arguments.

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

            patch_range (tuple, optional):
                The range of patches represented by this result.

                This is in the form of:

                Tuple:
                    0 (int):
                        The 1-based starting patch number.

                    1 (int):
                        The 1-based ending patch number.

                Version Added:
                    5.1

            binary_applied (list of str, optional):
                Binary files that were successfully applied.

                Version Added:
                    6.0

            binary_failed (dict, optional):
                Binary files that failed to apply, mapped to failure reason.

                Version Added:
                    6.0
        """
        self.applied = applied
        self.conflicting_files = conflicting_files or []
        self.has_conflicts = has_conflicts
        self.patch = patch
        self.patch_output = patch_output
        self.patch_range = patch_range
        self.binary_applied = binary_applied or []
        self.binary_failed = binary_failed or {}

    @property
    def success(self) -> bool:
        """Whether this was a successful patch application."""
        return (
            self.applied and
            not self.has_conflicts and
            len(self.binary_failed) == 0
        )

    def __repr__(self) -> str:
        """Return a string representation of the object.

        Returns:
            str:
            The string representation.
        """
        return (
            f'<PatchResult(success={self.success}, applied={self.applied},'
            f' has_conflicts={self.has_conflicts},'
            f' patch_range={self.patch_range!r},'
            f' conflicting_files={self.conflicting_files!r},'
            f' binary_applied={self.binary_applied},'
            f' binary_failed={self.binary_failed},'
            f' patch={self.patch!r})>'
        )
