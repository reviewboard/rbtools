"""Output management for commands.

Version Added:
    5.0
"""

from __future__ import annotations

import io
import json
from typing import (Any, AnyStr, Callable, Dict, Generic, IO, Optional,
                    TextIO, Union, cast)

from typing_extensions import TypeAlias

from rbtools.utils.encoding import force_bytes, force_unicode


#: Type alias for a force_bytes() or force_unicode() function.
#:
#: Version Added:
#:     5.0
_ForceStringFunc: TypeAlias = Callable[..., AnyStr]


class _Newline:
    """A wrapper for newline characters.

    This is used as a default parameter for indicating a newline when
    writing to an output stream.

    Version Added:
        5.0
    """

    def __bytes__(self) -> bytes:
        """Return the newline as a byte string.

        Returns:
            bytes:
            The newline character.
        """
        return b'\n'

    def __str__(self) -> str:
        """Return the newline as a Unicode string.

        Returns:
            bytes:
            The newline character.
        """
        return '\n'


#: Newline wrapper instance.
#:
#: Version Added:
#:     5.0
_newline = _Newline()


class JSONOutput:
    """Output wrapper for JSON output.

    JSON outputter class that stores Command outputs in python dictionary
    and outputs as JSON object to output stream object. Commands should add any
    structured output to this object. JSON output is then enabled with the
    --json argument.

    Version Changed:
        5.0:
        This moved from :py:mod:`rbtools.commands` to
        :py:mod:`rbtools.commands.base.commands`.

    Version Added:
        3.0
    """

    ######################
    # Instance variables #
    ######################

    #: Raw storage for JSON data scheduled to be output.
    #:
    #: Version Added:
    #:     5.0
    raw: Dict[str, Any]

    #: The stream where JSON output will be written to.
    _output_stream: TextIO

    def __init__(
        self,
        output_stream: TextIO,
    ) -> None:
        """Initialize JSONOutput class.

        Args:
            output_stream (io.IOBase):
                Object to output JSON object to.
        """
        self.raw = {}
        self._output_stream = output_stream

    def add(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Add a new key value pair.

        Args:
            key (str):
                The key associated with the value to be added to dictionary.

            value (object):
                The value to attach to the key in the dictionary.
        """
        self.raw[key] = value

    def append(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Add new value to an existing list associated with key.

        Version Changed:
            5.0:
            When appending to a non-list, a :py:exc:`TypeError` is now raised
            instead of a :py:exc:`AttributeError`.

        Args:
            key (str):
                The key associated with the list to append to.

            value (object):
                The value to append to the list associated with key.

        Raises:
            KeyError:
                The key was not found in the state.

            TypeError:
                The existing value was not a list.
        """
        items = self.raw[key]

        if not isinstance(items, list):
            raise TypeError('Expected "%s" to be a list, but it is a %s.'
                            % (key, type(items)))

        items.append(value)

    def add_error(
        self,
        error: str,
    ) -> None:
        """Add a new error to the "errors" key.

        Append a new error to the ``errors`` key, creating one if needed.

        Args:
            error (str):
                The error that will be added to ``errors``.
        """
        self.raw.setdefault('errors', []).append(error)

    def add_warning(
        self,
        warning: str,
    ) -> None:
        """Add a new warning to the "warnings" key.

        Append a new warning to the ``warnings`` key, creating one if needed.

        Args:
            warning (unicode):
                The warning that will be added to ``warnings``.
        """
        self.raw.setdefault('warnings', []).append(warning)

    def print_to_stream(self) -> None:
        """Output JSON string representation to output stream."""
        self._output_stream.write(json.dumps(self.raw,
                                             indent=4,
                                             sort_keys=True))
        self._output_stream.write('\n')


class OutputWrapper(Generic[AnyStr]):
    """Wrapper for output of a command.

    Wrapper around some output object that handles outputting messages.
    Child classes specify the default object. The wrapper can handle
    messages in either unicode or bytes.

    Version Changed:
        5.0:
        This moved from :py:mod:`rbtools.commands` to
        :py:mod:`rbtools.commands.base.commands`.

    Version Added:
        3.0
    """

    ######################
    # Instance variables #
    ######################

    #: The wrapped output stream.
    output_stream: Optional[IO[AnyStr]]

    #: A function to force a string type for writing.
    _force_str: _ForceStringFunc

    def __init__(
        self,
        output_stream: IO[AnyStr],
    ) -> None:
        """Initialize with an output object to stream to.

        Args:
            output_stream (io.IOBase):
                The output stream to send command output to.
        """
        self.output_stream = output_stream

        if isinstance(output_stream, io.TextIOBase):
            self._force_str = cast(_ForceStringFunc, force_unicode)
        else:
            self._force_str = cast(_ForceStringFunc, force_bytes)

    def write(
        self,
        msg: Optional[AnyStr] = None,
        end: Union[AnyStr, _Newline] = _newline,
    ) -> None:
        """Write a message to the output stream.

        Version Changed:
            5.0:
            This now handles incoming strings of either bytes or Unicode
            under the hood, but callers should take care to always use the
            intended string type. This behavior may change in future versions.

        Args:
            msg (bytes or str, optional):
                String to write to output stream.

                Version Changed:
                    5.0:
                    This is now optional, allowing just the ending marker to
                    be written if provided.

            end (bytes or str, optional):
                String to append to end.

                This defaults to a newline.
        """
        if msg:
            self._write(msg)

        if end:
            self._write(end)

    def new_line(self) -> None:
        """Write a newline to the output stream."""
        self.write()

    def _write(
        self,
        s: Union[AnyStr, _Newline],
    ) -> None:
        """Write a string to the output stream.

        This will take care to convert the string (or newline wrapper) as
        necessary.

        Args:
            s (bytes or str or _Newline):
                The string or newline wrapper to write.
        """
        # Make sure the stream hasn't been closed (for JSON writing).
        if self.output_stream is not None:
            self.output_stream.write(self._force_str(s, strings_only=False))
