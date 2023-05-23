"""Base support for commands.

This provides support for writing and executing commands. This can be used
by third-parties that want to introduce new commands for RBTools.

This module provides forwarding imports for:

.. autosummary::
   :nosignatures:

   ~rbtools.commands.base.commands.BaseCommand
   ~rbtools.commands.base.commands.BaseMultiCommand
   ~rbtools.commands.base.commands.BaseSubCommand
   ~rbtools.commands.base.errors.CommandError
   ~rbtools.commands.base.errors.CommandExit
   ~rbtools.commands.base.errors.ParseError
   ~rbtools.commands.base.options.Option
   ~rbtools.commands.base.options.OptionGroup

Version Added:
    5.0
"""

from rbtools.commands.base.commands import (BaseCommand,
                                            BaseMultiCommand,
                                            BaseSubCommand)
from rbtools.commands.base.options import Option, OptionGroup
from rbtools.commands.base.errors import (CommandError,
                                          CommandExit,
                                          ParseError)


__all__ = [
    'BaseCommand',
    'BaseMultiCommand',
    'BaseSubCommand',
    'CommandError',
    'CommandExit',
    'Option',
    'OptionGroup',
    'ParseError',
]
