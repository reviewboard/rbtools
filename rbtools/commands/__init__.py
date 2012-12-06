import logging
from optparse import OptionParser

from rbtools.utils.filesystem import load_config


RB_MAIN = "rb"


class Command(object):
    """Base class for rb commands.

    This class will handle retrieving the configuration, and parsing
    command line options.

    ``option_list`` is a list of command line options for the command.
    Each list entry should be an option created using the optparse.make_option
    function.
    """
    name = None
    author = None
    option_list = []
    option_defaults = {}

    def __init__(self):
        self.log = logging.getLogger('rb.%s' % self.name)
        self.config = load_config()

    def create_parser(self, prog_name, subcommand):
        """Create and return the ``OptionParser`` which will be used to
        parse the arguments to this command.
        """
        return OptionParser(prog=prog_name,
                            option_list=self.option_list,
                            add_help_option=False)

    def print_help(self, prog_name, subcommand):
        """Print the help message for the command."""
        parser = self.create_parser(prog_name, subcommand)
        parser.print_help()
        # TODO: Properly print help text from the .txt documentation.
        raise NotImplementedError()

    def run_from_argv(self, argv):
        """Execute the command using the provided arguments.

        The options and commandline arguments will be parsed
        from ``argv`` and the commands ``main`` method will
        be called.
        """
        parser = self.create_parser(argv[0], argv[1])
        parser.set_defaults(**self.option_defaults)
        options, args = parser.parse_args(argv[2:])
        self.options = options

        # TODO: Implement proper exception handling here. A
        # friendly error should be printed if the command
        # throws any exceptions.
        self.main(*args)

    def main(self, *args):
        """The main logic of the command.

        This method should be overridden to implement the commands
        functionality.
        """
        raise NotImplementedError()
