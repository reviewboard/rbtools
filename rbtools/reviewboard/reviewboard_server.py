import cookielib
import getpass
from json import loads as json_loads
import mimetools
import sys
import urllib2
from urlparse import urlparse, urljoin
from pkg_resources import parse_version
from rbtools import get_package_version
from rbtools.api.errors import APIError
from rbtools.utils.process import die
from custom_http import HTTPBasicAuthHandler, HTTPRequest, HTTPErrorProcessor

REPOSITORY_DOCS_URL = \
    'http://www.reviewboard.org/docs/manual/dev/admin/configuration/repositories/'

class ReviewBoardServer(object):
    """
    An instance of a Review Board server.
    """
    def __init__(self, url, info, cookie_file, password_mgr, auth_handler, options):
        self.url = url
        self._info = info
        self._server_info = None
        self.root_resource = None
        self.deprecated_api = False
        self.cookie_file = cookie_file
        self.cookie_jar  = cookielib.MozillaCookieJar(self.cookie_file)
        self.preset_auth_handler = auth_handler
        self.options = options

        if self.cookie_file:
            try:
                self.cookie_jar.load(self.cookie_file, ignore_expires=True)
            except IOError:
                pass

        handlers = []

        if self.options.disable_proxy:
            self.debug('Disabling HTTP(s) proxy support')
            handlers.append(urllib2.ProxyHandler({}))

        handlers += [
            urllib2.HTTPCookieProcessor(self.cookie_jar),
            HTTPBasicAuthHandler(password_mgr),
            urllib2.HTTPDigestAuthHandler(password_mgr),
            self.preset_auth_handler,
            HTTPErrorProcessor(),
        ]

        opener = urllib2.build_opener(*handlers)
        opener.addheaders = [('User-agent', 'RBTools/' + get_package_version())]
        urllib2.install_opener(opener)

    def debug(self, s):
        if self.options and self.options.debug:
            print ">>> %s" % s

    def check_api_version(self):
        """Checks the API version on the server to determine which to use."""
        try:
            root_resource = self.api_get('api/')
            rsp = self.api_get(root_resource['links']['info']['href'])

            self.rb_version = rsp['info']['product']['package_version']

            if parse_version(self.rb_version) >= parse_version('1.5.2'):
                self.deprecated_api = False
                self.root_resource = root_resource
                self.debug('Using the new web API')
                return True
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

                return False

        # This is an older Review Board server with the old API.
        self.deprecated_api = True
        self.debug('Using the deprecated Review Board 1.0 web API')
        return True

    def login(self, force=False):
        """
        Logs in to a Review Board server, prompting the user for login
        information if needed.
        """
        if (self.options.diff_filename == '-' and
            not (self.has_valid_cookie() or
                 (self.options.username and self.options.password))):
            die('Authentication information needs to be provided on '
                'the command line when using --diff-filename=-')

        if self.deprecated_api:
            print "==> Review Board Login Required"
            print "Enter username and password for Review Board at %s" % \
                  self.url

            if self.options.username:
                username = self.options.username
            elif self.options.submit_as:
                username = self.options.submit_as
            elif not force and self.has_valid_cookie():
                # We delay the check for a valid cookie until after looking
                # at args, so that it doesn't override the command line.
                return
            else:
                username = raw_input('Username: ')

            if not self.options.password:
                password = getpass.getpass('Password: ')
            else:
                password = self.options.password

            self.debug('Logging in with username "%s"' % username)
            try:
                self.api_post('api/json/accounts/login/', {
                    'username': username,
                    'password': password,
                })
            except APIError, e:
                die("Unable to log in: %s" % e)

            self.debug("Logged in.")
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

            self.debug("Looking for '%s %s' cookie in %s" % \
                  (host, path, self.cookie_file))

            try:
                cookie = self.cookie_jar._cookies[host][path]['rbsessionid']

                if not cookie.is_expired():
                    self.debug("Loaded valid cookie -- no login required")
                    return True

                self.debug("Cookie file loaded, but cookie has expired")
            except KeyError:
                self.debug("Cookie file loaded, but no cookie for this server")
        except IOError, error:
            self.debug("Couldn't load cookie file: %s" % error)

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

            self.debug("Repositories on Server: %s" % repositories)
            self.debug("Server Aliases: %s" % self.info.path)

            for repository in repositories:
                if repository['path'] in self.info.path:
                    self.info.path = repository['path']
                    break

            if isinstance(self.info.path, list):
                sys.stderr.write('\nThere was an error creating this review request.\n\n')
                sys.stderr.write('There was no matching repository path found on the server.\n')
                sys.stderr.write('List of configured repositories:\n')

                for repository in repositories:
                    sys.stderr.write('\t%s\n' % repository['path'])

                sys.stderr.write('Unknown repository paths found:\n')

                for foundpath in self.info.path:
                    sys.stderr.write('\t%s\n' % foundpath)

                sys.stderr.write('Ask the administrator to add one of these repositories\n')
                sys.stderr.write('to the Review Board server.\n')
                sys.stderr.write('For information on adding repositories, please read\n')
                sys.stderr.write(REPOSITORY_DOCS_URL + '\n')
                die()

        repository = self.options.repository_url or self.info.path

        try:
            self.debug("Attempting to create review request on %s for %s" %
                  (repository, changenum))
            data = {}

            if changenum:
                data['changenum'] = changenum

            if submit_as:
                self.debug("Submitting the review request as %s" % submit_as)
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

                if self.options.diff_only:
                    # In this case, fall through and return to tempt_fate.
                    self.debug("Review request already exists.")
                else:
                    self.debug("Review request already exists. Updating it...")
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
                sys.stderr.write(REPOSITORY_DOCS_URL + '\n')
                die()
            else:
                raise e
        else:
            self.debug("Review request created")

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

        self.debug("Attempting to set field '%s' to '%s' for review request '%s'" %
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

        self.debug("Review request draft saved")

    def upload_diff(self, review_request, diff_content, parent_diff_content):
        """
        Uploads a diff to a Review Board server.
        """
        self.debug("Uploading diff, size: %d" % len(diff_content))

        if parent_diff_content:
            self.debug("Uploading parent diff, size: %d" % len(parent_diff_content))

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
        self.debug("Reopening")

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
        self.debug("Publishing")

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

            self.debug("Got API Error %d (HTTP code %d): %s" %
                  (rsp['err']['code'], http_status, rsp['err']['msg']))
            self.debug("Error data: %r" % rsp)
            raise APIError(http_status, rsp['err']['code'], rsp,
                           rsp['err']['msg'])
        except ValueError:
            self.debug("Got HTTP error: %s: %s" % (http_status, data))
            raise APIError(http_status, None, None, data)

    def http_get(self, path):
        """
        Performs an HTTP GET on the specified path, storing any cookies that
        were set.
        """
        self.debug('HTTP GETting %s' % path)

        url = self._make_url(path)
        rsp = urllib2.urlopen(url).read()

        try:
            self.cookie_jar.save(self.cookie_file)
        except IOError, e:
            self.debug('Failed to write cookie file: %s' % e)
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
        self.debug('HTTP POSTing to %s: %s' % (url, debug_fields))

        content_type, body = self._encode_multipart_formdata(fields, files)
        headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(body))
        }

        try:
            r = urllib2.Request(str(url), body, headers)
            data = urllib2.urlopen(r).read()
            try:
                self.cookie_jar.save(self.cookie_file)
            except IOError, e:
                self.debug('Failed to write cookie file: %s' % e)
            return data
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            try:
                self.debug(e.read())
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
        self.debug('HTTP PUTting to %s: %s' % (url, fields))

        content_type, body = self._encode_multipart_formdata(fields, None)
        headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(body))
        }

        try:
            r = HTTPRequest(str(url), body, headers, method='PUT')
            data = urllib2.urlopen(r).read()
            try:
                self.cookie_jar.save(self.cookie_file)
            except IOError, e:
                self.debug('Failed to write cookie file: %s' % e)
            return data
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            try:
                self.debug(e.read())
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
        self.debug('HTTP DELETing %s' % url)

        try:
            r = HTTPRequest(url, method='DELETE')
            data = urllib2.urlopen(r).read()
            try:
                self.cookie_jar.save(self.cookie_file)
            except IOError, e:
                self.debug('Failed to write cookie file: %s' % e)
            return data
        except urllib2.HTTPError, e:
            # Re-raise so callers can interpret it.
            raise e
        except urllib2.URLError, e:
            try:
                self.debug(e.read())
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