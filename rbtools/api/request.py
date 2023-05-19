from __future__ import annotations

import base64
import logging
import mimetypes
import os
import random
import shutil
import ssl
import sys
from collections import OrderedDict
from http.client import (HTTPMessage, HTTPResponse, HTTPSConnection,
                         NOT_MODIFIED)
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
from io import BytesIO
from json import loads as json_loads
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import (
    BaseHandler,
    HTTPBasicAuthHandler,
    HTTPCookieProcessor,
    HTTPDigestAuthHandler,
    HTTPErrorProcessor,
    HTTPPasswordMgr,
    HTTPSHandler,
    ProxyHandler,
    Request as URLRequest,
    build_opener,
    install_opener,
    urlopen)

import certifi
from typing_extensions import TypeAlias

from rbtools import get_package_version
from rbtools.api.cache import APICache, CachedHTTPResponse, LiveHTTPResponse
from rbtools.api.errors import (APIError,
                                ServerInterfaceError,
                                ServerInterfaceSSLError,
                                create_api_error)
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.encoding import force_bytes, force_unicode
from rbtools.utils.filesystem import get_home_path


RBTOOLS_COOKIE_FILE = '.rbtools-cookies'
RB_COOKIE_NAME = 'rbsessionid'


AuthCallback: TypeAlias = Callable[..., Tuple[str, str]]
OTPCallback: TypeAlias = Callable[[str, str], str]
QueryArgs: TypeAlias = Union[bool, int, float, bytes, str]


