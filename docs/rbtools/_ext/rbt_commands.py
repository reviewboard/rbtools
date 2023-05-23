import re
import sys

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import ViewList

from rbtools import commands
from rbtools.commands.base import BaseMultiCommand, OptionGroup, Option


class CommandClassNotFound(Exception):
    def __init__(self, directive, classname):
        self.classname = classname
        self.error_node = [
            directive.state_machine.reporter.error(
                str(self),
                line=directive.lineno)
        ]

    def __str__(self):
        return ('Unable to import the RBTools command class "%s"'
                % self.classname)


class SubCommandNotFound(Exception):
    """An error indicating that a subcommand could not be found.

    Version Added:
        3.0
    """

    def __init__(self, directive, subcommand_name):
        """Initialize the error.

        Args:
            docutils.parsers.rst.Directive:
                The directive raising this error.

            subcommand_name (unicode):
                The name of the missing subcommand.
        """
        message = 'Unable to find subcommand for "%s"' % subcommand_name

        self.error_node = [
            directive.state_machine.reporter.error(
                message,
                line=directive.lineno)
        ]

        super(SubCommandNotFound, self).__init__(message)


class CommandDirective(Directive):
    """Sets up a doc page for an RBTools command.

    This will load the given command class, store some state on it for
    other directives to use, and then set up both targets and program
    domains. This must be used at the top of the page before any other
    RBTools command-related directive is used.
    """
    required_arguments = 1

    def run(self):
        doc = self.state.document
        env = doc.settings.env
        class_name = self.arguments[0].strip()

        try:
            cmd_class = self.get_command_class(class_name)
        except CommandClassNotFound as e:
            return e.error_node

        # Add the class's file, this extension, and the file containing the
        # global list of common arguments to the dependencies.
        for dep in (__file__, commands.__file__,
                    sys.modules[cmd_class.__module__].__file__):
            env.note_dependency(dep)

        name = make_command_section_ref_id(cmd_class.name)

        env.temp_data.update({
            'rbt-command:class': cmd_class,
            'rbt-command:doc-prefix': name,
        })

        target_node = nodes.target('', '', ids=[name], names=[name])
        doc.note_explicit_target(target_node)
        program_node = parse_text(
            self,
            '.. rbtcommand:: rbt %(command_name)s\n'
            '.. program:: rbt %(command_name)s'
            % {
                'command_name': cmd_class.name,
            })

        return [program_node, target_node]

    def get_command_class(self, class_name):
        try:
            return self.get_from_module(class_name)
        except ImportError:
            raise CommandClassNotFound(self, class_name)

    def get_from_module(self, name):
        i = name.rfind('.')
        module, attr = name[:i], name[i + 1:]

        try:
            mod = __import__(module, {}, {}, [attr])
            return getattr(mod, attr)
        except AttributeError:
            raise ImportError
        except ImportError:
            raise


class CommandUsageDirective(Directive):
    """Outputs usage information for a command.

    This outputs a section containing the usage information for a command.
    It's similar to what's shown on the command line when using --help.
    """

    for_subcommand = False

    def run(self):
        env = self.state.document.settings.env
        for_subcommand = self.for_subcommand

        command_cls = get_current_command_class(env)
        command = command_cls()

        if for_subcommand:
            subcommand_cls = get_current_command_class(env,
                                                       for_subcommand=True)

            command.create_parser(
                config={},
                argv=['rbt', command_cls.name, subcommand_cls.name])
            parser = command.subcommand_parsers[subcommand_cls.name]
        else:
            parser = command.create_parser({})

        usage = '$ %s' % parser.format_help().splitlines()[0][7:]

        section = nodes.section(ids=[
            get_current_command_usage_ref_id(env,
                                             for_subcommand=for_subcommand),
        ])
        section += nodes.title(text='Usage')
        section += parse_text(
            self,
            '.. code-block:: console\n'
            '\n'
            '   %s\n'
            % usage)

        if for_subcommand:
            # Insert this as a main section under the document section.
            level = 2
        else:
            level = 1

            if isinstance(command, BaseMultiCommand):
                subcommands_list = nodes.bullet_list()

                for subcommand_cls in command.subcommands:
                    ref_item = nodes.inline()
                    ref_item += nodes.reference(
                        text=subcommand_cls.name,
                        refid=make_command_section_ref_id(
                            command_cls.name,
                            subcommand_cls.name))

                    item = nodes.list_item()
                    item += ref_item

                    subcommands_list += item

                section += nodes.Text(
                    'This command provides several subcommands:')
                section += subcommands_list

        add_at_section_level(self, level, [section])

        return []


