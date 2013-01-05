import getpass
import logging
import os
import sys
from optparse import OptionParser
from urlparse import urlparse

from rbtools.api.client import RBClient
from rbtools.api.errors import APIError, ServerInterfaceError
from rbtools.clients import scan_usable_client
from rbtools.utils.filesystem import get_home_path, load_config
from rbtools.utils.process import die

RB_MAIN = "rbt"


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

    def get_cookie(self):
        """Return a cookie file that is read-only."""
        # If we end up creating a cookie file, make sure it's only
        # readable by the user.
        os.umask(0077)

        # Generate a path to the cookie file.
        return os.path.join(get_home_path(), ".post-review-cookies.txt")

    def initialize_scm_tool(self):
        """Initialize the SCM tool for the current working directory."""
        repository_info, tool = scan_usable_client(self.options)
        tool.user_config = self.config
        tool.configs = [self.config]
        tool.check_options()
        return repository_info, tool

    def get_server_url(self, repository_info, tool):
        """Returns the Review Board server url."""
        if self.options.server:
            server_url = self.options.server
        else:
            server_url = tool.scan_for_server(repository_info)

        if not server_url:
            print ("Unable to find a Review Board server "
                   "for this source code tree.")
            sys.exit(1)

        return server_url

    def credentials_prompt(self, realm, uri, *args, **kwargs):
        """Prompt the user for credentials using the command line.

        This will prompt the user, and then return the provided
        username and password. This is used as a callback in the
        API when the user requires authorization.
        """
        if getattr(self.options, 'diff_filename', None) == '-':
            die('HTTP authentication is required, but cannot be '
                'used with --diff-filename=-')

        print "==> HTTP Authentication Required"
        print 'Enter authorization information for "%s" at %s' % \
            (realm, urlparse(uri)[1])
        username = raw_input('Username: ')
        password = getpass.getpass('Password: ')

        return username, password

    def get_root(self, server_url):
        """Returns the root resource of an RBClient."""
        cookie_file = self.get_cookie()

        self.rb_api = RBClient(server_url,
                               cookie_file=cookie_file,
                               username=self.options.username,
                               password=self.options.password,
                               auth_callback=self.credentials_prompt)
        root = None
        try:
            root = self.rb_api.get_root()
        except ServerInterfaceError, e:
            die("Could not reach the review board server at %s" % server_url)
        except APIError, e:
            die("Error: %s" % e)

        return root

    def main(self, *args):
        """The main logic of the command.

        This method should be overridden to implement the commands
        functionality.
        """
        raise NotImplementedError()
