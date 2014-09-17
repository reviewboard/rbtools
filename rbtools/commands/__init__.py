import argparse
import getpass
import inspect
import logging
import platform
import os
import sys
from urlparse import urlparse

from rbtools import get_version_string
from rbtools.api.capabilities import Capabilities
from rbtools.api.client import RBClient
from rbtools.api.errors import APIError, ServerInterfaceError
from rbtools.clients import scan_usable_client
from rbtools.clients.errors import OptionsCheckError
from rbtools.utils.filesystem import (cleanup_tempfiles, get_home_path,
                                      load_config)
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
    to argparse's add_argument, with the exception that the keyword
    argument 'config_key' is also valid. If config_key is provided
    it will be used to retrieve the config value as a default if the
    option is not specified. This will take precedence over the
    default argument.

    Serves as a wrapper around the ArgumentParser options, allowing us
    to specify defaults which will be grabbed from the configuration
    after it is loaded.
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
        if 'config_key' in self.attrs:
            if self.attrs['config_key'] in config:
                self.attrs['default'] = config[self.attrs['config_key']]

            del self.attrs['config_key']

        parent.add_argument(*self.opts, **self.attrs)


class OptionGroup(object):
    """Represents a named group of options.

    Each group has a name, an optional description, and a list of options.
    It serves as a way to organize related options, making it easier for
    users to scan for the options they want.

    This works like argparse's argument groups, but is designed to work with
    our special Option class.
    """
    def __init__(self, name=None, description=None, option_list=[]):
        self.name = name
        self.description = description
        self.option_list = option_list

    def add_to(self, parser, config={}, argv=[]):
        """Adds the group and all its contained options to the parser."""
        group = parser.add_argument_group(self.name, self.description)

        for option in self.option_list:
            option.add_to(group, config, argv)


