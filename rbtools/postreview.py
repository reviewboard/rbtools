#!/usr/bin/env python
import base64
import cookielib
import getpass
import httplib
import logging
import mimetools
import os
import platform
import re
import signal
import sys
import urllib2
from optparse import OptionParser
from pkg_resources import parse_version
from urlparse import urljoin, urlparse

from rbtools import get_package_version, get_version_string
from rbtools.api.capabilities import Capabilities
from rbtools.api.errors import APIError, create_api_error
from rbtools.clients import print_clients, scan_usable_client
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.plastic import PlasticClient
from rbtools.utils.diffs import get_diff
from rbtools.utils.filesystem import get_config_value, load_config_files
from rbtools.utils.process import die

try:
    # Specifically import json_loads, to work around some issues with
    # installations containing incompatible modules named "json".
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads


options = None
configs = []

ADD_REPOSITORY_DOCS_URL = (
    'http://www.reviewboard.org/docs/manual/dev/admin/configuration/'
    'repositories/')


class HTTPRequest(urllib2.Request):
    def __init__(self, url, body='', headers={}, method="PUT"):
        urllib2.Request.__init__(self, url, body, headers)
        self.method = method

    def get_method(self):
        return self.method


class PresetHTTPAuthHandler(urllib2.BaseHandler):
    """urllib2 handler that conditionally presets the use of HTTP Basic Auth.

    This is used when specifying --username= on the command line. It will
    force an HTTP_AUTHORIZATION header with the user info, asking the user
    for any missing info beforehand. It will then try this header for that
    first request.

    It will only do this once.
    """
    handler_order = 480  # After Basic auth

    def __init__(self, url, password_mgr):
        self.url = url
        self.password_mgr = password_mgr
        self.used = False

    def reset(self):
        self.password_mgr.rb_user = options.http_username
        self.password_mgr.rb_pass = options.http_password
        self.used = False

    def http_request(self, request):
        if options.username and not self.used:
            # Note that we call password_mgr.find_user_password to get the
            # username and password we're working with. This allows us to
            # prompt if, say, --username was specified but --password was not.
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

    Python 2.6 gets HTTP error code processing right, but 2.4 and 2.5 only
    accepts HTTP 200 and 206 as success codes. This handler ensures that
    anything in the 200 range is a success.
    """
    def http_response(self, request, response):
        if not (httplib.OK <= response.code < httplib.MULTIPLE_CHOICES):
            response = self.parent.error('http', request, response,
                                         response.code, response.msg,
                                         response.info())

        return response

    https_response = http_response


class ReviewBoardHTTPBasicAuthHandler(urllib2.HTTPBasicAuthHandler):
    """Custom Basic Auth handler that doesn't retry excessively.

    urllib2's HTTPBasicAuthHandler retries over and over, which is useless.
    This subclass only retries once to make sure we've attempted with a
    valid username and password. It will then fail so we can use
    tempt_fate's retry handler.
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

            if response and response.code != httplib.UNAUTHORIZED:
                self._retried = False

            return response
        else:
            return None


class ReviewBoardHTTPPasswordMgr(urllib2.HTTPPasswordMgr):
    """
    Adds HTTP authentication support for URLs.

    Python 2.4's password manager has a bug in http authentication when the
    target server uses a non-standard port.  This works around that bug on
    Python 2.4 installs. This also allows post-review to prompt for passwords
    in a consistent way.

    See: http://bugs.python.org/issue974757
    """
    def __init__(self, reviewboard_url, rb_user=None, rb_pass=None):
        urllib2.HTTPPasswordMgr.__init__(self)
        self.passwd = {}
        self.rb_url = reviewboard_url
        self.rb_user = rb_user
        self.rb_pass = rb_pass

    def find_user_password(self, realm, uri):
        if realm == 'Web API':
            if self.rb_user is None or self.rb_pass is None:
                if options.diff_filename == '-':
                    die('HTTP authentication is required, but cannot be '
                        'used with --diff-filename=-')

                print "==> HTTP Authentication Required"
                print 'Enter authorization information for "%s" at %s' % \
                    (realm, urlparse(uri)[1])

                if not self.rb_user:
                    # getpass will write its prompt to stderr but raw_input
                    # writes to stdout. See bug 2831.
                    sys.stderr.write('Username: ')
                    self.rb_user = raw_input()

                if not self.rb_pass:
                    self.rb_pass = getpass.getpass('Password: ')

            return self.rb_user, self.rb_pass
        else:
            # If this is an auth request for some other domain (since HTTP
            # handlers are global), fall back to standard password management.
            return urllib2.HTTPPasswordMgr.find_user_password(self, realm, uri)


