from __future__ import unicode_literals

import base64
import logging
import mimetypes
import os
import random
import shutil
import sys
from io import BytesIO
from json import loads as json_loads

import six
from six.moves.http_client import UNAUTHORIZED, NOT_MODIFIED
from six.moves.http_cookiejar import Cookie, CookieJar, MozillaCookieJar
from six.moves.urllib.error import HTTPError, URLError
from six.moves.urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from six.moves.urllib.request import (
    BaseHandler,
    HTTPBasicAuthHandler,
    HTTPCookieProcessor,
    HTTPDigestAuthHandler,
    HTTPErrorProcessor,
    HTTPPasswordMgr,
    ProxyHandler,
    Request as URLRequest,
    build_opener,
    install_opener,
    urlopen)

from rbtools import get_package_version
from rbtools.api.cache import APICache
from rbtools.api.errors import APIError, create_api_error, ServerInterfaceError
from rbtools.utils.encoding import force_unicode
from rbtools.utils.filesystem import get_home_path

# Python 2.7.9+ added strict HTTPS certificate validation (finally). These APIs
# don't exist everywhere so soft-import them.
try:
    import ssl
    from six.moves.urllib.request import HTTPSHandler
except ImportError:
    ssl = None
    HTTPSHandler = None


RBTOOLS_COOKIE_FILE = '.rbtools-cookies'
RB_COOKIE_NAME = 'rbsessionid'


class HttpRequest(object):
    """High-level HTTP-request object."""
    def __init__(self, url, method='GET', query_args={}, headers={}):
        self.method = method
        self._fields = {}
        self._files = {}

        # Replace all underscores in each query argument
        # key with dashes.
        query_args = dict([
            (key.replace('_', '-'), value)
            for key, value in six.iteritems(query_args)
        ])

        # Make sure headers are always in the native string type.
        self.headers = {
            str(key): str(value)
            for key, value in six.iteritems(headers)
        }

        # Add the query arguments to the url
        url_parts = list(urlparse(str(url)))
        query = dict(parse_qsl(url_parts[4]))
        query.update(query_args)
        url_parts[4] = urlencode(query)
        self.url = urlunparse(url_parts)

    @property
    def method(self):
        return self._method

    @method.setter
    def method(self, method):
        self._method = str(method)

    def add_field(self, name, value):
        self._fields[name] = value

    def add_file(self, name, filename, content):
        self._files[name] = {
            'filename': filename,
            'content': content,
        }

    def del_field(self, name):
        del self._fields[name]

    def del_file(self, filename):
        del self._files[filename]

    def encode_multipart_formdata(self):
        """Encodes data for use in an HTTP request.

        Parameters:
            fields - the fields to be encoded.  This should be a dict in a
                     key:value format
            files  - the files to be encoded.  This should be a dict in a
                     key:dict, filename:value and content:value format
        """
        if not (self._fields or self._files):
            return None, None

        NEWLINE = b'\r\n'
        BOUNDARY = self._make_mime_boundary()
        content = BytesIO()

        for key in self._fields:
            content.write(b'--' + BOUNDARY + NEWLINE)
            content.write(b'Content-Disposition: form-data; '
                          b'name="%s"' % key.encode('utf-8'))
            content.write(NEWLINE + NEWLINE)

            if isinstance(self._fields[key], six.binary_type):
                content.write(self._fields[key] + NEWLINE)
            else:
                content.write(
                    six.text_type(self._fields[key]).encode('utf-8') +
                    NEWLINE)

        for key in self._files:
            filename = self._files[key]['filename']
            value = self._files[key]['content']

            mime_type = mimetypes.guess_type(filename)[0]
            if mime_type:
                mime_type = mime_type.encode('utf-8')
            else:
                mime_type = b'application/octet-stream'

            content.write(b'--' + BOUNDARY + NEWLINE)
            content.write(b'Content-Disposition: form-data; name="%s"; '
                          % key.encode('utf-8'))
            content.write(b'filename="%s"' % filename.encode('utf-8') +
                          NEWLINE)
            content.write(b'Content-Type: %s' % mime_type + NEWLINE)
            content.write(NEWLINE)

            if isinstance(value, six.text_type):
                content.write(value.encode('utf-8'))
            else:
                content.write(value)

            content.write(NEWLINE)

        content.write(b'--' + BOUNDARY + b'--' + NEWLINE + NEWLINE)
        content_type = ('multipart/form-data; boundary=%s'
                        % BOUNDARY.decode('utf-8'))

        return content_type, content.getvalue()

    def _make_mime_boundary(self):
        """Create a mime boundary.

        This exists because mimetools.choose_boundary() is gone in Python 3.x,
        and email.generator._make_boundary isn't really appropriate to use
        here.
        """
        fmt = '%%0%dd' % len(repr(sys.maxsize - 1))
        token = random.randrange(sys.maxsize)
        return (b'=' * 15) + (fmt % token).encode('utf-8') + b'=='


