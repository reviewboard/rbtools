import urllib2
import urllib
import cookielib
import getpass
import mimetools
from rbtools import get_package_version, get_version_string
try:
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads


class RequestWithMethod(urllib2.Request):
    """
    Wrapper class for urllib2.Request.  This allows for using PUT
    and DELETE, in addition to POST and GET.
    """
    def __init__(self, method, url, data=None, headers={},\
        """
        Parameters:
            method   - the HTTP request method (ie. POST, PUT, GET, DELETE)
            url      - the address to make the request on
            data     - the data to be used as the body of the request.  This 
                       should be un-encoded and in a dict key:value format.
            headers  - the data to be used in the header of the request.  This
                       should be un-encoded and in a dict key:value format.
        """
        origin_req_host=None, unverifiable=False):
        self._method = method
        urllib2.Request.__init__(self, url, data, headers,\
                 origin_req_host, unverifiable)

    def get_method(self):
        if self._method:
            return self._method
        else:
            return urllib2.Request.get_method(self)


class APIError(Exception):
    INVALID_REQUEST_METHOD = -1

    def __init__(self, http_status, error_code, rsp=None, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.http_status = http_status
        self.error_code = error_code
        self.rsp = rsp

    def __str__(self):
        code_str = "HTTP %d" % self.http_status

        if self.error_code:
            code_str += ', API Error %d' % self.error_code

        if self.rsp and 'err' in self.rsp:
            return '%s (%s)' % (self.rsp['err']['msg'], code_str)
        else:
            return code_str


class ServerInterface(object):
    """
    A class which performs basic communication with a ReviewBoard server and
    tracks cookie information.
    """

    def __init__(self, cookie_file = None):
        self.cookie_file = cookie_file
        self.cookie_jar = cookielib.MozillaCookieJar(self.cookie_file)
        cookie_handler = urllib2.HTTPCookieProcessor(self.cookie_jar)
        opener = urllib2.build_opener(cookie_handler)
        opener.addheaders = [('User-agent', 'RBTools/' + get_package_version())]
        urllib2.install_opener(opener)

    def process_error(self, http_status, data):
        """Processes an error, raising an APIError with the information."""
        try:
            rsp = json_loads(data)
            print rsp
            assert rsp['stat'] == 'fail'

            raise APIError(http_status, rsp['err']['code'], rsp,
                rsp['err']['msg'])
        except ValueError:
            pass
            #debug("Got HTTP error: %s: %s" % (http_status, data))
    
    def _request(self, method, url, fields=None, files=None, return_json=True):
        """
        Encodes the input fields and files and performs an HTTP request to the
        specified url using the specified method.  Any cookies set are stored.

        Parameteres:
            method      - the HTTP method to be used.  Accepts GET, POST,
                          PUT, and DELETE
            url         - the url to make the request to
            fields      - any data to be specified in the request.  This data
                          should be stored in a dict of key:value pairs 
            files       - any files to be specified in the request.  This data
                          should be stored in a dict of key:dict, filename:value
                          and content:value structure
            return_json - a boolean to specify the format of the data to be
                          returned.  If this value is set to False xml is 
                          returned.

        Returns:
            The response from the server in the format specified.  For more 
            information view the ReviewBoard WebAPI Documentation.
        """
        content_type, body = self._encode_multipart_formdata(fields, files)
        print body
        headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(body))
        }

        if not return_json:
            headers['Accept'] = 'application/xml'

        if not self._valid_method(method):
            raise APIError(APIError.INVALID_REQUEST_METHOD, 
                'An invalid HTTP method was used')

        try:
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

    def _request2(self, method, url, fields=None, files=None, return_json=True):
        """
        WORK IN PROGRESS - SAME AS _request BUT USING A DIFFERENT METHOD TO ENCODE

        Encodes the input fields and files and performs an HTTP request to the
        specified url using the specified method.  Any cookies set are stored.

        Parameteres:
            method      - the HTTP method to be used.  Accepts GET, POST,
                          PUT, and DELETE
            url         - the url to make the request to
            fields      - any data to be specified in the request.  This data
                          should be stored in a dict of key:value pairs 
            files       - any files to be specified in the request.  This data
                          should be stored in a dict of key:dict, filename:value
                          and content:value structure
            return_json - a boolean to specify the format of the data to be
                          returned.  If this value is set to False xml is 
                          returned.

        Returns:
            The response from the server in the format specified.  For more 
            information view the ReviewBoard WebAPI Documentation.
        """
        body = urllib.urlencode(fields)
        print body
        headers = {
            'Content-Length': str(len(body))
        }

        if not return_json:
            headers['Accept'] = 'application/xml'

        if not self._valid_method(method):
            raise APIError(APIError.INVALID_REQUEST_METHOD, 
                'An invalid HTTP method was used')

        try:
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

    def get(self, url, return_json=True):
        """
        Make an HTTP GET on the specified url, returning either json or xml
        """
        return self._request('GET', url, return_json=return_json)

    def delete(self, url, return_json=True):
        """
        Make an HTTP DELETE on the specified url, returning either json or xml
        """
        return self._request('DELETE', url, return_json=return_json)

    def post(self, url, fields, files=None, return_json=True):
        """
        Make an HTTP POST on the specified url with the specified data,
        returning either json or xml
        """
        return self._request('POST', url, fields, files, return_json) 

    def put(self, url, fields, files=None, return_json=True):
        """
        Make an HTTP PUT on the specified url with the specified data,
        returning either json or xml
        """
        return self._request('PUT', url, fields, files, return_json)

    def _encode_multipart_formdata(self, fields=None, files=None):
        """
        Encodes data for use in an HTTP request. 

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
            print key
            print fields[key]
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
        """
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
        """
        Returns true if the ServerInterface can find and load a cookie for the
        server that has not expired.
        """
        #TO DO