class HttpRequest:
    """A high-level HTTP request.

    This is used to construct an HTTP request to a Review Board server.
    It takes in the URL, HTTP method, any query arguments and headers
    needed to perform the request, and provides methods for building a
    request payload compatible with the Review Board API.

    Instances are intentionally generic and not tied to :py:mod:`urllib2`,
    providing API stability and a path toward eventually interfacing with
    other HTTP backends.
    """

    #: HTTP headers to provide when making the request
    #:
    #: Type: dict
    headers: Dict[str, str]

    #: The URL te request
    #:
    #: Type: str
    url: str

    def __init__(
        self,
        url: str,
        method: str = 'GET',
        query_args: Dict[str, QueryArgs] = {},
        headers: Dict[str, str] = {},
    ) -> None:
        """Initialize the HTTP request.

        Args:
            url (bytes or str):
                The URL to request.

            method (bytes or str, optional):
                The HTTP method to send to the server.

            query_args (dict, optional):
                Any query arguments to add to the URL.

            headers (dict, optional):
                Any HTTP headers to provide in the request.
        """
        self._method = method
        self.headers = headers
        self._fields = OrderedDict()
        self._files = OrderedDict()

        # Add the query arguments to the url
        url_parts = list(urlparse(url))
        query: Dict[str, str] = dict(parse_qsl(url_parts[4]))
        query.update({
            # Replace all underscores in each query argument key with dashes.
            self.encode_url_key(key): self.encode_url_value(key, value)
            for key, value in query_args.items()
        })

        url_parts[4] = urlencode(
            OrderedDict(
                pair
                for pair in sorted(query.items(),
                                   key=lambda pair: pair[0])
            ),
            doseq=True
        )

        self.url = urlunparse(url_parts)

    def encode_url_key(
        self,
        key: str,
    ) -> str:
        """Encode the given key for inclusion in a URL.

        Args:
            key (str):
                The key that is being encoded.

        Raises:
            ValueError:
                The given key was neither a unicode string or byte string.

        Returns:
            str:
            The key encoded as a unicode string.
        """
        return force_unicode(key).replace('_', '-')

    def encode_url_value(
        self,
        key: Union[bytes, str],
        value: QueryArgs,
    ) -> str:
        """Encode the given value for inclusion in a URL.

        Args:
            key (str):
                The field name for which the value is being encoded.
                This argument is only used to generate an error message.

            value (object):
                The value to be encoded.

        Raises:
            ValueError:
                The given value could not be encoded.

        Returns:
            str:
            The value encoded as a unicode string.
        """
        if isinstance(value, bool):
            if value:
                value = '1'
            else:
                value = '0'
        elif isinstance(value, (int, float)):
            value = str(value)
        elif isinstance(value, (bytes, str)):
            value = force_unicode(value)
        else:
            raise ValueError(
                'Could not encode value %r for key %s: expected int, float, '
                'bool, or string type; got %s instead'
                % (key, value, type(value).__name__)
            )

        assert isinstance(value, str)
        return value

    @property
    def method(self) -> str:
        """The HTTP method to send to the server."""
        return self._method

    @method.setter
    def method(
        self,
        method: str,
    ) -> None:
        """The HTTP method to send to the server.

        Args:
            method (str):
                The HTTP method to send to the server.
        """
        self._method = str(method)

    def add_field(
        self,
        name: Union[bytes, str],
        value: Union[bytes, str],
    ) -> None:
        """Add a form-data field for the request.

        Version Changed:
            4.0:
            Values of types other than bytes or str are now deprecated, and
            will be removed in 5.0.

        Args:
            name (bytes or str):
                The name of the field.

            value (bytes or str):
                The value to send for the field.

                For backwards-compatibility, other values will be converted to
                strings. This will be removed in 5.0.
        """
        if not isinstance(value, (bytes, str)):
            RemovedInRBTools50Warning.warn(
                'A value of type %s was passed to HttpRequest.add_field. In '
                'RBTools 5.0, only values of bytes or str types will be '
                'accepted.')
            value = str(value)

        self._fields[force_bytes(name)] = force_bytes(value)

    def add_file(
        self,
        name: Union[bytes, str],
        filename: Union[bytes, str],
        content: Union[bytes, str],
        mimetype: Optional[Union[bytes, str]] = None,
    ) -> None:
        """Add an uploaded file for the request.

        Args:
            name (bytes or str):
                The name of the field representing the file.

            filename (bytes or str):
                The filename.

            content (bytes or str):
                The contents of the file.

            mimetype (bytes or str, optional):
                The optional mimetype of the content. If not provided, it
                will be guessed.
        """
        if not mimetype:
            mimetype = (
                mimetypes.guess_type(force_unicode(filename))[0] or
                b'application/octet-stream')

        self._files[force_bytes(name)] = {
            'filename': force_bytes(filename),
            'content': force_bytes(content),
            'mimetype': force_bytes(mimetype),
        }

    def encode_multipart_formdata(
        self,
    ) -> Tuple[Optional[str], Optional[bytes]]:
        """Encode the request into a multi-part form-data payload.

        Returns:
            tuple:
            A tuple containing:

            * The content type (:py:class:`str`)
            * The form-data payload (:py:class:`bytes`)

            If there are no fields or files in the request, both values will
            be ``None``.
        """
        if not (self._fields or self._files):
            return None, None

        NEWLINE = b'\r\n'
        BOUNDARY = self._make_mime_boundary()
        content = BytesIO()

        for key, value in self._fields.items():
            content.write(b'--%s%s' % (BOUNDARY, NEWLINE))
            content.write(b'Content-Disposition: form-data; name="%s"%s'
                          % (key, NEWLINE))
            content.write(NEWLINE)
            content.write(value)
            content.write(NEWLINE)

        for key, file_info in self._files.items():
            content.write(b'--%s%s' % (BOUNDARY, NEWLINE))
            content.write(b'Content-Disposition: form-data; name="%s"; ' % key)
            content.write(b'filename="%s"%s' % (file_info['filename'],
                                                NEWLINE))
            content.write(b'Content-Type: %s%s' % (file_info['mimetype'],
                                                   NEWLINE))
            content.write(NEWLINE)
            content.write(file_info['content'])
            content.write(NEWLINE)

        content.write(b'--%s--%s%s' % (BOUNDARY, NEWLINE, NEWLINE))
        content_type = ('multipart/form-data; boundary=%s'
                        % BOUNDARY.decode('utf-8'))

        return content_type, content.getvalue()

    def _make_mime_boundary(self) -> bytes:
        """Create a mime boundary.

        This exists because :py:func:`mimetools.choose_boundary` is gone in
        Python 3.x, and :py:func:`email.generator._make_boundary` isn't really
        appropriate to use here.

        Returns:
            bytes:
            The generated boundary.
        """
        fmt = '%%0%dd' % len(repr(sys.maxsize - 1))
        token = random.randrange(sys.maxsize)
        return (b'=' * 15) + (fmt % token).encode('utf-8') + b'=='


