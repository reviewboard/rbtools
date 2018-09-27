from __future__ import print_function, unicode_literals

import argparse
import os
import pkg_resources
import signal
import subprocess
import sys

from rbtools import get_version_string
from rbtools.commands import find_entry_point_for_command, Option, RB_MAIN
from rbtools.utils.aliases import run_alias
from rbtools.utils.filesystem import load_config


GLOBAL_OPTIONS = [
    Option('-v', '--version',
           action='version',
           version='RBTools %s' % get_version_string()),
    Option('-h', '--help',
           action='store_true',
           dest='help',
           default=False),
    Option('command',
           nargs=argparse.REMAINDER,
           help='The RBTools command to execute, and any arguments. '
                '(See below)'),
]


def build_help_text(command_class):
    """Generate help text from a command class."""
    command = command_class()
    parser = command.create_parser({})

    return parser.format_help()


def help(args, parser):
    if args:
        # TODO: First check for static help text file before
        # generating it at run time.
        ep = find_entry_point_for_command(args[0])

        if ep:
            help_text = build_help_text(ep.load())
            print(help_text)
            sys.exit(0)

        print('No help found for %s' % args[0])
        sys.exit(0)

    parser.print_help()

    # We cast to a set to de-dupe the list, since third-parties may
    # try to override commands by using the same name, and then cast
    # back to a list for easy sorting.
    entrypoints = pkg_resources.iter_entry_points('rbtools_commands')
    commands = list(set([entrypoint.name for entrypoint in entrypoints]))
    common_commands = ['post', 'patch', 'close', 'diff']

    print('\nThe most commonly used commands are:')
    for command in common_commands:
        print('  %s' % command)

    print('\nOther commands:')
    for command in sorted(commands):
        if command not in common_commands:
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
    elif opt.help or b'--help' in args or b'-h' in args:
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
            sys.exit(
                subprocess.call(['%s-%s' % (RB_MAIN, command_name)] + args,
                                stdin=sys.stdin,
                                stdout=sys.stdout,
                                stderr=sys.stderr,
                                env=os.environ.copy()))
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
