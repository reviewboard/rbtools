"""Base support for creating commands."""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

import importlib_metadata

from rbtools.commands.base.commands import RB_MAIN as _RB_MAIN
from rbtools.commands.base.errors import (CommandError as _CommandError,
                                          CommandExit as _CommandExit,
                                          ParseError as _ParseError)
from rbtools.utils.filesystem import is_exe_in_path

if TYPE_CHECKING:
    from importlib_metadata import EntryPoint, EntryPoints


logger = logging.getLogger(__name__)


CommandExit = _CommandExit
CommandError = _CommandError
ParseError = _ParseError
RB_MAIN = _RB_MAIN


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


__autodoc_excludes__ = (
    'BaseSubCommand',
    'JSONOutput',
    'Option',
    'OptionGroup',
    'Output',
    'OutputWrapper',
)
