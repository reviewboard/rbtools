"""Rich theme and style constants for RBTools.

Version Added:
    7.0
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from rich.theme import Theme

if TYPE_CHECKING:
    from typing import Final, TypeAlias


#: Type for color overrides.
#:
#: Version Added:
#:     7.0
ColorOverrides: TypeAlias = Mapping[str, str | None]


#: The base styles for the RBTools theme.
#:
#: The ``logging.level.*`` entries provide defaults that match the historical
#: colorized log output. They can be overridden per-level from the ``COLOR``
#: configuration through :py:func:`build_theme`.
#:
#: Version Added:
#:     7.0
DEFAULT_RBTOOLS_STYLES: Final[Mapping[str, str]] = {
    'logging.level.critical': 'bold red',
    'logging.level.debug': 'dim',
    'logging.level.error': 'bold red',
    'logging.level.info': 'default',
    'logging.level.warning': 'bold yellow',
    'rb.draft': 'green',
    'rb.error': 'bold red',
    'rb.heading': 'bold',
    'rb.info': 'cyan',
    'rb.issues': 'yellow',
    'rb.muted': 'dim',
    'rb.pending': 'blue',
    'rb.shipit': 'bright_green',
    'rb.step': 'bold',
    'rb.success': 'bold green',
    'rb.url': 'blue underline',
    'rb.warning': 'bold yellow',
}


def build_theme(
    colors: (ColorOverrides | None) = None,
) -> Theme:
    """Return a Rich theme for RBTools output.

    This starts from :py:data:`DEFAULT_RBTOOLS_STYLES` and applies any
    log-level color overrides from the legacy ``COLOR`` configuration. The
    color names map directly to Rich style strings.

    Version Added:
        7.0

    Args:
        colors (dict, optional):
            A mapping of log level names (``DEBUG``, ``INFO``, ``WARNING``,
            ``ERROR``, ``CRITICAL``) to color names. Levels with a ``None``
            value are left at their default.

    Returns:
        rich.theme.Theme:
        The theme to use for the console.
    """
    styles = dict(DEFAULT_RBTOOLS_STYLES)

    if colors:
        for level in ('debug', 'info', 'warning', 'error', 'critical'):
            color = colors.get(level.upper())

            if color:
                styles[f'logging.level.{level}'] = color

    return Theme(styles)


#: Icon shown for successful operations.
#:
#: Version Added:
#:     7.0
ICON_SUCCESS = '✓'

#: Icon shown for warnings.
#:
#: Version Added:
#:     7.0
ICON_WARNING = '!'

#: Icon shown for errors.
#:
#: Version Added:
#:     7.0
ICON_ERROR = '✗'

#: Icon shown for step progress.
#:
#: Version Added:
#:     7.0
ICON_ARROW = '›'  # noqa: RUF001
