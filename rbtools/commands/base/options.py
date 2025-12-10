"""Command line option management for commands.

Version Added:
    5.0
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from collections.abc import Mapping

    from rbtools.config import RBToolsConfig


class Option:
    """Represents an option for a command.

    This serves as a wrapper around the ArgumentParser options, allowing us
    to specify additional attributes that are specific to RBTools, such as
    defaults which will be grabbed from the configuration after it is loaded.

    The arguments to the constructor should be treated like those
    to argparse's :py:meth:`ArgumentParser.add_argument`, with the exception
    of the custom arguments that are defined in the constructor.

    Version Added:
        5.4:
        The optional RBTools specific attributes are now stored on the class
        instead of in ``attrs``.

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
        added_in: (str | None) = None,
        config_key: (str | None) = None,
        deprecated_in: (str | None) = None,
        extended_help: (str | None) = None,
        removed_in: (str | None) = None,
        replacement: (str | None) = None,
        versions_changed: (Mapping[str, str] | None) = None,
        **attrs,
    ) -> None:
        """Initialize the option.

        Version Changed:
            5.4:
            Added explicit arguments for the optional RBTools specific
            arguments that may be set on an option, pulling them out of
            ``**attrs``.

        Args:
            *opts (tuple of str):
                The long and short form option names.

            added_in (str, optional):
                The version the option was added in.

                Version Added:
                    5.4

            config_key (str, optional):
                A config key to retrieve a default value from RBTools config
                when the option is not explicitly provided. This will take
                precedence over any ``default`` in ``attrs``.

                Version Added:
                    5.4

            deprecated_in (str, optional):
                The version the option was deprecated in.

                Version Added:
                    5.4

            extended_help (str, optional):
                Extended help message.

                Version Added:
                    5.4

            removed_in (str, optional):
                The version in which the option will be removed.

                Version Added:
                    5.4

            replacement (str, optional):
                The new option to use instead of the deprecated option, if any.

                This should be the longest form name for the option,
                including any preceding hyphens (e.g. ``--my-option``).

                Version Added:
                    5.4

            versions_changed (dict[str, str], optional):
                A dict of versions in which the option changed. The keys are
                version strings and values are change description strings.

                Version Added:
                    5.4

            **attrs (dict):
                The argparse attributes for the option.

                These should be valid arguments that can be passed to
                :py:meth:`ArgumentParser.add_argument`.
        """
        self.opts = opts
        self.attrs = attrs
        self.added_in = added_in
        self.config_key = config_key
        self.deprecated_in = deprecated_in
        self.extended_help = extended_help
        self.removed_in = removed_in
        self.replacement = replacement
        self.versions_changed = versions_changed

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

        if (config is not None and
            (config_key := self.config_key) and
            config_key in config):
                attrs['default'] = config[config_key]

        if deprecated_in := self.deprecated_in:
            if removed_in := self.removed_in:
                deprecated_str = (
                    f'Deprecated since {deprecated_in} and will be '
                    f'removed in {removed_in}.'
                )
            else:
                deprecated_str = f'Deprecated since {deprecated_in}.'

            if replacement := self.replacement:
                deprecated_str += f' Use {replacement} instead.'

            attrs['help'] += f'\n[{deprecated_str}]'

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
