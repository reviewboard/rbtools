"""Base support for creating commands."""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

import importlib_metadata
from housekeeping import ClassMovedMixin

from rbtools.commands.base.commands import (
    BaseCommand,
    BaseMultiCommand as _BaseMultiCommand,
    BaseSubCommand as _BaseSubCommand,
    LogLevelFilter as _LogLevelFilter,
    RB_MAIN as _RB_MAIN,
    SmartHelpFormatter as _SmartHelpFormatter)
from rbtools.commands.base.errors import (CommandError as _CommandError,
                                          CommandExit as _CommandExit,
                                          ParseError as _ParseError)
from rbtools.commands.base.options import (Option as _Option,
                                           OptionGroup as _OptionGroup)
from rbtools.commands.base.output import (JSONOutput as _JSONOutput,
                                          OutputWrapper as _OutputWrapper)
from rbtools.deprecation import RemovedInRBTools60Warning
from rbtools.utils.filesystem import is_exe_in_path

if TYPE_CHECKING:
    from importlib_metadata import EntryPoint, EntryPoints


logger = logging.getLogger(__name__)


CommandExit = _CommandExit
CommandError = _CommandError
ParseError = _ParseError
RB_MAIN = _RB_MAIN


class JSONOutput(ClassMovedMixin, _JSONOutput,
                 warning_cls=RemovedInRBTools60Warning):
    """Output wrapper for JSON output.

    JSON outputter class that stores Command outputs in python dictionary
    and outputs as JSON object to output stream object. Commands should add any
    structured output to this object. JSON output is then enabled with the
    --json argument.

    Deprecated:
        5.0:
        Consumers should use :py:class:`rbtools.commands.output.JSONOutput`
        instead.

        This will be removed in RBTools 6.

    Version Added:
        3.0
    """


class SmartHelpFormatter(ClassMovedMixin, _SmartHelpFormatter,
                         warning_cls=RemovedInRBTools60Warning):
    """Smartly formats help text, preserving paragraphs.

    Deprecated:
        5.0:
        Consumers should use
        :py:class:`rbtools.commands.base.commands.SmartHelpFormatter` instead.

        This will be removed in RBTools 6.
    """


class OutputWrapper(ClassMovedMixin, _OutputWrapper,
                    warning_cls=RemovedInRBTools60Warning):
    """Wrapper for output of a command.

    Wrapper around some output object that handles outputting messages.
    Child classes specify the default object. The wrapper can handle
    messages in either unicode or bytes.

    Version Added:
        3.0
    """


class Option(ClassMovedMixin, _Option,
             warning_cls=RemovedInRBTools60Warning):
    """Represents an option for a command.

    The arguments to the constructor should be treated like those
    to argparse's add_argument, with the exception that the keyword
    argument 'config_key' is also valid. If config_key is provided
    it will be used to retrieve the config value as a default if the
    option is not specified. This will take precedence over the
    default argument.

    Serves as a wrapper around the ArgumentParser options, allowing us
    to specify defaults which will be grabbed from the configuration
    after it is loaded.

    Deprecated:
        5.0:
        Consumers should use :py:class:`rbtools.commands.base.options.Option`
        instead.

        This will be removed in RBTools 6.
    """


class OptionGroup(ClassMovedMixin, _OptionGroup,
                  warning_cls=RemovedInRBTools60Warning):
    """Represents a named group of options.

    Each group has a name, an optional description, and a list of options.
    It serves as a way to organize related options, making it easier for
    users to scan for the options they want.

    This works like argparse's argument groups, but is designed to work with
    our special Option class.

    Deprecated:
        5.0:
        Consumers should use
        :py:class:`rbtools.commands.base.options.OptionGroup` instead.

        This will be removed in RBTools 6.
    """


class LogLevelFilter(ClassMovedMixin, _LogLevelFilter,
                     warning_cls=RemovedInRBTools60Warning):
    """Filters log messages of a given level.

    Only log messages that have the specified level will be allowed by
    this filter. This prevents propagation of higher level types to lower
    log handlers.

    Deprecated:
        5.0:
        Consumers should use
        :py:class:`rbtools.commands.base.commands.LogLevelFilter` instead.

        This will be removed in RBTools 6.
    """


class Command(ClassMovedMixin, BaseCommand,
              warning_cls=RemovedInRBTools60Warning):
    """Legacy base class for commands.

    Deprecated:
        5.0:
        Subclasses should inherit from
        :py:class:`rbtools.commands.base.commands.BaseCommand` (or a more
        specific subclass) instead.

        This will be removed in RBTools 6.
    """


class BaseSubCommand(ClassMovedMixin, _BaseSubCommand,
                     warning_cls=RemovedInRBTools60Warning):
    """Abstract base class for a subcommand.

    Deprecated:
        5.0:
        Subclasses should inherit from
        :py:class:`rbtools.commands.base.commands.BaseSubCommand` instead.

        This will be removed in RBTools 6.
    """


class BaseMultiCommand(ClassMovedMixin, _BaseMultiCommand,
                       warning_cls=RemovedInRBTools60Warning):
    """Abstract base class for commands which offer subcommands.

    Some commands (such as :command:`rbt review`) want to offer many
    subcommands.

    Deprecated:
        5.0:
        Subclasses should inherit from
        :py:class:`rbtools.commands.base.commands.BaseMultiCommand` instead.

        This will be removed in RBTools 6.

    Version Added:
        3.0
    """


def find_entry_point_for_command(
    command_name: str,
) -> Optional[EntryPoint]:
    """Return an entry point for the given RBTools command.

    Version Changed:
        5.0:
        This has been updated to return a modern
        :py:class:`importlib.metadata.EntryPoint`.

    Args:
        command_name (str):
            The name of the command to find.

    Returns:
        importlib.metadata.EntryPoint:
        The resulting entry point, if found, or ``None`` if not found.
    """
    entry_points: Optional[EntryPoints]

    # Attempt to retrieve the command class from the entry points. We
    # first look in rbtools for the commands, and failing that, we look
    # for third-party commands.
    try:
        entry_points = (
            importlib_metadata
            .distribution('rbtools')
            .entry_points
            .select(group='rbtools_commands',
                    name=command_name)
        )
    except Exception as e:
        logger.exception('Failed to read built-in RBTools commands: %s', e)
        entry_points = None

    if not entry_points:
        try:
            entry_points = importlib_metadata.entry_points(
                group='rbtools_commands',
                name=command_name)
        except Exception as e:
            logger.exception('Failed to read available RBTools commands: %s',
                             e)
            entry_points = None

    if entry_points:
        return next(iter(entry_points))

    return None


def command_exists(
    cmd_name: str,
) -> bool:
    """Determine if the given command exists.

    This function checks for the existence of an RBTools command entry point
    with the given name and an executable named rbt-"cmd_name" on the path.
    Aliases are not considered.

    Args:
        cmd_name (str):
            The name of the command.

    Returns:
        bool:
        ``True`` if the command exists. ``False`` if it doesn't.
    """
    return (find_entry_point_for_command(cmd_name) is not None or
            is_exe_in_path(f'rbt-{cmd_name}'))
