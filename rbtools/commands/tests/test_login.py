"""Unit tests for RBTools login command.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import kgb

from rbtools.api.client import RBClient
from rbtools.commands.login import Login
from rbtools.testing import CommandTestsMixin, TestCase

if TYPE_CHECKING:
    from rbtools.testing.api.transport import URLMapTransport


class LoginCommandTests(CommandTestsMixin[Login], TestCase):
    """Tests for rbt login.

    Version Added:
        6.0
    """

    command_cls = Login

    def test_login_with_no_session_cookie(self) -> None:
        """Testing login with no previous session cookie prints a success
        message
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(False))

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=True),
            )

        self.assertEqual(
            ctx.output[0],
            'INFO:root:Successfully logged in to Review Board.')

    def test_login_with_session_cookie(self) -> None:
        """Testing login with a previous session cookie prints an already
        logged in message
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(True))

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=True),
            )

        self.assertEqual(
            ctx.output[0],
            'INFO:root:You are already logged in to Review Board at '
            'reviews.example.com')

    def test_login_with_user_pass_and_no_session_cookie(self) -> None:
        """Testing login with a username and password and no previous session
        cookie prints a success message
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(False))

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                args=[
                    '--username', 'user',
                    '--password', 'pass',
                ],
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=True),
            )

        self.assertEqual(
            ctx.output[0],
            'INFO:root:Successfully logged in to Review Board.')

    def test_login_with_user_pass_and_session_cookie(self) -> None:
        """Testing login with a username and password and a previous session
        cookie prints a success message
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(True))

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                args=[
                    '--username', 'user',
                    '--password', 'pass',
                ],
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=True),
            )

        self.assertEqual(
            ctx.output[0],
            'INFO:root:Successfully logged in to Review Board.')

    def test_login_with_api_token_and_no_session_cookie(self) -> None:
        """Testing login with an api token and no previous session cookie
        prints a success message
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(False))

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                args=[
                    '--api-token', 'token',
                ],
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=True),
            )

        self.assertEqual(
            ctx.output[0],
            'INFO:root:Successfully logged in to Review Board.')

    def test_login_with_api_token_and_session_cookie(self) -> None:
        """Testing login with an api token and a previous session cookie
        prints a success message
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(True))

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                args=[
                    '--api-token', 'token',
                ],
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=True),
            )

        self.assertEqual(
            ctx.output[0],
            'INFO:root:Successfully logged in to Review Board.')

    def _setup_transport(
        self,
        transport: URLMapTransport,
        authenticated_session: bool,
    ) -> None:
        """Setup the transport.

        Args:
            transport (rbtools.api.transport.Transport:):
                Arguments to pass to the command.

            authenticated_session (bool, optional):
                Whether the session API URL should return an authenticated
                session.

        Raises:
            AssertionError:
                An expectation failed.
        """
        transport.add_root_url(package_version='7.1')
        transport.add_session_url(authenticated=authenticated_session)
