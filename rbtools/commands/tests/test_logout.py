"""Unit tests for RBTools logout command.

Version Added:
    6.0
"""

from __future__ import annotations

import kgb

from rbtools.api.client import RBClient
from rbtools.commands.logout import Logout
from rbtools.testing import CommandTestsMixin, TestCase
from rbtools.testing.api.transport import URLMapTransport


class LogoutCommandTests(CommandTestsMixin[Logout], TestCase):
    """Tests for rbt logout.

    Version Added:
        6.0
    """

    command_cls = Logout

    def test_logout_with_no_session_cookie(self) -> None:
        """Testing logout with no previous session cookie does not hit the
        API
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(False))
        self.spy_on(URLMapTransport.handle_api_path,
                    owner=URLMapTransport)

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=True),
            )

        self.assertSpyNotCalled(URLMapTransport.handle_api_path)
        self.assertEqual(
            ctx.output[0],
            'INFO:rb.logout:You are already logged out of Review Board at '
            'reviews.example.com')

    def test_logout_with_session_cookie_and_authed_session(self) -> None:
        """Testing logout with a previous session cookie and an authed
        session logs out
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(True))
        self.spy_on(RBClient.logout,
                    owner=RBClient,
                    call_original=False)

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=True),
            )

        self.assertSpyCalled(RBClient.logout)
        self.assertEqual(
            ctx.output[0],
            'INFO:rb.logout:You are now logged out of Review Board at '
            'reviews.example.com')

    def test_logout_with_session_cookie_and_no_authed_session(self) -> None:
        """Testing logout with a previous session cookie and no authed
        session print an already logged out message
        """
        self.spy_on(RBClient.has_session_cookie,
                    owner=RBClient,
                    op=kgb.SpyOpReturn(True))
        self.spy_on(RBClient.logout,
                    owner=RBClient,
                    call_original=False)

        with self.assertLogs(level='INFO') as ctx:
            self.run_command(
                setup_transport_func=lambda t: self._setup_transport(
                    t, authenticated_session=False),
            )

        self.assertSpyNotCalled(RBClient.logout)
        self.assertEqual(
            ctx.output[0],
            'INFO:rb.logout:You are already logged out of Review Board at '
            'reviews.example.com')

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
