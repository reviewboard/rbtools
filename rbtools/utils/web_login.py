"""Utilities to support web-based login.

Version Added:
    5.0
"""

from __future__ import annotations

import json
import logging
import random
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, TYPE_CHECKING, Type

from packaging.version import parse as parse_version

from rbtools.api.capabilities import Capabilities
from rbtools.api.client import RBClient
from rbtools.api.request import RBTOOLS_USER_AGENT
from rbtools.utils.browser import open_browser as open_browser_func

if TYPE_CHECKING:
    from rbtools.api.resource import ItemResource


logger = logging.getLogger(__name__)

DEFAULT_HOSTNAME = 'localhost'


class WebLoginManager:
    """A manager for a web login server.

    The login server allows users of RBTools to authenticate to the Review
    Board server via Review Board's login page. This is useful for users
    who normally authenticate to Review Board using SSO or similar methods,
    and would like to use those methods to authenticate to RBTools.

    This can be used to start a web login server (see
    :py:meth`start_web_login_server`) and wait for a successful login
    to Review Board (see :py:meth`wait_login_result`). The server will shut
    down after receiving a login response from the Review Board server,
    or will shut down after a timeout.

    Version Added:
        5.0
    """

    ######################
    # Instance variables #
    ######################

    #: The API client used to communicate with the Review Board server.
    #:
    #: Type:
    #:     str
    api_client: RBClient

    #: Whether to enable logging for the web login server.
    #:
    #: Type:
    #:     bool
    enable_logging: bool

    #: The hostname for the server. This defaults to localhost.
    #:
    #: Type:
    #:     str
    hostname: str

    #: Whether to automatically open the login page in a web browser.
    #:
    #: Type:
    #:     bool
    open_browser: bool

    #: The web login server.
    #:
    #: This will only be set after :py:meth`start_web_login_server` has
    #: been called.
    #:
    #: Type:
    #:     WebLoginServer
    server: WebLoginServer

    #: The thread that the web login server is running on.
    #:
    #: This will only be set after :py:meth`start_web_login_server` has
    #: been called.
    #:
    #: Type:
    #:     str
    thread: threading.Thread

    #: The timeout for the web login server in seconds.
    #:
    #: The web login server will shut down after this amount of time. This
    #: defaults to 3 minutes.
    #:
    #: Type:
    #:     int
    timeout_secs: int

    #: The time in seconds since epoch that the server must shut down after.
    #:
    #: This is compared against the current time (in seconds since epoch) to
    #: check whether the timeout has been reached. This will only be set
    #: after the web login server has started.
    #:
    #: Type:
    #:     float
    timeout_epoch_secs: float

    def __init__(
        self,
        *,
        api_client: RBClient,
        enable_logging: bool = False,
        hostname: str = DEFAULT_HOSTNAME,
        open_browser: bool = False,
        timeout_secs: int = 180,
    ) -> None:
        """Initialize the web login manager.

        Args:
            api_client (rbtools.api.client.RBClient):
                The API client used to communicate with the Review Board
                server.

            enable_logging (bool, optional):
                Whether to display the logs for the server.

            hostname (str, optional):
                The hostname for the server. This defaults to localhost.

            open_browser (bool, optional):
                Whether to automatically open the web login page in a web
                browser, or just display the URL.

            timeout_secs (int, optional):
                The timeout for the web login server in seconds. The web login
                server will shut down after this amount of time. This defaults
                to 3 minutes.
        """
        self.api_client = api_client
        self.enable_logging = enable_logging
        self.hostname = hostname
        self.open_browser = open_browser
        self.timeout_secs = timeout_secs

    @property
    def login_successful(self) -> bool:
        """Whether the login to the Review Board server is successful.

        Type:
            bool
        """
        return self.server.login_successful

    def start_web_login_server(self) -> None:
        """Start the web login server.

        This will run the server in a new thread and display or optionally
        open the URL to the login page.
        """
        api_client = self.api_client
        hostname = self.hostname
        port = self._find_port()
        login_url = f'http://{hostname}:{port}/login'
        server = WebLoginServer(
            (hostname, port),
            _WebLoginHandler_factory(api_client, self.enable_logging))
        self.server = server

        if self.open_browser:
            logger.info('Opening %s to log in to the %s Review Board '
                        'server...',
                        login_url, api_client.domain)
            open_browser_func(login_url)
        else:
            logger.info('Please log in to the %s Review Board server at %s',
                        api_client.domain, login_url)

        thread = threading.Thread(target=self._serve)
        self.thread = thread
        thread.start()

        self.timeout_epoch_secs = time.time() + self.timeout_secs

    def wait_login_result(self) -> bool:
        """Wait for the login result from the Review Board server.

        This will return ``True`` if the login was successful and ``False``
        otherwise. If no result is received, the web login server will
        eventually time out.

        Returns:
            bool:
            Whether the login was successful.
        """
        try:
            while not self.server.stop_event.is_set():
                time.sleep(0.1)

                if time.time() >= self.timeout_epoch_secs:
                    self._handle_timeout()

            self.stop_server()
            return self.login_successful
        except (KeyboardInterrupt, SystemExit, TimeoutError):
            self.stop_server()
            raise

    def stop_server(self) -> None:
        """Stop the web login server.

        Raises:
            AttributeError:
                The web login server is not currently running.
        """
        server = self.server
        thread = self.thread

        if not (thread and server):
            raise AttributeError('The web login server is not currently '
                                 'running.')

        server.shutdown()
        thread.join()

    def _find_port(
        self,
        start: int = 30000,
        end: int = 60000
    ) -> int:
        """Find an available port for the server.

        This will attempt to find an unused port in the given range. It
        will continue trying until it finds a port.

        Args:
            start (int, optional):
                The start of the range to search for the port.

            end (int, optional):
                The end of the range to search for the port.

        Returns:
            int:
            The unused port number.
        """
        # This is slightly racy but shouldn't be too bad.
        while True:
            port = random.randint(start, end)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            try:
                s.bind(('127.0.0.1', port))
                s.listen(1)
                return port
            except Exception:
                # Ignore the exception. This is likely to be an "Address
                # already in use" error. We'll continue on to the next
                # random port.
                pass
            finally:
                try:
                    s.close()
                except Exception:
                    pass

    def _serve(self) -> None:
        """Serve the web login server."""
        self.server.serve_forever()

    def _handle_timeout(self) -> None:
        """Handle a timeout for the server.

        Raises:
            TimeoutError:
                The server timed out.
        """
        self.stop_server()
        raise TimeoutError('The web login server timed out.')


