"""Base classes for commands.

Version Added:
    5.0
"""

from __future__ import annotations

import argparse
import inspect
import logging
import os
import platform
import subprocess
import sys
from http import HTTPStatus
from typing import ClassVar, Optional, TextIO, Union, TYPE_CHECKING
from urllib.parse import urlparse

import colorama
from typing_extensions import override

from rbtools import get_version_string
from rbtools.api.capabilities import Capabilities
from rbtools.api.client import RBClient
from rbtools.api.errors import APIError, ServerInterfaceError
from rbtools.api.transport.sync import SyncTransport
from rbtools.clients import scan_usable_client
from rbtools.clients.errors import OptionsCheckError
from rbtools.commands.base.errors import (
    CommandError,
    CommandExit,
    NeedsReinitialize,
    ParseError,
)
from rbtools.commands.base.options import Option, OptionGroup
from rbtools.commands.base.output import JSONOutput, OutputWrapper
from rbtools.config import ConfigData, RBToolsConfig, load_config
from rbtools.diffs.tools.errors import MissingDiffToolError
from rbtools.utils.console import get_input, get_pass
from rbtools.utils.filesystem import cleanup_tempfiles, get_home_path
from rbtools.utils.repository import get_repository_resource

if TYPE_CHECKING:
    from rbtools.api.resource import Resource, RootResource
    from rbtools.api.transport import Transport
    from rbtools.clients.base.repository import RepositoryInfo
    from rbtools.clients.base.scmclient import BaseSCMClient


RB_MAIN = 'rbt'


class LogLevelFilter(logging.Filter):
    """Filters log messages of a given level.

    Only log messages that have the specified level will be allowed by
    this filter. This prevents propagation of higher level types to lower
    log handlers.
    """

    def __init__(
        self,
        level: int,
    ) -> None:
        """Initialize the filter.

        Args:
            level (int):
                The log level to filter for.
        """
        self.level = level

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        """Filter a log record.

        Args:
            record (logging.LogRecord):
                The record to filter.

        Returns:
            bool:
            ``True`` if the record's log level matches the filter.
        """
        return record.levelno == self.level


class SmartHelpFormatter(argparse.HelpFormatter):
    """Smartly formats help text, preserving paragraphs.

    Version Changed:
        5.0:
        This moved from :py:mod:`rbtools.commands` to
        :py:mod:`rbtools.commands.base.commands`.
    """

    @override
    def _split_lines(
        self,
        text: str,
        width: int,
    ) -> list[str]:
        """Split text to a given width.

        Args:
            text (str):
                The log text to split.

            width (int):
                The width to split to.

        Returns:
            list of str:
            The list of split lines.
        """
        # NOTE: This function depends on overriding _split_lines's behavior.
        #       It is clearly documented that this function should not be
        #       considered public API. However, given that the width we need
        #       is calculated by HelpFormatter, and HelpFormatter has no
        #       blessed public API, we have no other choice but to override
        #       it here.
        lines: list[str] = []

        for line in text.splitlines():
            lines += super()._split_lines(line, width)
            lines.append('')

        return lines[:-1]