class Request(URLRequest):
    """A request which contains a method attribute."""
    def __init__(self, url, body=b'', headers={}, method='PUT'):
        normalized_headers = {
            str(key): str(value)
            for key, value in six.iteritems(headers)
        }

        URLRequest.__init__(self, str(url), body, normalized_headers)
        self.method = str(method)

    def get_method(self):
        return self.method


class PresetHTTPAuthHandler(BaseHandler):
    """Handler that presets the use of HTTP Basic Auth."""
    handler_order = 480  # After Basic auth

    AUTH_HEADER = 'Authorization'

    def __init__(self, url, password_mgr):
        self.url = url
        self.password_mgr = password_mgr
        self.used = False

    def reset(self, username, password):
        self.password_mgr.rb_user = username
        self.password_mgr.rb_pass = password
        self.used = False

    def http_request(self, request):
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


class ReviewBoardHTTPErrorProcessor(HTTPErrorProcessor):
    """Processes HTTP error codes.

    Python's built-in error processing understands 2XX responses as successful,
    but processes 3XX as an error. This handler ensures that all valid
    responses from the API are processed as such.
    """

    def http_response(self, request, response):
        if not (200 <= response.code < 300 or
                response.code == NOT_MODIFIED):
            response = self.parent.error('http', request, response,
                                         response.code, response.msg,
                                         response.info())

        return response

    https_response = http_response


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

    def __init__(self, *args, **kwargs):
        """Initialize the Basic Auth handler.

        Args:
            *args (tuple):
                Positional arguments to pass to the parent class.

            **kwargs (dict):
                Keyword arguments to pass to the parent class.
        """
        HTTPBasicAuthHandler.__init__(self, *args, **kwargs)

        self._tried_login = False
        self._otp_token_method = None
        self._otp_token_attempts = 0
        self._last_otp_token = None

    def http_error_auth_reqed(self, authreq, host, req, headers):
        """Handle an HTTP 401 Unauthorized from an API request.

        This will start by checking whether a two-factor authentication
        token is required by the server, and which method it will be sent
        by (SMS or token generator application), before handing back to the
        parent class, which will then call into our custom
        :py:meth:`retry_http_basic_auth`.

        Args:
            authreq (unicode):
                The authentication request type.

            host (unicode):
                The URL being accessed.

            req (rbtools.api.request.Request):
                The API request being made.

            headers (dict):
                The headers sent in the Unauthorized error response.

        Returns:
            httplib.HTTPResponse:
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

    def retry_http_basic_auth(self, host, request, realm):
        """Attempt another HTTP Basic Auth request.

        This will determine if another request should be made (based on
        previous attempts and 2FA requirements. Based on this, it may make
        another attempt.

        Args:
            host (unicode):
                The URL being accessed.

            request (rbtools.api.request.Request):
                The API request being made.

            realm (unicode):
                The Basic Auth realm, which will be used to look up any
                stored passwords.

        Returns:
            httplib.HTTPResponse:
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
            otp_token = (
                self.passwd.get_otp_token(request.get_full_url(),
                                          self._otp_token_method)
                .encode('utf-8')
            )
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


class ReviewBoardHTTPPasswordMgr(HTTPPasswordMgr):
    """Adds HTTP authentication support for URLs."""

    def __init__(self, reviewboard_url, rb_user=None, rb_pass=None,
                 api_token=None, auth_callback=None, otp_token_callback=None):
        HTTPPasswordMgr.__init__(self)
        self.passwd = {}
        self.rb_url = reviewboard_url
        self.rb_user = rb_user
        self.rb_pass = rb_pass
        self.api_token = api_token
        self.auth_callback = auth_callback
        self.otp_token_callback = otp_token_callback

    def find_user_password(self, realm, uri):
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
            # handlers are global), fall back to standard password management.
            return HTTPPasswordMgr.find_user_password(self, realm, uri)

    def get_otp_token(self, uri, method):
        if self.otp_token_callback:
            return self.otp_token_callback(uri, method)


def create_cookie_jar(cookie_file=None):
    """Return a cookie jar backed by cookie_file

    If cooie_file is not provided, we will default it. If the
    cookie_file does not exist, we will create it with the proper
    permissions.

    In the case where we default cookie_file, and it does not exist,
    we will attempt to copy the .post-review-cookies.txt file.
    """
    home_path = get_home_path()

    if not cookie_file:
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


class ReviewBoardServer(object):
    """Represents a Review Board server we are communicating with.

    Provides methods for executing HTTP requests on a Review Board
    server's Web API.

    The ``auth_callback`` parameter can be used to specify a callable
    which will be called when authentication fails. This callable will
    be passed the realm, and url of the Review Board server and should
    return a 2-tuple of username, password. The user can be prompted
    for their credentials using this mechanism.
    """
    def __init__(self, url, cookie_file=None, username=None, password=None,
                 api_token=None, agent=None, session=None, disable_proxy=False,
                 auth_callback=None, otp_token_callback=None,
                 verify_ssl=True, save_cookies=True, ext_auth_cookies=None):
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
                rest={'HttpOnly': None})
            self.cookie_jar.set_cookie(cookie)

            if self.save_cookies:
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

        handlers = []

        if not verify_ssl:
            context = ssl._create_unverified_context()
            handlers.append(HTTPSHandler(context=context))

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
            self.agent = ('RBTools/' + get_package_version()).encode('utf-8')

        opener = build_opener(*handlers)
        opener.addheaders = [
            (str('User-agent'), str(self.agent)),
        ]
        install_opener(opener)

        self._cache = None
        self._urlopen = urlopen

    def enable_cache(self, cache_location=None, in_memory=False):
        """Enable caching for all future HTTP requests.

        The cache will be created at the default location if none is provided.

        If the in_memory parameter is True, the cache will be created in memory
        instead of on disk. This overrides the cache_location parameter.
        """
        if not self._cache:
            self._cache = APICache(create_db_in_memory=in_memory,
                                   db_location=cache_location)

            self._urlopen = self._cache.make_request

    def login(self, username, password):
        """Reset the user information"""
        self.preset_auth_handler.reset(username, password)

    def logout(self):
        """Logs the user out of the session."""
        self.preset_auth_handler.reset(None, None)
        self.make_request(HttpRequest('%ssession/' % self.url,
                                      method='DELETE'))
        self.cookie_jar.clear(self.domain)

        if self.save_cookies:
            self.cookie_jar.save()

    def process_error(self, http_status, data):
        """Processes an error, raising an APIError with the information."""
        # In Python 3, the data can be bytes, not str, and json.loads
        # explicitly requires decoded strings.
        data = force_unicode(data)

        try:
            rsp = json_loads(data)

            assert rsp['stat'] == 'fail'

            logging.debug('Got API Error %d (HTTP code %d): %s',
                          rsp['err']['code'], http_status, rsp['err']['msg'])
            logging.debug('Error data: %r', rsp)

            raise create_api_error(http_status, rsp['err']['code'], rsp,
                                   rsp['err']['msg'])
        except ValueError:
            logging.debug('Got HTTP error: %s: %s', http_status, data)
            raise APIError(http_status, None, None, data)

    def make_request(self, request):
        """Perform an http request.

        The request argument should be an instance of
        'rbtools.api.request.HttpRequest'.
        """
        try:
            content_type, body = request.encode_multipart_formdata()
            headers = request.headers

            if body:
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
                self.cookie_jar.save()
            except IOError:
                pass

        return rsp
