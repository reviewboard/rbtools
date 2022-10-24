"""Writers to help programmatically generate new diffs.

Version Added:
    4.0
"""

import io
from typing import Iterable, Optional, Union

from typing_extensions import TypeAlias

from rbtools.diffs.tools.base.diff_file_result import DiffFileResult
from rbtools.utils.encoding import force_bytes


#: Type alias to accept either a bytes or Unicode string.
#:
#: This is used instead of :py:data:`typing.AnyStr`, which imposes
#: constraints on other arguments of the same type.
_BytesOrStr: TypeAlias = Union[bytes, str]


class UnifiedDiffWriter:
    """Writer for generating Unified Diff files.

    This can be used to incrementally build up one or more Unified Diff files
    from any provided input or from results from a diff tool.

    It takes care of ensuring proper newlines at the end of the file.

    This is the preferred interface for programmatically generating Unified
    Diff payloads, whether for DiffX or otherwise, starting in RBTools 4.0.

    Version Added:
        4.0
    """

    #: The encoding to use to encode Unicode strings.
    #:
    #: Type:
    #:     str
    encoding:  str

    #: The newline character(s) to use at the end of each line.
    #:
    #: Type:
    #:     bytes
    newline: bytes

    def __init__(
        self,
        stream: io.BufferedIOBase,
        encoding: str = 'utf-8',
        newline: bytes = b'\n',
    ) -> None:
        """Initialize the writer.

        Args:
            stream (io.BufferedIOBase):
                The stream to write to.

            encoding (str, optional):
                The encoding to use to encode Unicode strings.

                This defaults to encoding as UTF-8. It should generally
                not be changed.

            newline (bytes, optional):
                The newline character(s) to use at the end of each line.

                This defaults to UNIX newlines.
        """
        self.encoding = encoding
        self.newline = newline
        self.stream = stream

    def write_orig_file_header(
        self,
        path: _BytesOrStr,
        extra: Optional[_BytesOrStr] = None,
    ) -> None:
        """Write a header for the original file.

        This will write the ``---`` file header in a standard form,
        optionally containing extra data after the filename.

        String arguments will be encoded using the default encoding for the
        writer. Byte string arguments are expected to already be in the proper
        encoding.

        Args:
            path (bytes or str):
                The path to include in the header.

            extra (bytes or str, optional):
                Optional extra detail to include after the filename.
        """
        encoding = self.encoding

        if extra:
            self.write_line(b'--- %s\t%s'
                            % (force_bytes(path, encoding),
                               force_bytes(extra, encoding)))
        else:
            self.write_line(b'--- %s' % force_bytes(path, encoding))

    def write_modified_file_header(
        self,
        path: _BytesOrStr,
        extra: Optional[_BytesOrStr] = None,
    ) -> None:
        """Write a header for the modified file.

        This will write the ``+++`` file header in a standard form,
        optionally containing extra data after the filename.

        String arguments will be encoded using the default encoding for the
        writer. Byte string arguments are expected to already be in the proper
        encoding.

        Args:
            path (bytes or str):
                The path to include in the header.

            extra (bytes or str, optional):
                Optional extra detail to include after the filename.
        """
        encoding = self.encoding

        if extra:
            self.write_line(b'+++ %s\t%s' % (force_bytes(path, encoding),
                                             force_bytes(extra, encoding)))
        else:
            self.write_line(b'+++ %s' % force_bytes(path, encoding))

    def write_file_headers(
        self,
        *,
        orig_path: _BytesOrStr,
        modified_path: _BytesOrStr,
        orig_extra: Optional[_BytesOrStr] = None,
        modified_extra: Optional[_BytesOrStr] = None,
    ) -> None:
        """Write both original and modified file headers.

        This will write headers for the original and modified files, basing
        them on provided data.

        String arguments will be encoded using the default encoding for the
        writer. Byte string arguments, or byte strings from the diff result,
        are expected to already be in the proper encoding.

        Args:
            orig_path (bytes or str):
                The file path to use for the original file header.

            modified_path (bytes or str):
                The file path to use for the modified file header.

            orig_extra (bytes or str, optional):
                Extra details for the original file header.

            modified_extra (bytes or str, optional):
                Extra details for the modified file header.
        """
        self.write_orig_file_header(path=orig_path,
                                    extra=orig_extra)
        self.write_modified_file_header(path=modified_path,
                                        extra=modified_extra)

    def write_index(
        self,
        contents: _BytesOrStr,
    ) -> None:
        """Write a standard Index line.

        This is used by some Unified Diff variants to separate sections for
        different files, regardless of contents.

        This is in the form of :samp:`Index {content}`, followed by a line
        with 67 ``=`` characters.

        Args:
            contents (bytes or str):
                The contents to write after ``Index:``.
        """
        self.write_line(b'Index: %s' % force_bytes(contents, self.encoding))
        self.write_line(b'=' * 67)

    def write_hunks(
        self,
        hunks: Union[bytes, Iterable[bytes]],
    ) -> None:
        """Write hunks.

        This takes either a byte string of hunks to write, or an iterator
        yielding lines of hunks.

        If taking a byte string, the bytes are expected to have the proper
        encoding and newlines for the diff.

        If taking an iterator, the iterator is expected to yield byte strings
        in the proper encoding without any newlines.

        Args:
            hunks (bytes or iterable):
                The hunks to write.
        """
        if isinstance(hunks, bytes):
            # The hunks will be written as-is. It's assumed the caller was
            # careful about newlines.
            if hunks:
                self.stream.write(hunks)

                if not hunks.endswith(self.newline):
                    self.stream.write(self.newline)
        else:
            for line in hunks:
                self.write_line(line)

    def write_binary_files_differ(
        self,
        *,
        orig_path: _BytesOrStr,
        modified_path: _BytesOrStr,
    ) -> None:
        """Write a marker indicating that binary files differ.

        This provides the standard text used when diffing binary files
        without showing an actual difference between those files.

        Args:
            orig_path (bytes or str):
                The original file path.

            modified_path (bytes or str):
                The modified file path.
        """
        encoding = self.encoding

        self.write_line(b'Binary files %s and %s differ'
                        % (force_bytes(orig_path, encoding),
                           force_bytes(modified_path, encoding)))

    def write_diff_file_result_headers(
        self,
        diff_file_result: DiffFileResult,
        *,
        orig_path: Optional[_BytesOrStr] = None,
        modified_path: Optional[_BytesOrStr] = None,
        orig_extra: Optional[_BytesOrStr] = None,
        modified_extra: Optional[_BytesOrStr] = None,
    ) -> None:
        """Write file headers based on the result from a diff tool.

        This will write headers for the original and modified files, basing
        them on provided data or that found in the result of a diff operation.

        Provided arguments take precedence.

        String arguments will be encoded using the default encoding for the
        writer. Byte string arguments, or byte strings from the diff result,
        are expected to already be in the proper encoding.

        Args:
            diff_file_result (rbtools.diffs.tools.base.diff_file_result.
                              DiffFileResult):
                The result of a diff operation, used to provide defaults for
                the headers.

            orig_path (bytes or str, optional):
                An explicit file path to use for the original file header.

            modified_path (bytes or str, optional):
                An explicit file path to use for the modified file header.

            orig_extra (bytes or str, optional):
                Explicit extra details for the original file header.

            modified_extra (bytes or str, optional):
                Explicit extra details for the modified file header.
        """
        header_orig_path: bytes = b''
        header_orig_extra: bytes = b''
        header_modified_path: bytes = b''
        header_modified_extra: bytes = b''

        encoding = self.encoding
        orig_header = diff_file_result.parsed_orig_file_header
        modified_header = diff_file_result.parsed_modified_file_header

        # Prefer orig_path and modified_path, if provided. This enables
        # providing a more sane path in the resulting diff than what the
        # diff tool may generate.
        if orig_path:
            header_orig_path = force_bytes(orig_path, encoding)
        elif orig_header:
            header_orig_path = orig_header['path']

        if modified_path:
            header_modified_path = force_bytes(modified_path, encoding)
        elif modified_header:
            header_modified_path = modified_header['path']

        if orig_extra:
            header_orig_extra = force_bytes(orig_extra, encoding)
        elif orig_header:
            header_orig_extra = orig_header['extra']

        if modified_extra:
            header_modified_extra = force_bytes(modified_extra, encoding)
        elif modified_header:
            header_modified_extra = modified_header['extra']

        # Sanity-check that everything looks okay.
        if not header_orig_path:
            raise ValueError(
                'Either orig_path must be set or the provided diff result '
                'must have an original file header.')

        if not header_modified_path:
            raise ValueError(
                'Either modified_path must be set or the provided diff result '
                'must have an modified file header.')

        self.write_file_headers(
            orig_path=header_orig_path,
            orig_extra=header_orig_extra,
            modified_path=header_modified_path,
            modified_extra=header_modified_extra)

    def write_diff_file_result_hunks(
        self,
        diff_file_result: DiffFileResult,
    ) -> None:
        """Write hunks from the result of a diff tool.

        This is the most optimal way of writing hunks based on a diff result
        from a diff tool. Each line will be written with any original newlines
        stripped and the writer's configured newlines appended.

        Args:
            diff_file_result (rbtools.diffs.tools.base.diff_file_result.
                              DiffFileResult):
                The result of a diff operation, used to provide hunks.
        """
        self.write_hunks(
            diff_file_result.iter_hunk_lines(keep_newlines=False))

    def write_line(
        self,
        line: _BytesOrStr,
    ) -> None:
        """Write a line to the diff.

        This must not have a newline appended. The writer's configured newline
        will be used instead.

        String arguments will be encoded using the default encoding for the
        writer. Byte string arguments are expected to already be in the
        proper encoding.

        Args:
            line (bytes or str):
                The line to write, without a trailing newline.
        """
        norm_line = force_bytes(line, self.encoding)

        # The provided line should never end with a \r\n or \n.
        assert not norm_line.endswith(b'\n')

        self.stream.write(norm_line)
        self.stream.write(self.newline)