class ReviewBoardServer(object):
    """
    An instance of a Review Board server.
    """
    def __init__(self, url, info, cookie_file):
        self.url = url
        if self.url[-1] != '/':
            self.url += '/'
        self._info = info
        self._server_info = None
        self.capabilities = None
        self.root_resource = None
        self.deprecated_api = False
        self.rb_version = "0.0.0.0"
        self.cookie_file = cookie_file
        self.cookie_jar = cookielib.MozillaCookieJar(self.cookie_file)
        self.deprecated_api = False
        self.root_resource = None

        if self.cookie_file:
            try:
                self.cookie_jar.load(self.cookie_file, ignore_expires=True)
            except IOError:
                pass

        # Set up the HTTP libraries to support all of the features we need.
        password_mgr = ReviewBoardHTTPPasswordMgr(self.url,
                                                  options.username,
                                                  options.password)
        self.preset_auth_handler = PresetHTTPAuthHandler(self.url,
                                                         password_mgr)

        handlers = []

        if options.disable_proxy:
            debug('Disabling HTTP(s) proxy support')
            handlers.append(urllib2.ProxyHandler({}))

        handlers += [
            urllib2.HTTPCookieProcessor(self.cookie_jar),
            ReviewBoardHTTPBasicAuthHandler(password_mgr),
            urllib2.HTTPDigestAuthHandler(password_mgr),
            self.preset_auth_handler,
            ReviewBoardHTTPErrorProcessor(),
        ]

        opener = urllib2.build_opener(*handlers)
        opener.addheaders = [
            ('User-agent', 'RBTools/' + get_package_version())
        ]
        urllib2.install_opener(opener)

    def check_api_version(self):
        """Checks the API version on the server to determine which to use."""
        try:
            root_resource = self.api_get('api/')
            rsp = self.api_get(root_resource['links']['info']['href'])

            self.rb_version = rsp['info']['product']['package_version']

            if parse_version(self.rb_version) >= parse_version('1.5.2'):
                self.deprecated_api = False
                self.root_resource = root_resource
                debug('Using the new web API')
                return True
        except APIError, e:
            if e.http_status not in (httplib.UNAUTHORIZED, httplib.NOT_FOUND):
                # We shouldn't reach this. If there's a permission denied
                # from lack of logging in, then the basic auth handler
                # should have hit it.
                #
                # However in some versions it wants you to be logged in
                # and returns an UNAUTHORIZED from the application after you've
                # done your http basic auth
                die("Unable to access the root /api/ URL on the server.")

                return False

        # This is an older Review Board server with the old API.
        self.deprecated_api = True
        debug('Using the deprecated Review Board 1.0 web API')
        return True

    def load_capabilities(self):
        """Loads the server capabilities."""
        info = self.api_get('api/info/')
        caps = None

        try:
            caps = info['info']['capabilities']
        except KeyError:
            # The capabilities list is left empty.
            pass

        self.capabilities = Capabilities(caps)

    def login(self, force=False):
        """
        Logs in to a Review Board server, prompting the user for login
        information if needed.
        """
        if (options.diff_filename == '-' and
            not (self.has_valid_cookie() or
                 (options.username and options.password))):
            die('Authentication information needs to be provided on '
                'the command line when using --diff-filename=-')

        if self.deprecated_api:
            print "==> Review Board Login Required"
            print "Enter username and password for Review Board at %s" % \
                  self.url

            if options.username:
                username = options.username
            elif options.submit_as:
                username = options.submit_as
            elif not force and self.has_valid_cookie():
                # We delay the check for a valid cookie until after looking
                # at args, so that it doesn't override the command line.
                return
            else:
                # getpass will write its prompt to stderr but raw_input
                # writes to stdout. See bug 2831.
                sys.stderr.write('Username: ')
                username = raw_input()

            if not options.password:
                password = getpass.getpass('Password: ')
            else:
                password = options.password

            debug('Logging in with username "%s"' % username)
            try:
                self.api_post('api/json/accounts/login/', {
                    'username': username,
                    'password': password,
                })
            except APIError, e:
                die("Unable to log in: %s" % e)

            debug("Logged in.")
        elif force:
            self.preset_auth_handler.reset()

    def has_valid_cookie(self):
        """
        Load the user's cookie file and see if they have a valid
        'rbsessionid' cookie for the current Review Board server.  Returns
        true if so and false otherwise.
        """
        try:
            parsed_url = urlparse(self.url)
            host = parsed_url[1]
            path = parsed_url[2] or '/'

            # Cookie files don't store port numbers, unfortunately, so
            # get rid of the port number if it's present.
            host = host.split(":")[0]

            # Cookie files also append .local to bare hostnames
            if '.' not in host:
                host += '.local'

            debug("Looking for '%s %s' cookie in %s"
                  % (host, path, self.cookie_file))

            try:
                cookie = self.cookie_jar._cookies[host][path]['rbsessionid']

                if not cookie.is_expired():
                    debug("Loaded valid cookie -- no login required")
                    return True

                debug("Cookie file loaded, but cookie has expired")
            except KeyError:
                debug("Cookie file loaded, but no cookie for this server")
        except IOError, error:
            debug("Couldn't load cookie file: %s" % error)

        return False

    def new_review_request(self, changenum, submit_as=None):
        """
        Creates a review request on a Review Board server, updating an
        existing one if the changeset number already exists.

        If submit_as is provided, the specified user name will be recorded as
        the submitter of the review request (given that the logged in user has
        the appropriate permissions).
        """

        # If repository_path is a list, find a name in the list that's
        # registered on the server.
        if isinstance(self.info.path, list):
            repositories = self.get_repositories()

            debug("Repositories on Server: %s" % repositories)
            debug("Server Aliases: %s" % self.info.path)

            for repository in repositories:
                if repository['path'] in self.info.path:
                    self.info.path = repository['path']
                    break

            if isinstance(self.info.path, list):
                sys.stderr.write('\n')
                sys.stderr.write('There was an error creating this review '
                                 'request.\n')
                sys.stderr.write('\n')
                sys.stderr.write('There was no matching repository path'
                                 'found on the server.\n')
                sys.stderr.write('List of configured repositories:\n')

                for repository in repositories:
                    sys.stderr.write('\t%s\n' % repository['path'])

                sys.stderr.write('Unknown repository paths found:\n')

                for foundpath in self.info.path:
                    sys.stderr.write('\t%s\n' % foundpath)

                sys.stderr.write('Ask the administrator to add one of '
                                 'these repositories\n')
                sys.stderr.write('to the Review Board server.\n')
                sys.stderr.write('For information on adding repositories, '
                                 'please read\n')
                sys.stderr.write(ADD_REPOSITORY_DOCS_URL + '\n')
                die()

        repository = options.repository_url or self.info.path

        try:
            debug("Attempting to create review request on %s for %s" %
                  (repository, changenum))
            data = {}

            if changenum:
                data['changenum'] = changenum

            if submit_as:
                debug("Submitting the review request as %s" % submit_as)
                data['submit_as'] = submit_as

            if self.deprecated_api:
                data['repository_path'] = repository
                rsp = self.api_post('api/json/reviewrequests/new/', data)
            else:
                data['repository'] = repository

                links = self.root_resource['links']
                assert 'review_requests' in links
                review_request_href = links['review_requests']['href']
                rsp = self.api_post(review_request_href, data)
        except APIError, e:
            if e.error_code == 204:  # Change number in use
                rsp = e.rsp

                if options.diff_only:
                    # In this case, fall through and return to tempt_fate.
                    debug("Review request already exists.")
                else:
                    debug("Review request already exists. Updating it...")
                    self.update_review_request_from_changenum(
                        changenum, rsp['review_request'])
            elif e.error_code == 206:  # Invalid repository
                sys.stderr.write('\n')
                sys.stderr.write('There was an error creating this review '
                                 'request.\n')
                sys.stderr.write('\n')
                sys.stderr.write('The repository path "%s" is not in the\n' %
                                 self.info.path)
                sys.stderr.write('list of known repositories on the server.\n')
                sys.stderr.write('\n')
                sys.stderr.write('Ask the administrator to add this '
                                 'repository to the Review Board server.\n')
                sys.stderr.write('For information on adding repositories, '
                                 'please read\n')
                sys.stderr.write(ADD_REPOSITORY_DOCS_URL + '\n')
                die()
            else:
                raise e
        else:
            debug("Review request created")

        return rsp['review_request']

    def update_review_request_from_changenum(self, changenum, review_request):
        if self.deprecated_api:
            self.api_post(
                'api/json/reviewrequests/%s/update_from_changenum/'
                % review_request['id'])
        else:
            self.api_put(review_request['links']['self']['href'], {
                'changenum': review_request['changenum'],
            })

    def set_review_request_field(self, review_request, field, value):
        """
        Sets a field in a review request to the specified value.
        """
        rid = review_request['id']

        debug("Attempting to set field '%s' to '%s' for review request '%s'" %
              (field, value, rid))

        if self.deprecated_api:
            self.api_post('api/json/reviewrequests/%s/draft/set/' % rid, {
                field: value,
            })
        else:
            self.api_put(review_request['links']['draft']['href'], {
                field: value,
            })

    def get_review_request(self, rid):
        """
        Returns the review request with the specified ID.
        """
        if self.deprecated_api:
            url = 'api/json/reviewrequests/%s/' % rid
        else:
            url = '%s%s/' % (
                self.root_resource['links']['review_requests']['href'], rid)

        rsp = self.api_get(url)

        return rsp['review_request']

    def get_repositories(self):
        """
        Returns the list of repositories on this server.
        """
        if self.deprecated_api:
            rsp = self.api_get('api/json/repositories/')
            repositories = rsp['repositories']
        else:
            rsp = self.api_get(
                self.root_resource['links']['repositories']['href'])
            repositories = rsp['repositories']

            while 'next' in rsp['links']:
                rsp = self.api_get(rsp['links']['next']['href'])
                repositories.extend(rsp['repositories'])

        return repositories

    def get_repository_info(self, rid):
        """
        Returns detailed information about a specific repository.
        """
        if self.deprecated_api:
            url = 'api/json/repositories/%s/info/' % rid
        else:
            rsp = self.api_get(
                '%s%s/' % (self.root_resource['links']['repositories']['href'],
                           rid))
            url = rsp['repository']['links']['info']['href']

        rsp = self.api_get(url)

        return rsp['info']

    def save_draft(self, review_request):
        """
        Saves a draft of a review request.
        """
        if self.deprecated_api:
            self.api_post('api/json/reviewrequests/%s/draft/save/'
                          % review_request['id'])
        else:
            self.api_put(review_request['links']['draft']['href'], {
                'public': 1,
            })

        debug("Review request draft saved")

    def upload_diff(self, review_request, diff_content, parent_diff_content):
        """
        Uploads a diff to a Review Board server.
        """
        debug("Uploading diff, size: %d" % len(diff_content))

        if parent_diff_content:
            debug("Uploading parent diff, size: %d" % len(parent_diff_content))

        fields = {}
        files = {}

        if self.info.base_path:
            fields['basedir'] = self.info.base_path

        if options.basedir:
            fields['basedir'] = options.basedir

        files['path'] = {
            'filename': 'diff',
            'content': diff_content
        }

        if parent_diff_content:
            files['parent_diff_path'] = {
                'filename': 'parent_diff',
                'content': parent_diff_content
            }

        if self.deprecated_api:
            self.api_post('api/json/reviewrequests/%s/diff/new/' %
                          review_request['id'], fields, files)
        else:
            self.api_post(review_request['links']['diffs']['href'],
                          fields, files)

    def reopen(self, review_request):
        """
        Reopen discarded review request.
        """
        debug("Reopening")

        if self.deprecated_api:
            self.api_post('api/json/reviewrequests/%s/reopen/' %
                          review_request['id'])
        else:
            self.api_put(review_request['links']['self']['href'], {
                'status': 'pending',
            })

    def publish(self, review_request):
        """
        Publishes a review request.
        """
        debug("Publishing")

        if self.deprecated_api:
            self.api_post('api/json/reviewrequests/%s/publish/' %
                          review_request['id'])
        else:
            self.api_put(review_request['links']['draft']['href'], {
                'public': 1,
            })

    def _get_server_info(self):
        if not self._server_info:
            self._server_info = self._info.find_server_repository_info(self)

        return self._server_info

    info = property(_get_server_info)

    def process_json(self, data):
        """
        Loads in a JSON file and returns the data if successful. On failure,
        APIError is raised.
        """
        rsp = json_loads(data)

        if rsp['stat'] == 'fail':
            # With the new API, we should get something other than HTTP
            # 200 for errors, in which case we wouldn't get this far.
            assert self.deprecated_api
            self.process_error(200, data)

        return rsp

    def process_error(self, http_status, data):
        """Processes an error, raising an APIError with the information."""
        try:
            rsp = json_loads(data)

            assert rsp['stat'] == 'fail'

            debug("Got API Error %d (HTTP code %d): %s" %
                  (rsp['err']['code'], http_status, rsp['err']['msg']))
            debug("Error data: %r" % rsp)
            raise create_api_error(http_status, rsp['err']['code'], rsp)
        except ValueError:
            debug("Got HTTP error: %s: %s" % (http_status, data))
            raise APIError(http_status, None, None, data)

    def http_get(self, path):
        """
        Performs an HTTP GET on the specified path, storing any cookies that
        were set.
        """
        debug('HTTP GETting %s' % path)

        url = self._make_url(path)
        rsp = urllib2.urlopen(url).read()

        try:
            self.cookie_jar.save(self.cookie_file)
        except IOError, e:
            debug('Failed to write cookie file: %s' % e)
        return rsp

    def _make_url(self, path):
        """Given a path on the server returns a full http:// style url"""
        if path.startswith('http'):
            # This is already a full path.
            return path

        app = urlparse(self.url)[2]

        if path[0] == '/':
            url = urljoin(self.url, app[:-1] + path)
        else:
            url = urljoin(self.url, app + path)

        if not url.startswith('http'):
            url = 'http://%s' % url
        return url

    def api_get(self, path):
        """
        Performs an API call using HTTP GET at the specified path.
        """
        try:
            return self.process_json(self.http_get(path))
        except urllib2.HTTPError, e:
            self.process_error(e.code, e.read())

    def http_post(self, path, fields, files=None):
        """
        Performs an HTTP POST on the specified path, storing any cookies that
        were set.
        """
        if fields:
            debug_fields = fields.copy()
        else:
            debug_fields = {}

        if 'password' in debug_fields:
            debug_fields["password"] = "**************"
        url = self._make_url(path)
        debug('HTTP POSTing to %s: %s' % (url, debug_fields))

        content_type, body = self._encode_multipart_formdata(fields, files)
        headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(body))
        }

        try:
            if type(url) == unicode:
                url = url.encode('utf8')
            r = urllib2.Request(url, body, headers)
            data = urllib2.urlopen(r).read()
            try:
                self.cookie_jar.save(self.cookie_file)
            except IOError, e:
                debug('Failed to write cookie file: %s' % e)
            return data
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            try:
                debug(e.read())
            except AttributeError:
                pass

            die("Unable to access %s. The host path may be invalid\n%s"
                % (url, e))

    def http_put(self, path, fields):
        """
        Performs an HTTP PUT on the specified path, storing any cookies that
        were set.
        """
        url = self._make_url(path)
        debug('HTTP PUTting to %s: %s' % (url, fields))

        content_type, body = self._encode_multipart_formdata(fields, None)
        headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(body))
        }

        try:
            if type(url) == unicode:
                url = url.encode('utf8')
            r = HTTPRequest(url, body, headers, method='PUT')
            data = urllib2.urlopen(r).read()
            try:
                self.cookie_jar.save(self.cookie_file)
            except IOError, e:
                debug('Failed to write cookie file: %s' % e)
            return data
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            try:
                debug(e.read())
            except AttributeError:
                pass

            die("Unable to access %s. The host path may be invalid\n%s"
                % (url, e))

    def http_delete(self, path):
        """
        Performs an HTTP DELETE on the specified path, storing any cookies that
        were set.
        """
        url = self._make_url(path)
        debug('HTTP DELETing %s' % url)

        try:
            r = HTTPRequest(url, method='DELETE')
            data = urllib2.urlopen(r).read()
            try:
                self.cookie_jar.save(self.cookie_file)
            except IOError, e:
                debug('Failed to write cookie file: %s' % e)
            return data
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            try:
                debug(e.read())
            except AttributeError:
                pass

            die("Unable to access %s. The host path may be invalid\n%s"
                % (url, e))

    def api_post(self, path, fields=None, files=None):
        """
        Performs an API call using HTTP POST at the specified path.
        """
        try:
            return self.process_json(self.http_post(path, fields, files))
        except urllib2.HTTPError, e:
            self.process_error(e.code, e.read())

    def api_put(self, path, fields=None):
        """
        Performs an API call using HTTP PUT at the specified path.
        """
        try:
            return self.process_json(self.http_put(path, fields))
        except urllib2.HTTPError, e:
            self.process_error(e.code, e.read())

    def api_delete(self, path):
        """
        Performs an API call using HTTP DELETE at the specified path.
        """
        try:
            return self.process_json(self.http_delete(path))
        except urllib2.HTTPError, e:
            self.process_error(e.code, e.read())

    def _encode_multipart_formdata(self, fields, files):
        """
        Encodes data for use in an HTTP POST.
        """
        BOUNDARY = mimetools.choose_boundary()
        content = ""

        fields = fields or {}
        files = files or {}

        for key in fields:
            content += "--" + BOUNDARY + "\r\n"
            content += "Content-Disposition: form-data; name=\"%s\"\r\n" % key
            content += "\r\n"
            content += str(fields[key]) + "\r\n"

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