class CommandOptionsDirective(Directive):
    """Outputs the list of options, grouped by section, for a command.

    This goes through all the options and option groups for a command,
    outputting option documentation for them. This includes any meta
    variables, information on the defaults, and how to override the
    defaults.

    The option information is taken from the metadata passed to Option()
    instances.
    """
    CMD_REF_RE = re.compile(r'`rbt ([a-z-]+)`')
    OPT_REF_RE = re.compile(r'(--[a-z-]+(="[^"]+")?)')
    BACKTICK_RE = re.compile(r'(?<![:`])`([^`:]+)`')

    for_subcommand = False

    def run(self):
        doc = self.state.document
        env = doc.settings.env
        for_subcommand = self.for_subcommand

        self.cmd_class = get_current_command_class(
            env,
            for_subcommand=for_subcommand)

        options, option_groups = self.get_options_and_groups()

        name = get_current_command_options_ref_id(
            env,
            for_subcommand=for_subcommand)
        target_node = nodes.target('', '', ids=[name], names=[name])
        doc.note_explicit_target(target_node)

        section = nodes.section(ids=[name])
        section += nodes.title(text='Options')

        section += self.output_option_list(options)
        section += self.output_option_list(self.cmd_class._global_options)

        for option_group in option_groups:
            section += self.output_opt_group(option_group)

        if for_subcommand:
            level = 2
        else:
            level = 1

        add_at_section_level(self, level, [target_node, section])

        return []

    def get_options_and_groups(self):
        options = []
        option_groups = []

        for i in self.cmd_class.option_list:
            if isinstance(i, Option):
                options.append(i)
            elif isinstance(i, OptionGroup):
                option_groups.append(i)
            else:
                raise ValueError('Invalid item %r found in %r option list'
                                 % (i, self.cmd_class))

        return options, option_groups

    def output_option_list(self, option_list):
        result = []

        for i in option_list:
            result += self.output_option(i)

        return result

    def output_opt_section(self, name):
        env = self.state.document.settings.env

        section = nodes.section(ids=[
            get_current_command_option_ref_id(env, name),
        ])
        section += nodes.title(text=name)

        return section

    def output_opt_group(self, opt_group):
        section = self.output_opt_section(opt_group.name)

        if opt_group.description:
            section += nodes.paragraph(text=opt_group.description)

        section += self.output_option_list(opt_group.option_list)

        return [section]

    def output_option(self, option):
        default_text = ''

        content = [self.format_content(option.attrs['help'])]

        if 'extended_help' in option.attrs:
            content.append(self.format_content(option.attrs['extended_help']))

        if 'default' in option.attrs:
            action = option.attrs.get('action', 'store')
            default = option.attrs.get('default')

            if action == 'store_true' and default is True:
                default_text = 'This option is set by default.'
            elif action == 'store_false' and default is False:
                default_text = 'This option is set by default.'
            elif action == 'store' and default is not None:
                default_text = ('If not specified, ``%s`` is used by default.'
                                % default)

        if 'config_key' in option.attrs:
            if default_text:
                default_text += (
                    ' The default can be changed by setting :rbtconfig:`%s` '
                    'in :ref:`rbtools-reviewboardrc`.'
                    % option.attrs['config_key']
                )
            else:
                default_text = (
                    'The default can be set in :rbtconfig:`%s` in '
                    ':ref:`rbtools-reviewboardrc`.'
                    % option.attrs['config_key']
                )

        if default_text:
            content.append(default_text)

        if 'metavar' in option.attrs:
            norm_metavar = option.attrs['metavar'].lower().replace('_', ' ')

            option_args = ', '.join([
                '%s <%s>' % (option_name, norm_metavar)
                for option_name in option.opts
            ])
        elif 'choices' in option.attrs:
            norm_choices = '|'.join(option.attrs['choices'])

            if option.attrs.get('default') is not None:
                norm_choices = '[%s]' % norm_choices
            else:
                norm_choices = '<%s>' % norm_choices

            option_args = ', '.join([
                '%s %s' % (option_name, norm_choices)
                for option_name in option.opts
            ])
        else:
            option_args = ', '.join(option.opts)

        if 'deprecated_in' in option.attrs:
            content.append('.. deprecated:: %s'
                           % option.attrs['deprecated_in'])

        if 'added_in' in option.attrs:
            content.append('.. versionadded:: %s' % option.attrs['added_in'])

        if 'versions_changed' in option.attrs:
            versions_changed = option.attrs['versions_changed']

            for version in sorted(versions_changed, reverse=True):
                content.append(
                    '.. versionchanged:: %s\n%s' % (
                        version,
                        self.indent_content(
                            self.format_content(versions_changed[version]),
                            indent_level=2)))

        node = parse_text(
            self,
            '.. cmdoption:: %s\n\n%s'
            % (option_args, self.indent_content('\n\n'.join(content))))

        return [node]

    def indent_content(self, content, indent_level=1):
        indent_str = '   ' * indent_level

        return '\n'.join([
            '%s%s' % (indent_str, line)
            for line in content.splitlines()
        ])

    def format_content(self, content):
        content = content.replace('\n', '\n\n')
        content = content.replace('*', '\\*')
        content = content.replace('.reviewboardrc', ':file:`.reviewboardrc`')
        content = self.CMD_REF_RE.sub(r':ref:`rbt \1 <rbt-\1>`', content)
        content = self.OPT_REF_RE.sub(r':option:`\1`', content)
        content = self.BACKTICK_RE.sub(r'``\1``', content)

        return content


