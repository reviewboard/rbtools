"""Command unit testing support.

Version Added:
    3.1
"""

from __future__ import annotations

import io
from typing import (Any, Callable, Generic, Optional, TYPE_CHECKING, TypeVar,
                    Union)

import kgb
from housekeeping import deprecate_non_keyword_only_args
from typing_extensions import TypedDict

from rbtools.clients import scan_usable_client
from rbtools.commands.base import BaseCommand
from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.testing.api.transport import URLMapTransport
from rbtools.utils.filesystem import cleanup_tempfiles

if TYPE_CHECKING:
    from rbtools.api.transport import Transport
    from rbtools.clients.base.scmclient import BaseSCMClient
    from rbtools.clients.base.repository import RepositoryInfo


_CommandT = TypeVar('_CommandT', bound=BaseCommand)


class RunCommandResult(TypedDict, Generic[_CommandT]):
    """The result form a run_command operation.

    Version Added:
        5.0
    """

    #: The command instance that was executed.
    command: _CommandT

    #: The exit code of the command.
    exit_code: Optional[Union[int, str]]

    #: The JSON results of the command.
    json: dict[str, Any]

    #: Standard error output from the command.
    stderr: bytes

    #: Standard output from the command.
    stdout: bytes


class CommandTestsMixin(kgb.SpyAgency, Generic[_CommandT]):
    """Mixin for unit tests for commands.

    This provides utility commands for creating and running commands in a
    controlled environment, allowing API URLs to be created and output and
    exit codes to be captured.

    Subclasses must provide the type of the class as a generic to the mixin,
    and set :py:attr:`command_cls` appropriately.

    Version Changed:
        5.0:
        Added generic support for the mixin, to type command classes and
        instances.

    Version Added:
        3.1
    """

    #: The command class being tested.
    #:
    #: This must be a subclass of :py:class:`rbtools.commands.Command`.
    #:
    #: Type:
    #:     type
    command_cls: Optional[type[_CommandT]] = None

    needs_temp_home = True

    DEFAULT_SERVER_URL = 'https://reviews.example.com/'

    @deprecate_non_keyword_only_args(RemovedInRBTools70Warning)
    def create_command(
        self,
        *,
        args: Optional[list[str]] = None,
        server_url: str = DEFAULT_SERVER_URL,
        initialize: bool = False,
        **kwargs,
    ) -> _CommandT:
        """Create an argument parser with the given extra fields.

        Args:
            args (list of str, optional):
                A list of command line arguments to be passed to the parser.

                The command line will receive each item in the list.

            server_url (str, optional):
                The URL to use as the Review Board URL.

            initialize (bool, optional):
                Whether to initialize the command before returning.

            **kwargs (dict):
                Additional keyword arguments.

        Returns:
            rbtools.commands.base.commands.BaseCommand:
            The command instance.
        """
        if args is None:
            args = []

        command = self._create_command_common(args=args, **kwargs)

        argv = self._build_command_argv(args=args,
                                        server_url=server_url)

        parser = command.create_arg_parser(argv)
        command.options = parser.parse_args(argv[2:])

        if initialize:
            command.initialize()

        return command

    def run_command(
        self,
        args: Optional[list[str]] = None,
        server_url: str = DEFAULT_SERVER_URL,
        **kwargs,
    ) -> RunCommandResult[_CommandT]:
        """Run a command class and return results.

        Args:
            args (list of str, optional):
                A list of command line arguments to be passed to the parser.

                The command line will receive each item in the list.

            server_url (str, optional):
                The URL to use as the Review Board URL.

            **kwargs (dict):
                Additional keyword arguments.

        Returns:
            dict:
            A dictionary of results from the command execution. See
            :py:class:`RunCommandResult` for details.
        """
        if args is None:
            args = []

        stdout = io.BytesIO()
        stderr = io.BytesIO()

        command = self._create_command_common(stdout=stdout,
                                              stderr=stderr,
                                              **kwargs)

        argv = self._build_command_argv(args=args,
                                        server_url=server_url)

        # Avoid calling cleanup_tempfiles() during the run, or it might
        # interfere with the test.
        self.spy_on(cleanup_tempfiles, call_original=False)

        exit_code: Optional[Union[int, str]]

        try:
            command.run_from_argv(argv)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code
        finally:
            cleanup_tempfiles.unspy()

        if command.stdout.output_stream is not None:
            command.stdout.output_stream.flush()

        if command.stderr.output_stream is not None:
            command.stderr.output_stream.flush()

        return {
            'command': command,
            'exit_code': exit_code,
            'json': command.json.raw,
            'stderr': stderr.getvalue(),
            'stdout': stdout.getvalue(),
        }

    def _create_command_common(
        self,
        *,
        args: Optional[list[str]] = None,
        repository_info: Optional[RepositoryInfo] = None,
        tool: Optional[BaseSCMClient] = None,
        scan: bool = False,
        stdout: Optional[io.BytesIO] = None,
        stderr: Optional[io.BytesIO] = None,
        stdin: Optional[io.BytesIO] = None,
        setup_transport_func: Optional[Callable[[Transport], None]] = None,
    ) -> _CommandT:
        """Create a command instance.

        Args:
            args (list of str, optional):
                A list of command line arguments to be passed to the parser.

                The command line will receive each item in the list.

            repository_info (rbtools.clients.base.repository.RepositoryInfo):
                The repository information to set for the command.

                If being set, ``tool`` must also be set.

            tool (rbtools.clients.base.BaseSCMClient):
                The SCM client to set for the command.

                If being set, ``repository_info`` must also be set.

            scan (bool, optional):
                Whether to allow for repository scanning. If ``False``,
                and ``repository_info`` and ``tool`` aren't provided, then
                no repositories will be matched.

            stdout (io.BytesIO, optional):
                A stream used to capture standard output.

            stderr (io.BytesIO, optional):
                A stream used to capture standard error.

            stdin (io.BytesIO, optional):
                A stream used to provide standard input.

            setup_transport_func (callable, optional):
                A callback to call in order to set up transport URLs.

                This must take a ``transport`` argument.

            initialize (bool, optional):
                Whether to initialize the command before returning.

        Returns:
            rbtools.commands.Command:
            The command instance.
        """
        if args is None:
            args = []

        assert (repository_info is not None) == (tool is not None), (
            'repository_info and tool must either both be set or both be '
            'None.'
        )

        assert self.command_cls is not None

        command_kwargs = {
            _name: io.TextIOWrapper(_stream)
            for _name, _stream in (('stdout', stdout),
                                   ('stderr', stderr),
                                   ('stdin', stdin))
            if _stream is not None
        }

        command = self.command_cls(transport_cls=URLMapTransport,
                                   **command_kwargs)

        if hasattr(scan_usable_client, 'spy'):
            scan_usable_client.unspy()

        if repository_info or tool or not scan:
            self.spy_on(scan_usable_client,
                        op=kgb.SpyOpReturn((repository_info, tool)))

        if setup_transport_func:
            @self.spy_for(command._make_api_client)
            def _make_api_client(_self, *args, **kwargs):
                client = command._make_api_client.call_original(*args,
                                                                **kwargs)

                setup_transport_func(client._transport)

                return client

        return command

    def _build_command_argv(
        self,
        *,
        args: list[str],
        server_url: Optional[str] = None,
    ) -> list[str]:
        """Return a command line argument list.

        Args:
            args (list of str):
                Arguments to append to the command.

            server_url (str, optional):
                The server URL to pass in the argument list, if the command
                requires the API.

        Returns:
            list of str:
            The command line arguments.
        """
        assert self.command_cls is not None

        argv: list[str] = ['rbt', self.command_cls.name]

        if server_url and self.command_cls.needs_api:
            argv += ['--server', server_url]

        if args:
            argv += args

        return argv
