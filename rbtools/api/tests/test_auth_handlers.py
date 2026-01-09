"""Unit tests for HTTP auth handlers.

Version Added:
    6.0
"""

from __future__ import annotations

import base64
from http.client import HTTPMessage
from urllib.request import build_opener

import kgb

from rbtools.api.request import (PresetHTTPAuthHandler,
                                 Request,
                                 ReviewBoardHTTPBasicAuthHandler,
                                 ReviewBoardHTTPPasswordMgr,
                                 ReviewBoardWebLoginHandler)
from rbtools.commands.base import BaseCommand
from rbtools.testing import CommandTestsMixin, TestCase
from rbtools.utils.web_login import WebLoginNotAllowed


class _TestCommand(BaseCommand):
    """Testing command.

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
        return 0


class PresetHTTPAuthHandlerTests(CommandTestsMixin[_TestCommand], TestCase):
    """Unit tests for PresetHTTPAuthHandler.

    Version Added:
        6.0
    """

    command_cls = _TestCommand

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

        server_url = self.TEST_SERVER_URL
        command = self.create_command()
        self.command = command
        password_manager = ReviewBoardHTTPPasswordMgr(
            reviewboard_url=server_url,
            auth_callback=command.credentials_prompt,
            otp_token_callback=command.otp_token_prompt,
            web_login_callback=command.web_login_callback)
        handler = PresetHTTPAuthHandler(url=self.TEST_SERVER_URL,
                                        password_mgr=password_manager)

        self.password_manager = password_manager
        self.handler = handler
        req_before = Request(url=f'{self.TEST_SERVER_URL}api')

        # timeout gets set in urllib when calling open() on the request.
        req_before.timeout = None
        self.req_before = req_before

    def test_api_token(self) -> None:
        """Testing PresetHTTPAuthHandler with API token"""
        handler = self.handler
        password_manager = self.password_manager
        password_manager.api_token = 'ABC123'

        req_after = handler.http_request(self.req_before)

        self.assertEqual(req_after.get_header('Authorization'), 'token ABC123')
        self.assertTrue(handler.used)

    def test_username_password(self) -> None:
        """Testing PresetHTTPAuthHandler with username and password"""
        handler = self.handler
        password_manager = self.password_manager
        password_manager.rb_user = 'user'
        password_manager.rb_pass = 'pass'

        req_after = handler.http_request(self.req_before)

        header = b'Basic %s' % base64.b64encode(b'user:pass').strip()

        self.assertEqual(req_after.get_header('Authorization'),
                         header.decode())
        self.assertTrue(handler.used)

    def test_username(self) -> None:
        """Testing PresetHTTPAuthHandler with username"""
        handler = self.handler
        password_manager = self.password_manager
        password_manager.rb_user = 'user'

        self.spy_on(password_manager.find_user_password,
                    op=kgb.SpyOpReturn(('user', 'pass')))

        req_after = handler.http_request(self.req_before)

        header = b'Basic %s' % base64.b64encode(b'user:pass').strip()

        self.assertEqual(req_after.get_header('Authorization'),
                         header.decode())
        self.assertTrue(handler.used)
        self.assertSpyCalled(password_manager.find_user_password)

    def test_used(self) -> None:
        """Testing PresetHTTPAuthHandler when already used"""
        handler = self.handler
        password_manager = self.password_manager
        password_manager.api_token = 'ABC123'
        handler.used = True

        req_after = handler.http_request(self.req_before)

        self.assertIsNone(req_after.get_header('Authorization'))


class ReviewBoardWebLoginHandlerTests(CommandTestsMixin[_TestCommand],
                                      TestCase):
    """Unit tests for ReviewBoardWebLoginHandler.

    Version Added:
        6.0
    """

    command_cls = _TestCommand

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

        server_url = self.TEST_SERVER_URL
        command = self.create_command()
        password_manager = ReviewBoardHTTPPasswordMgr(
            reviewboard_url=server_url,
            auth_callback=command.credentials_prompt,
            otp_token_callback=command.otp_token_prompt,
            web_login_callback=command.web_login_callback)
        handler = ReviewBoardWebLoginHandler(password_manager)
        build_opener(handler)

        self.command = command
        self.password_manager = password_manager
        self.handler = handler
        req_before = Request(url=f'{self.TEST_SERVER_URL}api')

        # timeout gets set in urllib when calling open() on the request.
        req_before.timeout = None
        self.req_before = req_before

    def test_default(self) -> None:
        """Testing ReviewBoardWebLoginHandler with default state"""
        command = self.command
        handler = self.handler

        self.spy_on(BaseCommand.web_login_callback,
                    owner=BaseCommand,
                    op=kgb.SpyOpReturn(True))
        self.spy_on(handler.parent.open, call_original=False)

        handler.http_error_401(
            self.req_before,
            fp=None,
            code=401,
            msg='Unauthorized',
            headers=HTTPMessage())

        self.assertSpyCalled(command.web_login_callback)
        self.assertTrue(handler.used)
        self.assertSpyCalled(handler.parent.open)

    def test_used(self) -> None:
        """Testing ReviewBoardWebLoginHandler when its been used"""
        command = self.command
        handler = self.handler
        handler.used = True

        self.spy_on(BaseCommand.web_login_callback,
                    owner=BaseCommand)
        self.spy_on(handler.parent.open)

        req_after = handler.http_error_401(
            self.req_before,
            fp=None,
            code=401,
            msg='Unauthorized',
            headers=HTTPMessage())

        self.assertSpyNotCalled(command.web_login_callback)
        self.assertSpyNotCalled(handler.parent.open)
        self.assertIsNone(req_after)

    def test_not_authenticated(self) -> None:
        """Testing ReviewBoardWebLoginHandler with a not authenticated state
        returned from the web login server
        """
        command = self.command
        handler = self.handler

        self.spy_on(BaseCommand.web_login_callback,
                    owner=BaseCommand,
                    op=kgb.SpyOpReturn(False))
        self.spy_on(handler.parent.open)

        req_after = handler.http_error_401(
            self.req_before,
            fp=None,
            code=401,
            msg='Unauthorized',
            headers=HTTPMessage())

        self.assertSpyCalled(command.web_login_callback)
        self.assertTrue(handler.used)
        self.assertSpyNotCalled(handler.parent.open)
        self.assertIsNone(req_after)

    def test_with_username(self) -> None:
        """Testing ReviewBoardWebLoginHandler with a username set on the
        password manager
        """
        command = self.command
        handler = self.handler
        password_manager = self.password_manager
        password_manager.rb_user = 'user'

        self.spy_on(BaseCommand.web_login_callback,
                    owner=BaseCommand)
        self.spy_on(handler.parent.open)

        req_after = handler.http_error_401(
            self.req_before,
            fp=None,
            code=401,
            msg='Unauthorized',
            headers=HTTPMessage())

        self.assertSpyNotCalled(command.web_login_callback)
        self.assertTrue(handler.used)
        self.assertSpyNotCalled(handler.parent.open)
        self.assertIsNone(req_after)

    def test_with_password(self) -> None:
        """Testing ReviewBoardWebLoginHandler with a password set on the
        password manager
        """
        command = self.command
        handler = self.handler
        password_manager = self.password_manager
        password_manager.rb_pass = 'password'

        self.spy_on(BaseCommand.web_login_callback,
                    owner=BaseCommand)
        self.spy_on(handler.parent.open)

        req_after = handler.http_error_401(
            self.req_before,
            fp=None,
            code=401,
            msg='Unauthorized',
            headers=HTTPMessage())

        self.assertSpyNotCalled(command.web_login_callback)
        self.assertTrue(handler.used)
        self.assertSpyNotCalled(handler.parent.open)
        self.assertIsNone(req_after)

    def test_with_api_token(self) -> None:
        """Testing ReviewBoardWebLoginHandler with an api token set on the
        password manager
        """
        command = self.command
        handler = self.handler
        password_manager = self.password_manager
        password_manager.api_token = 'ABC123'

        self.spy_on(BaseCommand.web_login_callback,
                    owner=BaseCommand)
        self.spy_on(handler.parent.open)

        req_after = handler.http_error_401(
            self.req_before,
            fp=None,
            code=401,
            msg='Unauthorized',
            headers=HTTPMessage())

        self.assertSpyNotCalled(command.web_login_callback)
        self.assertTrue(handler.used)
        self.assertSpyNotCalled(handler.parent.open)
        self.assertIsNone(req_after)

    def test_web_login_not_allowed(self) -> None:
        """Testing ReviewBoardWebLoginHandler with web login not allowed"""
        command = self.command
        handler = self.handler

        self.spy_on(BaseCommand.web_login_callback,
                    owner=BaseCommand,
                    op=kgb.SpyOpRaise(WebLoginNotAllowed))
        self.spy_on(handler.parent.open)

        req_after = handler.http_error_401(
            self.req_before,
            fp=None,
            code=401,
            msg='Unauthorized',
            headers=HTTPMessage())

        self.assertSpyCalled(command.web_login_callback)
        self.assertTrue(handler.used)
        self.assertSpyNotCalled(handler.parent.open)
        self.assertIsNone(req_after)


class ReviewBoardHTTPBasicAuthHandlerTests(CommandTestsMixin[_TestCommand],
                                           TestCase):
    """Unit tests for ReviewBoardHTTPBasicAuthHandler.

    Version Added:
        6.0
    """

    command_cls = _TestCommand

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

        server_url = self.TEST_SERVER_URL
        command = self.create_command()
        password_manager = ReviewBoardHTTPPasswordMgr(
            reviewboard_url=server_url,
            auth_callback=command.credentials_prompt,
            otp_token_callback=command.otp_token_prompt,
            web_login_callback=command.web_login_callback)
        handler = ReviewBoardHTTPBasicAuthHandler()
        handler.passwd = password_manager
        build_opener(handler)

        self.command = command
        self.password_manager = password_manager
        self.handler = handler
        req_before = Request(url=f'{self.TEST_SERVER_URL}api')

        # timeout gets set in urllib when calling open() on the request.
        req_before.timeout = None
        self.req_before = req_before

    def test_retry_with_username_password(self) -> None:
        """Testing retry_http_basic_auth with username and password"""
        password_manager = self.password_manager
        handler = self.handler
        req_before = self.req_before

        self.spy_on(handler.parent.open, call_original=False)
        self.spy_on(password_manager.find_user_password,
                    op=kgb.SpyOpReturn(('user', 'pass')))

        self.assertIsNone(req_before.get_header('Authorization'))

        self.handler.retry_http_basic_auth(
            host='reviews.example.com',
            request=req_before,
            realm='Web API')

        header = b'Basic %s' % base64.b64encode(b'user:pass').strip()

        self.assertEqual(req_before.get_header('Authorization'),
                         header.decode())
        self.assertSpyCalled(password_manager.find_user_password)

    def test_retry_with_username(self) -> None:
        """Testing retry_http_basic_auth with only username"""
        password_manager = self.password_manager
        handler = self.handler
        req_before = self.req_before

        self.spy_on(handler.parent.open, call_original=False)
        self.spy_on(password_manager.find_user_password,
                    op=kgb.SpyOpReturn(('user', None)))

        self.assertIsNone(req_before.get_header('Authorization'))

        rsp = self.handler.retry_http_basic_auth(
            host='reviews.example.com',
            request=req_before,
            realm='Web API')

        self.assertIsNone(req_before.get_header('Authorization'))
        self.assertSpyCalled(password_manager.find_user_password)
        self.assertSpyNotCalled(handler.parent.open)
        self.assertIsNone(rsp)

    def test_retry_with_api_token(self) -> None:
        """Testing retry_http_basic_auth with api token"""
        password_manager = self.password_manager
        handler = self.handler
        req_before = self.req_before

        password_manager.api_token = 'ABC123'

        self.spy_on(handler.parent.open)
        self.spy_on(password_manager.find_user_password)

        rsp = self.handler.retry_http_basic_auth(
            host='reviews.example.com',
            request=self.req_before,
            realm='Web API')

        self.assertSpyNotCalled(password_manager.find_user_password)
        self.assertSpyNotCalled(handler.parent.open)
        self.assertIsNone(rsp)
        self.assertIsNone(req_before.get_header('Authorization'))

    # TODO: Add tests for otp token login.
