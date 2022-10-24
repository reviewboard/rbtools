"""Classes for working with the result of a diff between files.

Version Added:
    4.0
"""

import io
import re
from typing import Iterator, List, Optional, Tuple

from typing_extensions import TypedDict


_DEFAULT_FILE_HEADER_RE = re.compile(
    br'^(?P<marker>---|\+\+\+) (?P<path>.+?)((?:\t| {2,})(?P<extra>.*))?$'
)


class DiffFileHeaderDict(TypedDict):
    """Parsed information from a diff file header.

    This represents information found in a ``---``` or ``+++`` header in
    a Unified Diff file.

    Version Added:
        4.0
    """

    #: The marker at the start of the header line.
    #:
    #: This will be ``---`` or ``+++``.
    #:
    #: Type:
    #:     bytes
    marker: bytes

    #: The path listed in the header line.
    #:
    #: Type:
    #:     bytes
    path: bytes

    #: Extra information shown after the filename.
    #:
    #: This will be empty if not present.
    #:
    #: Type:
    #:     bytes
    extra: bytes


class DiffFileResult:
    """The result of diffing a file.

    This contains the stream of diff contents, flags indicating what type
    of diff this is, and whether any changes were found.

    There's parsing helpers in here to extract the most relevant information
    from the diff, for use when assembling new SCM-specific diffs from the
    contents.

    Version Added:
        4.0
    """

    ######################
    # Instance variables #
    ######################

    #: The original path passed to the diff tool.
    #:
    #: This may be different from the information shown in
    #: :py:attr:`orig_file_header`.
    #:
    #: Type:
    #:     str
    orig_path: str

    #: The modified path passed to the diff tool.
    #:
    #: This may be different from the information shown in
    #: :py:attr:`modified_file_header`.
    #:
    #: Type:
    #:     str
    modified_path: str

    #: A stream containing the full diff content.
    #:
    #: Consumers can read directly from this, but it's recommended that they
    #: use one of the many available properties or functions for fetching
    #: content instead.
    #:
    #: Type:
    #:     io.BytesIO
    diff: io.BytesIO

    #: Whether this represents a change to a binary file.
    #:
    #: Type:
    #:     bool
    is_binary: bool

    #: Whether differences were found in a text file.
    #:
    #: This will be ``True`` if there were any changes at all to the file.
    #:
    #: This will be ``False`` if the files were identical, or if one or both
    #: files were binary.
    #:
    #: Type:
    #:     bool
    has_text_differences: bool

    #: Whether any differences were found.
    #:
    #: If diffing against a binary file, this will always be ``True``.
    #: Otherwise, it depends on the value of :py:attr:`has_text_differences`.
    #:
    #: Type:
    #:     bool
    has_differences: bool

    #: The line number containing the original line header.
    #:
    #: Type:
    #:     int
    orig_file_header_line_num: int

    #: The line number containing the modified line header.
    #:
    #: Type:
    #:     int
    modified_file_header_line_num: int

    #: The starting line number containing the Unified Diff hunks.
    #:
    #: Type:
    #:     int
    hunks_start_line_num: int

    #: Internal cache of line offsets and line lengths.
    #:
    #: This helps quickly navigate to specific lines when reading content.
    #: It's incrementally populated whenever seeking to a specific line, and
    #: can then be used to more quickly reach that line in future parses.
    #:
    #: Type:
    #:     list of tuple:
    #:     Tuple:
    #:         0 (int):
    #:             The offset of the line in the stream.
    #:
    #:         1 (int):
    #:             The length of the line.
    _line_offset_cache: List[Tuple[int, int]]

    def __init__(
        self,
        *,
        orig_path: str,
        modified_path: str,
        diff: io.BytesIO,
        is_binary: bool = False,
        has_text_differences: bool = True,
        orig_file_header_line_num: int = 0,
        modified_file_header_line_num: int = 1,
        hunks_start_line_num: int = 2,
        file_header_re: re.Pattern = _DEFAULT_FILE_HEADER_RE,
    ) -> None:
        """Initialize the diff result.

        Args:
            orig_path (str):
                The original filename passed to the diff tool.

                This may be different from the information shown in the
                diff itself.

            modified_path (str):
                The modified filename passed to the diff tool.

                This may be different from the information shown in the
                diff itself.

            diff (io.BytesIO):
                A stream containing the full diff content.

            is_binary (bool, optional):
                Whether this represents a change to a binary file.

            has_text_differences (bool, optional):
                Whether differences were found in a text file.

            orig_file_header_line_num (int, optional):
                The line number containing the original line header.

                This is a hint for parsing. It shouldn't need to be changed,
                but can be set by a diff tool if required.

            modified_file_header_line_num (int, optional):
                The line number containing the modified line header.

                This is a hint for parsing. It shouldn't need to be changed,
                but can be set by a diff tool if required.

            hunks_start_line_num (int, optional):
                The starting line number containing the Unified Diff hunks.

                This is a hint for parsing. It shouldn't need to be changed,
                but can be set by a diff tool if required.

            file_header_re (re.Pattern, optional):
                A regex used to parse file headers.

                This must capture ``marker``, ``path``, and ``extra`` groups
                for a standard Unified Diff original/modified file header line.
        """
        self.orig_path = orig_path
        self.modified_path = modified_path
        self.diff = diff
        self.is_binary = is_binary
        self.has_text_differences = has_text_differences
        self.orig_file_header_line_num = orig_file_header_line_num
        self.modified_file_header_line_num = modified_file_header_line_num
        self.hunks_start_line_num = hunks_start_line_num
        self.has_differences = has_text_differences or is_binary
        self.file_header_re = file_header_re
        self._line_offset_cache = []

    @property
    def orig_file_header(self) -> bytes:
        """The content of the original file header.

        The format of this header may vary between diff tools.

        Type:
            bytes
        """
        if self.has_text_differences:
            line = self._get_line(self.orig_file_header_line_num)

            if line.startswith(b'--- '):
                return line

        return b''

    @property
    def parsed_orig_file_header(self) -> Optional[DiffFileHeaderDict]:
        """The extra contents on the file header.

        This is usually a timestamp, but its presence and format may vary
        between diff tools.

        See :py:class:`DiffFileHeaderDict` for the contents of the
        dictionary.

        Type:
            dict
        """
        return self._parse_file_header(self.orig_file_header)

    @property
    def modified_file_header(self) -> bytes:
        """The content of the modified file header.

        The format of this header may vary between diff tools.

        Type:
            bytes
        """
        if self.has_text_differences:
            line = self._get_line(self.modified_file_header_line_num)

            if line.startswith(b'+++ '):
                return line

        return b''

    @property
    def parsed_modified_file_header(self) -> Optional[DiffFileHeaderDict]:
        """The extra contents on the file header.

        This is usually a timestamp, but its presence and format may vary
        between diff tools.

        See :py:class:`DiffFileHeaderDict` for the contents of the
        dictionary.

        Type:
            dict
        """
        return self._parse_file_header(self.modified_file_header)

    @property
    def hunks(self) -> bytes:
        """The full content of the diff hunks.

        This does not normalize line endings.

        Type:
            bytes
        """
        self.seek_diff_hunks()

        return self.diff.read()

    def iter_hunk_lines(
        self,
        keep_newlines=False,
    ) -> Iterator[bytes]:
        """Iterate through all hunk lines.

        Lines may optionally contain newlines.

        Note that any CRCRLF newlines will be converted to CRLF. While
        uncommon, CRCRLF can happen with some SCMs if editing and diffing code
        across two different operating systems (usually Windows and either
        Linux or macOS).

        Args:
            keep_newlines (bool):
                Whether to keep newlines in yielded lines.

        Yields:
            bytes:
            Each line of bytes in the hunk data.
        """
        self.seek_diff_hunks()

        if keep_newlines:
            for line in self.diff:
                if line.endswith(b'\r\r\n'):
                    yield b'%s\r\n' % line[:-3]
                else:
                    yield line
        else:
            for line in self.diff:
                yield line.rstrip(b'\r\n')

    def seek_diff_hunks(self) -> None:
        """Seek to the position of the diff hunks.

        This can be used by consumers to place the read offset at the
        correct position in order to perform operations on the hunk portion
        of the diff.

        If there are no text differences, this seeks to the beginning of the
        diff.
        """
        if self.has_text_differences:
            self._seek_line(self.hunks_start_line_num)
        else:
            self.diff.seek(0)

    def _parse_file_header(
        self,
        header: bytes,
    ) -> Optional[DiffFileHeaderDict]:
        """Return parsed information from a file header.

        Args:
            header (bytes):
                The file header to parse.

        Returns:
            dict:
            A dictionary of parsed information.

            See :py:class:`DiffFileHeaderDict` for the contents of the
            dictionary.
        """
        m = self.file_header_re.match(header)

        if m:
            return {
                'extra': m.group('extra') or b'',
                'marker': m.group('marker'),
                'path': m.group('path'),
            }

        return None

    def _get_line(
        self,
        line_num: int,
    ) -> bytes:
        """Return the contents of a line.

        This will seek to the correct position in the buffer and read the
        line, returning it.

        If ``line_num`` is greater than the number of lines in the file,
        this will not seek and will instead return an empty byte string. It's
        up to the caller to check for this.

        Args:
            line_num (int):
                The line number to read.

        Returns:
            bytes:
            The line content.

            This will be empty if there was nothing more to read.
        """
        line_len = self._seek_line(line_num)

        if line_len > 0:
            return self.diff.read(line_len)
        else:
            return b''

    def _seek_line(
        self,
        line_num: int,
    ) -> int:
        """Seek to a specific line number.

        This will manage a line offset/length cache, to speed up seeking to
        specific line numbers.

        If ``line_num`` is greater than the number of lines in the file,
        this will not seek and will instead return an empty line length. It's
        up to the caller to check for this.

        Args:
            line_num (int):
                The line number to seek to.

        Returns:
            int:
            The line length.
        """
        diff = self.diff
        line_offset_cache = self._line_offset_cache
        num_cached_lines = len(line_offset_cache)

        if line_num + 1 > num_cached_lines:
            # Update our cache for the offsets and lengths of lines, so we
            # can quickly get where we need to go.
            try:
                offset, line_len = line_offset_cache[-1]
            except IndexError:
                offset = 0
                line_len = 0

            offset += line_len
            diff.seek(offset)

            for i in range(num_cached_lines, line_num + 1):
                line = diff.readline()
                line_len = len(line)

                if line_len == 0:
                    # We hit EOF.
                    return 0

                line_offset_cache.append((offset, line_len))
                offset += line_len

        offset, line_len = line_offset_cache[line_num]
        diff.seek(offset)

        return line_len
