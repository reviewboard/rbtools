"""Command line option management for commands.

Version Added:
    5.0
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

    from rbtools.config import RBToolsConfig


class Option:
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

    Version Added:
        5.0:
        This is the new location for the old
        :py:class:`rbtools.commands.Option` class.
    """

    ######################
    # Instance variables #
    ######################

    #: The long and short form option names.
    #:
    #: Type:
    #:     tuple
    opts: tuple[str, ...]

    #: The attributes for the option.
    #:
    #: Type:
    #:     dict
    attrs: dict[str, Any]

    def __init__(
        self,
        *opts: str,
        **attrs,
    ) -> None:
        """Initialize the option.

        Args:
            *opts (tuple of str):
                The long and short form option names.

            **attrs (dict):
                The attributes for the option.
        """
        self.opts = opts
        self.attrs = attrs

    def add_to(
        self,
        parent: argparse._ActionsContainer,
        config: Optional[RBToolsConfig] = None,
        argv: Optional[list[str]] = None,
    ) -> None:
        """Add the option to the parent parser or group.

        If the option maps to a configuration key, this will handle figuring
        out the correct default.

        Once we've determined the right set of flags, the option will be
        added to the parser.

        Args:
            parent (argparse._ActionsContainer):
                The parent argument parser or group.

            config (dict):
                The loaded RBTools configuration.

            argv (list, deprecated):
                Unused list of deprecated command line arguments.
        """
        attrs = self.attrs.copy()

        if config is not None and 'config_key' in attrs:
            config_key = attrs.pop('config_key')

            if config_key in config:
                attrs['default'] = config[config_key]

        if 'deprecated_in' in attrs:
            attrs['help'] = (
                '%(help)s\n[Deprecated since %(deprecated_in)s]'
                % attrs)

        # These are used for other purposes, and are not supported by
        # argparse.
        for attr in ('added_in',
                     'deprecated_in',
                     'extended_help',
                     'versions_changed'):
            attrs.pop(attr, None)

        parent.add_argument(*self.opts, **attrs)


class OptionGroup:
    """Represents a named group of options.

    Each group has a name, an optional description, and a list of options.
    It serves as a way to organize related options, making it easier for
    users to scan for the options they want.

    This works like argparse's argument groups, but is designed to work with
    our special Option class.

    Version Added:
        5.0:
        This is the new location for the old
        :py:class:`rbtools.commands.OptionGroup` class.
    """

    ######################
    # Instance variables #
    ######################

    #: The description of this option group.
    #:
    #: This may be ``None``.
    #:
    #: Type:
    #:     str
    description: Optional[str]

    #: The name of this option group.
    #:
    #: This may be ``None``.
    #:
    #: Type:
    #:     str
    name: Optional[str]

    #: The list of options this group was initialized with.
    #:
    #: Type:
    #:     list of Option
    option_list: list[Option]

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        option_list: Optional[list[Option]] = None,
    ) -> None:
        """Initialize the option group.

        Args:
            name (str, optional):
                The name of the option group.

            description (str, optional):
                The description of this option group.

            option_list (list of Option, optional):
                The list of options in this group.
        """
        self.name = name
        self.description = description
        self.option_list = option_list or []

    def add_to(
        self,
        parser: argparse.ArgumentParser,
        config: RBToolsConfig,
        argv: Optional[list[str]] = None,
    ) -> None:
        """Add the group and all its contained options to the parser.

        Args:
            parser (argparse.ArgumentParser):
                The command-line parser.

            config (rbtools.config.RBToolsConfig):
                The loaded RBTools configuration.

            argv (list, deprecated):
                Unused legacy argument.
        """
        # First look for an existing group with the same name. This allows
        # a BaseSubCommand to merge option groups with its parent
        # BaseMultiCommand.
        for group in parser._action_groups:
            if group.title == self.name:
                break
        else:
            group = parser.add_argument_group(self.name, self.description)

        for option in self.option_list:
            option.add_to(group, config, argv)
