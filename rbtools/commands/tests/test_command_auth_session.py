"""Unit tests for session authentication in commands.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import kgb

from rbtools.api.errors import AuthorizationError
from rbtools.commands.base.commands import BaseCommand
from rbtools.testing import CommandTestsMixin, TestCase
from rbtools.testing.api.transport import URLMapTransport
from rbtools.utils.users import credentials_prompt, get_authenticated_session
from rbtools.utils.web_login import (WebLoginManager,
                                     WebLoginNotAllowed,
                                     attempt_web_login)

if TYPE_CHECKING:
    from typing import Any


class GetAuthSessionCommand(BaseCommand):
    """Command that gets an authenticated session.

    This mimics the types of commands that call :py:func`~rbtools.utils.
    users.get_authenticated_session` before making any API requests, which
    will authenticate the command caller using the logic in that function
    instead of going through our HTTP auth handlers.

    Version Added:
        6.0
    """

    needs_api = True

    option_list = [
        BaseCommand.server_options,
    ]

    def main(self, *args) -> int:
        """Run the command.

        Args:
            *args (tuple):
                Positional arguments for the command.

        Returns:
            int:
            The return code for the process.
        """
        api_client = self.api_client
        api_root = self.api_root
        assert api_client is not None
        assert api_root is not None

        get_authenticated_session(
            api_client=api_client,
            api_root=api_root,
            auth_required=True)

        return 0


class GetAuthSessionCommandTests(CommandTestsMixin[GetAuthSessionCommand],
                                 TestCase):
    """Tests for commands that get an authenticated session.

    Version Added:
        6.0
    """

    command_cls = GetAuthSessionCommand

    def test_default(self) -> None:
        """Testing authenticating a command with the default settings"""
        self.spy_on(attempt_web_login)
        self.spy_on(credentials_prompt, op=kgb.SpyOpReturn(('user', 'pass')))

        self._run_command()

        self.assertSpyLastRaised(attempt_web_login, WebLoginNotAllowed)
        self.assertSpyCalled(credentials_prompt)

    def test_with_username(self) -> None:
        """Testing authenticating a command with a username and password
        passed
        """
        self.spy_on(URLMapTransport.handle_api_path,
                    owner=URLMapTransport)
        self.spy_on(credentials_prompt)

        self._run_command(
            [
                '--username',
                'user',
                '--password',
                'pass',
            ],
            authenticated_session=True)

        # In practice when passing a username to a command that calls
        # get_authenticated_session(), we'll perform this API request which
        # triggers our PresetHTTPAuthHandler. The handler prompts the user
        # for a password if one isn't provided, then attaches the Basic Auth
        # info to the request header.
        #
        # Since we're not using the SyncTransport that sets up auth handlers
        # in our unit tests, its sufficient to just check that we're making
        # this API request.
        #
        # If this test fails, we'll need to make sure that we're making
        # some sort of authenticated request in get_authenticated_session()
        # before we hit the web-login code.
        self.assertSpyCalledWith(
            URLMapTransport.handle_api_path.calls[1],
            f'{self.DEFAULT_SERVER_URL}api/session/?expand=user',
            'GET')

        self.assertSpyNotCalled(credentials_prompt)

    def test_with_api_token(self) -> None:
        """Testing authenticating a command with an API token passed"""
        self.spy_on(attempt_web_login)
        self.spy_on(credentials_prompt)

        self.spy_on(URLMapTransport.handle_api_path,
                    owner=URLMapTransport)

        self._run_command(['--api-token', 'token'],
                          authenticated_session=True)

        # In practice when passing an api token to a command that calls
        # get_authenticated_session(), we'll perform this API request which
        # triggers our PresetHTTPAuthHandler. The handler then attaches the
        # Basic Auth info to the request header.
        #
        # Since we're not using the SyncTransport that sets up auth handlers
        # in our unit tests, its sufficient to just check that we're making
        # this API request.
        #
        # If this test fails, we'll need to make sure that we're making
        # some sort of authenticated request in get_authenticated_session()
        # before we hit the web-login code.
        self.assertSpyCalledWith(
            URLMapTransport.handle_api_path.calls[1],
            f'{self.DEFAULT_SERVER_URL}api/session/?expand=user',
            'GET')

        self.assertSpyNotCalled(credentials_prompt)

    def test_with_username_and_web_login(self) -> None:
        """Testing authenticating a command with a username and password
        passed, and web login passed
        """
        self.spy_on(URLMapTransport.handle_api_path,
                    owner=URLMapTransport)
        self.spy_on(attempt_web_login)

        self._run_command(
            [
                '--username',
                'user',
                '--password',
                'pass',
                '--web-login',
            ],
            authenticated_session=True)

        # In practice when passing a username to a command that calls
        # get_authenticated_session(), we'll perform this API request which
        # triggers our PresetHTTPAuthHandler. The handler prompts the user
        # for a password if one isn't provided, then attaches the Basic Auth
        # info to the request header.
        #
        # Since we're not using the SyncTransport that sets up auth handlers
        # in our unit tests, its sufficient to just check that we're making
        # this API request.
        #
        # If this test fails, we'll need to make sure that we're making
        # some sort of authenticated request in get_authenticated_session()
        # before we hit the web-login code.
        self.assertSpyCalledWith(
            URLMapTransport.handle_api_path.calls[1],
            f'{self.DEFAULT_SERVER_URL}api/session/?expand=user',
            'GET')

        self.assertSpyNotCalled(attempt_web_login)

    def test_with_web_login_option(self) -> None:
        """Testing authenticating a command with the web login option passed"""
        self.spy_on(WebLoginManager.wait_login_result,
                    owner=WebLoginManager,
                    op=kgb.SpyOpReturn(True))
        self.spy_on(credentials_prompt)

        self._run_command(command_args=['--web-login'])

        self.assertSpyCalled(WebLoginManager.wait_login_result)
        self.assertSpyNotCalled(credentials_prompt)

    def test_with_web_login_config(self) -> None:
        """Testing authenticating a command with the web login set in
        .reviewboardrc
        """
        self.spy_on(WebLoginManager.wait_login_result,
                    owner=WebLoginManager,
                    op=kgb.SpyOpReturn(True))
        self.spy_on(credentials_prompt)

        config: dict[str, Any] = {
            'WEB_LOGIN': True,
        }

        with self.reviewboardrc(config):
            self._run_command()

        self.assertSpyCalled(WebLoginManager.wait_login_result)
        self.assertSpyNotCalled(credentials_prompt)

    def test_with_web_login_not_enabled(self) -> None:
        """Testing authenticating a command with the web login option passed
        but web login not available on the server
        """
        self.spy_on(attempt_web_login)
        self.spy_on(credentials_prompt, op=kgb.SpyOpReturn(('user', 'pass')))

        self._run_command(command_args=['--web-login'],
                          web_login_capability_enabled=False)

        self.assertSpyLastRaised(attempt_web_login, WebLoginNotAllowed)

        # Fall back on username and password.
        self.assertSpyCalled(credentials_prompt)

    def test_with_web_login_failed(self) -> None:
        """Testing authenticating a command with the web login option passed
        but web login failed
        """
        self.spy_on(WebLoginManager.wait_login_result,
                    owner=WebLoginManager,
                    op=kgb.SpyOpReturn(False))
        self.spy_on(credentials_prompt)

        with self.assertRaises(AuthorizationError):
            # Pass --debug so that the AuthorizationError in
            # get_authenticated_session bubbles up instead of getting
            # caught so that we can easily test for it.
            self._run_command(command_args=['--web-login', '--debug'],)

        self.assertSpyCalled(WebLoginManager.wait_login_result)
        self.assertSpyNotCalled(credentials_prompt)

    def _run_command(
        self,
        command_args: (list[str] | None) = None,
        web_login_capability_enabled: bool = True,
        review_board_version: str = '5.3.0',
        authenticated_session: bool = False,
    ) -> None:
        """Run the command.

        This sets various things on the transport used in the tests.

        Args:
            command_args (list of str, optional):
                Arguments to pass to the command.

            web_login_capability_enabled (bool, optional):
                Whether the web login capability should be enabled on
                the server.

            review_board_version (str, optional):
                The Review Board version to set on the server.

            authenticated_session (bool, optional):
                Whether the session API URL should return an authenticated
                session.

        Raises:
            AssertionError:
                An expectation failed.
        """
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            transport.add_root_url(package_version=review_board_version)
            transport.add_session_url(authenticated=authenticated_session)

            transport.capabilities['authentication'] = {
                'client_web_login': web_login_capability_enabled,
            }

        self.spy_on(WebLoginManager.start_web_login_server,
                    owner=WebLoginManager,
                    call_original=False)

        if not command_args:
            command_args = []

        self.run_command(
            args=command_args,
            setup_transport_func=setup_transport)