def debug(s):
    """
    Prints debugging information if post-review was run with --debug
    """
    if options and options.debug:
        print ">>> %s" % s


def tempt_fate(server, tool, changenum, diff_content=None,
               parent_diff_content=None, submit_as=None, retries=3):
    """
    Attempts to create a review request on a Review Board server and upload
    a diff. On success, the review request path is displayed.
    """
    try:
        if options.rid:
            review_request = server.get_review_request(options.rid)
            status = review_request['status']

            if status == 'submitted':
                die("Review request %s is marked as %s. In order to "
                    "update it, please reopen the request using the web "
                    "interface and try again." % (options.rid, status))
        else:
            review_request = server.new_review_request(changenum, submit_as)

        if options.target_groups:
            server.set_review_request_field(review_request, 'target_groups',
                                            options.target_groups)

        if options.target_people:
            server.set_review_request_field(review_request, 'target_people',
                                            options.target_people)

        if options.summary:
            server.set_review_request_field(review_request, 'summary',
                                            options.summary)

        if options.branch:
            server.set_review_request_field(review_request, 'branch',
                                            options.branch)

        if options.bugs_closed:     # append to existing list
            options.bugs_closed = options.bugs_closed.strip(", ")
            bug_set = (set(re.split("[, ]+", options.bugs_closed)) |
                       set(review_request['bugs_closed']))
            options.bugs_closed = ",".join(bug_set)
            server.set_review_request_field(review_request, 'bugs_closed',
                                            options.bugs_closed)

        if options.description:
            server.set_review_request_field(review_request, 'description',
                                            options.description)

        if options.testing_done:
            server.set_review_request_field(review_request, 'testing_done',
                                            options.testing_done)

        if options.change_description:
            server.set_review_request_field(review_request,
                                            'changedescription',
                                            options.change_description)
    except APIError, e:
        if e.error_code == 103:  # Not logged in
            retries = retries - 1

            # We had an odd issue where the server ended up a couple of
            # years in the future. Login succeeds but the cookie date was
            # "odd" so use of the cookie appeared to fail and eventually
            # ended up at max recursion depth :-(. Check for a maximum
            # number of retries.
            if retries >= 0:
                server.login(force=True)
                return tempt_fate(server, tool, changenum, diff_content,
                                  parent_diff_content, submit_as,
                                  retries=retries)

        if options.rid:
            die("Error getting review request %s: %s" % (options.rid, e))
        else:
            die("Error creating review request: %s" % e)

    if not server.info.supports_changesets or not options.change_only:
        try:
            server.upload_diff(review_request, diff_content,
                               parent_diff_content)
        except APIError, e:
            sys.stderr.write('\n')
            sys.stderr.write('Error uploading diff\n')
            sys.stderr.write('\n')

            if e.error_code == 101 and e.http_status == httplib.FORBIDDEN:
                die('You do not have permissions to modify this review '
                    'request\n')
            elif e.error_code == 219:
                sys.stderr.write('The generated diff file was empty. This '
                                 'usually means no files were\n')
                sys.stderr.write('modified in this change.\n')
                sys.stderr.write('\n')
                sys.stderr.write('Try running with --output-diff and --debug '
                                 'for more information.\n')
                sys.stderr.write('\n')

            die("Your review request still exists, but the diff is not " +
                "attached.")

    if options.reopen:
        server.reopen(review_request)

    if options.publish:
        server.publish(review_request)

    request_url = 'r/' + str(review_request['id']) + '/'
    review_url = urljoin(server.url, request_url)

    if not review_url.startswith('http'):
        review_url = 'http://%s' % review_url

    print "Review request #%s posted." % (review_request['id'],)
    print
    print review_url

    return review_url


