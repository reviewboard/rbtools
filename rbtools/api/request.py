import base64
import cookielib
import mimetools
import mimetypes
from StringIO import StringIO
import urllib
import urllib2
from urlparse import urlparse, urlunparse

from rbtools import get_package_version
from rbtools.api.errors import APIError, ServerInterfaceError

try:
    # Specifically import json_loads, to work around some issues with
    # installations containing incompatible modules named "json".
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads

try:
    # In python 2.6, parse_qsl was deprectated in cgi, and
    # moved to urlparse.
    from urlparse import parse_qsl
except ImportError:
    from cgi import parse_qsl


RB_COOKIE_NAME = 'rbsessionid'


class HttpRequest(object):
    """High-level HTTP-request object."""
    def __init__(self, url, method='GET', query_args={}):
        self.method = method
        self.headers = {}
        self._fields = {}
        self._files = {}

        # Replace all underscores in each query argument
        # key with dashes.
        query_args = dict([
            (key.replace('_', '-'), value)
            for key, value in query_args.iteritems()
        ])

        # Add the query arguments to the url
        # TODO: Make work with Python < 2.6. In 2.6
        # parse_qsl was moved from cgi to urlparse.
        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update(query_args)
        url_parts[4] = urllib.urlencode(query)
        self.url = urlunparse(url_parts)

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
        """ Encodes data for use in an HTTP request.

        Parameters:
            fields - the fields to be encoded.  This should be a dict in a
                     key:value format
            files  - the files to be encoded.  This should be a dict in a
                     key:dict, filename:value and content:value format
        """
        if not (self._fields or self._files):
            return None, None

        NEWLINE = '\r\n'
        BOUNDARY = mimetools.choose_boundary()
        content = StringIO()

        for key in self._fields:
            content.write('--' + BOUNDARY + NEWLINE)
            content.write('Content-Disposition: form-data; name="%s"' % key)
            content.write(NEWLINE + NEWLINE)
            content.write(str(self._fields[key]) + NEWLINE)

        for key in self._files:
            filename = self._files[key]['filename']
            value = self._files[key]['content']
            mime_type = (mimetypes.guess_type(filename)[0] or
                         'application/octet-stream')
            content.write('--' + BOUNDARY + NEWLINE)
            content.write('Content-Disposition: form-data; name="%s"; ' % key)
            content.write('filename="%s"' % filename + NEWLINE)
            content.write('Content-Type: %s' % mime_type + NEWLINE)
            content.write('Content-Transfer-Encoding: base64' + NEWLINE)
            content.write(NEWLINE)
            content.write(base64.b64encode(value).decode())
            content.write(NEWLINE)

        content.write('--' + BOUNDARY + '--' + NEWLINE + NEWLINE)
        content_type = 'multipart/form-data; boundary=%s' % BOUNDARY

        return content_type, content.getvalue()


class Request(urllib2.Request):
    """A request which contains a method attribute."""
    def __init__(self, url, body='', headers={}, method="PUT"):
        urllib2.Request.__init__(self, url, body, headers)
        self.method = method

    def get_method(self):
        return self.method


class PresetHTTPAuthHandler(urllib2.BaseHandler):
    """urllib2 handler that presets the use of HTTP Basic Auth."""
    handler_order = 480  # After Basic auth

    def __init__(self, url, password_mgr):
        self.url = url
        self.password_mgr = password_mgr
        self.used = False

    def reset(self, username, password):
        self.password_mgr.rb_user = username
        self.password_mgr.rb_pass = password
        self.used = False

    def http_request(self, request):
        if not self.used and self.password_mgr.rb_user:
            # Note that we call password_mgr.find_user_password to get the
            # username and password we're working with.
            username, password = \
                self.password_mgr.find_user_password('Web API', self.url)
            raw = '%s:%s' % (username, password)
            request.add_header(
                urllib2.HTTPBasicAuthHandler.auth_header,
                'Basic %s' % base64.b64encode(raw).strip())
            self.used = True

        return request

    https_request = http_request


class ReviewBoardHTTPErrorProcessor(urllib2.HTTPErrorProcessor):
    """Processes HTTP error codes.

    Python 2.6 gets HTTP error code processing right, but 2.4 and 2.5
    only accepts HTTP 200 and 206 as success codes. This handler
    ensures that anything in the 200 range is a success.
    """
    def http_response(self, request, response):
        if not (200 <= response.code < 300):
            response = self.parent.error('http', request, response,
                                         response.code, response.msg,
                                         response.info())

        return response

    https_response = http_response


