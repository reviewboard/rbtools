import cookielib
import mimetools
import urllib
import urllib2
import urlparse

from rbtools import get_package_version, get_version_string
from rbtools.commands.utils import DefaultPasswordInputer
from rbtools.api.errors import InvalidRequestMethodError

try:
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads

DEBUG = False


def debug(str):
    if DEBUG:
        print ">>>> %s" % str


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


class ServerInterface(object):
    """ An object used to make HTTP requests to a ReviewBoard server.

    A class which performs basic communication with a ReviewBoard server and
    tracks cookie information.
    """
    LOGIN_PATH = 'api/json/accounts/login/'

    def __init__(self, server_url, cookie_file=".cookie",
                 password_inputer=None):
        self.server_url = server_url
        self.cookie_file = cookie_file

        if password_inputer:
            self.password_inputer = password_inputer
        else:
            self.password_inputer = DefaultPasswordInputer()

        self.cookie_jar = cookielib.MozillaCookieJar(self.cookie_file)
        self.cookie_handler = urllib2.HTTPCookieProcessor(self.cookie_jar)
        self.user = None
        opener = urllib2.build_opener(self.cookie_handler)
        opener.addheaders = [
            ('User-agent', 'RBTools/' + get_package_version())
        ]
        urllib2.install_opener(opener)

    def login(self, username=None, password=None):
        if self.has_valid_cookie():
            return True
        else:
            username, password = self.password_inputer.get_username_password()
            self.user = username

            resp = self.post(self.server_url + self.LOGIN_PATH,
                            {'username': self.user, 'password': password})
            data = json_loads(resp)

            if data['stat'] == 'ok':
                return True

        return False

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

    def _request2(self, method, url, fields=None, files=None):
        """
        WORK IN PROGRESS - SAME AS _request BUT USING A DIFFERENT METHOD
        TO ENCODE

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
        if fields:
            body = urllib.urlencode(fields)
        else:
            body = ""

        headers = {
            'Content-Length': str(len(body))
        }

        if not self._valid_method(method):
            raise APIError(APIError.INVALID_REQUEST_METHOD,
                           'An invalid HTTP method was used')

        try:
            debug("_requesting with the header: %s" % headers)
            debug("and data: %s" % body)
            r = RequestWithMethod(method, url, body, headers)
            resource = urllib2.urlopen(r)
            self.cookie_jar.save(self.cookie_file)
            return resource.read()
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            # Re-raise so callers can interpret it.
            raise e

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
        parsed_url = urlparse.urlparse(self.server_url)
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
