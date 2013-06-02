import getpass
import inspect
import logging
import sys
from optparse import make_option, OptionParser
from urlparse import urlparse

from rbtools.api.capabilities import Capabilities
from rbtools.api.client import RBClient
from rbtools.api.errors import APIError, ServerInterfaceError
from rbtools.clients import scan_usable_client
from rbtools.utils.filesystem import cleanup_tempfiles, \
                                     load_config
from rbtools.utils.process import die


RB_MAIN = "rbt"


class CommandExit(Exception):
    def __init__(self, exit_code=0):
        super(CommandExit, self).__init__("Exit with code %s" % exit_code)
        self.exit_code = exit_code


class CommandError(Exception):
    pass


class ParseError(CommandError):
    pass


class Option(object):
    """Represents an option for a command.

    The arguments to the constructor should be treated like those
    to optparse.make_option, with the exception that the keyword
    argument 'config_key' is also valid. If config_key is provided
    it will be used to retreive the config value as a default if the
    option is not specified. This will take precedence over the
    default argument.

    Serves as a wrapper around the OptionParser options, allowing us
    to specify defaults which will be grabbed from the configuration
    after it is loaded.
    """
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def make_option(self, config):
        """Return an optparse option.

        Check the loaded configuration for a provided default and
        return an optparse option using it as the default.
        """
        if 'config_key' in self.kwargs:
            if self.kwargs['config_key'] in config:
                self.kwargs['default'] = config[self.kwargs['config_key']]

            del self.kwargs['config_key']

        return make_option(*self.args, **self.kwargs)


class Command(object):
    """Base class for rb commands.

    This class will handle retrieving the configuration, and parsing
    command line options.

    ``description`` is a string containing a short description of the
    command which is suitable for display in usage text.

    ``usage`` is a list of usage strings each showing a use case. These
    should not include the main rbt command or the command name; they
    will be added automatically.

    ``args`` is a string containing the usage text for what arguments the
    command takes.

    ``option_list`` is a list of command line options for the command.
    Each list entry should be an option created using the optparse.make_option
    function.
    """
    name = ""
    author = ""
    description = ""
    args = ""
    option_list = []
    _global_options = [
        Option("-d", "--debug",
               action="store_true",
               dest="debug",
               config_key="DEBUG",
               default=False,
               help="display debug output"),
    ]

    def __init__(self):
        self.log = logging.getLogger('rb.%s' % self.name)

    def create_parser(self, config):
        """Create and return the ``OptionParser`` which will be used to
        parse the arguments to this command.
        """
        option_list = [
            opt.make_option(config) for opt in self.option_list
        ] + [
            opt.make_option(config) for opt in self._global_options
        ]

        return OptionParser(prog=RB_MAIN,
                            usage=self.usage(),
                            option_list=option_list,
                            add_help_option=False)

    def usage(self):
        """Return a usage string for the command."""
        usage = '%%prog %s [options] %s' % (self.name, self.args)

        if self.description:
            return '%s\n\n%s' % (usage, self.description)
        else:
            return usage

    def run_from_argv(self, argv):
        """Execute the command using the provided arguments.

        The options and commandline arguments will be parsed
        from ``argv`` and the commands ``main`` method will
        be called.
        """
        self.config = load_config()
        parser = self.create_parser(self.config)
        options, args = parser.parse_args(argv[2:])
        self.options = options

        # Check that the proper number of arguments have been provided.
        argspec = inspect.getargspec(self.main)
        minargs = len(argspec[0]) - 1
        maxargs = minargs

        if argspec[1] is not None:
            maxargs = None

        if len(args) < minargs or (maxargs is not None and
                                   len(args) > maxargs):

            parser.error("Invalid number of arguments provided")
            sys.exit(1)

        if self.options.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        try:
            exit_code = self.main(*args) or 0
        except CommandError, e:
            if isinstance(e, ParseError):
                parser.error(e)
            elif self.options.debug:
                raise

            logging.error(e)
            exit_code = 1
        except CommandExit, e:
            exit_code = e.exit_code
        except Exception, e:
            # If debugging is on, we'll let python spit out the
            # stack trace and report the exception, otherwise
            # we'll suppress the trace and print the exception
            # manually.
            if self.options.debug:
                raise

            logging.critical(e)
            exit_code = 1

        cleanup_tempfiles()
        sys.exit(exit_code)

    def initialize_scm_tool(self, client_name=None):
        """Initialize the SCM tool for the current working directory."""
        repository_info, tool = scan_usable_client(self.options,
                                                   client_name=client_name)
        tool.user_config = self.config
        tool.configs = [self.config]
        tool.check_options()
        return repository_info, tool

    def setup_tool(self, tool, api_root=None):
        """Performs extra initialization on the tool.

        If api_root is not provided we'll assume we want to
        initialize the tool using only local information
        """
        tool.capabilities = self.get_capabilities(api_root)

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
        # getpass will write its prompt to stderr but raw_input
        # writes to stdout. See bug 2831.
        sys.stderr.write('Username: ')
        username = raw_input()
        password = getpass.getpass('Password: ')

        return username, password

    def _make_api_client(self, server_url):
        """Return an RBClient object for the server.

        The RBClient will be instantiated with the proper arguments
        for talking to the provided Review Board server url.
        """
        return RBClient(server_url,
                        username=self.options.username,
                        password=self.options.password,
                        auth_callback=self.credentials_prompt)

    def get_api(self, server_url):
        """Returns an RBClient instance and the associated root resource.

        Commands should use this method to gain access to the API,
        instead of instantianting their own client.
        """
        api_client = self._make_api_client(server_url)

        try:
            api_root = api_client.get_root()
        except ServerInterfaceError, e:
            raise CommandError("Could not reach the Review Board "
                               "server at %s" % server_url)
        except APIError, e:
            raise CommandError("Unexpected API Error: %s" % e)

        return api_client, api_root

    def get_capabilities(self, api_root):
        """Retrieve Capabilities from the server and return them."""
        info = api_root.get_info()

        if 'capabilities' in info:
            return Capabilities(info.capabilities)
        else:
            return Capabilities({})

    def main(self, *args):
        """The main logic of the command.

        This method should be overridden to implement the commands
        functionality.
        """
        raise NotImplementedError()
