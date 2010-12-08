import base64
import cookielib
import mimetools
import os
import re
import urllib
import urllib2
from urlparse import urlparse

from rbtools import get_package_version, get_version_string
from rbtools.api.errors import *
from rbtools.commands.utils import *

try:
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads


class RequestWithMethod(urllib2.Request):
    """
    Wrapper class for urllib2.Request.  This allows for using PUT
    and DELETE, in addition to POST and GET.
    """
    def __init__(self, method, *args, **kwargs):
        """
        Parameters:
            method   - the HTTP request method (ie. POST, PUT, GET, DELETE)
            url      - the address to make the request on
            data     - the data to be used as the body of the request.  This
                       should be un-encoded and in a dict key:value format.
            headers  - the data to be used in the header of the request.  This
                       should be un-encoded and in a dict key:value format.
        """
        self._method = method
        urllib2.Request.__init__(self, *args, **kwargs)

    def get_method(self):
        return self._method or super(RequestWithMethod, self).get_method()


class ReviewBoardHTTPPasswordMgr(urllib2.HTTPPasswordMgr):
    """ Adds HTTP authentication support for URLs.

    Python 2.4's password manager has a bug in http authentication when the
    target server uses a non-standard port.  This works around that bug on
    Python 2.4 installs. This also allows post-review to prompt for passwords
    in a consistent way.

    See: http://bugs.python.org/issue974757
    """
    def __init__(self, reviewboard_url, password_inputer=None):
        self.passwd = {}
        self.rb_url = reviewboard_url
        self.rb_user = None
        self.rb_pass = None

        if password_inputer:
            if isinstance(password_inputer, ReviewBoardPasswordInputer):
                self.password_inputer = password_inputer
            else:
                raise InvalidPasswordInputerError(
                    'The password inputer is not a ReviewBoardPasswordInputer')
        else:
            self.password_inputer = DefaultPasswordInputer()

    def find_user_password(self, realm, uri):
        if uri.startswith(self.rb_url):
            if self.rb_user is None or self.rb_pass is None:
                self.rb_user, self.rb_pass = \
                    self.password_inputer.get_user_password(realm,
                                                            urlparse(uri)[1])

            return self.rb_user, self.rb_pass
        else:
            # If this is an auth request for some other domain (since HTTP
            # handlers are global), fall back to standard password management.
            return urllib2.HTTPPasswordMgr.find_user_password(self, realm, uri)


class ServerInterface(object):
    """ An object used to make HTTP requests to a ReviewBoard server.

    A class which performs basic communication with a ReviewBoard server and
    tracks cookie information.
    """
    def __init__(self, server_url, cookie_path_file, password_mgr=None):
        self.server_url = server_url

        if os.path.isfile(cookie_path_file):
            self.cookie_file = cookie_path_file
        else:
            self.cookie_file = os.path.join(
                os.path.split(cookie_path_file)[0], '.default_cookie')

        if password_mgr and \
            isinstance(password_mgr, ReviewBoardHTTPPasswordMgr):
            self.password_mgr = password_mgr
        else:
            self.password_mgr = ReviewBoardHTTPPasswordMgr(self.server_url)

        self.cookie_jar = cookielib.MozillaCookieJar(self.cookie_file)

        if os.path.isfile(self.cookie_file):
            self.cookie_jar.load()

        cookie_handler = urllib2.HTTPCookieProcessor(self.cookie_jar)
        basic_auth_handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        digest_auth_handler = urllib2.HTTPDigestAuthHandler(self.password_mgr)
        opener = urllib2.build_opener(cookie_handler,
                                      basic_auth_handler,
                                      digest_auth_handler)
        opener.addheaders = [
            ('User-agent', 'RBTools/' + get_package_version())
        ]
        urllib2.install_opener(opener)

    def is_logged_in(self):
        return self.has_valid_cookie()

    def _request(self, method, url, fields=None, files=None):
        """ Makes an HTTP request.

        Encodes the input fields and files and performs an HTTP request to the
        specified url using the specified method.  Any cookies set are stored.

        Parameteres:
            method      - the HTTP method to be used.  Accepts GET, POST,
                          PUT, and DELETE
            url         - the url to make the request to
            fields      - any data to be specified in the request.  This data
                          should be stored in a dict of key:value pairs
            files       - any files to be specified in the request.  This data
                          should be stored in a dict of key:dict,
                          filename:value and content:value structure

        Returns:
            The response from the server.  For more information view the
            ReviewBoard WebAPI Documentation.
        """
        content_type, body = self._encode_multipart_formdata(fields, files)
        headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(body))
        }

        if not self._valid_method(method):
            raise InvalidRequestMethod('An invalid HTTP method was used.')

        r = RequestWithMethod(method, url, body, headers)
        resource = urllib2.urlopen(r)
        self.cookie_jar.save(self.cookie_file)
        return resource.read()

    def get(self, url):
        """ Make an HTTP GET on the specified url returning the response.
        """
        return self._request('GET', url)

    def delete(self, url):
        """ Make an HTTP DELETE on the specified url returning the response.
        """
        return self._request('DELETE', url)

    def post(self, url, fields, files=None):
        """ Make an HTTP POST on the specified url returning the response.
        """
        return self._request('POST', url, fields, files)

    def put(self, url, fields, files=None):
        """ Make an HTTP PUT on the specified url returning the response.
        """
        return self._request('PUT', url, fields, files)

    def _encode_multipart_formdata(self, fields=None, files=None):
        """ Encodes data for use in an HTTP request.

        Paramaters:
            fields - the fields to be encoded.  This should be a dict in a
                     key:value format
            files  - the files to be encoded.  This should be a dict in a
                     key:dict, filename:value and content:value format
        """
        BOUNDARY = mimetools.choose_boundary()
        content = ""

        fields = fields or {}
        files = files or {}

        for key in fields:
            content += "--" + BOUNDARY + "\r\n"
            content += "Content-Disposition: form-data; name=\"%s\"\r\n" % key
            content += "\r\n"
            content += fields[key] + "\r\n"

        for key in files:
            filename = files[key]['filename']
            value = files[key]['content']
            content += "--" + BOUNDARY + "\r\n"
            content += "Content-Disposition: form-data; name=\"%s\"; " % key
            content += "filename=\"%s\"\r\n" % filename
            content += "\r\n"
            content += value + "\r\n"

        content += "--" + BOUNDARY + "--\r\n"
        content += "\r\n"

        content_type = "multipart/form-data; boundary=%s" % BOUNDARY

        return content_type, content

    def _valid_method(self, method):
        """ Checks if the method is a valid HTTP request for an RB server.

        Returns true if the specified method is a valid HTTP request method for
        the ServerInterface.  Valid methods are:
                                           POST
                                           PUT
                                           GET
                                           DELETE
        """
        return method == 'POST' or method == 'PUT' \
            or method == 'GET' or method == 'DELETE'

    def has_valid_cookie(self):
        """ Checks if a valid cookie already exists for to the RB server.

        Returns true if the ServerInterface can find and load a cookie for the
        server that has not expired.
        """
        parsed_url = urlparse(self.server_url)
        host = parsed_url[1]
        host = host.split(":")[0]
        path = parsed_url[2] or '/'

        try:
            self.cookie_jar.load(self.cookie_file, ignore_expires=True)

            try:
                cookie = self.cookie_jar._cookies[host][path]['rbsessionid']

                if not cookie.is_expired():
                    return True
            except KeyError, e:
                # Cookie file loaded, but no cookie for this server
                pass
        except IOError, e:
            # Couldn't load cookie file
            pass

        return False