class SubCommandDirective(Directive):
    """Sets up a section for a subcommand.

    This will set up references and state for the subcommand, allowing other
    subcommand directives to do the right thing.
    """

    required_arguments = 1

    def run(self):
        """Run the directive.

        This will load the information on the subcommand, set up state, and
        begin injecting new ReST code.

        Returns:
            list:
            The list of nodes to inject.
        """
        doc = self.state.document
        env = doc.settings.env
        subcommand_name = self.arguments[0].strip()

        command_cls = get_current_command_class(env)

        try:
            subcommand_cls = self.get_subcommand_class(command_cls,
                                                       subcommand_name)
        except SubCommandNotFound as e:
            return e.error_node

        # Add the subcommand class's file as a dependency for this page.
        for dep in (sys.modules[subcommand_cls.__module__].__file__):
            env.note_dependency(dep)

        # Record the state on this subcommand for later directives.
        name = make_command_section_ref_id(command_cls.name,
                                           subcommand_name)

        env.temp_data.update({
            'rbt-subcommand:class': subcommand_cls,
            'rbt-subcommand:doc-prefix': name,
        })

        # Set up the initial target for this subcommand.
        target_node = nodes.target('', '',
                                   ids=[name],
                                   names=[name])
        doc.note_explicit_target(target_node)
        program_node = parse_text(
            self,
            '.. rbtcommand:: rbt %(command_name)s %(subcommand_name)s\n'
            '.. program:: rbt %(command_name)s %(subcommand_name)s'
            % {
                'command_name': command_cls.name,
                'subcommand_name': subcommand_cls.name,
            })

        add_at_section_level(self, 1, [program_node, target_node])

        return []

    def get_subcommand_class(self, command_cls, subcommand_name):
        """Return the requested subcommand class from the main class.

        Args:
            command_cls (type):
                The main multi-command class.

            subcommand_name (unicode):
                The name of the subcommand to return.

        Returns:
            type:
            The subcommand class matching the given name.

        Raises:
            SubCommandNotFound:
                The subcommand could not be found.
        """
        for subcommand_cls in command_cls.subcommands:
            if subcommand_cls.name == subcommand_name:
                return subcommand_cls

        raise SubCommandNotFound(self, subcommand_name)


class SubCommandUsageDirective(CommandUsageDirective):
    """Outputs usage information for a subcommand."""

    for_subcommand = True


class SubCommandOptionsDirective(CommandOptionsDirective):
    """Outputs options for a subcommand.

    Version Added:
        3.0
    """

    for_subcommand = True


def parse_text(directive, text, node_type=nodes.paragraph, where=None):
    """Parses text in ReST format and returns a node with the content."""
    assert text is not None, 'Missing text during parse_text in %s' % where

    vl = ViewList()

    for line in text.split('\n'):
        vl.append(line, line)

    node = node_type(rawsource=text)
    directive.state.nested_parse(vl, 0, node)

    return node


