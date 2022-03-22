from __future__ import print_function, unicode_literals

import argparse
import glob
import os
import pkg_resources
import signal
import subprocess
import sys

from rbtools import get_version_string
from rbtools.commands import (BaseMultiCommand,
                              Option,
                              RB_MAIN,
                              find_entry_point_for_command)
from rbtools.utils.aliases import run_alias
from rbtools.utils.filesystem import load_config


GLOBAL_OPTIONS = [
    Option('-v', '--version',
           action='version',
           version='RBTools %s (Python %d.%d.%d)' % (
               get_version_string(),
               sys.version_info[:3][0],
               sys.version_info[:3][1],
               sys.version_info[:3][2])),
    Option('-h', '--help',
           action='store_true',
           dest='help',
           default=False),
    Option('command',
           nargs=argparse.REMAINDER,
           help='The RBTools command to execute, and any arguments. '
                '(See below)'),
]


def print_help_text(command_class, argv):
    """Print help text from a command class.

    This will work with any of the following invocations:

    * :command:`rbt help <command>`
    * :command:`rbt help <command> <subcommand>`
    * :command:`rbt --help <command>`
    * :command:`rbt --help <command> <subcommand>`
    * :command:`rbt <command> --help`
    * :command:`rbt <command> --help <subcommand>`
    * :command:`rbt <command> <subcommand> --help`

    Args:
        command_class (type):
            The command class to instantiate.

        argv (list):
            The arguments to parse.
    """
    help_args = []

    if issubclass(command_class, BaseMultiCommand):
        # We need to be able to handle --help for both the main command or
        # the subcommand. By default, we're showing help for the main command,
        # but if the first positional argument is a subcommand, we'll switch
        # to showing help for that instead.
        pos_args = [
            _arg
            for _arg in argv[1:]
            if not _arg.startswith('-')
        ]

        if pos_args:
            # Check if we got a subcommand.
            subcommand_arg = pos_args[0]

            for subcommand_cls in command_class.subcommands:
                if subcommand_cls.name == subcommand_arg:
                    # We found the subcommand the user wants help on. Put
                    # together command line arguments for getting help on
                    # this subcommand, for parsing below.
                    help_args = [argv[0], subcommand_cls.name, '--help']
                    break

    parser = command_class().create_parser({}, help_args)

    if help_args:
        parser.parse_args(help_args[1:])

    print(parser.format_help())


def help(args, parser):
    if args:
        # TODO: First check for static help text file before
        # generating it at run time.
        ep = find_entry_point_for_command(args[0])

        if ep:
            print_help_text(ep.load(), args)
            sys.exit(0)
        else:
            try:
                returncode = subprocess.call(
                    ['%s-%s' % (RB_MAIN, args[0]), '--help'],
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    env=os.environ.copy())
                sys.exit(returncode)
            except OSError:
                # OSError is only raised in this scenario when subprocess.call
                # cannot find an executable with the name rbt-<command_name>.
                # If this command doesn't exist, we will check if an alias
                # exists with the name before printing an error message.
                pass

            aliases = load_config().get('ALIASES', {})

            if args[0] in aliases:
                if aliases[args[0]].startswith('!'):
                    print('"%s" is an alias for the shell command "%s"' %
                          (args[0], aliases[args[0]][1:]))
                else:
                    print('"%s" is an alias for the command "%s %s"' %
                          (args[0], RB_MAIN, aliases[args[0]]))
                sys.exit(0)

        print('No help found for %s' % args[0])
        sys.exit(0)

    parser.print_help()

    # We cast to a set to de-dupe the list, since third-parties may
    # try to override commands by using the same name, and then cast
    # back to a list for easy sorting.
    entrypoints = pkg_resources.iter_entry_points('rbtools_commands')
    commands = {entrypoint.name for entrypoint in entrypoints}

    for path_dir in os.environ.get('PATH').split(':'):
        path_prefix = '%s/%s-' % (path_dir, RB_MAIN)

        for cmd in glob.glob(path_prefix + '*'):
            commands.add(cmd.replace(path_prefix, ''))

    aliases = load_config().get('ALIASES', {})
    commands |= set(aliases.keys())
    common_commands = ['post', 'patch', 'close', 'diff']
    other_commands = commands - set(common_commands)

    print('\nThe most commonly used commands are:')
    for command in common_commands:
        print('  %s' % command)

    print('\nOther commands:')
    for command in sorted(other_commands):
        print('  %s' % command)

    print('See "%s help <command>" for more information on a specific '
          'command.' % RB_MAIN)
    sys.exit(0)


def main():
    """Execute a command."""
    def exit_on_int(sig, frame):
        sys.exit(128 + sig)
    signal.signal(signal.SIGINT, exit_on_int)

    parser = argparse.ArgumentParser(
        prog=RB_MAIN,
        usage='%(prog)s [--version] <command> [options] [<args>]',
        add_help=False)

    for option in GLOBAL_OPTIONS:
        option.add_to(parser)

    opt = parser.parse_args()

    if not opt.command:
        help([], parser)

    command_name = opt.command[0]
    args = opt.command[1:]

    if command_name == 'help':
        help(args, parser)
    elif opt.help or '--help' in args or '-h' in args:
        help(opt.command, parser)

    ep = find_entry_point_for_command(command_name)

    if ep:
        try:
            command = ep.load()()
        except ImportError:
            # TODO: It might be useful to actual have the stack
            # trace here, due to an import somewhere down the import
            # chain failing.
            sys.stderr.write('Could not load command entry point %s\n' %
                             ep.name)
            sys.exit(1)
        except Exception as e:
            sys.stderr.write('Unexpected error loading command %s: %s\n' %
                             (ep.name, e))
            sys.exit(1)

        command.run_from_argv([RB_MAIN, command_name] + args)
    else:
        # A command class could not be found, so try and execute
        # the "rb-<command>" on the system.
        try:
            returncode = subprocess.call(
                ['%s-%s' % (RB_MAIN, command_name)] + args,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
                env=os.environ.copy())
            sys.exit(returncode)
        except OSError:
            # OSError is only raised in this scenario when subprocess.call
            # cannot find an executable with the name rbt-<command_name>. If
            # this command doesn't exist, we will check if an alias exists
            # with the name before printing an error message.
            pass

        aliases = load_config().get('ALIASES', {})

        if command_name in aliases:
            sys.exit(run_alias(command_name, aliases[command_name], args))
        else:
            parser.error('"%s" is not a command' % command_name)


if __name__ == '__main__':
    main()