class RBToolsHTTPSConnection(HTTPSConnection):
    """Connection class for HTTPS connections.

    This is a specialization of the default HTTPS connection class that
    provides custom error handling for SSL errors.

    Version Added:
        4.1
    """

    def connect(self, *args, **kwargs) -> Any:
        """Connect to the server.

        This will catch SSL errors and wrap them with our own error classes.

        Args:
            *args (tuple):
                Positional arguments to pass to the parent method.

            **kwargs (dict):
                Keyword arguments to pass to the parent method.

        Returns:
            object:
            The result from the parent method.

        Raises:
            rbtools.api.errors.ServerInterfaceSSLError:
                An SSL error occurred during communication. Details will be
                in the error message.
        """
        try:
            return super().connect(*args, **kwargs)
        except ssl.SSLError as e:
            # This seems to be the only way to get access to the context
            # here. Assert that it's reachable.
            context = getattr(self, '_context', None)
            assert context is not None

            raise ServerInterfaceSSLError(
                host=self.host,
                port=self.port,
                ssl_error=e,
                ssl_context=context)


class RBToolsHTTPSHandler(HTTPSHandler):
    """Request/response handler for HTTPS connections.

    This wraps the default HTTPS handler, passing in a specialized HTTPS
    connection class used to generate more useful SSL-related errors.

    Version Added:
        4.1
    """

    def do_open(
        self,
        http_class,
        *args,
        **kwargs,
    ) -> HTTPResponse:
        """Open a connection to the server.

        Args:
            http_class (type, unused):
                The original HTTPS connection class. This will be replaced
                with our own.

            *args (tuple):
                Positional arguments to pass to the parent method.

            **kwargs (dict):
                Keyword arguments to pass to the parent method.

        Returns:
            http.client.HTTPResponse:
            The resulting HTTP response.

        Raises:
            rbtools.api.errors.ServerInterfaceSSLError:
                An SSL error occurred during communication. Details will be
                in the error message.
        """
        # Note that we're ignoring the typing below, as the type hints for
        # do_open() mistakenly lack the 'self' parameter and think that
        # RBToolsHTTPSConnection is therefore a mismatch on a different
        # parameter.
        return super().do_open(RBToolsHTTPSConnection,  # type: ignore
                               *args, **kwargs)


class Request(URLRequest):
    """A request which contains a method attribute."""

    #: The HTTP method to use.
    #:
    #: Type: str
    method: str

    def __init__(
        self,
        url: str,
        body: Optional[bytes] = b'',
        headers: Dict[str, str] = {},
        method: str = 'PUT',
    ) -> None:
        """Initialize the request.

        Args:
            url (str):
                The URL to make the request at.

            body (bytes, optional):
                The body to send with the request.

            headers (dict, optional):
                The headers to send with the request.

            method (str, optional):
                The HTTP method to use.
        """
        super().__init__(url, body, headers)
        self.method = method

    def get_method(self) -> str:
        """Return the HTTP method.

        Returns:
            str:
            The HTTP method.
        """
        return self.method


class ReviewBoardHTTPErrorProcessor(HTTPErrorProcessor):
    """Processes HTTP error codes.

    Python's built-in error processing understands 2XX responses as successful,
    but processes 3XX as an error. This handler ensures that all valid
    responses from the API are processed as such.
    """

    def http_response(self, request, response):
        if not (200 <= response.status < 300 or
                response.status == NOT_MODIFIED):
            response = self.parent.error('http', request, response,
                                         response.status, response.msg,
                                         response.headers)

        return response

    https_response = http_response