class BaseCommand:
    """Base class for RBTools commands.

    This class will handle retrieving the configuration, and parsing
    command line options.

    ``usage`` is a list of usage strings each showing a use case. These
    should not include the main rbt command or the command name; they
    will be added automatically.

    Version Changed:
        5.0:
        This moved from :py:mod:`rbtools.commands` to
        :py:mod:`rbtools.commands.base.commands`.
    """

    #: The name of the command.
    #:
    #: Type:
    #:     str
    name: ClassVar[str] = ''

    #: The author of the command.
    #:
    #: Type:
    #:     str
    author: ClassVar[str] = ''

    #: A short description of the command, suitable for display in usage text.
    #:
    #: Type:
    #:     str
    description: ClassVar[str] = ''

    #: Whether the command needs the API client.
    #:
    #: If this is set, the initialization of the command will set
    #: :py:attr:`api_client` and :py:attr:`api_root`.
    #:
    #: Version Added:
    #:     3.0
    #:
    #: Type:
    #:     bool
    needs_api: ClassVar[bool] = False

    #: Whether the command needs to generate diffs.
    #:
    #: If this is set, the initialization of the command will check for the
    #: presence of a diff tool compatible with the chosen type of repository.
    #:
    #: This depends on :py:attr:`needs_repository` and
    #: :py:attr:`needs_scm_client` both being set to ``True``.
    #:
    #: Version Added:
    #:     4.0
    #:
    #: Type:
    #:     bool
    needs_diffs: ClassVar[bool] = False

    #: Whether the command needs the SCM client.
    #:
    #: If this is set, the initialization of the command will set
    #: :py:attr:`repository_info` and :py:attr:`tool`.
    #:
    #: Version Added:
    #:     3.0
    #:
    #: Type:
    #:     bool
    needs_scm_client: ClassVar[bool] = False

    #: Whether the command needs the remote repository object.
    #:
    #: If this is set, the initialization of the command will set
    #: :py:attr:`repository`.
    #:
    #: Setting this will imply setting both :py:attr:`needs_api` and
    #: :py:attr:`needs_scm_client` to ``True``.
    #:
    #: Version Added:
    #:     3.0
    #:
    #: Type:
    #:     bool
    needs_repository: ClassVar[bool] = False

    #: Usage text for what arguments the command takes.
    #:
    #: Arguments for the command are anything passed in other than defined
    #: options (for example, revisions passed to :command:`rbt post`).
    #:
    #: Type:
    #:     str
    args: ClassVar[str] = ''

    #: Command-line options for this command.
    #:
    #: Type:
    #:     list of Option or OptionGroup
    option_list: ClassVar[list[Union[Option, OptionGroup]]] = []

    ######################
    # Instance variables #
    ######################

    #: The client used to connect to the API.
    #:
    #: This will be set when the command is run if :py:attr:`needs_api` is
    #: ``True``. Otherwise it will be ``None``.
    api_client: Optional[RBClient]

    #: The root of the API tree.
    #:
    #: This will be set when the command is run if :py:attr:`needs_api` is
    #: ``True``. Otherwise it will be ``None``.
    api_root: Optional[RootResource]

    #: Capabilities set by the API.
    #:
    #: This will be set when the command is run if :py:attr:`needs_api` is
    #: ``True``. Otherwise it will be ``None``.
    capabilities: Optional[Capabilities]

    #: The loaded configuration for RBTools.
    #:
    #: Version Changed:
    #:     5.0:
    #:     This is now a :py:class:`~rbtools.config.config.RBToolsConfig`
    #:     instance, instead of a plain dictionary.
    config: Optional[RBToolsConfig]

    #: An output buffer for JSON results.
    #:
    #: Commands can set this to return data used when a command is passed
    #: :option:`--json`.
    json: JSONOutput

    #: A logger for the command.
    log: logging.Logger

    #: Options parsed for the command.
    options: argparse.Namespace

    #: The resource for the matching repository.
    #:
    #: This will be set when the command is run if both :py:attr:`needs_api`
    #: and :py:attr:`needs_repository` are ``True``.
    repository: Optional[Resource]

    #: Information on the local repository.
    #:
    #: This will be set when the command is run if :py:attr:`needs_scm_client`
    #: is run. Otherwise it will be ``None``.
    repository_info: Optional[RepositoryInfo]

    #: The URL to the Review Board server.
    #:
    #: This will be set when the command is run if :py:attr:`needs_api` is
    #: ``True``.
    server_url: Optional[str]

    #: The stream for writing error output as Unicode strings.
    #:
    #: Commands should write error text using this instead of :py:func:`print`
    #: or :py:func:`sys.stderr`.
    stderr: OutputWrapper[str]

    #: The stream for writing error output as byte strings.
    #:
    #: Commands should write error text using this instead of :py:func:`print`
    #: or :py:func:`sys.stderr`.
    stderr_bytes: OutputWrapper[bytes]

    #: Whether the stderr stream is from an interactive session.
    #:
    #: This applies to :py:attr:`stderr`.
    #:
    #: Version Added:
    #:     3.1
    stderr_is_atty: bool

    #: The stream for reading standard input.
    #:
    #: Commands should read input from here instead of using
    #: :py:func:`sys.stdin`.
    #:
    #: Version Added:
    #:     3.1
    stdin: TextIO

    #: Whether the stdin stream is from an interactive session.
    #:
    #: This applies to :py:attr:`stdin`.
    #:
    #: Version Added:
    #:     3.1
    stdin_is_atty: bool

    #: The stream for writing standard output as Unicode strings.
    #:
    #: Commands should write text using this instead of :py:func:`print` or
    #: :py:func:`sys.stdout`.
    stdout: OutputWrapper[str]

    #: The stream for writing standard output as byte strings.
    #:
    #: Commands should write text using this instead of :py:func:`print` or
    #: :py:func:`sys.stdout`.
    stdout_bytes: OutputWrapper[bytes]

    #: Whether the stdout stream is from an interactive session.
    #:
    #: This applies to :py:attr:`stdout`.
    #:
    #: Version Added:
    #:     3.1
    stdout_is_atty: bool

    #: The client/tool used to communicate with the repository.
    #:
    #: This will be set when the command is run if :py:attr:`needs_scm_client`
    #: is run. Otherwise it will be ``None``.
    tool: Optional[BaseSCMClient]

    #: The transport class used for talking to the API.
    transport_cls: type[Transport]

    _global_options: list[Option] = [
        Option('-d', '--debug',
               action='store_true',
               dest='debug',
               config_key='DEBUG',
               default=False,
               help='Displays debug output.',
               extended_help='This information can be valuable when debugging '
                             'problems running the command.'),
        Option('--json',
               action='store_true',
               dest='json_output',
               config_key='JSON_OUTPUT',
               default=False,
               added_in='3.0',
               help='Output results as JSON data instead of text.'),
    ]

    server_options = OptionGroup(
        name='Review Board Server Options',
        description='Options necessary to communicate and authenticate '
                    'with a Review Board server.',
        option_list=[
            Option('--server',
                   dest='server',
                   metavar='URL',
                   config_key='REVIEWBOARD_URL',
                   default=None,
                   help='Specifies the Review Board server to use.'),
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
            Option('--ext-auth-cookies',
                   dest='ext_auth_cookies',
                   metavar='EXT_AUTH_COOKIES',
                   config_key='EXT_AUTH_COOKIES',
                   default=None,
                   help='Use an external cookie store with pre-fetched '
                        'authentication data. This is useful with servers '
                        'that require extra web authentication to access '
                        'Review Board, e.g. on single sign-on enabled sites.',
                   added_in='0.7.5'),
            Option('--api-token',
                   dest='api_token',
                   metavar='TOKEN',
                   config_key='API_TOKEN',
                   default=None,
                   help='The API token to use for authentication, instead of '
                        'using a username and password.',
                   added_in='0.7'),
            Option('--disable-proxy',
                   action='store_false',
                   dest='enable_proxy',
                   config_key='ENABLE_PROXY',
                   default=True,
                   help='Prevents requests from going through a proxy '
                        'server.'),
            Option('--disable-ssl-verification',
                   action='store_true',
                   dest='disable_ssl_verification',
                   config_key='DISABLE_SSL_VERIFICATION',
                   default=False,
                   help='Disable SSL certificate verification. This is useful '
                        'with servers that have self-signed certificates.',
                   added_in='0.7.3'),
            Option('--disable-cookie-storage',
                   config_key='SAVE_COOKIES',
                   dest='save_cookies',
                   action='store_false',
                   default=True,
                   help='Use an in-memory cookie store instead of writing '
                        'them to a file. No credentials will be saved or '
                        'loaded.',
                   added_in='0.7.3'),
            Option('--disable-cache',
                   dest='disable_cache',
                   config_key='DISABLE_CACHE',
                   action='store_true',
                   default=False,
                   help='Disable the HTTP cache completely. This will '
                        'result in slower requests.',
                   added_in='0.7.3'),
            Option('--disable-cache-storage',
                   dest='in_memory_cache',
                   config_key='IN_MEMORY_CACHE',
                   action='store_true',
                   default=False,
                   help='Disable storing the API cache on the filesystem, '
                        'instead keeping it in memory temporarily.',
                   added_in='0.7.3'),
            Option('--cache-location',
                   dest='cache_location',
                   metavar='FILE',
                   config_key='CACHE_LOCATION',
                   default=None,
                   help='The file to use for the API cache database.',
                   added_in='0.7.3'),
            Option('--ca-certs',
                   dest='ca_certs',
                   metavar='FILE',
                   config_key='CA_CERTS',
                   default=None,
                   help='Additional TLS CA bundle.'),
            Option('--client-key',
                   dest='client_key',
                   metavar='FILE',
                   config_key='CLIENT_KEY',
                   default=None,
                   help='Key for TLS client authentication.'),
            Option('--client-cert',
                   dest='client_cert',
                   metavar='FILE',
                   config_key='CLIENT_CERT',
                   default=None,
                   help='Certificate for TLS client authentication.'),
            Option('--proxy-authorization',
                   dest='proxy_authorization',
                   metavar='PROXY_AUTHORIZATION',
                   config_key='PROXY_AUTHORIZATION',
                   default=None,
                   help='Value of the Proxy-Authorization header to send with '
                        'HTTP requests.'),
        ],
    )

    repository_options = OptionGroup(
        name='Repository Options',
        option_list=[
            Option('--repository',
                   dest='repository_name',
                   metavar='NAME',
                   config_key='REPOSITORY',
                   default=None,
                   help='The name of the repository configured on '
                        'Review Board that matches the local repository.'),
            Option('--repository-url',
                   dest='repository_url',
                   metavar='URL',
                   config_key='REPOSITORY_URL',
                   default=None,
                   help='The URL for a repository.'
                        '\n'
                        'When generating diffs, this can be used for '
                        'creating a diff outside of a working copy '
                        '(currently only supported by Subversion with '
                        'specific revisions or --diff-filename, and by '
                        'ClearCase with relative paths outside the view).'
                        '\n'
                        'For Git, this specifies the origin URL of the '
                        'current repository, overriding the origin URL '
                        'supplied by the client.',
                   versions_changed={
                       '0.6': 'Prior versions used the `REPOSITORY` setting '
                              'in .reviewboardrc, and allowed a '
                              'repository name to be passed to '
                              '--repository-url. This is no '
                              'longer supported in 0.6 and higher. You '
                              'may need to update your configuration and '
                              'scripts appropriately.',
                   }),
            Option('--repository-type',
                   dest='repository_type',
                   metavar='TYPE',
                   config_key='REPOSITORY_TYPE',
                   default=None,
                   help='The type of repository in the current directory. '
                        'In most cases this should be detected '
                        'automatically, but some directory structures '
                        'containing multiple repositories require this '
                        'option to select the proper type. The '
                        '`rbt list-repo-types` command can be used to '
                        'list the supported values.'),
        ],
    )

    diff_options = OptionGroup(
        name='Diff Generation Options',
        description='Options for choosing what gets included in a diff, '
                    'and how the diff is generated.',
        option_list=[
            Option('--no-renames',
                   dest='no_renames',
                   action='store_true',
                   help='Add the --no-renames option to the git when '
                        'generating diff.'
                        '\n'
                        'Supported by: Git',
                   added_in='0.7.11'),
            Option('--revision-range',
                   dest='revision_range',
                   metavar='REV1:REV2',
                   default=None,
                   help='Generates a diff for the given revision range.',
                   deprecated_in='0.6'),
            Option('-I', '--include',
                   metavar='FILENAME',
                   dest='include_files',
                   action='append',
                   help='Includes only the specified file in the diff. '
                        'This can be used multiple times to specify '
                        'multiple files.'
                        '\n'
                        'Supported by: Bazaar, CVS, Git, Mercurial, '
                        'Perforce, SOS, and Subversion.',
                   added_in='0.6'),
            Option('-X', '--exclude',
                   metavar='PATTERN',
                   dest='exclude_patterns',
                   action='append',
                   config_key='EXCLUDE_PATTERNS',
                   help='Excludes all files that match the given pattern '
                        'from the diff. This can be used multiple times to '
                        'specify multiple patterns. UNIX glob syntax is used '
                        'for pattern matching.'
                        '\n'
                        'Supported by: Bazaar, CVS, Git, Mercurial, '
                        'Perforce, SOS, and Subversion.',
                   extended_help=(
                       'Patterns that begin with a path separator (/ on Mac '
                       'OS and Linux, \\ on Windows) will be treated as being '
                       'relative to the root of the repository. All other '
                       'patterns are treated as being relative to the current '
                       'working directory.'
                       '\n'
                       'For example, to exclude all ".txt" files from the '
                       'resulting diff, you would use "-X /\'*.txt\'".'
                       '\n'
                       'When working with Mercurial, the patterns are '
                       'provided directly to "hg" and are not limited to '
                       'globs. For more information on advanced pattern '
                       'syntax in Mercurial, run "hg help patterns"'
                       '\n'
                       'When working with CVS all diffs are generated '
                       'relative to the current working directory so '
                       'patterns beginning with a path separator are treated '
                       'as relative to the current working directory.'
                       '\n'
                       'When working with Perforce, an exclude pattern '
                       'beginning with `//` will be matched against depot '
                       'paths; all other patterns will be matched against '
                       'local paths.'),
                   added_in='0.7'),
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
        ],
    )

    branch_options = OptionGroup(
        name='Branch Options',
        description='Options for selecting branches.',
        option_list=[
            Option('--tracking-branch',
                   dest='tracking',
                   metavar='BRANCH',
                   config_key='TRACKING_BRANCH',
                   default=None,
                   help='The remote tracking branch from which your local '
                        'branch is derived (Git/Mercurial only).'
                        '\n'
                        'For Git, the default is to use the remote branch '
                        'that the local branch is tracking, if any, falling '
                        'back on `origin/master`.'
                        '\n'
                        'For Mercurial, the default is one of: '
                        '`reviewboard`, `origin`, `parent`, or `default`.'),
        ],
    )

    git_options = OptionGroup(
        name='Git Options',
        description='Git-specific options for diff generation.',
        option_list=[
            Option('--git-find-renames-threshold',
                   dest='git_find_renames_threshold',
                   metavar='THRESHOLD',
                   default=None,
                   help='The threshold to pass to `--find-renames` when '
                        'generating a git diff.'
                        '\n'
                        'For more information, see `git help diff`.'),
        ],
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
        ],
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
                   metavar='USERNAME',
                   help='The username for the SVN repository.'),
            Option('--svn-password',
                   dest='svn_password',
                   default=None,
                   metavar='PASSWORD',
                   help='The password for the SVN repository.'),
            Option('--svn-prompt-password',
                   dest='svn_prompt_password',
                   config_key='SVN_PROMPT_PASSWORD',
                   default=False,
                   action='store_true',
                   help="Prompt for the user's svn password. This option "
                        "overrides the password provided by the "
                        "--svn-password option.",
                   added_in='0.7.3'),
            Option('--svn-show-copies-as-adds',
                   dest='svn_show_copies_as_adds',
                   metavar='y|n',
                   default=None,
                   help='Treat copied or moved files as new files.'
                        '\n'
                        'This is only supported in Subversion 1.7+.',
                   added_in='0.5.2'),
            Option('--svn-changelist',
                   dest='svn_changelist',
                   default=None,
                   metavar='ID',
                   help='Generates the diff for review based on a '
                        'local changelist.',
                   deprecated_in='0.6'),
        ],
    )

    tfs_options = OptionGroup(
        name='TFS Options',
        description='Team Foundation Server specific options for '
                    'communicating with the TFS server.',
        option_list=[
            Option('--tfs-login',
                   dest='tfs_login',
                   default=None,
                   metavar='TFS_LOGIN',
                   help='Logs in to TFS as a specific user (ie.'
                        'user@domain,password). Visit https://msdn.microsoft.'
                        'com/en-us/library/hh190725.aspx to learn about '
                        'saving credentials for reuse.'),
            Option('--tf-cmd',
                   dest='tf_cmd',
                   default=None,
                   metavar='TF_CMD',
                   config_key='TF_CMD',
                   help='The full path of where to find the tf command. This '
                        'overrides any detected path.'),
            Option('--tfs-shelveset-owner',
                   dest='tfs_shelveset_owner',
                   default=None,
                   metavar='TFS_SHELVESET_OWNER',
                   help='When posting a shelveset name created by another '
                        'user (other than the one who owns the current '
                        'workdir), look for that shelveset using this '
                        'username.'),
        ],
    )

    default_transport_cls = SyncTransport

    def __init__(
        self,
        transport_cls: type[Transport] = SyncTransport,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
        stdin: TextIO = sys.stdin,
    ) -> None:
        """Initialize the base functionality for the command.

        Args:
            transport_cls (rbtools.api.transport.Transport, optional):
                The transport class used for all API communication. By default,
                this uses the transport defined in
                :py:attr:`default_transport_cls`.

            stdout (io.TextIOWrapper, optional):
                The standard output stream. This can be used to capture output
                programmatically.

                Version Added:
                    3.1

            stderr (io.TextIOWrapper, optional):
                The standard error stream. This can be used to capture errors
                programmatically.

                Version Added:
                    3.1

            stdin (io.TextIOWrapper, optional):
                The standard input stream. This can be used to provide input
                programmatically.

                Version Added:
                    3.1
        """
        self.log = logging.getLogger('rb.%s' % self.name)
        self.transport_cls = transport_cls or self.default_transport_cls
        self.api_client = None
        self.api_root = None
        self.capabilities = None
        self.repository = None
        self.repository_info = None
        self.server_url = None
        self.tool = None
        self.config = None

        self.stdout = OutputWrapper[str](stdout)
        self.stderr = OutputWrapper[str](stderr)
        self.stdin = stdin

        self.stdout_bytes = OutputWrapper[bytes](stdout.buffer)
        self.stderr_bytes = OutputWrapper[bytes](stderr.buffer)

        self.stdout_is_atty = hasattr(stdout, 'isatty') and stdout.isatty()
        self.stderr_is_atty = hasattr(stderr, 'isatty') and stderr.isatty()
        self.stdin_is_atty = hasattr(stdin, 'isatty') and stdin.isatty()

        self.json = JSONOutput(stdout)

    def create_parser(
        self,
        config: RBToolsConfig,
        argv: Optional[list[str]] = None,
    ) -> argparse.ArgumentParser:
        """Return a new argument parser for this command.

        Args:
            config (dict):
                The loaded RBTools configuration.

            argv (list of str):
                The list of command line arguments.

        Returns:
            argparse.ArgumentParser:
            The new argument parser for the command.
        """
        if argv is None:
            argv = []

        parser = argparse.ArgumentParser(
            prog=RB_MAIN,
            usage=self.usage(),
            formatter_class=SmartHelpFormatter)

        for option in self.option_list:
            option.add_to(parser, config, argv)

        for option in self._global_options:
            option.add_to(parser, config, argv)

        return parser

    def post_process_options(self) -> None:
        """Post-process options for the command.

        This can validate and update options before the command is invoked.

        Raises:
            rbtools.commands.base.errors.CommandError:
                There was an error found with an option.
        """
        if self.options.disable_ssl_verification:
            try:
                import ssl
                ssl._create_unverified_context()
            except Exception:
                raise CommandError('The --disable-ssl-verification flag is '
                                   'only available with Python 2.7.9+')

    def usage(self) -> str:
        """Return a usage string for the command.

        Returns:
            str:
            Usage text for the command.
        """
        usage = f'%(prog)s {self.name} [options] {self.args}'

        if self.description:
            return f'{usage}\n\n{self.description}'
        else:
            return usage

    def _create_formatter(
        self,
        level: str,
        fmt: str,
    ) -> logging.Formatter:
        """Create a logging formatter for the appropriate logging level.

        When writing to a TTY, the format will be colorized by the colors
        specified in the ``COLORS`` configuration in :file:`.reviewboardrc`.
        Otherwise, the format will not be altered.

        Args:
            level (str):
                The logging level name.

            fmt (str):
                The logging format.

        Returns:
            logging.Formatter:
            The created formatter.
        """
        color: str = ''
        reset: str = ''

        if self.stdout_is_atty:
            color_name = self.config['COLOR'].get(level.upper())

            if color_name:
                color = getattr(colorama.Fore, color_name.upper(), '')

                if color:
                    reset = colorama.Fore.RESET

        return logging.Formatter(fmt.format(color=color, reset=reset))

    def initialize(self) -> None:
        """Initialize the command.

        This will set up various prerequisites for commands. Individual command
        subclasses can control what gets done by setting the various
        ``needs_*`` attributes (as documented in this class).

        Raises:
            rbtools.commands.base.errors.CommandError:
                An error occurred while initializing the command.

            rbtools.commands.base.errors.NeedsReinitialize:
                The initialization process needs to be restarted (due to
                loading additional config).
        """
        assert self.config is not None

        options = self.options

        if self.needs_repository:
            # If we need the repository, we implicitly need the API and SCM
            # client as well.
            self.needs_api = True
            self.needs_scm_client = True

        repository_info = self.repository_info
        tool = self.tool

        if self.needs_scm_client:
            # _init_server_url might have already done this, in the case that
            # it needed to use the SCM client to detect the server name. Only
            # repeat if necessary.
            if repository_info is None and tool is None:
                repository_info, tool = self.initialize_scm_tool(
                    client_name=getattr(self.options, 'repository_type', None))
                self.repository_info = repository_info
                self.tool = tool

            assert tool is not None

            # Some SCMs allow configuring the repository name in the SCM
            # metadata. This is a legacy configuration, and is only used as a
            # fallback for when the repository name is not specified through
            # the config or command line.
            if options.repository_name is None:
                options.repository_name = tool.get_repository_name()

        # The TREES config allows people to namespace config keys in a single
        # .reviewboardrc file. We look for matching keys in that for the local
        # repository path, as well as all remote paths for the repository. If
        # one is found, we want to merge that into the config dictionary and
        # restart the entire initialization process.
        if trees := self.config.get('TREES'):
            # If we haven't attempted to initialize a client yet (either
            # through _init_server_url or with needs_scm_client), try one last
            # time. People who are using TREES often are using repository paths
            # as the keys, which means we need a repository.
            if repository_info is None and tool is None:
                repository_info, tool = self.initialize_scm_tool(
                    client_name=getattr(self.options, 'repository_type', None),
                    tool_required=False)

            paths: list[str] = []

            if repository_info is not None:
                if repository_info.local_path:
                    paths.append(repository_info.local_path)

                if isinstance(repository_info.path, list):
                    paths.extend(repository_info.path)
                elif repository_info.path is not None:
                    paths.append(repository_info.path)
            else:
                paths.append(os.getcwd())

            if not isinstance(trees, dict):
                raise CommandError(
                    'TREES is defined in the Review Board configuration, but '
                    'is not a dictionary.')

            for path in paths:
                if path in trees:
                    trees_config = trees[path]
                    self.config.merge(ConfigData(config_dict=trees_config))
                    del self.config['TREES']

                    raise NeedsReinitialize()

        if self.needs_api:
            self.server_url = self._init_server_url()
            self.api_client, self.api_root = self.get_api(self.server_url)
            self.capabilities = self.get_capabilities(self.api_root)

            if tool is not None:
                tool.capabilities = self.capabilities

        if self.needs_repository:
            assert self.api_root is not None
            assert repository_info is not None

            repository, info = get_repository_resource(
                api_root=self.api_root,
                tool=tool,
                repository_name=options.repository_name,
                repository_paths=repository_info.path,
                capabilities=self.capabilities)
            self.repository = repository

            if repository:
                repository_info.update_from_remote(repository, info)

        if options.json_output:
            self.stdout.output_stream = None
            self.stderr.output_stream = None
            self.stderr_bytes.output_stream = None
            self.stdout_bytes.output_stream = None

    def create_arg_parser(
        self,
        argv: list[str],
    ) -> argparse.ArgumentParser:
        """Create and return the argument parser.

        Args:
            argv (list of str):
                A list of command line arguments

        Returns:
            argparse.ArgumentParser:
            Argument parser for commandline arguments
        """
        if self.config is None:
            self.config = load_config()

        parser = self.create_parser(self.config, argv)
        parser.add_argument('args', nargs=argparse.REMAINDER)

        return parser

    def run_from_argv(
        self,
        argv: list[str],
    ) -> None:
        """Execute the command using the provided arguments.

        The options and commandline arguments will be parsed
        from ``argv`` and the commands ``main`` method will
        be called.

        Args:
            argv (list of str):
                A list of command line arguments
        """
        parser = self.create_arg_parser(argv)
        self.options = parser.parse_args(argv[2:])

        args = self.options.args

        # Check that the proper number of arguments have been provided.
        argspec = inspect.getfullargspec(self.main)
        minargs = len(argspec.args) - 1
        maxargs: Optional[int] = minargs

        # Arguments that have a default value are considered optional.
        if argspec.defaults is not None:
            minargs -= len(argspec.defaults)

        if argspec.varargs is not None:
            maxargs = None

        if len(args) < minargs or (maxargs is not None and
                                   len(args) > maxargs):
            parser.error('Invalid number of arguments provided')

            sys.exit(1)

        try:
            self._init_logging()
            logging.debug('Command line: %s', subprocess.list2cmdline(argv))

            try:
                self.initialize()
            except NeedsReinitialize:
                # This happens when we find a matching path in the TREES
                # config. That gets merged into self.config, but then we need
                # to rerun argument parsing and initialization so that we can
                # incorporate those settings.
                parser = self.create_arg_parser(argv)
                self.options = parser.parse_args(argv[2:])

                self.server_url = None
                self.api_client = None
                self.api_root = None
                self.capabilities = None
                self.repository_info = None
                self.tool = None

                self.initialize()

            exit_code = self.main(*args) or 0
        except CommandError as e:
            if isinstance(e, ParseError):
                parser.error(str(e))
            elif self.options.debug:
                raise

            logging.error(e)
            self.json.add_error(str(e))
            exit_code = 1
        except CommandExit as e:
            exit_code = e.exit_code
        except Exception as e:
            # If debugging is on, we'll let python spit out the
            # stack trace and report the exception, otherwise
            # we'll suppress the trace and print the exception
            # manually.
            if self.options.debug:
                raise

            self.json.add_error(f'Internal error: {type(e).__name__}: {e}')
            logging.critical(e)
            exit_code = 1

        cleanup_tempfiles()

        if self.options.json_output:
            if 'errors' in self.json.raw:
                self.json.add('status', 'failed')
            else:
                self.json.add('status', 'success')

            self.json.print_to_stream()

        sys.exit(exit_code)

    def initialize_scm_tool(
        self,
        client_name: Optional[str] = None,
        *,
        tool_required: bool = True,
    ) -> tuple[Optional[RepositoryInfo], Optional[BaseSCMClient]]:
        """Initialize the SCM tool for the current working directory.

        Version Changed:
            5.0.3:
            Added the ``tool_required`` argument.

        Version Changed:
            5.0:
            Removed deprecated ``require_repository_info`` argument.

        Args:
            client_name (str, optional):
                A specific client name, which can come from the configuration.
                This can be used to disambiguate if there are nested
                repositories, or to speed up detection.

            tool_required (bool, optional):
                Whether a tool is required to be found or not.

                Version Added:
                    5.0.3

        Returns:
            tuple:
            A 2-tuple:

            Tuple:
                0 (rbtools.clients.base.repository.RepositoryInfo):
                    The repository information.

                1 (rbtools.clients.base.scmclient.BaseSCMClient):
                    The SCMTool client instance.
        """
        repository_info, tool = scan_usable_client(
            self.config,
            self.options,
            client_name=client_name)

        if tool is None and not tool_required:
            return repository_info, None

        try:
            tool.check_options()
        except OptionsCheckError as e:
            raise CommandError(str(e))

        if self.needs_diffs:
            try:
                tool.get_diff_tool()
            except MissingDiffToolError as e:
                raise CommandError(str(e))

        return repository_info, tool

    def credentials_prompt(
        self,
        realm: str,
        uri: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        *args,
        **kwargs,
    ) -> tuple[str, str]:
        """Prompt the user for credentials using the command line.

        This will prompt the user, and then return the provided
        username and password. This is used as a callback in the
        API when the user requires authorization.

        Args:
            realm (str):
                The HTTP realm.

            uri (str):
                The URI of the endpoint requiring authentication.

            username (str, optional):
                The default username for authentication.

            password (str, optional):
                The default password for authentication.

            *args (tuple, unused):
                Unused additional positional arguments.

            **kwargs (dict, unused):
                Unused additional keyword arguments.

        Returns:
            tuple:
            A 2-tuple of:

            Tuple:
                username (str):
                    The user-provided username.

                password (str):
                    The user-provided password.

        Raises:
            rbtools.commands.base.errors.CommandError:
                HTTP authentication failed.
        """
        # TODO: Consolidate the logic in this function with
        #       get_authenticated_session() in rbtools/utils/users.py.

        if username is None or password is None:
            if getattr(self.options, 'diff_filename', None) == '-':
                raise CommandError('HTTP authentication is required, but '
                                   'cannot be used with --diff-filename=-')

            # Interactive prompts don't work correctly when input doesn't come
            # from a terminal. This could seem to be a rare case not worth
            # worrying about, but this is what happens when using native
            # Python in Cygwin terminal emulator under Windows and it's very
            # puzzling to the users, especially because stderr is also _not_
            # flushed automatically in this case, so the program just appears
            # to hang.
            if not self.stdin_is_atty:
                message_parts = [
                    'Authentication is required but RBTools cannot prompt for '
                    'it.',
                ]

                if sys.platform == 'win32':
                    message_parts.append(
                        'This can occur if you are piping input into the '
                        'command, or if you are running in a Cygwin terminal '
                        'emulator and not using Cygwin Python.'
                    )
                else:
                    message_parts.append(
                        'This can occur if you are piping input into the '
                        'command.'
                    )

                message_parts.append(
                    'You may need to explicitly provide API credentials when '
                    'invoking the command, or try logging in separately.'
                )

                raise CommandError(' '.join(message_parts))

            self.stdout.new_line()
            self.stdout.write('Please log in to the Review Board server at '
                              '%s.'
                              % urlparse(uri)[1])

            if username is None:
                username = get_input('Username: ')

            if password is None:
                password = get_pass('Password: ')

        return username, password

    def otp_token_prompt(
        self,
        uri: str,
        token_method: str,
        *args,
        **kwargs,
    ) -> str:
        """Prompt the user for a one-time password token.

        Their account is configured with two-factor authentication. The
        server will have sent a token to their configured mobile device
        or application. The user will be prompted for this token.

        Args:
            uri (str):
                The URI of the endpoint requiring authentication.

            token_method (str):
                The token method requested.

            *args (tuple, unused):
                Unused positional arguments.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            str:
            The user-provided token.
        """
        if getattr(self.options, 'diff_filename', None) == '-':
            raise CommandError('A two-factor authentication token is '
                               'required, but cannot be used with '
                               '--diff-filename=-')

        self.stdout.new_line()
        self.stdout.write('Please enter your two-factor authentication '
                          'token for Review Board.')

        if token_method == 'sms':
            self.stdout.write('You should be getting a text message with '
                              'an authentication token.')
            self.stdout.write('Enter the token below.')
        elif token_method == 'call':
            self.stdout.write('You should be getting an automated phone '
                              'call with an authentication token.')
            self.stdout.write('Enter the token below.')
        elif token_method == 'generator':
            self.stdout.write('Enter the token shown on your token '
                              'generator app below.')

        self.stdout.new_line()

        return get_pass('Token: ', require=True)

    def _make_api_client(
        self,
        server_url: str,
    ) -> RBClient:
        """Return an RBClient object for the server.

        The RBClient will be instantiated with the proper arguments
        for talking to the provided Review Board server url.

        Args:
            server_url (str):
                The URL to the Review Board server.

        Returns:
            rbtools.api.client.RBClient:
            The new API client.
        """
        options = self.options

        return RBClient(
            server_url,
            username=options.username,
            password=options.password,
            api_token=options.api_token,
            auth_callback=self.credentials_prompt,
            otp_token_callback=self.otp_token_prompt,
            disable_proxy=not options.enable_proxy,
            verify_ssl=not options.disable_ssl_verification,
            allow_caching=not options.disable_cache,
            cache_location=options.cache_location,
            in_memory_cache=options.in_memory_cache,
            save_cookies=options.save_cookies,
            ext_auth_cookies=options.ext_auth_cookies,
            ca_certs=options.ca_certs,
            client_key=options.client_key,
            client_cert=options.client_cert,
            proxy_authorization=options.proxy_authorization,
            transport_cls=self.transport_cls,
            config=self.config)

    def get_api(
        self,
        server_url: str,
    ) -> tuple[RBClient, RootResource]:
        """Return an RBClient instance and the associated root resource.

        Commands should use this method to gain access to the API,
        instead of instantianting their own client.

        Args:
            server_url (str):
                The URL to the Review Board server.

        Returns:
            tuple:
            A 2-tuple of:

            Tuple:
                0 (rbtools.api.client.RBClient):
                    The new API client.

                1 (rbtools.api.resource.RootResource):
                    The root resource for the API.
        """
        if not urlparse(server_url).scheme:
            server_url = f'http://{server_url}'

        api_client = self._make_api_client(server_url)
        api_root = None

        try:
            api_root = api_client.get_root()
        except ServerInterfaceError as e:
            raise CommandError(
                f'Could not reach the Review Board server at '
                f'{server_url}: {e}')
        except APIError as e:
            if e.http_status != HTTPStatus.NOT_FOUND:
                raise CommandError('Unexpected API Error: %s' % e)

        # If we either couldn't find an API endpoint or its contents don't
        # appear to be from Review Board, we should provide helpful
        # instructions to the user.
        if api_root is None or not hasattr(api_root, 'get_review_requests'):
            if server_url.rstrip('/') == 'https://rbcommons.com':
                raise CommandError(
                    'RBTools must be configured to point to your RBCommons '
                    'team account. For example: '
                    'https://rbcommons.com/s/<myteam>/')
            elif server_url.startswith('https://rbcommons.com/s/'):
                raise CommandError(
                    'Your configured RBCommons team account could not be '
                    'found. Make sure the team name is correct and the team '
                    'is still active.')
            else:
                raise CommandError(
                    'The configured Review Board server URL (%s) does not '
                    'appear to be correct.'
                    % server_url)

        return api_client, api_root

    def get_capabilities(
        self,
        api_root: RootResource,
    ) -> Capabilities:
        """Retrieve capabilities from the server and return them.

        Args:
            api_root (rbtools.api.resource.RootResource):
                The root resource

        Returns:
            rbtools.api.capabilities.Capabilities:
            The server capabilities.
        """
        if 'capabilities' in api_root:
            # Review Board 2.0+ provides capabilities in the root resource.
            return Capabilities(api_root.capabilities)

        info = api_root.get_info()

        if 'capabilities' in info:
            return Capabilities(info.capabilities)
        else:
            return Capabilities({})

    def main(self, *args) -> int:
        """Run the main logic of the command.

        This method should be overridden to implement the commands
        functionality.

        Args:
             *args (tuple):
                Positional arguments passed to the command.

        Returns:
            int:
            The resulting exit code.
        """
        raise NotImplementedError()

    def _init_logging(self) -> None:
        """Initialize logging for the command.

        This will set up different log handlers based on the formatting we want
        for the given levels.

        The INFO log handler will just show the text, like a print statement.

        WARNING and higher will show the level name as a prefix, in the form of
        "LEVEL: message".

        If debugging is enabled, a debug log handler will be set up showing
        debug messages in the form of ">>> message", making it easier to
        distinguish between debugging and other messages.
        """
        if self.stderr_is_atty:
            # We only use colorized logging when writing to TTYs, so we don't
            # bother initializing it then.
            colorama.init()

        # We use the stderr interface to be compliant with the default
        # behavior of StreamHandler (which will use sys.stderr if not
        # specified).
        log_stream = self.stderr.output_stream

        root = logging.getLogger()

        if self.options.debug:
            handler = logging.StreamHandler(log_stream)
            handler.setFormatter(self._create_formatter(
                'DEBUG', '{color}>>>{reset} %(message)s'))
            handler.setLevel(logging.DEBUG)
            handler.addFilter(LogLevelFilter(logging.DEBUG))
            root.addHandler(handler)

            root.setLevel(logging.DEBUG)
        else:
            root.setLevel(logging.INFO)

        # Handler for info messages. We'll treat these like prints.
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(self._create_formatter(
            'INFO', '{color}%(message)s{reset}'))

        handler.setLevel(logging.INFO)
        handler.addFilter(LogLevelFilter(logging.INFO))
        root.addHandler(handler)

        # Handlers for warnings, errors, and criticals. They'll show the
        # level prefix and the message.
        levels = (
            ('WARNING', logging.WARNING),
            ('ERROR', logging.ERROR),
            ('CRITICAL', logging.CRITICAL),
        )

        for level_name, level in levels:
            handler = logging.StreamHandler(log_stream)
            handler.setFormatter(self._create_formatter(
                level_name, '{color}%(levelname)s:{reset} %(message)s'))
            handler.addFilter(LogLevelFilter(level))
            handler.setLevel(level)
            root.addHandler(handler)

        logging.debug('RBTools %s', get_version_string())
        logging.debug('Python %s', sys.version)
        logging.debug('Running on %s', platform.platform())
        logging.debug('Home = %s', get_home_path())
        logging.debug('Current directory = %s', os.getcwd())

    def _init_server_url(self) -> str:
        """Initialize the server URL.

        This will discover the URL to the Review Board server (if possible),
        and store it in :py:attr:`server_url`.

        Returns:
            str:
            The Review Board server URL.

        Raises:
            rbtools.commands.base.errors.CommandError:
                The Review Board server could not be detected.
        """
        # First use anything directly provided on the command line or in the
        # config file. This may be None or empty.
        server_url = self.options.server

        # Now try to use the SCM to discover the server name. Several SCMs have
        # ways for the administrator to configure the Review Board server in
        # the SCM metadata.
        if not server_url:
            if self.repository_info is None or self.tool is None:
                self.repository_info, self.tool = self.initialize_scm_tool(
                    client_name=getattr(self.options, 'repository_type', None))

            server_url = self.tool.scan_for_server(self.repository_info)

        if not server_url:
            raise CommandError('Unable to find a Review Board server for this '
                               'source code tree.')

        return server_url

    def _get_text_type(
        self,
        markdown: bool,
    ) -> str:
        """Return the appropriate text type for a field.

        Args:
            markdown (bool):
                Whether the field should be interpreted as Markdown-formatted
                text.

        Returns:
            str:
            The text type value to set for the field.
        """
        assert self.capabilities

        if markdown and self.capabilities.has_capability('text', 'markdown'):
            return 'markdown'
        else:
            return 'plain'


