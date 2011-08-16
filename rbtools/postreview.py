#!/usr/bin/env python
import base64
import cookielib
import getpass
import mimetools
import os
import re
import sys
import urllib2
from optparse import OptionParser
from pkg_resources import parse_version
from urlparse import urljoin, urlparse

from rbtools import get_package_version, get_version_string
from rbtools.api.errors import APIError
from rbtools.clients import scan_usable_client
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.plastic import PlasticClient
from rbtools.utils.filesystem import get_config_value, load_config_files
from rbtools.utils.process import die

try:
    # Specifically import json_loads, to work around some issues with
    # installations containing incompatible modules named "json".
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads



###
# Default configuration -- user-settable variables follow.
###

# The following settings usually aren't needed, but if your Review
# Board crew has specific preferences and doesn't want to express
# them with command line switches, set them here and you're done.
# In particular, setting the REVIEWBOARD_URL variable will allow
# you to make it easy for people to submit reviews regardless of
# their SCM setup.
#
# Note that in order for this script to work with a reviewboard site
# that uses local paths to access a repository, the 'Mirror path'
# in the repository setup page must be set to the remote URL of the
# repository.

#
# Reviewboard URL.
#
# Set this if you wish to hard-code a default server to always use.
# It's generally recommended to set this using your SCM repository
# (for those that support it -- currently only SVN, Git, and Perforce).
#
# For example, on SVN:
#   $ svn propset reviewboard:url http://reviewboard.example.com .
#
# Or with Git:
#   $ git config reviewboard.url http://reviewboard.example.com
#
# On Perforce servers version 2008.1 and above:
#   $ p4 counter reviewboard.url http://reviewboard.example.com
#
# Older Perforce servers only allow numerical counters, so embedding
# the url in the counter name is also supported:
#   $ p4 counter reviewboard.url.http:\|\|reviewboard.example.com 1
#
# Note that slashes are not allowed in Perforce counter names, so replace them
# with pipe characters (they are a safe substitute as they are not used
# unencoded in URLs). You may need to escape them when issuing the p4 counter
# command as above.
#
# If this is not possible or desired, setting the value here will let
# you get started quickly.
#
# For all other repositories, a .reviewboardrc file present at the top of
# the checkout will also work. For example:
#
#   $ cat .reviewboardrc
#   REVIEWBOARD_URL = "http://reviewboard.example.com"
#
REVIEWBOARD_URL = None

# Default submission arguments.  These are all optional; run this
# script with --help for descriptions of each argument.
TARGET_GROUPS   = None
TARGET_PEOPLE   = None
SUBMIT_AS       = None
PUBLISH         = False
OPEN_BROWSER    = False

# Debugging.  For development...
DEBUG           = False

###
# End user-settable variables.
###


options = None
configs = []