class ReviewBoardHTTPBasicAuthHandler(urllib2.HTTPBasicAuthHandler):
    """Custom Basic Auth handler that doesn't retry excessively.

    urllib2's HTTPBasicAuthHandler retries over and over, which is
    useless. This subclass only retries once to make sure we've
    attempted with a valid username and password. It will then fail so
    we can use our own retry handler.
    """
    def __init__(self, *args, **kwargs):
        urllib2.HTTPBasicAuthHandler.__init__(self, *args, **kwargs)
        self._retried = False
        self._lasturl = ""

    def retry_http_basic_auth(self, *args, **kwargs):
        if self._lasturl != args[0]:
            self._retried = False

        self._lasturl = args[0]

        if not self._retried:
            self._retried = True
            self.retried = 0
            response = urllib2.HTTPBasicAuthHandler.retry_http_basic_auth(
                self, *args, **kwargs)

            if response.code != 401:
                self._retried = False

            return response
        else:
            return None


class ReviewBoardHTTPPasswordMgr(urllib2.HTTPPasswordMgr):
    """Adds HTTP authentication support for URLs.

    Python 2.4's password manager has a bug in http authentication
    when the target server uses a non-standard port.  This works
    around that bug on Python 2.4 installs.

    See: http://bugs.python.org/issue974757
    """
    def __init__(self, reviewboard_url, rb_user=None, rb_pass=None):
        self.passwd = {}
        self.rb_url = reviewboard_url
        self.rb_user = rb_user
        self.rb_pass = rb_pass

    def find_user_password(self, realm, uri):
        if realm == 'Web API':
            return self.rb_user, self.rb_pass
        else:
            # If this is an auth request for some other domain (since HTTP
            # handlers are global), fall back to standard password management.
            return urllib2.HTTPPasswordMgr.find_user_password(self, realm, uri)


class ReviewBoardServer(object):
    """Represents a Review Board server we are communicating with.

    Provides methods for executing HTTP requests on a Review Board
    server's Web API.
    """
    def __init__(self, url, cookie_file, username=None, password=None,
                 agent=None, session=None):
        self.url = url
        if self.url[-1] != '/':
            self.url += '/'
        self.cookie_file = cookie_file
        self.cookie_jar = cookielib.MozillaCookieJar(self.cookie_file)

        if self.cookie_file:
            try:
                self.cookie_jar.load(self.cookie_file, ignore_expires=True)
            except IOError:
                pass

        if session:
            parsed_url = urlparse(url)
            # Get the cookie domain from the url. If the domain
            # does not contain a '.' (e.g. 'localhost'), we assume
            # it is a local domain and suffix it (See RFC 2109).
            domain = parsed_url.hostname
            if domain.count('.') < 1:
                domain = "%s.local" % domain

            cookie = cookielib.Cookie(
                version=0,
                name=RB_COOKIE_NAME,
                value=session,
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=True,
                domain_initial_dot=True,
                path=parsed_url.path,
                path_specified=True,
                secure=False,
                expires=None,
                discard=False,
                comment=None,
                comment_url=None,
                rest={'HttpOnly': None})
            self.cookie_jar.set_cookie(cookie)
            self.cookie_jar.save()

        # Set up the HTTP libraries to support all of the features we need.
        password_mgr = ReviewBoardHTTPPasswordMgr(self.url,
                                                  username,
                                                  password)
        self.preset_auth_handler = PresetHTTPAuthHandler(self.url,
                                                         password_mgr)

        handlers = []

        handlers += [
            urllib2.HTTPCookieProcessor(self.cookie_jar),
            ReviewBoardHTTPBasicAuthHandler(password_mgr),
            urllib2.HTTPDigestAuthHandler(password_mgr),
            self.preset_auth_handler,
            ReviewBoardHTTPErrorProcessor(),
        ]

        if agent:
            self.agent = agent
        else:
            self.agent = 'RBTools/' + get_package_version()

        opener = urllib2.build_opener(*handlers)
        opener.addheaders = [
            ('User-agent', self.agent),
        ]
        urllib2.install_opener(opener)

    def login(self, username, password):
        """Reset the user information"""
        self.preset_auth_handler.reset(username, password)

    def process_error(self, http_status, data):
        """Processes an error, raising an APIError with the information."""
        try:
            rsp = json_loads(data)

            assert rsp['stat'] == 'fail'

            raise APIError(http_status, rsp['err']['code'], rsp,
                           rsp['err']['msg'])
        except ValueError:
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

            r = Request(request.url, body, headers, request.method)
            rsp = urllib2.urlopen(r)
        except urllib2.HTTPError, e:
            self.process_error(e.code, e.read())
        except urllib2.URLError, e:
            raise ServerInterfaceError("%s" % e.reason)

        try:
            self.cookie_jar.save(self.cookie_file)
        except IOError:
            pass

        return rsp
