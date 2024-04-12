"""Unit tests for rbtools.utils.web_login_server.

Version Added:
    5.0
"""

from __future__ import annotations

import json
from io import BytesIO

import kgb

from rbtools.api.request import RBTOOLS_USER_AGENT
from rbtools.testing import TestCase
from rbtools.utils.web_login import WebLoginHandler

#: The host and port for the web login server to use for tests.
TEST_HOST_PORT = ('localhost', 8080)


class MockSocket:
    """A fake socket to use in unit tests.

    Version Added:
        5.0
    """
    def __init__(
        self,
        data: bytes,
    ) -> None:
        """Initialize the socket.

        Args:
            data (bytes):
                The request data to initialize the socket with. This is
                unused and is expected to be overwritten.
        """
        self._fileobj = BytesIO(data)
        self._buffer = b""
        self._closed = False

    def makefile(
        self,
        *args,
        **kwargs
    ) -> BytesIO:
        """Return the file object.

        Args:
            *args (tuple):
                Positional arguments.

            **kwargs (dict):
                Keyword arguments.

        Returns:
            BytesIO:
            The file object.
        """
        return self._fileobj

    def sendall(
        self,
        data: bytes,
    ) -> None:
        """Send data to the socket.

        Args:
            data (bytes):
                The data.
        """
        if not self._closed:
            self._buffer += data

    def recv(
        self,
        bufsize: int,
    ) -> bytes:
        """Receive data from the socket.

        Args:
            bufsize (int):
                The max amount of data to receive.

        Returns:
            bytes:
            The data received from the socket.
        """
        data = self._buffer[:bufsize]
        self._buffer = self._buffer[bufsize:]
        return data

    def close(self) -> None:
        """Close the socket."""
        self._closed = True


class MockServer:
    """A fake server to use in unit tests.

    Version Added:
        5.0
    """
    server_address = TEST_HOST_PORT

    def stop(self) -> None:
        """Mock method to stop the server."""
        pass


