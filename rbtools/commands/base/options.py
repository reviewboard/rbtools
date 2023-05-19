"""Command line option management for commands.

Version Added:
    5.0
"""

from __future__ import annotations


class Option(object):
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
        This replaces the old :py:class:`rbtools.commands.Option` class.
    """

    def __init__(self, *opts, **attrs):
        self.opts = opts
        self.attrs = attrs

    def add_to(self, parent, config={}, argv=[]):
        """Adds the option to the parent parser or group.

        If the option maps to a configuration key, this will handle figuring
        out the correct default.

        Once we've determined the right set of flags, the option will be
        added to the parser.
        """
        attrs = self.attrs.copy()

        if 'config_key' in attrs:
            config_key = attrs.pop('config_key')

            if config_key in config:
                attrs['default'] = config[config_key]

        if 'deprecated_in' in attrs:
            attrs['help'] += '\n[Deprecated since %s]' % attrs['deprecated_in']

        # These are used for other purposes, and are not supported by
        # argparse.
        for attr in ('added_in', 'deprecated_in', 'extended_help',
                     'versions_changed'):
            attrs.pop(attr, None)

        parent.add_argument(*self.opts, **attrs)


class OptionGroup(object):
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

    def __init__(self, name=None, description=None, option_list=[]):
        self.name = name
        self.description = description
        self.option_list = option_list

    def add_to(self, parser, config={}, argv=[]):
        """Add the group and all its contained options to the parser.

        Args:
            parser (argparse.ArgumentParser):
                The command-line parser.

            config (dict):
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
