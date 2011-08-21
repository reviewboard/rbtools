import sys
from optparse import IndentedHelpFormatter, OptionParser

from rbtools import get_version_string
from rbtools.commands import RB_CMD_PATTERN, RB_COMMANDS, RB_MAIN
from rbtools.utils.process import execute


_indent = max([len(cmd) for cmd in RB_COMMANDS]) - len(RB_MAIN)

_COMMANDS_LIST_STR = 'Available commands are:\n' + '\n'.join([
    "  %-*s  %s" % (_indent, cmd[len(RB_MAIN):], desc)
    for cmd, desc in RB_COMMANDS.iteritems()
])


class SimpleIndentedFormatter(IndentedHelpFormatter):
    """Indents text without causing the description text to wrap.

    IndentedHelpFormatter wraps the output so that it fits into the
    terminal width. This generally is intended to wrap the description text.
    However, we store our list of commands in the description, and we don't
    want this to wrap oddly.
    """
    def format_description(self, description):
        if description:
            return description + '\n'
        else:
            return ''


def main():
    parser = OptionParser(prog=RB_MAIN,
                          usage='%prog [options] <command> [<args>]',
                          formatter=SimpleIndentedFormatter(),
                          description=_COMMANDS_LIST_STR,
                          version='RBTools %s' % get_version_string())
    parser.disable_interspersed_args()
    opt, args = parser.parse_args()

    if not args:
        parser.print_help()
        sys.exit(1)

    if RB_MAIN + args[0] in RB_COMMANDS:
        args[0] = RB_CMD_PATTERN % {'name': args[0]}
        print execute(args)
    else:
        parser.error("'%s' is not a command" % args[0])


if __name__ == "__main__":
    main()