class ReviewBoardHTTPPasswordMgr(HTTPPasswordMgr):
    """Adds HTTP authentication support for URLs."""

    def __init__(
        self,
        reviewboard_url: str,
        rb_user: Optional[str] = None,
        rb_pass: Optional[str] = None,
        api_token: Optional[str] = None,
        auth_callback: Optional[AuthCallback] = None,
        otp_token_callback: Optional[OTPCallback] = None,
    ) -> None:
        """Initialize the password manager.

        Args:
            reviewboard_url (str):
                The URL of the Review Board server.

            rb_user (str, optional):
                The username to authenticate with.

            rb_pass (str, optional):
                The password to authenticate with.

            api_token (str, optional):
                The API token to authenticate with. If present, this takes
                priority over the username and password.

            auth_callback (callable, optional):
                A callback to prompt the user for their username and password.

            otp_token_callback (callable, optional):
                A callback to prompt the user for their two-factor
                authentication code.
        """
        super().__init__()
        self.rb_url = reviewboard_url
        self.rb_user = rb_user
        self.rb_pass = rb_pass
        self.api_token = api_token
        self.auth_callback = auth_callback
        self.otp_token_callback = otp_token_callback

    def find_user_password(
        self,
        realm: str,
        uri: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Return the username and password for the given realm.

        Args:
            realm (str):
                The HTTP Basic authentication realm.

            uri (str):
                The URI being accessed.

        Returns:
            tuple:
            A 2-tuple containing:

            Tuple:
                0 (str):
                    The username to use.

                1 (str):
                    The password to use.
        """
        if realm == 'Web API':
            if self.auth_callback:
                username, password = self.auth_callback(realm, uri,
                                                        username=self.rb_user,
                                                        password=self.rb_pass)
                self.rb_user = username
                self.rb_pass = password

            return self.rb_user, self.rb_pass
        else:
            # If this is an auth request for some other domain (since HTTP
            # handlers are globaltake), fall back to standard password
            # management.
            return HTTPPasswordMgr.find_user_password(self, realm, uri)

    def get_otp_token(
        self,
        uri: str,
        method: str,
    ) -> Optional[str]:
        """Return the two-factor authentication code.

        Args:
            uri (str):
                The URI being accessed.

            method (str):
                The HTTP method being used.

        Returns:
            str:
            The user's two-factor authentication code, if available.
        """
        if self.otp_token_callback:
            return self.otp_token_callback(uri, method)

        return None


class PresetHTTPAuthHandler(BaseHandler):
    """Handler that presets the use of HTTP Basic Auth."""

    handler_order = 480  # After Basic auth

    AUTH_HEADER = 'Authorization'

    def __init__(
        self,
        url: str,
        password_mgr: ReviewBoardHTTPPasswordMgr,
    ) -> None:
        """Initialize the handler.

        Args:
            url (str):
                The URL fo the Review Board server.

            password_mgr (ReviewBoardHTTPPasswordMgr):
                The password manager to use for requests.
        """
        self.url = url
        self.password_mgr = password_mgr
        self.used = False

    def reset(
        self,
        username: Optional[str],
        password: Optional[str],
    ) -> None:
        """Reset the stored authentication credentials.

        Args:
            username (str):
                The username to use for authentication. If ``None``, this will
                effectively log out the user.

            passsword (str):
                The password to use for authentication. If ``None``, this will
                effectively log out the user.
        """
        self.password_mgr.rb_user = username
        self.password_mgr.rb_pass = password
        self.used = False

    def http_request(
        self,
        request: Request,
    ) -> Request:
        """Modify an HTTP request with authentication information.

        Args:
            request (rbtools.api.request.Request):
                The HTTP request to make.

        Returns:
            rbtools.api.request.Request:
            The HTTP request, with authentication headers added.
        """
        if not self.used:
            if self.password_mgr.api_token:
                request.add_header(self.AUTH_HEADER,
                                   'token %s' % self.password_mgr.api_token)
                self.used = True
            elif self.password_mgr.rb_user:
                # Note that we call password_mgr.find_user_password to get the
                # username and password we're working with.
                username, password = \
                    self.password_mgr.find_user_password('Web API', self.url)
                raw = '%s:%s' % (username, password)
                header = (b'Basic %s'
                          % base64.b64encode(raw.encode('utf-8')).strip())

                request.add_header(self.AUTH_HEADER, header.decode('utf-8'))
                self.used = True

        return request

    https_request = http_request


class ReviewBoardHTTPBasicAuthHandler(HTTPBasicAuthHandler):
    """Custom Basic Auth handler that doesn't retry excessively.

    urllib's HTTPBasicAuthHandler retries over and over, which is useless. This
    subclass only retries once to make sure we've attempted with a valid
    username and password. It will then fail so we can use our own retry
    handler.

    This also supports two-factor auth, for Review Board servers that
    support it. When requested by the server, the client will be prompted
    for a one-time password token, which would be sent generally through
    a mobile device. In this case, the client will prompt up to a set
    number of times until a valid token is entered.
    """

    OTP_TOKEN_HEADER = 'X-ReviewBoard-OTP'
    MAX_OTP_TOKEN_ATTEMPTS = 2

    passwd: ReviewBoardHTTPPasswordMgr

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the Basic Auth handler.

        Args:
            *args (tuple):
                Positional arguments to pass to the parent class.

            **kwargs (dict):
                Keyword arguments to pass to the parent class.
        """
        HTTPBasicAuthHandler.__init__(self, *args, **kwargs)

        self._tried_login: bool = False
        self._otp_token_method: Optional[str] = None
        self._otp_token_attempts: int = 0
        self._last_otp_token: Optional[str] = None

    def http_error_auth_reqed(
        self,
        authreq: str,
        host: str,
        req: URLRequest,
        headers: HTTPMessage,
    ) -> None:
        """Handle an HTTP 401 Unauthorized from an API request.

        This will start by checking whether a two-factor authentication
        token is required by the server, and which method it will be sent
        by (SMS or token generator application), before handing back to the
        parent class, which will then call into our custom
        :py:meth:`retry_http_basic_auth`.

        Args:
            authreq (str):
                The authentication request type.

            host (str):
                The URL being accessed.

            req (rbtools.api.request.Request):
                The API request being made.

            headers (http.client.HTTPMessage):
                The headers sent in the Unauthorized error response.

        Returns:
            http.client.HTTPResponse:
            If attempting another request, this will be the HTTP response
            from that request. This will be ``None`` if not making another
            request.

        Raises:
            urllib2.URLError:
                The HTTP request resulted in an error. If this is an
                :http:`401`, it may be handled by this class again.
        """
        otp_header = headers.get(self.OTP_TOKEN_HEADER, '')

        if otp_header and otp_header.startswith('required'):
            try:
                self._otp_token_method = otp_header.split(';')[1].strip()
            except IndexError:
                logging.error('Invalid %s header value: "%s". This header '
                              'is needed for two-factor authentication to '
                              'work. Please report this!',
                              self.OTP_TOKEN_HEADER, otp_header)
                return None

        return HTTPBasicAuthHandler.http_error_auth_reqed(
            self, authreq, host, req, headers)

    def retry_http_basic_auth(
        self,
        host: str,
        request: URLRequest,
        realm: str,
    ) -> Optional[HTTPResponse]:
        """Attempt another HTTP Basic Auth request.

        This will determine if another request should be made (based on
        previous attempts and 2FA requirements. Based on this, it may make
        another attempt.

        Args:
            host (str):
                The URL being accessed.

            request (rbtools.api.request.Request):
                The API request being made.

            realm (str):
                The Basic Auth realm, which will be used to look up any
                stored passwords.

        Returns:
            http.client.HTTPResponse:
            If attempting another request, this will be the HTTP response
            from that request. This will be ``None`` if not making another
            request.

        Raises:
            urllib2.URLError:
                The HTTP request resulted in an error. If this is an
                :http:`401`, it may be handled by this class again.
        """
        # First, check if we even want to try again. If two-factor
        # authentication is disabled and we've made one username/password
        # attempt, or it's enabled and we've made too many 2FA token attempts,
        # we're done.
        if (self._otp_token_attempts > self.MAX_OTP_TOKEN_ATTEMPTS or
            (not self._otp_token_method and self._tried_login)):
            return None

        # Next, figure out what credentials we'll be working with.
        if self._otp_token_attempts > 0:
            # We've made at least one 2FA attempt. Reuse the login and
            # password so we don't prompt for it again.
            user = self.passwd.rb_user
            password = self.passwd.rb_pass
        else:
            # We don't have a login and password recorded for this request.
            # Request one from the user.
            user, password = self.passwd.find_user_password(realm, host)

        if password is None:
            return None

        # If the response had sent a X-ReviewBoard-OTP header stating that
        # a 2FA token is required, request it from the user.
        if self._otp_token_method:
            otp_token = self.passwd.get_otp_token(
                request.get_full_url(), self._otp_token_method)
        else:
            otp_token = None

        # Prepare some auth headers and then check if we've already made an
        # attempt with them.
        raw = '%s:%s' % (user, password)
        auth = b'Basic %s' % base64.b64encode(raw.encode('utf-8')).strip()

        if (request.get_header(self.auth_header) == auth and
            (not otp_token or otp_token == self._last_otp_token)):
            # We've already tried with these credentials/token, and the
            # attempt failed. No point trying again and wasting a login
            # attempt.
            return None

        # Based on the above, set the headers for the next login attempt and
        # try again. If it fails, we'll end up back in http_error_auth_reqed(),
        # starting again but with the recorded state.
        request.add_unredirected_header(self.auth_header, auth.decode('utf-8'))

        if otp_token:
            request.add_unredirected_header(self.OTP_TOKEN_HEADER, otp_token)
            self._otp_token_attempts += 1
            self._last_otp_token = otp_token

        self._tried_login = True

        return self.parent.open(request, timeout=request.timeout)


def create_cookie_jar(
    cookie_file: Optional[str] = None,
) -> Tuple[MozillaCookieJar, str]:
    """Return a cookie jar backed by cookie_file

    If cooie_file is not provided, we will default it. If the
    cookie_file does not exist, we will create it with the proper
    permissions.

    In the case where we default cookie_file, and it does not exist,
    we will attempt to copy the .post-review-cookies.txt file.

    Args:
        cookie_file (str, optional):
            The filename to use for cookies.

    Returns:
        tuple:
        A two-tuple containing:


        Tuple:
            0 (http.cookiejar.MozillaCookieJar):
                The cookie jar object.

            1 (str):
                The name of the cookie file.
    """
    if not cookie_file:
        home_path = get_home_path()
        cookie_file = os.path.join(home_path, RBTOOLS_COOKIE_FILE)
        post_review_cookies = os.path.join(home_path,
                                           '.post-review-cookies.txt')

        if (not os.path.isfile(cookie_file) and
            os.path.isfile(post_review_cookies)):
            try:
                shutil.copyfile(post_review_cookies, cookie_file)
                os.chmod(cookie_file, 0o600)
            except IOError as e:
                logging.warning('There was an error while copying '
                                'legacy post-review cookies: %s', e)

    if not os.path.isfile(cookie_file):
        try:
            open(cookie_file, 'w').close()
            os.chmod(cookie_file, 0o600)
        except IOError as e:
            logging.warning('There was an error while creating a '
                            'cookie file: %s', e)

    return MozillaCookieJar(cookie_file), cookie_file


class ReviewBoardServer:
    """Represents a Review Board server we are communicating with.

    Provides methods for executing HTTP requests on a Review Board
    server's Web API.

    The ``auth_callback`` parameter can be used to specify a callable
    which will be called when authentication fails. This callable will
    be passed the realm, and url of the Review Board server and should
    return a 2-tuple of username, password. The user can be prompted
    for their credentials using this mechanism.
    """

    ######################
    # Instance variables #
    ######################

    #: The path to the file for storing authentication cookies.
    #:
    #: Type:
    #:     str
    cookie_file: Optional[str]

    #: The cookie jar object for managing authentication cookies.
    #:
    #: Type:
    #:     http.cookiejar.CookieJar
    cookie_jar: CookieJar

    _cache: Optional[APICache] = None

    def __init__(
        self,
        url: str,
        cookie_file: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_token: Optional[str] = None,
        agent: Optional[str] = None,
        session: Optional[str] = None,
        disable_proxy: bool = False,
        auth_callback: Optional[AuthCallback] = None,
        otp_token_callback: Optional[OTPCallback] = None,
        verify_ssl: bool = True,
        save_cookies: bool = True,
        ext_auth_cookies: Optional[str] = None,
        ca_certs: Optional[str] = None,
        client_key: Optional[str] = None,
        client_cert: Optional[str] = None,
        proxy_authorization: Optional[str] = None,
    ) -> None:
        """Initialize the server object.

        Args:
            url (str):
                The URL of the Review Board server.

            cookie_file (str, optional):
                The name of the file to store authentication cookies in.

            username (str, optional):
                The username to use for authentication.

            password (str, optional):
                The password to use for authentication.

            api_token (str, optional):
                An API token to use for authentication. If present, this is
                preferred over the username and password.

            agent (str, optional):
                A User-Agent string to use for the client. If not specified,
                the default RBTools User-Agent will be used.

            session (str, optional):
                An ``rbsessionid`` string to use for authentication.

            disable_proxy (bool, optional):
                Whether to disable HTTP proxies.

            auth_callback (callable, optional):
                A callback method to prompt the user for a username and
                password.

            otp_callback (callable, optional):
                A callback method to prompt the user for their two-factor
                authentication code.

            verify_ssl (bool, optional):
                Whether to verify SSL certificates.

            save_cookies (bool, optional):
                Whether to save authentication cookies.

            ext_auth_cookies (str, optional):
                The name of a file to load additional cookies from. These will
                be layered on top of any cookies loaded from ``cookie_file``.

            ca_certs (str, optional):
                The name of a file to load certificates from.

            client_key (str, optional):
                The key for a client certificate to load into the chain.

            client_cert (str, optional):
                A client certificate to load into the chain.

            proxy_authorization (str, optional):
                A string to use for the ``Proxy-Authorization`` header.
        """
        if not url.endswith('/'):
            url += '/'

        self.url = url + 'api/'

        self.save_cookies = save_cookies
        self.ext_auth_cookies = ext_auth_cookies

        if self.save_cookies:
            self.cookie_jar, self.cookie_file = create_cookie_jar(
                cookie_file=cookie_file)

            try:
                self.cookie_jar.load(ignore_expires=True)
            except IOError:
                pass
        else:
            self.cookie_jar = CookieJar()
            self.cookie_file = None

        if self.ext_auth_cookies:
            try:
                assert isinstance(self.cookie_jar, MozillaCookieJar)
                self.cookie_jar.load(ext_auth_cookies, ignore_expires=True)
            except IOError as e:
                logging.critical('There was an error while loading a '
                                 'cookie file: %s', e)
                pass

        # Get the cookie domain from the url. If the domain
        # does not contain a '.' (e.g. 'localhost'), we assume
        # it is a local domain and suffix it (See RFC 2109).
        parsed_url = urlparse(url)
        self.domain = parsed_url[1].partition(':')[0]  # Remove Port.

        if self.domain.count('.') < 1:
            self.domain = '%s.local' % self.domain

        if session:
            cookie = Cookie(
                version=0,
                name=RB_COOKIE_NAME,
                value=session,
                port=None,
                port_specified=False,
                domain=self.domain,
                domain_specified=True,
                domain_initial_dot=True,
                path=parsed_url[2],
                path_specified=True,
                secure=False,
                expires=None,
                discard=False,
                comment=None,
                comment_url=None,
                rest={'HttpOnly': ''})
            self.cookie_jar.set_cookie(cookie)

            if self.save_cookies:
                assert isinstance(self.cookie_jar, MozillaCookieJar)
                self.cookie_jar.save()

        if username:
            # If the username parameter is given, we have to clear the session
            # cookie manually or it will override the username:password
            # combination retrieved from the authentication callback.
            try:
                self.cookie_jar.clear(self.domain, parsed_url[2],
                                      RB_COOKIE_NAME)
            except KeyError:
                pass

        # Set up the HTTP libraries to support all of the features we need.
        password_mgr = ReviewBoardHTTPPasswordMgr(self.url,
                                                  username,
                                                  password,
                                                  api_token,
                                                  auth_callback,
                                                  otp_token_callback)
        self.preset_auth_handler = PresetHTTPAuthHandler(self.url,
                                                         password_mgr)

        handlers: List[BaseHandler] = []

        if verify_ssl:
            context = ssl.create_default_context(
                cafile=ca_certs or certifi.where())
        else:
            context = ssl._create_unverified_context()

        if client_cert and client_key:
            context.load_cert_chain(client_cert, client_key)

        handlers.append(RBToolsHTTPSHandler(context=context))

        if disable_proxy:
            handlers.append(ProxyHandler({}))

        handlers += [
            HTTPCookieProcessor(self.cookie_jar),
            ReviewBoardHTTPBasicAuthHandler(password_mgr),
            HTTPDigestAuthHandler(password_mgr),
            self.preset_auth_handler,
            ReviewBoardHTTPErrorProcessor(),
        ]

        if agent:
            self.agent = agent
        else:
            self.agent = 'RBTools/' + get_package_version()

        opener = build_opener(*handlers)
        headers = [(str('User-agent'), str(self.agent))]

        if proxy_authorization:
            headers.append((str('Proxy-Authorization'),
                            str(proxy_authorization)))

        opener.addheaders = headers
        install_opener(opener)

        self._cache = None
        self._urlopen = urlopen

    def enable_cache(
        self,
        cache_location: Optional[str] = None,
        in_memory: bool = False,
    ) -> None:
        """Enable caching for all future HTTP requests.

        The cache will be created at the default location if none is provided.

        If the in_memory parameter is True, the cache will be created in memory
        instead of on disk. This overrides the cache_location parameter.

        Args:
            cache_location (str, optional):
                The name of the file to use for the cache database.

            in_memory (bool, optional):
                Whether to only use in-memory caching. If ``True``, the
                ``cache_location`` argument is ignored.
        """
        if not self._cache:
            self._cache = APICache(create_db_in_memory=in_memory,
                                   db_location=cache_location)

            self._urlopen = self._cache.make_request

    def login(
        self,
        username: str,
        password: str,
    ) -> None:
        """Log in to the Review Board server.

        Args:
            username (str):
                The username to use to log in.

            password (str):
                The password to use to log in.
        """
        self.preset_auth_handler.reset(username, password)

    def logout(self) -> None:
        """Log the user out of the session."""
        self.preset_auth_handler.reset(None, None)
        self.make_request(HttpRequest('%ssession/' % self.url,
                                      method='DELETE'))
        self.cookie_jar.clear(self.domain)

        if self.save_cookies:
            assert isinstance(self.cookie_jar, MozillaCookieJar)
            self.cookie_jar.save()

    def process_error(
        self,
        http_status: int,
        data: Union[str, bytes],
    ) -> None:
        """Process an error, raising an APIError with the information.

        Args:
            http_status (int):
                The HTTP status code.

            data (bytes or str):
                The data returned by the server.

        Raises:
            rbtools.api.errors.APIError:
                The API error object.
        """
        data_str = force_unicode(data)

        try:
            rsp = json_loads(data_str)

            assert rsp['stat'] == 'fail'

            logging.debug('Got API Error %d (HTTP code %d): %s',
                          rsp['err']['code'], http_status, rsp['err']['msg'])
            logging.debug('Error data: %r', rsp)

            raise create_api_error(http_status, rsp['err']['code'], rsp,
                                   rsp['err']['msg'])
        except ValueError:
            logging.debug('Got HTTP error: %s: %s', http_status, data_str)
            raise APIError(http_status, None, None, data_str)

    def make_request(
        self,
        request: HttpRequest,
    ) -> Optional[Union[HTTPResponse, CachedHTTPResponse, LiveHTTPResponse]]:
        """Perform an http request.

        Args:
            request (rbtools.api.request.HttpRequest):
                The request object.

        Returns:
            http.client.HTTPResponse:
            The HTTP response.
        """
        rsp = None

        try:
            content_type, body = request.encode_multipart_formdata()
            headers = request.headers

            if content_type and body:
                headers.update({
                    'Content-Type': content_type,
                    'Content-Length': str(len(body)),
                })
            else:
                headers['Content-Length'] = '0'

            rsp = self._urlopen(Request(
                request.url, body, headers, request.method))
        except HTTPError as e:
            self.process_error(e.code, e.read())
        except URLError as e:
            raise ServerInterfaceError('%s' % e.reason)

        if self.save_cookies:
            try:
                assert isinstance(self.cookie_jar, MozillaCookieJar)
                self.cookie_jar.save()
            except IOError:
                pass

        return rsp