class WebLoginServer(ThreadingHTTPServer):
    """The web login server.

    This should not be called directly, callers should use
    :py:class:`WebLoginManager` instead.

    Version Added:
        5.0
    """

    ######################
    # Instance variables #
    ######################

    #: Whether the login to Review Board was successful.
    #:
    #: Type:
    #:     bool
    login_successful: bool

    #: An event for stopping the server.
    #:
    #: When this event is set, the server will stop.
    #:
    #: Type:
    #:     threading.Event
    stop_event: threading.Event

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the server.

        Args:
            *args (tuple):
                Positional arguments to pass to the parent constructor.

            **kwargs (dict):
                Keyword arguments to pass to the parent constructor.
        """
        self.login_successful = False
        self.stop_event = threading.Event()

        super().__init__(*args, **kwargs)

    def stop(self) -> None:
        """Trigger the event to stop the server.

        This triggers the stop event for the server, but does not shut down
        the server or clean up any threads associated with it.
        """
        self.stop_event.set()


class WebLoginHandler(BaseHTTPRequestHandler):
    """A handler for requests made to a web login server.

    This should not be called directly, callers should use
    :py:class:`WebLoginManager` instead.

    Version Added:
        5.0
    """

    #: Specifies the HTTP version to which the server is conformant.
    #:
    #: Type:
    #:     str
    protocol_version = 'HTTP/1.1'

    ######################
    # Instance variables #
    ######################

    #: The API client used to communicate with the Review Board server.
    #:
    #: Type:
    #:     str
    api_client: RBClient

    #: Whether to enable logging for the web login server.
    #:
    #: Type:
    #:     bool
    enable_logging: bool

    #: The URL of the Review Board server.
    #:
    #: Type:
    #:     str
    rb_server_url: str

    #: The web login server to handle requests for.
    #:
    #: Type:
    #:     WebLoginServer
    server: WebLoginServer

    #: The user agent for the web login server.
    #:
    #: Type:
    #:     str
    user_agent: str

    def __init__(
        self,
        *args,
        api_client: RBClient,
        enable_logging: bool = False,
        **kwargs,
    ) -> None:
        """Initialize the request handler.

        Args:
            *args (tuple):
                Positional arguments to pass to the parent constructor.

            api_client (rbtools.api.client.RBClient):
                The API client used to communicate with the Review Board
                server.

            enable_logging (bool, optional):
                Whether to enable logging for the web login server.

            **kwargs (dict):
                Additional keyword arguments to pass to the parent constructor.
        """
        self.api_client = api_client
        self.user_agent = api_client.user_agent or RBTOOLS_USER_AGENT
        self.enable_logging = enable_logging
        url = self.api_client.url

        if not url.endswith('/'):
            url += '/'

        self.rb_server_url = url

        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        """Handle GET requests."""
        endpoint = self.path.rstrip('/')

        if endpoint == '/login':
            self.GET_login()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        """Handle POST requests."""
        endpoint = self.path.rstrip('/')

        if endpoint == '/login':
            self.POST_login()
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests."""
        self.send_response(200)
        self.end_headers()

    def GET_login(self) -> None:
        """Handle GET requests for the /login endpoint.

        This redirects to the Review Board login page.
        """
        self.send_response(301)
        self.send_header(
            'Location',
            ('%saccount/login/'
             '?client-name=RBTools&client-url=http://localhost:%s/login'
             % (self.rb_server_url, self.server.server_address[1])))
        self.send_header('User-Agent', self.user_agent)
        self.end_headers()

    def POST_login(self) -> None:
        """Handle POST requests for the /login endpoint.

        This stores the authentication data received from the Review Board
        server.
        """
        content_length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(content_length))
        api_token = data.get('api_token')

        if api_token:
            self.api_client.login(api_token=api_token)
            self.server.login_successful = True
            self.send_response(200)
            self.end_headers()
        else:
            self.server.login_successful = False
            logger.exception(
                'Did not receive valid data for authentication: %s', data)
            self.send_response(400)
            self.end_headers()

        self.server.stop()

    def end_headers(self) -> None:
        """Add headers and indicate the end of headers in the response."""
        self.send_header('Content-Length', '0')
        self.send_header('Content-Type', 'text/html')
        self.send_header('Access-Control-Allow-Origin',
                         self.rb_server_url.rstrip('/'))
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Vary', 'Origin')
        super().end_headers()

    def log_message(
        self,
        format: str,
        *args,
    ) -> None:
        """Log messages for the server, if logging is enabled.

        Args:
            format (str):
                A standard printf-style format string, where additional
                arguments to this method are applied as inputs to the
                formatting.

            *args (str):
                Additional arguments to format.
        """
        if self.enable_logging:
            super().log_message(format, *args)