def add_at_section_level(node, level, nodes):
    """Adds a list of nodes at the specified section level."""
    parent = node.state.parent

    for i in range(level, node.state.memo.section_level):
        parent = parent.parent

    parent += nodes


def get_current_command_class(env, for_subcommand=False):
    """Return the current command or subcommand class.

    Version Added:
        3.0

    Args:
        env (sphinx.environment.BuildEnvironment):
            The current build environment.

        for_subcommand (bool, optional):
            Whether to return the subcommand class.

    Returns:
        type:
        The command or subcommand class.
    """
    if for_subcommand:
        key = 'rbt-subcommand'
    else:
        key = 'rbt-command'

    return env.temp_data['%s:class' % key]


def make_command_section_ref_id(command_name, subcommand_name=None):
    """Return a new reference ID for a command section.

    Version Added:
        3.0

    Args:
        command_name (unicode):
            The name of the command.

        subcommand_name (unicode, optional):
            The name of a subcommand.

    Returns:
        unicode:
        The reference ID.
    """
    ref_id = 'rbt-%s' % command_name

    if subcommand_name:
        ref_id = '%s-%s' % (ref_id, subcommand_name)

    return ref_id


def get_current_command_section_ref_id(env, for_subcommand=False):
    """Return the reference ID for the current command section.

    Version Added:
        3.0

    Args:
        env (sphinx.environment.BuildEnvironment):
            The current build environment.

        for_subcommand (bool, optional):
            Whether this reference is for the section in a subcommand.

    Returns:
        unicode:
        The section's reference ID.
    """
    if for_subcommand:
        key = 'rbt-subcommand'
    else:
        key = 'rbt-command'

    return env.temp_data['%s:doc-prefix' % key]


def get_current_command_usage_ref_id(env, for_subcommand=False):
    """Return the reference ID for the current command usage section.

    Version Added:
        3.0

    Args:
        env (sphinx.environment.BuildEnvironment):
            The current build environment.

        for_subcommand (bool, optional):
            Whether this reference is for the usage section in a subcommand.

    Returns:
        unicode:
        The usage section's reference ID.
    """
    return ('%s-usage'
            % get_current_command_section_ref_id(
                env,
                for_subcommand=for_subcommand))


def get_current_command_options_ref_id(env, for_subcommand=False):
    """Return the reference ID for the current command options section.

    Version Added:
        3.0

    Args:
        env (sphinx.environment.BuildEnvironment):
            The current build environment.

        for_subcommand (bool, optional):
            Whether this reference is for the options section in a subcommand.

    Returns:
        unicode:
        The option section's reference ID.
    """
    return ('%s-options'
            % get_current_command_section_ref_id(
                env,
                for_subcommand=for_subcommand))


def get_current_command_option_ref_id(env, option_name,
                                      for_subcommand=False):
    """Return the reference ID for an option in the current command.

    Version Added:
        3.0

    Args:
        env (sphinx.environment.BuildEnvironment):
            The current build environment.

        option_name (unicode):
            The name of the option to reference.

        for_subcommand (bool, optional):
            Whether this reference is for an option in a subcommand.

    Returns:
        unicode:
        The option's reference ID.
    """
    return ('%s-%s'
            % (get_current_command_section_ref_id(
                env,
                for_subcommand=for_subcommand),
               option_name.lower().replace(' ', '-')))


def setup(app):
    app.add_directive('rbt-command', CommandDirective)
    app.add_directive('rbt-command-usage', CommandUsageDirective)
    app.add_directive('rbt-command-options', CommandOptionsDirective)
    app.add_directive('rbt-subcommand', SubCommandDirective)
    app.add_directive('rbt-subcommand-usage', SubCommandUsageDirective)
    app.add_directive('rbt-subcommand-options', SubCommandOptionsDirective)
    app.add_crossref_type(directivename=str('rbtcommand'),
                          rolename=str('rbtcommand'),
                          indextemplate=str('pair: %s; RBTools command'))
    app.add_crossref_type(
        directivename=str('rbtconfig'),
        rolename=str('rbtconfig'),
        indextemplate=str('pair: %s; .reviewboardrc setting'))
