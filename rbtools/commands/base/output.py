"""Output management for commands.

Version Added:
    5.0
"""

from __future__ import annotations

import json

import six


class JSONOutput(object):
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

    def __init__(self, output_stream):
        """Initialize JSONOutput class.

        Args:
            output_stream (Object):
                Object to output JSON object to.
        """
        self._output = {}
        self._output_stream = output_stream

    def add(self, key, value):
        """Add a new key value pair.

        Args:
            key (unicode):
                The key associated with the value to be added to dictionary.

            value (object):
                The value to attach to the key in the dictionary.
        """
        self._output[key] = value

    def append(self, key, value):
        """Add new value to an existing list associated with key.

        Args:
            key (unicode):
                The key associated with the list to append to.

            value (object):
                The value to append to the list associated with key.

        Raises:
            KeyError:
                The key was not found in the state.

            AttributeError:
                The existing value was not a list.
        """
        self._output[key].append(value)

    def add_error(self, error):
        """Add new error to 'errors' key.

        Append a new error to the ``errors`` key, creating one if needed.

        Args:
            error (unicode):
                The error that will be added to ``errors``.
        """
        self._output.setdefault('errors', []).append(error)

    def add_warning(self, warning):
        """Add new warning to 'warnings' key.

        Append a new warning to the ``warnings`` key, creating one if needed.

        Args:
            warning (unicode):
                The warning that will be added to ``warnings``.
        """
        self._output.setdefault('warnings', []).append(warning)

    def print_to_stream(self):
        """Output JSON string representation to output stream."""
        self._output_stream.write(json.dumps(self._output,
                                             indent=4,
                                             sort_keys=True))
        self._output_stream.write('\n')


class OutputWrapper(object):
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

    def __init__(self, output_stream):
        """Initialize with an output object to stream to.

        Args:
            output_stream (object):
                The output stream to send command output to.
        """
        self.output_stream = output_stream

    def write(self, msg, end='\n'):
        """Write a message to the output stream.

        Write a string to output stream object if defined, otherwise
        do nothing. end specifies a string that should be appended to
        the end of msg before being given to the output stream.

        Args:
            msg (unicode):
                String to write to output stream.

            end (unicode, optional):
                String to append to end of msg. This defaults to ``\\n```.
        """
        if self.output_stream:
            if end:
                if (isinstance(msg, bytes) and
                    isinstance(end, six.string_types)):
                    msg += end.encode('utf-8')
                else:
                    msg += end

            self.output_stream.write(msg)

    def new_line(self):
        """Pass a new line character to output stream object.
        """
        if self.output_stream:
            self.output_stream.write('\n')
