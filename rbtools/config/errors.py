"""Configuration-related error classes.

Version Added:
    5.0
"""

from __future__ import annotations

from typing import Optional


class ConfigError(Exception):
    """A base class for configuration errors.

    Version Added:
        5.0
    """

    ######################
    # Instance variables #
    ######################

    #: The configuration filename.
    #:
    #: Type:
    #:     str
    filename: Optional[str]

    def __init__(
        self,
        msg: str,
        *,
        filename: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            msg (str):
                The error message.

            filename (str):
                The configuration filename.
        """
        super().__init__(msg)

        self.filename = filename


class ConfigSyntaxError(ConfigError):
    """A syntax error in a configuration file.

    Version Added:
        5.0
    """

    ######################
    # Instance variables #
    ######################

    #: The 1-based column number containing the bad syntax.
    #:
    #: This may be ``None``.
    #:
    #: Type:
    #:     int
    column: Optional[int]

    #: Extra details shown about the syntax error.
    #:
    #: Type:
    #:     str
    details: str

    #: The 1-based line number containing the bad syntax.
    #:
    #: This may be ``None``.
    #:
    #: Type:
    #:     int
    line: Optional[int]

    def __init__(
        self,
        *,
        filename: Optional[str] = None,
        line: Optional[int],
        column: Optional[int],
        details: str,
    ) -> None:
        """Initialize the error.

        Args:
            filename (str):
                The configuration filename.

            line (int):
                The 1-based line number containing the bad syntax.

            column (int):
                The 1-based column number containing the bad syntax.

            details (str):
                Extra details to show about the syntax error.
        """
        if filename:
            msg = (
                f'Syntax error in RBTools configuration file "{filename}" at '
                f'line {line}, column {column}: {details}'
            )
        else:
            msg = (
                f'Syntax error in RBTools configuration file at line {line}, '
                f'column {column}: {details}'
            )

        super().__init__(msg, filename=filename)

        self.filename = filename
        self.line = line
        self.column = column
        self.details = details
