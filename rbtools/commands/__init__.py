import getpass
import inspect
import logging
import sys
from optparse import make_option, OptionParser, OptionGroup as BaseOptionGroup
from urlparse import urlparse

from rbtools.api.capabilities import Capabilities
from rbtools.api.client import RBClient
from rbtools.api.errors import APIError, ServerInterfaceError
from rbtools.clients import scan_usable_client
from rbtools.clients.errors import OptionsCheckError
from rbtools.utils.filesystem import cleanup_tempfiles, load_config
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
    it will be used to retrieve the config value as a default if the
    option is not specified. This will take precedence over the
    default argument.

    Serves as a wrapper around the OptionParser options, allowing us
    to specify defaults which will be grabbed from the configuration
    after it is loaded.
    """
    def __init__(self, *opts, **attrs):
        self.opts = opts
        self.attrs = attrs

    def make_option(self, config, argv=[]):
        """Return an optparse option.

        Check the loaded configuration for a provided default and
        return an optparse option using it as the default.
        """
        if 'config_key' in self.attrs:
            if self.attrs['config_key'] in config:
                self.attrs['default'] = config[self.attrs['config_key']]

            del self.attrs['config_key']

        if self.attrs.get('value_optional', False):
            # Check if the argument is in sys.argv without an explicit
            # value assigned (using --opt=value or -ovalue).
            #
            # If found, we're going to want to assign it the default value
            # from the 'empty_default' attribute.
            assert 'empty_default' in self.attrs

            for opt in self.opts:
                for i, arg in enumerate(argv):
                    if arg == opt:
                        if opt.startswith('--'):
                            argv[i] += '='

                        argv[i] += self.attrs['empty_default']
                        break

            del self.attrs['empty_default']
            del self.attrs['value_optional']

        return make_option(*self.opts, **self.attrs)

    def add_to(self, parent, config, argv):
        """Adds the option to the parent parser or group."""
        parent.add_option(self.make_option(config, argv))


class OptionGroup(object):
    """Represents a named group of options.

    Each group has a name, an optional description, and a list of options.
    It serves as a way to organize related options, making it easier for
    users to scan for the options they want.

    This works like optparse's OptionGroup, but is designed to work with
    our special Option class.
    """
    def __init__(self, name=None, description=None, option_list=[]):
        self.name = name
        self.description = description
        self.option_list = option_list

    def add_to(self, parser, config, argv):
        """Adds the group and all its contained options to the parser."""
        group = BaseOptionGroup(parser, self.name, self.description)

        for option in self.option_list:
            option.add_to(group, config, argv)

        parser.add_option_group(group)


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
        ]
    )

    git_options = OptionGroup(
        name='Git Options',
        description='Git-specific options for selecting revisions for '
                    'diff generation.',
        option_list=[
            Option('--tracking-branch',
                   dest='tracking',
                   metavar='BRANCH',
                   config_key='TRACKING_BRANCH',
                   default=None,
                   help='The remote tracking branch from which your '
                        'local branch is derived '
                        '(defaults to origin/master).'),
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
        """Create and return the ``OptionParser`` which will be used to
        parse the arguments to this command.
        """
        parser = OptionParser(prog=RB_MAIN,
                              usage=self.usage(),
                              add_help_option=False)

        for option in self.option_list:
            option.add_to(parser, config, argv)

        for option in self._global_options:
            option.add_to(parser, config, argv)

        return parser

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
        parser = self.create_parser(self.config, argv)
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
                        auth_callback=self.credentials_prompt,
                        otp_token_callback=self.otp_token_prompt)

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