def _WebLoginHandler_factory(
    api_client: RBClient,
    enable_logging: bool,
) -> Type[WebLoginHandler]:
    """A class factory for :py:class`WebLoginHandler`.

    This allows us to set attributes on the :py:class`WebLoginHandler` object.

    Version Added:
        5.0

    Args:
        api_client (rbtools.api.client.RBClient):
            The API client used to communicate with the Review Board server.

        enable_logging (bool):
            Whether to display the logs for the server.

    Returns:
        WebLoginHandler:
        The WebLoginHandler class.
    """
    class Handler(WebLoginHandler):
        def __init__(
            self,
            *args,
            **kwargs,
        ) -> None:
            """Initialize the handler.

            Args:
                *args (tuple):
                    Positional arguments to pass to the parent constructor.

                **kwargs (dict):
                    Keyword arguments to pass to the parent constructor.
            """
            super().__init__(*args,
                             api_client=api_client,
                             enable_logging=enable_logging,
                             **kwargs)

    return Handler


def is_web_login_enabled(
    *,
    server_info: ItemResource,
    capabilities: Optional[Capabilities],
) -> bool:
    """Return whether client web login is enabled on a Review Board server.

    Version Added:
        5.0

    Args:
        server_info (rbtools.api.resource.ItemResource):
            The server info resource for the Review Board server.

        capabilities (rbtools.api.capabilities.Capabilities):
            The capabilities for the Review Board server.

    Returns:
        bool:
        Whether client web-based login is enabled on the given Review Board
        server.
    """
    minimum_supported_version = parse_version('5.0.5')
    rb_version = parse_version(server_info.product.package_version)

    if rb_version < minimum_supported_version:
        # This version is too old to support web-based login.
        return False
    elif (minimum_supported_version <= rb_version <= parse_version('5.0.7') or
          parse_version('6.0.0') <= rb_version <= parse_version('6.0.2')):
        # These versions have a bug with the client_web_login server
        # capability (see https://reviews.reviewboard.org/r/13693/). We'll
        # assume that web-based login is enabled.
        return True
    else:
        # This version will list the client_web_login server capability, which
        # will likely be True, but we'll fall back on a default of False just
        # in case.
        if capabilities is None:
            capabilities = Capabilities(server_info.capabilities)

        return capabilities.has_capability('authentication',
                                           'client_web_login')
