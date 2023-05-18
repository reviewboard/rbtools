"""Command unit testing support.

Version Added:
    3.1
"""

import io

import kgb

from rbtools.clients import scan_usable_client
from rbtools.testing.api.transport import URLMapTransport
from rbtools.utils.filesystem import cleanup_tempfiles


class CommandTestsMixin(kgb.SpyAgency):
    """Mixin for unit tests for commands.

    This provides utility commands for creating and running commands in a
    controlled environment, allowing API URLs to be created and output and
    exit codes to be captured.

    Version Added:
        3.1
    """

    #: The command class being tested.
    #:
    #: This must be a subclass of :py:class:`rbtools.commands.Command`.
    #:
    #: Type:
    #:     type
    command_cls = None

    needs_temp_home = True

    DEFAULT_SERVER_URL = 'https://reviews.example.com/'

    def create_command(self, args=[], server_url=DEFAULT_SERVER_URL,
                       initialize=False, **kwargs):
        """Create an argument parser with the given extra fields.

        Args:
            args (list of unicode, optional):
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

            server_url (unicode, optional):
                The URL to use as the Review Board URL.

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
        command = self._create_command_common(args=args, **kwargs)

        argv = self._build_command_argv(args=args,
                                        server_url=server_url)

        parser = command.create_arg_parser(argv)
        command.options = parser.parse_args(argv[2:])

        if initialize:
            command.initialize()

        return command

    def run_command(self, args=[], server_url=DEFAULT_SERVER_URL,
                    **kwargs):
        """Run a command class and return results.

        Args:
            args (list of unicode, optional):
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

            server_url (unicode, optional):
                The URL to use as the Review Board URL.

            stdin (io.BytesIO, optional):
                A stream used to provide standard input.

            setup_transport_func (callable, optional):
                A callback to call in order to set up transport URLs.

                This must take a ``transport`` argument.

        Returns:
            dict:
            A dictionary of results, containing:

            Keys:
                command (rbtools.commands.Command):
                    The command instance.

                exit_code (int):
                    The exit code.

                stderr (bytes):
                    The standard error output.

                stdout (bytes):
                    The standard output.
        """
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

        try:
            command.run_from_argv(argv)
        except SystemExit as e:
            exit_code = e.code

        cleanup_tempfiles.unspy()

        command.stdout.output_stream.flush()
        command.stderr.output_stream.flush()

        return {
            'command': command,
            'exit_code': exit_code,
            'stderr': stderr.getvalue(),
            'stdout': stdout.getvalue(),
        }

    def _create_command_common(self, args=[], repository_info=None, tool=None,
                               scan=False, stdout=None, stderr=None,
                               stdin=None, setup_transport_func=None):
        """Common code to create a command instance.

        Args:
            args (list of unicode, optional):
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
        assert (repository_info is not None) == (tool is not None), (
            'repository_info and tool must either both be set or both be '
            'None.'
        )

        command_kwargs = {
            _name: io.TextIOWrapper(_stream)
            for _name, _stream in (('stdout', stdout),
                                   ('stderr', stderr),
                                   ('stdin', stdin))
            if _stream is not None
        }

        command = self.command_cls(transport_cls=URLMapTransport,
                                   **command_kwargs)

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

    def _build_command_argv(self, args, server_url=None):
        """Return a command line argument list.

        Args:
            args (list of unicode):
                Arguments to append to the command.

            server_url (unicode, optional):
                The server URL to pass in the argument list, if the command
                requires the API.

        Returns:
            list of unicode:
            The command line arguments.
        """
        argv = ['rbt', self.command_cls.name]

        if server_url and self.command_cls.needs_api:
            argv += ['--server', server_url]

        if args:
            argv += args

        return argv
