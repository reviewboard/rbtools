"""Error types for commands.

Version Added:
    5.0
"""

from __future__ import annotations


class CommandExit(Exception):
    """An error indicating a command is ready to exit."""

    ######################
    # Instance variables #
    ######################

    #: The exit code.
    exit_code: int

    def __init__(
        self,
        exit_code: int = 0,
    ) -> None:
        """Initialize the error.

        Args:
            exit_code (int):
                The exit code.
        """
        super().__init__('Exit with code %s' % exit_code)
        self.exit_code = exit_code


class CommandError(Exception):
    """A general error for a command."""


class ParseError(CommandError):
    """An error indicating a command failed to parse some information."""


class NeedsReinitialize(Exception):
    """Exception thrown when we need to restart the command initialization.

    Version Added:
        5.1
    """