def parse_options(args):
    parser = OptionParser(usage="%prog [-pond] [-r review_id] [changenum]",
                          version="RBTools " + get_version_string())

    parser.add_option("-p", "--publish",
                      dest="publish", action="store_true",
                      default=get_config_value(configs, 'PUBLISH', False),
                      help="publish the review request immediately after "
                           "submitting")
    parser.add_option("-r", "--review-request-id",
                      dest="rid", metavar="ID", default=None,
                      help="existing review request ID to update")
    parser.add_option("-o", "--open",
                      dest="open_browser", action="store_true",
                      default=get_config_value(configs, 'OPEN_BROWSER', False),
                      help="open a web browser to the review request page")
    parser.add_option("-n", "--output-diff",
                      dest="output_diff_only", action="store_true",
                      default=False,
                      help="outputs a diff to the console and exits. "
                           "Does not post")
    parser.add_option("--server",
                      dest="server",
                      default=get_config_value(configs, 'REVIEWBOARD_URL'),
                      metavar="SERVER",
                      help="specify a different Review Board server to use")
    parser.add_option("--disable-proxy",
                      action='store_true',
                      dest='disable_proxy',
                      default=not get_config_value(configs, 'ENABLE_PROXY',
                                                   True),
                      help="prevents requests from going through a proxy "
                           "server")
    parser.add_option("--diff-only",
                      dest="diff_only", action="store_true", default=False,
                      help="uploads a new diff, but does not update "
                           "info from changelist")
    parser.add_option("--reopen",
                      dest="reopen", action="store_true", default=False,
                      help="reopen discarded review request "
                           "after update")
    parser.add_option("--target-groups",
                      dest="target_groups",
                      default=get_config_value(configs, 'TARGET_GROUPS'),
                      help="names of the groups who will perform "
                           "the review")
    parser.add_option("--target-people",
                      dest="target_people",
                      default=get_config_value(configs, 'TARGET_PEOPLE'),
                      help="names of the people who will perform "
                           "the review")
    parser.add_option("--summary",
                      dest="summary", default=None,
                      help="summary of the review ")
    parser.add_option("--description",
                      dest="description", default=None,
                      help="description of the review ")
    parser.add_option("--description-file",
                      dest="description_file", default=None,
                      help="text file containing a description of the review")
    parser.add_option('-g', '--guess-fields',
                      dest="guess_fields", action="store_true",
                      default=get_config_value(configs, 'GUESS_FIELDS',
                                               False),
                      help="equivalent to --guess-summary --guess-description")
    parser.add_option("--guess-summary",
                      dest="guess_summary", action="store_true",
                      default=get_config_value(configs, 'GUESS_SUMMARY',
                                               False),
                      help="guess summary from the latest commit (bzr/git/"
                           "hg/hgsubversion only)")
    parser.add_option("--guess-description",
                      dest="guess_description", action="store_true",
                      default=get_config_value(configs, 'GUESS_DESCRIPTION',
                                               False),
                      help="guess description based on commits on this branch "
                           "(bzr/git/hg/hgsubversion only)")
    parser.add_option("--testing-done",
                      dest="testing_done", default=None,
                      help="details of testing done ")
    parser.add_option("--testing-done-file",
                      dest="testing_file", default=None,
                      help="text file containing details of testing done ")
    parser.add_option("--branch",
                      dest="branch",
                      default=get_config_value(configs, 'BRANCH'),
                      help="affected branch ")
    parser.add_option("--bugs-closed",
                      dest="bugs_closed", default=None,
                      help="list of bugs closed ")
    parser.add_option("--change-description", default=None,
                      help="description of what changed in this revision of "
                      "the review request when updating an existing request")
    parser.add_option("--revision-range",
                      dest="revision_range", default=None,
                      help="generate the diff for review based on given "
                           "revision range")
    parser.add_option("--submit-as",
                      dest="submit_as",
                      default=get_config_value(configs, 'SUBMIT_AS'),
                      metavar="USERNAME",
                      help="user name to be recorded as the author of the "
                           "review request, instead of the logged in user")
    parser.add_option("--username",
                      dest="username",
                      default=get_config_value(configs, 'USERNAME'),
                      metavar="USERNAME",
                      help="user name to be supplied to the reviewboard "
                           "server")
    parser.add_option("--password",
                      dest="password",
                      default=get_config_value(configs, 'PASSWORD'),
                      metavar="PASSWORD",
                      help="password to be supplied to the reviewboard server")
    parser.add_option("--change-only",
                      dest="change_only", action="store_true",
                      default=False,
                      help="updates info from changelist, but does "
                           "not upload a new diff (only available if your "
                           "repository supports changesets)")
    parser.add_option("--parent",
                      dest="parent_branch",
                      default=get_config_value(configs, 'PARENT_BRANCH'),
                      metavar="PARENT_BRANCH",
                      help="the parent branch this diff should be against "
                           "(only available if your repository supports "
                           "parent diffs)")
    parser.add_option("--tracking-branch",
                      dest="tracking",
                      default=get_config_value(configs, 'TRACKING_BRANCH'),
                      metavar="TRACKING",
                      help="Tracking branch from which your branch is derived "
                           "(git only, defaults to origin/master)")
    parser.add_option("--p4-client",
                      dest="p4_client",
                      default=get_config_value(configs, 'P4_CLIENT'),
                      help="the Perforce client name that the review is in")
    parser.add_option("--p4-port",
                      dest="p4_port",
                      default=get_config_value(configs, 'P4_PORT'),
                      help="the Perforce servers IP address that the review "
                           "is on")
    parser.add_option("--p4-passwd",
                      dest="p4_passwd",
                      default=get_config_value(configs, 'P4_PASSWD'),
                      help="the Perforce password or ticket of the user "
                           "in the P4USER environment variable")
    parser.add_option('--svn-changelist', dest='svn_changelist', default=None,
                      help='generate the diff for review based on a local SVN '
                           'changelist')
    parser.add_option("--repository-url",
                      dest="repository_url",
                      default=get_config_value(configs, 'REPOSITORY'),
                      help="the url for a repository for creating a diff "
                           "outside of a working copy (currently only "
                           "supported by Subversion with --revision-range or "
                           "--diff-filename and ClearCase with relative "
                           "paths outside the view). For git, this specifies"
                           "the origin url of the current repository, "
                           "overriding the origin url supplied by the git "
                           "client.")
    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug",
                      default=get_config_value(configs, 'DEBUG', False),
                      help="display debug output")
    parser.add_option("--diff-filename",
                      dest="diff_filename", default=None,
                      help='upload an existing diff file, instead of '
                           'generating a new diff')
    parser.add_option('--http-username',
                      dest='http_username',
                      default=get_config_value(configs, 'HTTP_USERNAME'),
                      metavar='USERNAME',
                      help='username for HTTP Basic authentication')
    parser.add_option('--http-password',
                      dest='http_password',
                      default=get_config_value(configs, 'HTTP_PASSWORD'),
                      metavar='PASSWORD',
                      help='password for HTTP Basic authentication')
    parser.add_option('--basedir',
                      dest='basedir',
                      default=None,
                      help='the absolute path in the repository the diff was '
                           'generated in. Will override the path detected '
                           'by post-review.')
    parser.add_option('--repository-type',
                      dest='repository_type',
                      default=get_config_value(configs, 'REPOSITORY_TYPE',
                                               None),
                      help='the type of repository in the current directory. '
                           'In most cases this should be detected '
                           'automatically, but some directory structures '
                           'containing multiple repositories require this '
                           'option to select the proper type. The '
                           '`--list-repository-types` option can be used to '
                           'list the supported values.')
    parser.add_option('--list-repository-types',
                      dest='list_repository_types',
                      action="store_true",
                      default=False,
                      help='print the list of supported repository types. '
                           'Each printed type can be used as a value to the '
                           '`--repository-type` option.')

    (globals()["options"], args) = parser.parse_args(args)

    if options.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if options.list_repository_types:
        print_clients(options)
        sys.exit(0)

    if options.description and options.description_file:
        sys.stderr.write("The --description and --description-file options "
                         "are mutually exclusive.\n")
        sys.exit(1)

    if options.description_file:
        if os.path.exists(options.description_file):
            fp = open(options.description_file, "r")
            options.description = fp.read()
            fp.close()
        else:
            sys.stderr.write("The description file %s does not exist.\n" %
                             options.description_file)
            sys.exit(1)

    if options.guess_fields:
        options.guess_summary = True
        options.guess_description = True

    if options.testing_done and options.testing_file:
        sys.stderr.write("The --testing-done and --testing-done-file options "
                         "are mutually exclusive.\n")
        sys.exit(1)

    if options.testing_file:
        if os.path.exists(options.testing_file):
            fp = open(options.testing_file, "r")
            options.testing_done = fp.read()
            fp.close()
        else:
            sys.stderr.write("The testing file %s does not exist.\n" %
                             options.testing_file)
            sys.exit(1)

    if options.reopen and not options.rid:
        sys.stderr.write("The --reopen option requires "
                         "--review-request-id option.\n")
        sys.exit(1)

    if options.change_description and not options.rid:
        sys.stderr.write("--change-description may only be used "
                         "when updating an existing review-request\n")
        sys.exit(1)

    return args