class LogLevelFilter(logging.Filter):
    """Filters log messages of a given level.

    Only log messages that have the specified level will be allowed by
    this filter. This prevents propagation of higher level types to lower
    log handlers.
    """
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno == self.level


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
    Each list entry should be an Option or OptionGroup instance.
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

    server_options = OptionGroup(
        name='Review Board Server Options',
        description='Options necessary to communicate and authenticate '
                    'with a Review Board server.',
        option_list=[
            Option('--server',
                   dest='server',
                   metavar='SERVER',
                   config_key='REVIEWBOARD_URL',
                   default=None,
                   help='Specifies the Review Board server to use.'),
            Option('--disable-proxy',
                   action='store_false',
                   dest='enable_proxy',
                   config_key='ENABLE_PROXY',
                   default=True,
                   help='Prevents requests from going through a proxy '
                        'server.'),
            Option('--username',
                   dest='username',
                   metavar='USERNAME',
                   config_key='USERNAME',
                   default=None,
                   help='The user name to be supplied to the Review Board '
                        'server.'),
            Option('--password',
                   dest='password',
                   metavar='PASSWORD',
                   config_key='PASSWORD',
                   default=None,
                   help='The password to be supplied to the Review Board '
                        'server.'),
            Option('--api-token',
                   dest='api_token',
                   metavar='TOKEN',
                   config_key='API_TOKEN',
                   default=None,
                   help='The API token to use for authentication, instead of '
                        'using a username and password.'),
        ]
    )

    repository_options = OptionGroup(
        name='Repository Options',
        option_list=[
            Option('--repository',
                   dest='repository_name',
                   config_key='REPOSITORY',
                   default=None,
                   help='The name of the repository configured on '
                        'Review Board that matches the local repository.'),
            Option('--repository-url',
                   dest='repository_url',
                   config_key='REPOSITORY_URL',
                   default=None,
                   help='The URL for a repository, used for creating '
                        'a diff outside of a working copy (currently only '
                        'supported by Subversion with specific revisions '
                        'or --diff-filename and ClearCase with relative '
                        'paths outside the view). For git, this specifies '
                        'the origin url of the current repository, '
                        'overriding the origin URL supplied by the git '
                        'client.'),
            Option('--repository-type',
                   dest='repository_type',
                   config_key='REPOSITORY_TYPE',
                   default=None,
                   help='The type of repository in the current directory. '
                        'In most cases this should be detected '
                        'automatically, but some directory structures '
                        'containing multiple repositories require this '
                        'option to select the proper type. The '
                        '`rbt list-repo-types` command can be used to '
                        'list the supported values.'),
        ]
    )

    diff_options = OptionGroup(
        name='Diff Generation Options',
        description='Options for choosing what gets included in a diff, '
                    'and how the diff is generated.',
        option_list=[
            Option('--revision-range',
                   dest='revision_range',
                   default=None,
                   help='Generates a diff for the given revision range. '
                        '[DEPRECATED]'),
            Option('-I', '--include',
                   dest='include_files',
                   action='append',
                   help='Includes only the given file in the diff. '
                        'This can be used multiple times to specify '
                        'multiple files.'),
            Option('-X', '--exclude',
                   dest='exclude_files',
                   action='append',
                   config_key='EXCLUDE_FILES',
                   help='Exclude the given file from the diff. This can be '
                        'used multiple times to specify multiple files.'),
            Option('--parent',
                   dest='parent_branch',
                   metavar='BRANCH',
                   config_key='PARENT_BRANCH',
                   default=None,
                   help='The parent branch this diff should be generated '
                        'against (Bazaar/Git/Mercurial only).'),
            Option('--diff-filename',
                   dest='diff_filename',
                   default=None,
                   metavar='FILENAME',
                   help='Uploads an existing diff file, instead of '
                        'generating a new diff.'),
            Option('--tracking-branch',
                   dest='tracking',
                   metavar='BRANCH',
                   config_key='TRACKING_BRANCH',
                   default=None,
                   help='The remote tracking branch from which your local '
                        'branch is derived (Git/Mercurial only). Defaults '
                        'are "origin/master" for Git and one of '
                        '"reviewboard", "origin", "parent", or "default" for '
                        'Mercurial.'),
        ]
    )

    perforce_options = OptionGroup(
        name='Perforce Options',
        description='Perforce-specific options for selecting the '
                    'Perforce client and communicating with the '
                    'repository.',
        option_list=[
            Option('--p4-client',
                   dest='p4_client',
                   config_key='P4_CLIENT',
                   default=None,
                   metavar='CLIENT_NAME',
                   help='The Perforce client name for the repository.'),
            Option('--p4-port',
                   dest='p4_port',
                   config_key='P4_PORT',
                   default=None,
                   metavar='PORT',
                   help='The IP address for the Perforce server.'),
            Option('--p4-passwd',
                   dest='p4_passwd',
                   config_key='P4_PASSWD',
                   default=None,
                   metavar='PASSWORD',
                   help='The Perforce password or ticket of the user '
                        'in the P4USER environment variable.'),
        ]
    )

    subversion_options = OptionGroup(
        name='Subversion Options',
        description='Subversion-specific options for controlling diff '
                    'generation.',
        option_list=[
            Option('--basedir',
                   dest='basedir',
                   config_key='BASEDIR',
                   default=None,
                   metavar='PATH',
                   help='The path within the repository where the diff '
                        'was generated. This overrides the detected path. '
                        'Often used when passing --diff-filename.'),
            Option('--svn-username',
                   dest='svn_username',
                   default=None,
                   metavar='SVN_USERNAME',
                   help='The username for the SVN repository.'),
            Option('--svn-password',
                   dest='svn_password',
                   default=None,
                   metavar='SVN_PASSWORD',
                   help='The password for the SVN repository.'),
            Option('--svn-show-copies-as-adds',
                   dest='svn_show_copies_as_adds',
                   metavar='y/n',
                   default=None,
                   help='Treat copied or moved files as new files.'),
            Option('--svn-changelist',
                   dest='svn_changelist',
                   default=None,
                   metavar='ID',
                   help='Generates the diff for review based on a '
                        'local changelist. [DEPRECATED]'),
        ]
    )

    def __init__(self):
        self.log = logging.getLogger('rb.%s' % self.name)

    def create_parser(self, config, argv=[]):
        """Create and return the argument parser for this command."""
        parser = argparse.ArgumentParser(prog=RB_MAIN,
                                         usage=self.usage(),
                                         add_help=False)

        for option in self.option_list:
            option.add_to(parser, config, argv)

        for option in self._global_options:
            option.add_to(parser, config, argv)

        return parser

    def usage(self):
        """Return a usage string for the command."""
        usage = '%%(prog)s %s [options] %s' % (self.name, self.args)

        if self.description:
            return '%s\n\n%s' % (usage, self.description)
        else:
            return usage

    def init_logging(self):
        """Initializes logging for the command.

        This will set up different log handlers based on the formatting we want
        for the given levels.

        The INFO log handler will just show the text, like a print statement.

        WARNING and higher will show the level name as a prefix, in the form of
        "LEVEL: message".

        If debugging is enabled, a debug log handler will be set up showing
        debug messages in the form of ">>> message", making it easier to
        distinguish between debugging and other messages.
        """
        root = logging.getLogger()

        if self.options.debug:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('>>> %(message)s'))
            handler.setLevel(logging.DEBUG)
            handler.addFilter(LogLevelFilter(logging.DEBUG))
            root.addHandler(handler)

            root.setLevel(logging.DEBUG)
        else:
            root.setLevel(logging.INFO)

        # Handler for info messages. We'll treat these like prints.
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.setLevel(logging.INFO)
        handler.addFilter(LogLevelFilter(logging.INFO))
        root.addHandler(handler)

        # Handler for warnings, errors, and criticals. They'll show the
        # level prefix and the message.
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        handler.setLevel(logging.WARNING)
        root.addHandler(handler)

        logging.debug('RBTools %s', get_version_string())
        logging.debug('Python %s', sys.version)
        logging.debug('Running on %s', platform.platform())
        logging.debug('Home = %s', get_home_path())
        logging.debug('Current directory = %s', os.getcwd())

    def run_from_argv(self, argv):
        """Execute the command using the provided arguments.

        The options and commandline arguments will be parsed
        from ``argv`` and the commands ``main`` method will
        be called.
        """
        self.config = load_config()

        parser = self.create_parser(self.config, argv)
        parser.add_argument('args', nargs=argparse.REMAINDER)

        self.options = parser.parse_args(argv[2:])
        args = self.options.args

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

        self.init_logging()

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

        try:
            tool.check_options()
        except OptionsCheckError, e:
            sys.stderr.write('%s\n' % e)
            sys.exit(1)

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

    def credentials_prompt(self, realm, uri, username=None, password=None,
                           *args, **kwargs):
        """Prompt the user for credentials using the command line.

        This will prompt the user, and then return the provided
        username and password. This is used as a callback in the
        API when the user requires authorization.
        """
        if getattr(self.options, 'diff_filename', None) == '-':
            die('HTTP authentication is required, but cannot be '
                'used with --diff-filename=-')

        if username is None or password is None:
            print
            print "==> HTTP Authentication Required"
            print 'Enter authorization information for "%s" at %s' % \
                (realm, urlparse(uri)[1])

            # getpass will write its prompt to stderr but raw_input
            # writes to stdout. See bug 2831.
            if username is None:
                sys.stderr.write('Username: ')
                username = raw_input()

            if password is None:
                password = getpass.getpass('Password: ')

        return username, password

    def otp_token_prompt(self, uri, token_method, *args, **kwargs):
        """Prompt the user for a one-time password token.

        Their account is configured with two-factor authentication. The
        server will have sent a token to their configured mobile device
        or application. The user will be prompted for this token.
        """
        if getattr(self.options, 'diff_filename', None) == '-':
            die('A two-factor authentication token is required, but cannot '
                'be used with --diff-filename=-')

        print
        print '==> Two-factor authentication token required'

        if token_method == 'sms':
            print ('You should be getting a text message with '
                   'an authentication token.')
            print 'Enter the token below.'
        elif token_method == 'call':
            print ('You should be getting an automated phone call with '
                   'an authentication token.')
            print 'Enter the token below.'
        elif token_method == 'generator':
            print 'Enter the token shown on your token generator app below.'

        print

        return getpass.getpass('Token: ')

    def _make_api_client(self, server_url):
        """Return an RBClient object for the server.

        The RBClient will be instantiated with the proper arguments
        for talking to the provided Review Board server url.
        """
        return RBClient(server_url,
                        username=self.options.username,
                        password=self.options.password,
                        api_token=self.options.api_token,
                        auth_callback=self.credentials_prompt,
                        otp_token_callback=self.otp_token_prompt,
                        disable_proxy=not self.options.enable_proxy)

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
        if 'capabilities' in api_root:
            # Review Board 2.0+ provides capabilities in the root resource.
            return Capabilities(api_root.capabilities)

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
