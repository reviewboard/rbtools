"""Error types for commands.

Version Added:
    5.0
"""

from __future__ import annotations


class CommandExit(Exception):
    def __init__(self, exit_code=0):
        super(CommandExit, self).__init__('Exit with code %s' % exit_code)
        self.exit_code = exit_code


class CommandError(Exception):
    pass


class ParseError(CommandError):
    pass