class WebLoginHandlerTests(kgb.SpyAgency, TestCase):
    """Unit tests for rbtools.utils.web_login_server.WebLoginHandler.

    Version Added:
        5.0
    """

    def setUp(self) -> None:
        """Set up the unit tests."""
        self.client = self.create_rbclient()

        client_socket = MockSocket(b'')
        self.handler = WebLoginHandler(client_socket,
                                       TEST_HOST_PORT,
                                       MockServer(),
                                       api_client=self.client,
                                       enable_logging=False,)
        super().setUp()

    def test_user_agent(self) -> None:
        """Testing WebLoginHandler with a custom user agent"""
        self.client.user_agent = 'Custom Agent'

        client_socket = MockSocket(b'')
        self.handler = WebLoginHandler(client_socket,
                                       TEST_HOST_PORT,
                                       MockServer(),
                                       api_client=self.client,
                                       enable_logging=False,)

        self.assertEqual(self.handler.user_agent, 'Custom Agent')

    def test_get(self) -> None:
        """Testing WebLoginHandler GET to an endpoint that doesn't exist"""
        request = '\r\n'.join([
            'GET / HTTP/1.1',
            'Host: https://reviews.example.com',
            '\r\n',
        ]).encode('utf-8')

        response = self._get_response(request)

        self.assertEqual(response['Status-line'], 'HTTP/1.1 404 Not Found')

    def test_get_login(self) -> None:
        """Testing WebLoginHandler GET to /login"""
        request = '\r\n'.join([
            'GET /login HTTP/1.1',
            'Host: https://reviews.example.com',
            '\r\n',
        ]).encode('utf-8')

        response = self._get_response(request)

        self.assertEqual(response['Status-line'],
                         'HTTP/1.1 301 Moved Permanently')
        self.assertEqual(
            response['Location'],
            'https://reviews.example.com/account/login/?client-name=RBTools'
            '&client-url=http://localhost:8080/login')
        self.assertEqual(response['User-Agent'],
                         RBTOOLS_USER_AGENT)

    def test_options(self) -> None:
        """Testing WebLoginHandler OPTIONS"""
        request = '\r\n'.join([
            'OPTIONS / HTTP/1.1',
            'Host: https://reviews.example.com',
            '\r\n',
        ]).encode('utf-8')

        response = self._get_response(request)

        self.assertEqual(response['Status-line'], 'HTTP/1.1 200 OK')
        self.assertEqual(response['Access-Control-Allow-Origin'],
                         'https://reviews.example.com')
        self.assertEqual(response['Access-Control-Allow-Methods'],
                         'GET, POST, OPTIONS')
        self.assertEqual(response['Access-Control-Allow-Headers'],
                         'Content-Type')

    def test_put(self) -> None:
        """Testing WebLoginHandler PUT to /login"""
        request = '\r\n'.join([
            'PUT /login HTTP/1.1',
            'Host: https://reviews.example.com',
            '\r\n',
        ]).encode('utf-8')

        response = self._get_response(request)

        self.assertEqual(response['Status-line'],
                         "HTTP/1.1 501 Unsupported method ('PUT')")

    def test_post(self) -> None:
        """Testing WebLoginHandler POST to an endpoint that doesn't exist"""
        request = '\r\n'.join([
            'POST /test HTTP/1.1',
            'Host: https://reviews.example.com',
            '\r\n',
        ]).encode('utf-8')

        response = self._get_response(request)

        self.assertEqual(response['Status-line'], 'HTTP/1.1 404 Not Found')

    def test_post_login(self) -> None:
        """Testing WebLoginHandler POST to /login"""
        self.spy_on(self.client._transport.login)
        self.spy_on(self.handler.server.stop, call_original=False)

        content = json.dumps({'api_token': 'test'})
        request = '\r\n'.join([
            'POST /login HTTP/1.1',
            'Host: https://reviews.example.com',
            'Accept: application/json',
            'Content-Type: application/json',
            'Content-Length: %s' % (len(content) + 2),
            '\r\n',
            content,
            '\r\n',
        ]).encode('utf-8')

        response = self._get_response(request)

        self.assertSpyCalledWith(self.client._transport.login,
                                 api_token='test')
        self.assertSpyCalled(self.handler.server.stop)
        self.assertEqual(response['Status-line'], 'HTTP/1.1 200 OK')

    def test_post_login_no_api_token(self) -> None:
        """Testing WebLoginHandler POST to /login with no API token"""
        self.spy_on(self.client._transport.login)
        self.spy_on(self.handler.server.stop, call_original=False)

        content = json.dumps({'foo': 'bar'})
        request = '\r\n'.join([
            'POST /login HTTP/1.1',
            'Host: https://reviews.example.com',
            'Accept: application/json',
            'Content-Type: application/json',
            'Content-Length: %s' % (len(content) + 2),
            '\r\n',
            content,
            '\r\n',
        ]).encode('utf-8')

        with self.assertLogs() as logs:
            response = self._get_response(request)

            self.assertSpyNotCalled(self.client._transport.login)
            self.assertEqual(response['Status-line'],
                             'HTTP/1.1 400 Bad Request')
            self.assertSpyCalled(self.handler.server.stop)
            self.assertEqual(
                logs.records[0].message,
                'Did not receive valid data for authentication: '
                "{'foo': 'bar'}")

    def _get_response(
        self,
        request: bytes,
    ) -> dict[str, str]:
        """Get a response from the WebLoginHandler.

        Args:
            request (bytes):
                The request to send to the WebLoginHandler.

        Returns:
            dict:
                The response as a dict containing headers as keys and the
                header value as values. The ``Status-line`` key contains
                the status line.
        """
        handler = self.handler
        handler.rfile = BytesIO(request)
        handler.wfile = BytesIO()

        handler.handle_one_request()
        response = handler.wfile.getvalue().decode('utf-8').split('\r\n')[:-2]
        response_dict = {
            'Status-line': response[0]
        }

        for line in response[1:]:
            key, value = line.split(': ')
            response_dict[key] = value

        return response_dict