def main():
    def exit_on_int(sig, frame):
        sys.exit(128 + sig)
    signal.signal(signal.SIGINT, exit_on_int)

    origcwd = os.path.abspath(os.getcwd())

    if 'APPDATA' in os.environ:
        homepath = os.environ['APPDATA']
    elif 'HOME' in os.environ:
        homepath = os.environ["HOME"]
    else:
        homepath = ''

    sys.stderr.write('The "post-review" tool is deprecated in favor of the'
                     '"rbt" suite of commands. post-review will go away in '
                     'RBTools 0.6.x.\n\n\n')

    # If we end up creating a cookie file, make sure it's only readable by the
    # user.
    os.umask(0077)

    # Load the config and cookie files
    cookie_file = os.path.join(homepath, ".post-review-cookies.txt")
    user_config, globals()['configs'] = load_config_files(homepath)

    args = parse_options(sys.argv[1:])

    debug('RBTools %s' % get_version_string())
    debug('Python %s' % sys.version)
    debug('Running on %s' % (platform.platform()))
    debug('Home = %s' % homepath)
    debug('Current Directory = %s' % os.getcwd())

    debug('Checking the repository type. Errors shown below are mostly '
          'harmless.')
    repository_info, tool = scan_usable_client(
        options,
        client_name=options.repository_type)
    debug('Finished checking the repository type.')

    tool.user_config = user_config
    tool.configs = configs

    # Verify that options specific to an SCM Client have not been mis-used.
    try:
        tool.check_options()
    except OptionsCheckError, e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)

    # Try to find a valid Review Board server to use.
    if options.server:
        server_url = options.server
    else:
        server_url = tool.scan_for_server(repository_info)

    if not server_url:
        print "Unable to find a Review Board server for this source code tree."
        sys.exit(1)

    server = ReviewBoardServer(server_url, repository_info, cookie_file)

    # Load the server capabilities
    server.load_capabilities()

    # Pass the tool a pointer to the capabilities
    tool.capabilities = server.capabilities

    if repository_info.supports_changesets:
        changenum = tool.get_changenum(args)
    else:
        changenum = None

    if options.diff_filename:
        parent_diff = None

        if options.diff_filename == '-':
            diff = sys.stdin.read()
        else:
            try:
                fp = open(os.path.join(origcwd, options.diff_filename), 'r')
                diff = fp.read()
                fp.close()
            except IOError, e:
                die("Unable to open diff filename: %s" % e)
    else:
        diff_info = get_diff(
            tool,
            repository_info,
            revision_range=options.revision_range,
            svn_changelist=options.svn_changelist,
            files=args)

        diff = diff_info['diff']
        parent_diff = diff_info.get('parent_diff')

    if len(diff) == 0:
        die("There don't seem to be any diffs!")

    if options.output_diff_only:
        # The comma here isn't a typo, but rather suppresses the extra newline
        print diff,
        sys.exit(0)

    if (isinstance(tool, PerforceClient) or
        isinstance(tool, PlasticClient)) and changenum is not None:
        changenum = tool.sanitize_changenum(changenum)

        # NOTE: In Review Board 1.5.2 through 1.5.3.1, the changenum support
        #       is broken, so we have to force the deprecated API.
        if (parse_version(server.rb_version) >= parse_version('1.5.2') and
            parse_version(server.rb_version) <= parse_version('1.5.3.1')):
            debug('Using changenums on Review Board %s, which is broken. '
                  'Falling back to the deprecated 1.0 API' % server.rb_version)
            server.deprecated_api = True

    # Handle the case where /api/ requires authorization (RBCommons).
    if not server.check_api_version():
        die("Unable to log in with the supplied username and password.")

    # Let's begin.
    server.login()

    review_url = tempt_fate(server, tool, changenum, diff_content=diff,
                            parent_diff_content=parent_diff,
                            submit_as=options.submit_as)

    # Load the review up in the browser if requested to:
    if options.open_browser:
        try:
            import webbrowser
            if 'open_new_tab' in dir(webbrowser):
                # open_new_tab is only in python 2.5+
                webbrowser.open_new_tab(review_url)
            elif 'open_new' in dir(webbrowser):
                webbrowser.open_new(review_url)
            else:
                os.system('start %s' % review_url)
        except:
            print 'Error opening review URL: %s' % review_url


if __name__ == "__main__":
    main()