ADD_REPOSITORY_DOCS_URL = \
    'http://www.reviewboard.org/docs/manual/dev/admin/management/repositories/'


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
    handler_order = 480 # After Basic auth

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
        if not (200 <= response.code < 300):
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

            if response.code != 401:
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
        self.passwd  = {}
        self.rb_url  = reviewboard_url
        self.rb_user = rb_user
        self.rb_pass = rb_pass

    def find_user_password(self, realm, uri):
        if uri.startswith(self.rb_url):
            if self.rb_user is None or self.rb_pass is None:
                if options.diff_filename == '-':
                    die('HTTP authentication is required, but cannot be '
                        'used with --diff-filename=-')

                print "==> HTTP Authentication Required"
                print 'Enter authorization information for "%s" at %s' % \
                    (realm, urlparse(uri)[1])

                if not self.rb_user:
                    self.rb_user = raw_input('Username: ')

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
        self.root_resource = None
        self.deprecated_api = False
        self.cookie_file = cookie_file
        self.cookie_jar  = cookielib.MozillaCookieJar(self.cookie_file)

        if self.cookie_file:
            try:
                self.cookie_jar.load(self.cookie_file, ignore_expires=True)
            except IOError:
                pass

        # Set up the HTTP libraries to support all of the features we need.
        cookie_handler      = urllib2.HTTPCookieProcessor(self.cookie_jar)
        password_mgr        = ReviewBoardHTTPPasswordMgr(self.url,
                                                         options.username,
                                                         options.password)
        basic_auth_handler  = ReviewBoardHTTPBasicAuthHandler(password_mgr)
        digest_auth_handler = urllib2.HTTPDigestAuthHandler(password_mgr)
        self.preset_auth_handler = PresetHTTPAuthHandler(self.url, password_mgr)
        http_error_processor = ReviewBoardHTTPErrorProcessor()

        opener = urllib2.build_opener(cookie_handler,
                                      basic_auth_handler,
                                      digest_auth_handler,
                                      self.preset_auth_handler,
                                      http_error_processor)
        opener.addheaders = [('User-agent', 'RBTools/' + get_package_version())]
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
                return
        except APIError, e:
            if e.http_status not in (401, 404):
                # We shouldn't reach this. If there's a permission denied
                # from lack of logging in, then the basic auth handler
                # should have hit it.
                #
                # However in some versions it wants you to be logged in
                # and returns a 401 from the application after you've
                # done your http basic auth
                die("Unable to access the root /api/ URL on the server.")

        # This is an older Review Board server with the old API.
        self.deprecated_api = True
        debug('Using the deprecated Review Board 1.0 web API')

    def login(self, force=False):
        """
        Logs in to a Review Board server, prompting the user for login
        information if needed.
        """
        if (options.diff_filename == '-' and
            not options.username and not options.submit_as and
            not options.password):
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
                username = raw_input('Username: ')

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

            debug("Looking for '%s %s' cookie in %s" % \
                  (host, path, self.cookie_file))

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

    def get_configured_repository(self):
        return get_config_value(configs, 'REPOSITORY')

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

        repository = options.repository_url \
                     or self.get_configured_repository() \
                     or self.info.path

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
            if e.error_code == 204: # Change number in use
                rsp = e.rsp

                if options.diff_only:
                    # In this case, fall through and return to tempt_fate.
                    debug("Review request already exists.")
                else:
                    debug("Review request already exists. Updating it...")
                    self.update_review_request_from_changenum(
                        changenum, rsp['review_request'])
            elif e.error_code == 206: # Invalid repository
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
            self.api_post('api/json/reviewrequests/%s/draft/save/' % \
                          review_request['id'])
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
            raise APIError(http_status, rsp['err']['code'], rsp,
                           rsp['err']['msg'])
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

            die("Unable to access %s. The host path may be invalid\n%s" % \
                (url, e))

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
            r = HTTPRequest(url, body, headers, method='PUT')
            data = urllib2.urlopen(r).read()
            self.cookie_jar.save(self.cookie_file)
            return data
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            try:
                debug(e.read())
            except AttributeError:
                pass

            die("Unable to access %s. The host path may be invalid\n%s" % \
                (url, e))

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
            self.cookie_jar.save(self.cookie_file)
            return data
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            try:
                debug(e.read())
            except AttributeError:
                pass

            die("Unable to access %s. The host path may be invalid\n%s" % \
                (url, e))

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
    if DEBUG or options and options.debug:
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
            bug_set = set(re.split("[, ]+", options.bugs_closed)) | \
                      set(review_request['bugs_closed'])
            options.bugs_closed = ",".join(bug_set)
            server.set_review_request_field(review_request, 'bugs_closed',
                                            options.bugs_closed)

        if options.description:
            server.set_review_request_field(review_request, 'description',
                                            options.description)

        if options.testing_done:
            server.set_review_request_field(review_request, 'testing_done',
                                            options.testing_done)
    except APIError, e:
        if e.error_code == 103: # Not logged in
            retries = retries - 1

            # We had an odd issue where the server ended up a couple of
            # years in the future. Login succeeds but the cookie date was
            # "odd" so use of the cookie appeared to fail and eventually
            # ended up at max recursion depth :-(. Check for a maximum
            # number of retries.
            if retries >= 0:
                server.login(force=True)
                tempt_fate(server, tool, changenum, diff_content,
                           parent_diff_content, submit_as, retries=retries)
                return

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

            if e.error_code == 105:
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
                      dest="publish", action="store_true", default=PUBLISH,
                      help="publish the review request immediately after "
                           "submitting")
    parser.add_option("-r", "--review-request-id",
                      dest="rid", metavar="ID", default=None,
                      help="existing review request ID to update")
    parser.add_option("-o", "--open",
                      dest="open_browser", action="store_true",
                      default=OPEN_BROWSER,
                      help="open a web browser to the review request page")
    parser.add_option("-n", "--output-diff",
                      dest="output_diff_only", action="store_true",
                      default=False,
                      help="outputs a diff to the console and exits. "
                           "Does not post")
    parser.add_option("--server",
                      dest="server", default=REVIEWBOARD_URL,
                      metavar="SERVER",
                      help="specify a different Review Board server "
                           "to use")
    parser.add_option("--diff-only",
                      dest="diff_only", action="store_true", default=False,
                      help="uploads a new diff, but does not update "
                           "info from changelist")
    parser.add_option("--reopen",
                      dest="reopen", action="store_true", default=False,
                      help="reopen discarded review request "
                           "after update")
    parser.add_option("--target-groups",
                      dest="target_groups", default=TARGET_GROUPS,
                      help="names of the groups who will perform "
                           "the review")
    parser.add_option("--target-people",
                      dest="target_people", default=TARGET_PEOPLE,
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
    parser.add_option("--guess-summary",
                      dest="guess_summary", action="store_true",
                      default=False,
                      help="guess summary from the latest commit (git/"
                           "hg/hgsubversion only)")
    parser.add_option("--guess-description",
                      dest="guess_description", action="store_true",
                      default=False,
                      help="guess description based on commits on this branch "
                           "(git/hg/hgsubversion only)")
    parser.add_option("--testing-done",
                      dest="testing_done", default=None,
                      help="details of testing done ")
    parser.add_option("--testing-done-file",
                      dest="testing_file", default=None,
                      help="text file containing details of testing done ")
    parser.add_option("--branch",
                      dest="branch", default=None,
                      help="affected branch ")
    parser.add_option("--bugs-closed",
                      dest="bugs_closed", default=None,
                      help="list of bugs closed ")
    parser.add_option("--revision-range",
                      dest="revision_range", default=None,
                      help="generate the diff for review based on given "
                           "revision range")
    parser.add_option("--submit-as",
                      dest="submit_as", default=SUBMIT_AS, metavar="USERNAME",
                      help="user name to be recorded as the author of the "
                           "review request, instead of the logged in user")
    parser.add_option("--username",
                      dest="username", default=None, metavar="USERNAME",
                      help="user name to be supplied to the reviewboard server")
    parser.add_option("--password",
                      dest="password", default=None, metavar="PASSWORD",
                      help="password to be supplied to the reviewboard server")
    parser.add_option("--change-only",
                      dest="change_only", action="store_true",
                      default=False,
                      help="updates info from changelist, but does "
                           "not upload a new diff (only available if your "
                           "repository supports changesets)")
    parser.add_option("--parent",
                      dest="parent_branch", default=None,
                      metavar="PARENT_BRANCH",
                      help="the parent branch this diff should be against "
                           "(only available if your repository supports "
                           "parent diffs)")
    parser.add_option("--tracking-branch",
                      dest="tracking", default=None,
                      metavar="TRACKING",
                      help="Tracking branch from which your branch is derived "
                           "(git only, defaults to origin/master)")
    parser.add_option("--p4-client",
                      dest="p4_client", default=None,
                      help="the Perforce client name that the review is in")
    parser.add_option("--p4-port",
                      dest="p4_port", default=None,
                      help="the Perforce servers IP address that the review is on")
    parser.add_option("--p4-passwd",
                      dest="p4_passwd", default=None,
                      help="the Perforce password or ticket of the user in the P4USER environment variable")
    parser.add_option('--svn-changelist', dest='svn_changelist', default=None,
                      help='generate the diff for review based on a local SVN '
                           'changelist')
    parser.add_option("--repository-url",
                      dest="repository_url", default=None,
                      help="the url for a repository for creating a diff "
                           "outside of a working copy (currently only "
                           "supported by Subversion with --revision-range or "
                           "--diff-filename and ClearCase with relative "
                           "paths outside the view). For git, this specifies"
                           "the origin url of the current repository, "
                           "overriding the origin url supplied by the git client.")
    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug", default=DEBUG,
                      help="display debug output")
    parser.add_option("--diff-filename",
                      dest="diff_filename", default=None,
                      help='upload an existing diff file, instead of '
                           'generating a new diff')
    parser.add_option('--http-username',
                      dest='http_username', default=None, metavar='USERNAME',
                      help='username for HTTP Basic authentication')
    parser.add_option('--http-password',
                      dest='http_password', default=None, metavar='PASSWORD',
                      help='password for HTTP Basic authentication')

    (globals()["options"], args) = parser.parse_args(args)

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

    return args