class BaseSubCommand(BaseCommand):
    """Abstract base class for a subcommand."""

    #: The subcommand's help text.
    #:
    #: Type:
    #:     str
    help_text: str = ''

    def __init__(
        self,
        options: argparse.Namespace,
        config: RBToolsConfig,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the subcommand.

        Args:
            options (argparse.Namespace):
                The parsed options.

            config (rbtools.config.RBToolsConfigg):
                The loaded RBTools configuration.

            *args (list):
                Positional arguments to pass to the Command class.

            **kwargs (dict):
                Keyword arguments to pass to the Command class.
        """
        super().__init__(*args, **kwargs)
        self.options = options
        self.config = config


class BaseMultiCommand(BaseCommand):
    """Abstract base class for commands which offer subcommands.

    Some commands (such as :command:`rbt review`) want to offer many
    subcommands.

    Version Added:
        3.0
    """

    #: The available subcommands.
    #:
    #: This is a list of BaseSubCommand subclasses.
    #:
    #: Type:
    #:     list
    subcommands: list[type[BaseSubCommand]] = []

    #: Options common to all subcommands.
    #:
    #: Type:
    #:     list
    common_subcommand_option_list: list[Union[Option, OptionGroup]] = []

    ######################
    # Instance variables #
    ######################

    #: The currently-running subcommand.
    subcommand: BaseSubCommand

    #: A mapping of subcommand names to argument parsers.
    subcommand_parsers: dict[str, argparse.ArgumentParser]

    def usage(
        self,
        command_cls: Optional[type[BaseSubCommand]] = None,
    ) -> str:
        """Return a usage string for the command.

        Args:
            command_cls (type, optional):
                The subcommand class to generate usage information for.

        Returns:
            str:
            The usage string.
        """
        if command_cls is None:
            subcommand = ' <subcommand>'
            description = self.description
        else:
            subcommand = ''
            description = command_cls.description

        usage = f'%(prog)s{subcommand} [options] {self.args}'

        if description:
            return f'{usage}\n\n{description}'
        else:
            return usage

    def create_parser(
        self,
        config: RBToolsConfig,
        argv: Optional[list[str]] = None,
    ) -> argparse.ArgumentParser:
        """Create and return the argument parser for this command.

        Args:
            config (dict):
                The loaded RBTools config.

            argv (list, optional):
                The argument list.

        Returns:
            argparse.ArgumentParser:
            The argument parser.
        """
        if argv is None:
            argv = []

        subcommand_parsers: dict[str, argparse.ArgumentParser] = {}

        prog = f'{RB_MAIN} {self.name}'

        # Set up a parent parser containing the options that will be shared.
        #
        # Ideally the globals would also be available to the main command,
        # but it ends up leading to arguments on the main command overruling
        # those on the subcommand, which is a problem for --json. For now,
        # we are only sharing on the subcommands.
        common_parser = argparse.ArgumentParser(add_help=False)

        for option in self.common_subcommand_option_list:
            option.add_to(common_parser, config, argv)

        for option in self._global_options:
            option.add_to(common_parser, config, argv)

        # Set up the parser for the main command.
        parser = argparse.ArgumentParser(
            prog=prog,
            usage=self.usage(),
            formatter_class=SmartHelpFormatter)

        for option in self.option_list:
            option.add_to(parser, config, argv)

        # Set up the parsers for each subcommand.
        subparsers = parser.add_subparsers(
            description=(
                'To get additional help for these commands, run: '
                '%s <subcommand> --help' % prog))

        for command_cls in self.subcommands:
            subcommand_name = command_cls.name

            subparser = subparsers.add_parser(
                subcommand_name,
                usage=self.usage(command_cls),
                formatter_class=SmartHelpFormatter,
                prog=f'{parser.prog} {subcommand_name}',
                description=command_cls.description,
                help=command_cls.help_text,
                parents=[common_parser])

            for option in command_cls.option_list:
                option.add_to(subparser, config, argv)

            subparser.set_defaults(command_cls=command_cls)
            subcommand_parsers[subcommand_name] = subparser

        self.subcommand_parsers = subcommand_parsers

        return parser

    def initialize(self) -> None:
        """Initialize the command."""
        super().initialize()

        command = self.options.command_cls(options=self.options,
                                           config=self.config,
                                           transport_cls=self.transport_cls)
        command.stdout = self.stdout
        command.stderr = self.stderr
        command.json = self.json
        command.initialize()
        self.subcommand = command

    def main(self, *args) -> int:
        """Run the command.

        Args:
             *args (tuple):
                Positional arguments passed to the command.

        Returns:
            int:
            The resulting exit code.
        """
        return self.subcommand.main(*args)