def main():
    origcwd = os.path.abspath(os.getcwd())

    if 'APPDATA' in os.environ:
        homepath = os.environ['APPDATA']
    elif 'HOME' in os.environ:
        homepath = os.environ["HOME"]
    else:
        homepath = ''

    # Load the config and cookie files
    cookie_file = os.path.join(homepath, ".post-review-cookies.txt")
    user_config, globals()['configs'] = load_config_files(homepath)

    args = parse_options(sys.argv[1:])

    debug('RBTools %s' % get_version_string())
    debug('Home = %s' % homepath)

    repository_info, tool = scan_usable_client(options)
    tool.user_config = user_config
    tool.configs = configs

    # Verify that options specific to an SCM Client have not been mis-used.
    tool.check_options()

    # Try to find a valid Review Board server to use.
    if options.server:
        server_url = options.server
    else:
        server_url = tool.scan_for_server(repository_info)

    if not server_url:
        print "Unable to find a Review Board server for this source code tree."
        sys.exit(1)

    server = ReviewBoardServer(server_url, repository_info, cookie_file)
    server.check_api_version()

    if repository_info.supports_changesets:
        changenum = tool.get_changenum(args)
    else:
        changenum = None

    if options.revision_range:
        diff, parent_diff = tool.diff_between_revisions(options.revision_range, args,
                                                        repository_info)
    elif options.svn_changelist:
        diff, parent_diff = tool.diff_changelist(options.svn_changelist)
    elif options.diff_filename:
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
        diff, parent_diff = tool.diff(args)

    if len(diff) == 0:
        die("There don't seem to be any diffs!")

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

    if options.output_diff_only:
        # The comma here isn't a typo, but rather suppresses the extra newline
        print diff,
        sys.exit(0)

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
                os.system( 'start %s' % review_url )
        except:
            print 'Error opening review URL: %s' % review_url


if __name__ == "__main__":
    main()
