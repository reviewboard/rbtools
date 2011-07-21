#!/usr/bin/env python
import base64
import cookielib
import getpass
import marshal
import mimetools
import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
import urllib
import urllib2
from datetime import datetime
from optparse import OptionParser
from pkg_resources import parse_version
from tempfile import mkstemp
from urlparse import urljoin, urlparse

try:
    from hashlib import md5
except ImportError:
    # Support Python versions before 2.5.
    from md5 import md5

try:
    # Specifically import json_loads, to work around some issues with
    # installations containing incompatible modules named "json".
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads

# This specific import is necessary to handle the paths for
# cygwin enabled machines.
if (sys.platform.startswith('win')
    or sys.platform.startswith('cygwin')):
    import ntpath as cpath
else:
    import posixpath as cpath

from rbtools import get_package_version, get_version_string


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


user_config = None
tempfiles = []
options = None
configs = []

ADD_REPOSITORY_DOCS_URL = \
    'http://www.reviewboard.org/docs/manual/dev/admin/management/repositories/'
GNU_DIFF_WIN32_URL = 'http://gnuwin32.sourceforge.net/packages/diffutils.htm'


class APIError(Exception):
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


class HTTPRequest(urllib2.Request):
    def __init__(self, url, body='', headers={}, method="PUT"):
        urllib2.Request.__init__(self, url, body, headers)
        self.method = method

    def get_method(self):
        return self.method


class RepositoryInfo:
    """
    A representation of a source code repository.
    """
    def __init__(self, path=None, base_path=None, supports_changesets=False,
                 supports_parent_diffs=False):
        self.path = path
        self.base_path = base_path
        self.supports_changesets = supports_changesets
        self.supports_parent_diffs = supports_parent_diffs
        debug("repository info: %s" % self)

    def __str__(self):
        return "Path: %s, Base path: %s, Supports changesets: %s" % \
            (self.path, self.base_path, self.supports_changesets)

    def set_base_path(self, base_path):
        if not base_path.startswith('/'):
            base_path = '/' + base_path
        debug("changing repository info base_path from %s to %s" % \
              (self.base_path, base_path))
        self.base_path = base_path

    def find_server_repository_info(self, server):
        """
        Try to find the repository from the list of repositories on the server.
        For Subversion, this could be a repository with a different URL. For
        all other clients, this is a noop.
        """
        return self


class SvnRepositoryInfo(RepositoryInfo):
    """
    A representation of a SVN source code repository. This version knows how to
    find a matching repository on the server even if the URLs differ.
    """
    def __init__(self, path, base_path, uuid, supports_parent_diffs=False):
        RepositoryInfo.__init__(self, path, base_path,
                                supports_parent_diffs=supports_parent_diffs)
        self.uuid = uuid

    def find_server_repository_info(self, server):
        """
        The point of this function is to find a repository on the server that
        matches self, even if the paths aren't the same. (For example, if self
        uses an 'http' path, but the server uses a 'file' path for the same
        repository.) It does this by comparing repository UUIDs. If the
        repositories use the same path, you'll get back self, otherwise you'll
        get a different SvnRepositoryInfo object (with a different path).
        """
        repositories = server.get_repositories()

        for repository in repositories:
            if repository['tool'] != 'Subversion':
                continue

            info = self._get_repository_info(server, repository)

            if not info or self.uuid != info['uuid']:
                continue

            repos_base_path = info['url'][len(info['root_url']):]
            relpath = self._get_relative_path(self.base_path, repos_base_path)
            if relpath:
                return SvnRepositoryInfo(info['url'], relpath, self.uuid)

        # We didn't find a matching repository on the server. We'll just return
        # self and hope for the best.
        return self

    def _get_repository_info(self, server, repository):
        try:
            return server.get_repository_info(repository['id'])
        except APIError, e:
            # If the server couldn't fetch the repository info, it will return
            # code 210. Ignore those.
            # Other more serious errors should still be raised, though.
            if e.error_code == 210:
                return None

            raise e

    def _get_relative_path(self, path, root):
        pathdirs = self._split_on_slash(path)
        rootdirs = self._split_on_slash(root)

        # root is empty, so anything relative to that is itself
        if len(rootdirs) == 0:
            return path

        # If one of the directories doesn't match, then path is not relative
        # to root.
        if rootdirs != pathdirs[:len(rootdirs)]:
            return None

        # All the directories matched, so the relative path is whatever
        # directories are left over. The base_path can't be empty, though, so
        # if the paths are the same, return '/'
        if len(pathdirs) == len(rootdirs):
            return '/'
        else:
            return '/' + '/'.join(pathdirs[len(rootdirs):])

    def _split_on_slash(self, path):
        # Split on slashes, but ignore multiple slashes and throw away any
        # trailing slashes.
        split = re.split('/*', path)
        if split[-1] == '':
            split = split[0:-1]
        return split

class ClearCaseRepositoryInfo(RepositoryInfo):
    """
    A representation of a ClearCase source code repository. This version knows
    how to find a matching repository on the server even if the URLs differ.
    """

    def __init__(self, path, base_path, vobstag, supports_parent_diffs=False):
        RepositoryInfo.__init__(self, path, base_path,
                                supports_parent_diffs=supports_parent_diffs)
        self.vobstag = vobstag

    def find_server_repository_info(self, server):
        """
        The point of this function is to find a repository on the server that
        matches self, even if the paths aren't the same. (For example, if self
        uses an 'http' path, but the server uses a 'file' path for the same
        repository.) It does this by comparing VOB's name. If the
        repositories use the same path, you'll get back self, otherwise you'll
        get a different ClearCaseRepositoryInfo object (with a different path).
        """

        # Find VOB's family uuid based on VOB's tag
        uuid = self._get_vobs_uuid(self.vobstag)
        debug("Repositorie's %s uuid is %r" % (self.vobstag, uuid))

        repositories = server.get_repositories()
        for repository in repositories:
            if repository['tool'] != 'ClearCase':
                continue

            info = self._get_repository_info(server, repository)

            if not info or uuid != info['uuid']:
                continue

            debug('Matching repository uuid:%s with path:%s' %(uuid,
                  info['repopath']))
            return ClearCaseRepositoryInfo(info['repopath'],
                    info['repopath'], uuid)

        # We didn't found uuid but if version is >= 1.5.3
        # we can try to use VOB's name hoping it is better
        # than current VOB's path.
        if server.rb_version >= '1.5.3':
            self.path = cpath.split(self.vobstag)[1]

        # We didn't find a matching repository on the server.
        # We'll just return self and hope for the best.
        return self

    def _get_vobs_uuid(self, vobstag):
        """Return family uuid of VOB."""

        property_lines = execute(["cleartool", "lsvob", "-long", vobstag],
                                 split_lines=True)
        for line  in property_lines:
            if line.startswith('Vob family uuid:'):
                return  line.split(' ')[-1].rstrip()

    def _get_repository_info(self, server, repository):
        try:
            return server.get_repository_info(repository['id'])
        except APIError, e:
            # If the server couldn't fetch the repository info, it will return
            # code 210. Ignore those.
            # Other more serious errors should still be raised, though.
            if e.error_code == 210:
                return None

            raise e


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
        for config in configs:
            if 'REPOSITORY' in config:
                return config['REPOSITORY']

        return None

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


class SCMClient(object):
    """
    A base representation of an SCM tool for fetching repository information
    and generating diffs.
    """
    def get_repository_info(self):
        return None

    def check_options(self):
        pass

    def scan_for_server(self, repository_info):
        """
        Scans the current directory on up to find a .reviewboard file
        containing the server path.
        """
        server_url = None

        if user_config:
            server_url = self._get_server_from_config(user_config,
                                                      repository_info)

        if not server_url:
            for config in configs:
                server_url = self._get_server_from_config(config,
                                                          repository_info)

                if server_url:
                    break

        return server_url

    def diff(self, args):
        """
        Returns the generated diff and optional parent diff for this
        repository.

        The returned tuple is (diff_string, parent_diff_string)
        """
        return (None, None)

    def diff_between_revisions(self, revision_range, args, repository_info):
        """
        Returns the generated diff between revisions in the repository.
        """
        return (None, None)

    def _get_server_from_config(self, config, repository_info):
        if 'REVIEWBOARD_URL' in config:
            return config['REVIEWBOARD_URL']
        elif 'TREES' in config:
            trees = config['TREES']
            if not isinstance(trees, dict):
                die("Warning: 'TREES' in config file is not a dict!")

            # If repository_info is a list, check if any one entry is in trees.
            path = None

            if isinstance(repository_info.path, list):
                for path in repository_info.path:
                    if path in trees:
                        break
                else:
                    path = None
            elif repository_info.path in trees:
                path = repository_info.path

            if path and 'REVIEWBOARD_URL' in trees[path]:
                return trees[path]['REVIEWBOARD_URL']

        return None


class CVSClient(SCMClient):
    """
    A wrapper around the cvs tool that fetches repository
    information and generates compatible diffs.
    """
    def get_repository_info(self):
        if not check_install("cvs"):
            return None

        cvsroot_path = os.path.join("CVS", "Root")

        if not os.path.exists(cvsroot_path):
            return None

        fp = open(cvsroot_path, "r")
        repository_path = fp.read().strip()
        fp.close()

        i = repository_path.find("@")
        if i != -1:
            repository_path = repository_path[i + 1:]

        i = repository_path.rfind(":")
        if i != -1:
            host = repository_path[:i]
            try:
                canon = socket.getfqdn(host)
                repository_path = repository_path.replace('%s:' % host,
                                                          '%s:' % canon)
            except socket.error, msg:
                debug("failed to get fqdn for %s, msg=%s" % (host, msg))

        return RepositoryInfo(path=repository_path)

    def diff(self, files):
        """
        Performs a diff across all modified files in a CVS repository.

        CVS repositories do not support branches of branches in a way that
        makes parent diffs possible, so we never return a parent diff
        (the second value in the tuple).
        """
        return (self.do_diff(files), None)

    def diff_between_revisions(self, revision_range, args, repository_info):
        """
        Performs a diff between 2 revisions of a CVS repository.
        """
        revs = []

        for rev in revision_range.split(":"):
            revs += ["-r", rev]

        return (self.do_diff(revs + args), None)

    def do_diff(self, params):
        """
        Performs the actual diff operation through cvs diff, handling
        fake errors generated by CVS.
        """
        # Diff returns "1" if differences were found.
        return execute(["cvs", "diff", "-uN"] + params,
                        extra_ignore_errors=(1,))


class ClearCaseClient(SCMClient):
    """
    A wrapper around the clearcase tool that fetches repository
    information and generates compatible diffs.
    This client assumes that cygwin is installed on windows.
    """
    viewtype = None

    def get_repository_info(self):
        """Returns information on the Clear Case repository.

        This will first check if the cleartool command is
        installed and in the path, and post-review was run
        from inside of the view.
        """
        if not check_install('cleartool help'):
            return None

        viewname = execute(["cleartool", "pwv", "-short"]).strip()
        if viewname.startswith('** NONE'):
            return None

        # Now that we know it's ClearCase, make sure we have GNU diff installed,
        # and error out if we don't.
        check_gnu_diff()

        property_lines = execute(["cleartool", "lsview", "-full", "-properties",
                                  "-cview"], split_lines=True)
        for line in property_lines:
            properties = line.split(' ')
            if properties[0] == 'Properties:':
                # Determine the view type and check if it's supported.
                #
                # Specifically check if webview was listed in properties
                # because webview types also list the 'snapshot'
                # entry in properties.
                if 'webview' in properties:
                    die("Webviews are not supported. You can use post-review"
                        " only in dynamic or snapshot view.")
                if 'dynamic' in properties:
                    self.viewtype = 'dynamic'
                else:
                    self.viewtype = 'snapshot'

                break

        # Find current VOB's tag
        vobstag = execute(["cleartool", "describe", "-short", "vob:."],
                            ignore_errors=True).strip()
        if "Error: " in vobstag:
            die("To generate diff run post-review inside vob.")

        # From current working directory cut path to VOB.
        # VOB's tag contain backslash character before VOB's name.
        # I hope that first character of VOB's tag like '\new_proj'
        # won't be treat as new line character but two separate:
        # backslash and letter 'n'
        cwd = os.getcwd()
        base_path = cwd[:cwd.find(vobstag) + len(vobstag)]

        return ClearCaseRepositoryInfo(path=base_path,
                              base_path=base_path,
                              vobstag=vobstag,
                              supports_parent_diffs=False)

    def check_options(self):
        if ((options.revision_range or options.tracking)
            and self.viewtype != "dynamic"):
            die("To generate diff using parent branch or by passing revision "
                "ranges, you must use a dynamic view.")

    def _determine_version(self, version_path):
        """Determine numeric version of revision.

        CHECKEDOUT is marked as infinity to be treated
        always as highest possible version of file.
        CHECKEDOUT, in ClearCase, is something like HEAD.
        """
        branch, number = cpath.split(version_path)
        if number == 'CHECKEDOUT':
            return float('inf')
        return int(number)

    def _construct_extended_path(self, path, version):
        """Combine extended_path from path and version.

        CHECKEDOUT must be removed becasue this one version
        doesn't exists in MVFS (ClearCase dynamic view file
        system). Only way to get content of checked out file
        is to use filename only."""
        if not version or version.endswith('CHECKEDOUT'):
            return path

        return "%s@@%s" % (path, version)

    def _sanitize_branch_changeset(self, changeset):
        """Return changeset containing non-binary, branched file versions.

        Changeset contain only first and last version of file made on branch.
        """
        changelist = {}

        for path, previous, current in changeset:
            version_number = self._determine_version(current)

            if path not in changelist:
                changelist[path] = {
                    'highest': version_number,
                    'current': current,
                    'previous': previous
                }

            if version_number == 0:
                # Previous version of 0 version on branch is base
                changelist[path]['previous'] = previous
            elif version_number > changelist[path]['highest']:
                changelist[path]['highest'] = version_number
                changelist[path]['current'] = current

        # Convert to list
        changeranges = []
        for path, version in changelist.iteritems():
            changeranges.append(
                (self._construct_extended_path(path, version['previous']),
                 self._construct_extended_path(path, version['current']))
            )

        return changeranges

    def _sanitize_checkedout_changeset(self, changeset):
        """Return changeset containing non-binary, checkdout file versions."""

        changeranges = []
        for path, previous, current in changeset:
            version_number = self._determine_version(current)
            changeranges.append(
                (self._construct_extended_path(path, previous),
                self._construct_extended_path(path, current))
            )

        return changeranges

    def _directory_content(self, path):
        """Return directory content ready for saving to tempfile."""

        return ''.join([
            '%s\n' % s
            for s in sorted(os.listdir(path))
        ])

    def _construct_changeset(self, output):
        return [
            info.split('\t')
            for info in output.strip().split('\n')
        ]

    def get_checkedout_changeset(self):
        """Return information about the checked out changeset.

        This function returns: kind of element, path to file,
        previews and current file version.
        """
        changeset = []
        # We ignore return code 1 in order to
        # omit files that Clear Case can't read.
        output = execute([
            "cleartool",
            "lscheckout",
            "-all",
            "-cview",
            "-me",
            "-fmt",
            r"%En\t%PVn\t%Vn\n"],
            extra_ignore_errors=(1,),
            with_errors=False)

        if output:
            changeset = self._construct_changeset(output)

        return self._sanitize_checkedout_changeset(changeset)

    def get_branch_changeset(self, branch):
        """Returns information about the versions changed on a branch.

        This takes into account the changes on the branch owned by the
        current user in all vobs of the current view.
        """
        changeset = []

        # We ignore return code 1 in order to
        # omit files that Clear Case can't read.
        if sys.platform.startswith('win'):
            CLEARCASE_XPN = '%CLEARCASE_XPN%'
        else:
            CLEARCASE_XPN = '$CLEARCASE_XPN'

        output = execute([
            "cleartool",
            "find",
            "-all",
            "-version",
            "brtype(%s)" % branch,
            "-exec",
            'cleartool descr -fmt ' \
            r'"%En\t%PVn\t%Vn\n" ' \
            + CLEARCASE_XPN],
            extra_ignore_errors=(1,),
            with_errors=False)

        if output:
            changeset = self._construct_changeset(output)

        return self._sanitize_branch_changeset(changeset)

    def diff(self, files):
        """Performs a diff of the specified file and its previous version."""

        if options.tracking:
            changeset = self.get_branch_changeset(options.tracking)
        else:
            changeset = self.get_checkedout_changeset()

        return self.do_diff(changeset)

    def diff_between_revisions(self, revision_range, args, repository_info):
        """Performs a diff between passed revisions or branch."""

        # Convert revision range to list of:
        # (previous version, current version) tuples
        revision_range = revision_range.split(';')
        changeset = zip(revision_range[0::2], revision_range[1::2])

        return (self.do_diff(changeset)[0], None)

    def diff_files(self, old_file, new_file):
        """Return unified diff for file.

        Most effective and reliable way is use gnu diff.
        """
        diff_cmd = ["diff", "-uN", old_file, new_file]
        dl = execute(diff_cmd, extra_ignore_errors=(1,2),
                     translate_newlines=False)

        # If the input file has ^M characters at end of line, lets ignore them.
        dl = dl.replace('\r\r\n', '\r\n')
        dl = dl.splitlines(True)

        # Special handling for the output of the diff tool on binary files:
        #     diff outputs "Files a and b differ"
        # and the code below expects the output to start with
        #     "Binary files "
        if (len(dl) == 1 and
            dl[0].startswith('Files %s and %s differ' % (old_file, new_file))):
            dl = ['Binary files %s and %s differ\n' % (old_file, new_file)]

        # We need oids of files to translate them to paths on reviewboard repository
        old_oid = execute(["cleartool", "describe", "-fmt", "%On", old_file])
        new_oid = execute(["cleartool", "describe", "-fmt", "%On", new_file])

        if dl == [] or dl[0].startswith("Binary files "):
            if dl == []:
                dl = ["File %s in your changeset is unmodified\n" % new_file]

            dl.insert(0, "==== %s %s ====\n" % (old_oid, new_oid))
            dl.append('\n')
        else:
            dl.insert(2, "==== %s %s ====\n" % (old_oid, new_oid))

        return dl

    def diff_directories(self, old_dir, new_dir):
        """Return uniffied diff between two directories content.

        Function save two version's content of directory to temp
        files and treate them as casual diff between two files.
        """
        old_content = self._directory_content(old_dir)
        new_content = self._directory_content(new_dir)

        old_tmp = make_tempfile(content=old_content)
        new_tmp = make_tempfile(content=new_content)

        diff_cmd = ["diff", "-uN", old_tmp, new_tmp]
        dl = execute(diff_cmd,
                     extra_ignore_errors=(1,2),
                     translate_newlines=False,
                     split_lines=True)

        # Replacing temporary filenames to
        # real directory names and add ids
        if dl:
            dl[0] = dl[0].replace(old_tmp, old_dir)
            dl[1] = dl[1].replace(new_tmp, new_dir)
            old_oid = execute(["cleartool", "describe", "-fmt", "%On", old_dir])
            new_oid = execute(["cleartool", "describe", "-fmt", "%On", new_dir])
            dl.insert(2, "==== %s %s ====\n" % (old_oid, new_oid))

        return dl

    def do_diff(self, changeset):
        """Generates a unified diff for all files in the changeset."""

        diff = []
        for old_file, new_file in changeset:
            dl = []
            if cpath.isdir(new_file):
                dl = self.diff_directories(old_file, new_file)
            elif cpath.exists(new_file):
                dl = self.diff_files(old_file, new_file)
            else:
                debug("File %s does not exist or access is denied." % new_file)
                continue

            if dl:
                diff.append(''.join(dl))

        return (''.join(diff), None)


class SVNClient(SCMClient):
    # Match the diff control lines generated by 'svn diff'.
    DIFF_ORIG_FILE_LINE_RE = re.compile(r'^---\s+.*\s+\(.*\)')
    DIFF_NEW_FILE_LINE_RE = re.compile(r'^\+\+\+\s+.*\s+\(.*\)')

    """
    A wrapper around the svn Subversion tool that fetches repository
    information and generates compatible diffs.
    """
    def get_repository_info(self):
        if not check_install('svn help'):
            return None

        # Get the SVN repository path (either via a working copy or
        # a supplied URI)
        svn_info_params = ["svn", "info"]

        if options.repository_url:
            svn_info_params.append(options.repository_url)

        data = execute(svn_info_params,
                       ignore_errors=True)

        m = re.search(r'^Repository Root: (.+)$', data, re.M)
        if not m:
            return None

        path = m.group(1)

        m = re.search(r'^URL: (.+)$', data, re.M)
        if not m:
            return None

        base_path = m.group(1)[len(path):] or "/"

        m = re.search(r'^Repository UUID: (.+)$', data, re.M)
        if not m:
            return None

        # Now that we know it's SVN, make sure we have GNU diff installed,
        # and error out if we don't.
        check_gnu_diff()

        return SvnRepositoryInfo(path, base_path, m.group(1))

    def check_options(self):
        if (options.repository_url and
            not options.revision_range and
            not options.diff_filename):
            sys.stderr.write("The --repository-url option requires either the "
                             "--revision-range option or the --diff-filename "
                             "option.\n")
            sys.exit(1)

    def scan_for_server(self, repository_info):
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = super(SVNClient, self).scan_for_server(repository_info)
        if server_url:
            return server_url

        return self.scan_for_server_property(repository_info)

    def scan_for_server_property(self, repository_info):
        def get_url_prop(path):
            url = execute(["svn", "propget", "reviewboard:url", path]).strip()
            return url or None

        for path in walk_parents(os.getcwd()):
            if not os.path.exists(os.path.join(path, ".svn")):
                break

            prop = get_url_prop(path)
            if prop:
                return prop

        return get_url_prop(repository_info.path)

    def diff(self, files):
        """
        Performs a diff across all modified files in a Subversion repository.

        SVN repositories do not support branches of branches in a way that
        makes parent diffs possible, so we never return a parent diff
        (the second value in the tuple).
        """
        return (self.do_diff(["svn", "diff", "--diff-cmd=diff"] + files),
                None)

    def diff_changelist(self, changelist):
        """
        Performs a diff for a local changelist.
        """
        return (self.do_diff(["svn", "diff", "--changelist", changelist]),
                None)

    def diff_between_revisions(self, revision_range, args, repository_info):
        """
        Performs a diff between 2 revisions of a Subversion repository.
        """
        if options.repository_url:
            revisions = revision_range.split(':')
            if len(revisions) < 1:
                return None
            elif len(revisions) == 1:
                revisions.append('HEAD')

            # if a new path was supplied at the command line, set it
            files = []
            if len(args) == 1:
                repository_info.set_base_path(args[0])
            elif len(args) > 1:
                files = args

            url = repository_info.path + repository_info.base_path

            new_url = url + '@' + revisions[1]

            # When the source revision is zero, assume the user wants to
            # upload a diff containing all the files in ``base_path`` as new
            # files. If the base path within the repository is added to both
            # the old and new URLs, the ``svn diff`` command will error out
            # since the base_path didn't exist at revision zero. To avoid
            # that error, use the repository's root URL as the source for
            # the diff.
            if revisions[0] == "0":
                url = repository_info.path

            old_url = url + '@' + revisions[0]

            return (self.do_diff(["svn", "diff", "--diff-cmd=diff", old_url,
                                  new_url] + files,
                                 repository_info), None)
        # Otherwise, perform the revision range diff using a working copy
        else:
            return (self.do_diff(["svn", "diff", "--diff-cmd=diff", "-r",
                                  revision_range],
                                 repository_info), None)

    def do_diff(self, cmd, repository_info=None):
        """
        Performs the actual diff operation, handling renames and converting
        paths to absolute.
        """
        diff = execute(cmd, split_lines=True)
        diff = self.handle_renames(diff)
        diff = self.convert_to_absolute_paths(diff, repository_info)

        return ''.join(diff)

    def handle_renames(self, diff_content):
        """
        The output of svn diff is incorrect when the file in question came
        into being via svn mv/cp. Although the patch for these files are
        relative to its parent, the diff header doesn't reflect this.
        This function fixes the relevant section headers of the patch to
        portray this relationship.
        """

        # svn diff against a repository URL on two revisions appears to
        # handle moved files properly, so only adjust the diff file names
        # if they were created using a working copy.
        if options.repository_url:
            return diff_content

        result = []

        from_line = ""
        for line in diff_content:
            if self.DIFF_ORIG_FILE_LINE_RE.match(line):
                from_line = line
                continue

            # This is where we decide how mangle the previous '--- '
            if self.DIFF_NEW_FILE_LINE_RE.match(line):
                to_file, _ = self.parse_filename_header(line[4:])
                info       = self.svn_info(to_file)
                if info.has_key("Copied From URL"):
                    url       = info["Copied From URL"]
                    root      = info["Repository Root"]
                    from_file = urllib.unquote(url[len(root):])
                    result.append(from_line.replace(to_file, from_file))
                else:
                    result.append(from_line) #as is, no copy performed

            # We only mangle '---' lines. All others get added straight to
            # the output.
            result.append(line)

        return result


    def convert_to_absolute_paths(self, diff_content, repository_info):
        """
        Converts relative paths in a diff output to absolute paths.
        This handles paths that have been svn switched to other parts of the
        repository.
        """

        result = []

        for line in diff_content:
            front = None
            if (self.DIFF_NEW_FILE_LINE_RE.match(line)
                or self.DIFF_ORIG_FILE_LINE_RE.match(line)
                or line.startswith('Index: ')):
                front, line = line.split(" ", 1)

            if front:
                if line.startswith('/'): #already absolute
                    line = front + " " + line
                else:
                    # filename and rest of line (usually the revision
                    # component)
                    file, rest = self.parse_filename_header(line)

                    # If working with a diff generated outside of a working
                    # copy, then file paths are already absolute, so just
                    # add initial slash.
                    if options.repository_url:
                        path = urllib.unquote(
                            "%s/%s" % (repository_info.base_path, file))
                    else:
                        info = self.svn_info(file)
                        url  = info["URL"]
                        root = info["Repository Root"]
                        path = urllib.unquote(url[len(root):])

                    line = front + " " + path + rest

            result.append(line)

        return result

    def svn_info(self, path):
        """Return a dict which is the result of 'svn info' at a given path."""
        svninfo = {}
        for info in execute(["svn", "info", path],
                            split_lines=True):
            parts = info.strip().split(": ", 1)
            if len(parts) == 2:
                key, value = parts
                svninfo[key] = value

        return svninfo

    # Adapted from server code parser.py
    def parse_filename_header(self, s):
        parts = None
        if "\t" in s:
            # There's a \t separating the filename and info. This is the
            # best case scenario, since it allows for filenames with spaces
            # without much work. The info can also contain tabs after the
            # initial one; ignore those when splitting the string.
            parts = s.split("\t", 1)

        # There's spaces being used to separate the filename and info.
        # This is technically wrong, so all we can do is assume that
        # 1) the filename won't have multiple consecutive spaces, and
        # 2) there's at least 2 spaces separating the filename and info.
        if "  " in s:
            parts = re.split(r"  +", s)

        if parts:
            parts[1] = '\t' + parts[1]
            return parts

        # strip off ending newline, and return it as the second component
        return [s.split('\n')[0], '\n']


class PerforceClient(SCMClient):
    """
    A wrapper around the p4 Perforce tool that fetches repository information
    and generates compatible diffs.
    """
    def get_repository_info(self):
        if not check_install('p4 help'):
            return None

        data = execute(["p4", "info"], ignore_errors=True)

        m = re.search(r'^Server address: (.+)$', data, re.M)
        if not m:
            return None

        repository_path = m.group(1).strip()

        try:
            hostname, port = repository_path.split(":")
            info = socket.gethostbyaddr(hostname)

            # If aliases exist for hostname, create a list of alias:port
            # strings for repository_path.
            if info[1]:
                servers = [info[0]] + info[1]
                repository_path = ["%s:%s" % (server, port)
                                   for server in servers]
            else:
                repository_path = "%s:%s" % (info[0], port)
        except (socket.gaierror, socket.herror):
            pass

        m = re.search(r'^Server version: [^ ]*/([0-9]+)\.([0-9]+)/[0-9]+ .*$',
                      data, re.M)
        self.p4d_version = int(m.group(1)), int(m.group(2))

        return RepositoryInfo(path=repository_path, supports_changesets=True)

    def scan_for_server(self, repository_info):
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = \
            super(PerforceClient, self).scan_for_server(repository_info)

        if server_url:
            return server_url

        return self.scan_for_server_counter(repository_info)

    def scan_for_server_counter(self, repository_info):
        """
        Checks the Perforce counters to see if the Review Board server's url
        is specified. Since Perforce only started supporting non-numeric
        counter values in server version 2008.1, we support both a normal
        counter 'reviewboard.url' with a string value and embedding the url in
        a counter name like 'reviewboard.url.http:||reviewboard.example.com'.
        Note that forward slashes aren't allowed in counter names, so
        pipe ('|') characters should be used. These should be safe because they
        should not be used unencoded in urls.
        """

        counters_text = execute(["p4", "counters"])

        # Try for a "reviewboard.url" counter first.
        m = re.search(r'^reviewboard.url = (\S+)', counters_text, re.M)

        if m:
            return m.group(1)

        # Next try for a counter of the form:
        # reviewboard_url.http:||reviewboard.example.com
        m2 = re.search(r'^reviewboard.url\.(\S+)', counters_text, re.M)

        if m2:
            return m2.group(1).replace('|', '/')

        return None

    def get_changenum(self, args):
        if len(args) == 0:
            return "default"
        elif len(args) == 1:
            if args[0] == "default":
                return "default"

            try:
                return str(int(args[0]))
            except ValueError:
                # (if it isn't a number, it can't be a cln)
                return None
        # there are multiple args (not a cln)
        else:
            return None

    def diff(self, args):
        """
        Goes through the hard work of generating a diff on Perforce in order
        to take into account adds/deletes and to provide the necessary
        revision information.
        """
        # set the P4 enviroment:
        if options.p4_client:
           os.environ['P4CLIENT'] = options.p4_client

        if options.p4_port:
           os.environ['P4PORT'] = options.p4_port

        if options.p4_passwd:
            os.environ['P4PASSWD'] = options.p4_passwd

        changenum = self.get_changenum(args)
        if changenum is None:
            return self._path_diff(args)
        else:
            return self._changenum_diff(changenum)


    def _path_diff(self, args):
        """
        Process a path-style diff.  See _changenum_diff for the alternate
        version that handles specific change numbers.

        Multiple paths may be specified in `args`.  The path styles supported
        are:

        //path/to/file
        Upload file as a "new" file.

        //path/to/dir/...
        Upload all files as "new" files.

        //path/to/file[@#]rev
        Upload file from that rev as a "new" file.

        //path/to/file[@#]rev,[@#]rev
        Upload a diff between revs.

        //path/to/dir/...[@#]rev,[@#]rev
        Upload a diff of all files between revs in that directory.
        """
        r_revision_range = re.compile(r'^(?P<path>//[^@#]+)' +
                                      r'(?P<revision1>[#@][^,]+)?' +
                                      r'(?P<revision2>,[#@][^,]+)?$')

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        diff_lines = []

        for path in args:
            m = r_revision_range.match(path)

            if not m:
                die('Path %r does not match a valid Perforce path.' % (path,))
            revision1 = m.group('revision1')
            revision2 = m.group('revision2')
            first_rev_path = m.group('path')

            if revision1:
                first_rev_path += revision1
            records = self._run_p4(['files', first_rev_path])

            # Make a map for convenience.
            files = {}

            # Records are:
            # 'rev': '1'
            # 'func': '...'
            # 'time': '1214418871'
            # 'action': 'edit'
            # 'type': 'ktext'
            # 'depotFile': '...'
            # 'change': '123456'
            for record in records:
                if record['action'] not in ('delete', 'move/delete'):
                    if revision2:
                        files[record['depotFile']] = [record, None]
                    else:
                        files[record['depotFile']] = [None, record]

            if revision2:
                # [1:] to skip the comma.
                second_rev_path = m.group('path') + revision2[1:]
                records = self._run_p4(['files', second_rev_path])
                for record in records:
                    if record['action'] not in ('delete', 'move/delete'):
                        try:
                            m = files[record['depotFile']]
                            m[1] = record
                        except KeyError:
                            files[record['depotFile']] = [None, record]

            old_file = new_file = empty_filename
            changetype_short = None

            for depot_path, (first_record, second_record) in files.items():
                old_file = new_file = empty_filename
                if first_record is None:
                    self._write_file(depot_path + '#' + second_record['rev'],
                                     tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                    changetype_short = 'A'
                    base_revision = 0
                elif second_record is None:
                    self._write_file(depot_path + '#' + first_record['rev'],
                                     tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                    changetype_short = 'D'
                    base_revision = int(first_record['rev'])
                elif first_record['rev'] == second_record['rev']:
                    # We when we know the revisions are the same, we don't need
                    # to do any diffing. This speeds up large revision-range
                    # diffs quite a bit.
                    continue
                else:
                    self._write_file(depot_path + '#' + first_record['rev'],
                                     tmp_diff_from_filename)
                    self._write_file(depot_path + '#' + second_record['rev'],
                                     tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                    old_file = tmp_diff_from_filename
                    changetype_short = 'M'
                    base_revision = int(first_record['rev'])

                dl = self._do_diff(old_file, new_file, depot_path,
                                   base_revision, changetype_short,
                                   ignore_unmodified=True)
                diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)
        return (''.join(diff_lines), None)

    def _run_p4(self, command):
        """Execute a perforce command using the python marshal API.

        - command: A list of strings of the command to execute.

        The return type depends on the command being run.
        """
        command = ['p4', '-G'] + command
        p = subprocess.Popen(command, stdout=subprocess.PIPE)
        result = []
        has_error = False

        while 1:
            try:
                data = marshal.load(p.stdout)
            except EOFError:
                break
            else:
                result.append(data)
                if data.get('code', None) == 'error':
                    has_error = True

        rc = p.wait()

        if rc or has_error:
            for record in result:
                if 'data' in record:
                    print record['data']
            die('Failed to execute command: %s\n' % (command,))

        return result

    """
    Return a "sanitized" change number for submission to the Review Board
    server. For default changelists, this is always None. Otherwise, use the
    changelist number for submitted changelists, or if the p4d is 2002.2 or
    newer.

    This is because p4d < 2002.2 does not return enough information about
    pending changelists in 'p4 describe' for Review Board to make use of them
    (specifically, the list of files is missing). This would result in the
    diffs being rejected.
    """
    def sanitize_changenum(self, changenum):
        if changenum == "default":
            return None
        else:
            v = self.p4d_version

            if v[0] < 2002 or (v[0] == "2002" and v[1] < 2):
                describeCmd = ["p4"]

                if options.p4_passwd:
                    describeCmd.append("-P")
                    describeCmd.append(options.p4_passwd)

                describeCmd = describeCmd + ["describe", "-s", changenum]

                description = execute(describeCmd, split_lines=True)

                if '*pending*' in description[0]:
                    return None

        return changenum

    def _changenum_diff(self, changenum):
        """
        Process a diff for a particular change number.  This handles both
        pending and submitted changelists.

        See _path_diff for the alternate version that does diffs of depot
        paths.
        """
        # TODO: It might be a good idea to enhance PerforceDiffParser to
        # understand that newFile could include a revision tag for post-submit
        # reviewing.
        cl_is_pending = False

        debug("Generating diff for changenum %s" % changenum)

        description = []

        if changenum == "default":
            cl_is_pending = True
        else:
            describeCmd = ["p4"]

            if options.p4_passwd:
                describeCmd.append("-P")
                describeCmd.append(options.p4_passwd)

            describeCmd = describeCmd + ["describe", "-s", changenum]

            description = execute(describeCmd, split_lines=True)

            if re.search("no such changelist", description[0]):
                die("CLN %s does not exist." % changenum)

            # Some P4 wrappers are addding an extra line before the description
            if '*pending*' in description[0] or '*pending*' in description[1]:
                cl_is_pending = True

        v = self.p4d_version

        if cl_is_pending and (v[0] < 2002 or (v[0] == "2002" and v[1] < 2)
                              or changenum == "default"):
            # Pre-2002.2 doesn't give file list in pending changelists,
            # or we don't have a description for a default changeset,
            # so we have to get it a different way.
            info = execute(["p4", "opened", "-c", str(changenum)],
                           split_lines=True)

            if len(info) == 1 and info[0].startswith("File(s) not opened on this client."):
                die("Couldn't find any affected files for this change.")

            for line in info:
                data = line.split(" ")
                description.append("... %s %s" % (data[0], data[2]))

        else:
            # Get the file list
            for line_num, line in enumerate(description):
                if 'Affected files ...' in line:
                    break
            else:
                # Got to the end of all the description lines and didn't find
                # what we were looking for.
                die("Couldn't find any affected files for this change.")

            description = description[line_num+2:]

        diff_lines = []

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        for line in description:
            line = line.strip()
            if not line:
                continue

            m = re.search(r'\.\.\. ([^#]+)#(\d+) '
                          r'(add|edit|delete|integrate|branch|move/add'
                          r'|move/delete)',
                          line)
            if not m:
                die("Unsupported line from p4 opened: %s" % line)

            depot_path = m.group(1)
            base_revision = int(m.group(2))
            if not cl_is_pending:
                # If the changelist is pending our base revision is the one that's
                # currently in the depot. If we're not pending the base revision is
                # actually the revision prior to this one
                base_revision -= 1

            changetype = m.group(3)

            debug('Processing %s of %s' % (changetype, depot_path))

            old_file = new_file = empty_filename
            old_depot_path = new_depot_path = None
            changetype_short = None

            if changetype in ['edit', 'integrate']:
                # A big assumption
                new_revision = base_revision + 1

                # We have an old file, get p4 to take this old version from the
                # depot and put it into a plain old temp file for us
                old_depot_path = "%s#%s" % (depot_path, base_revision)
                self._write_file(old_depot_path, tmp_diff_from_filename)
                old_file = tmp_diff_from_filename

                # Also print out the new file into a tmpfile
                if cl_is_pending:
                    new_file = self._depot_to_local(depot_path)
                else:
                    new_depot_path = "%s#%s" %(depot_path, new_revision)
                    self._write_file(new_depot_path, tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename

                changetype_short = "M"
            elif changetype in ['add', 'branch', 'move/add']:
                # We have a new file, get p4 to put this new file into a pretty
                # temp file for us. No old file to worry about here.
                if cl_is_pending:
                    new_file = self._depot_to_local(depot_path)
                else:
                    self._write_file(depot_path, tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                changetype_short = "A"
            elif changetype in ['delete', 'move/delete']:
                # We've deleted a file, get p4 to put the deleted file into  a temp
                # file for us. The new file remains the empty file.
                old_depot_path = "%s#%s" % (depot_path, base_revision)
                self._write_file(old_depot_path, tmp_diff_from_filename)
                old_file = tmp_diff_from_filename
                changetype_short = "D"
            else:
                die("Unknown change type '%s' for %s" % (changetype, depot_path))

            dl = self._do_diff(old_file, new_file, depot_path, base_revision, changetype_short)
            diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)
        return (''.join(diff_lines), None)

    def _do_diff(self, old_file, new_file, depot_path, base_revision,
                 changetype_short, ignore_unmodified=False):
        """
        Do the work of producing a diff for Perforce.

        old_file - The absolute path to the "old" file.
        new_file - The absolute path to the "new" file.
        depot_path - The depot path in Perforce for this file.
        base_revision - The base perforce revision number of the old file as
            an integer.
        changetype_short - The change type as a single character string.
        ignore_unmodified - If True, will return an empty list if the file
            is not changed.

        Returns a list of strings of diff lines.
        """
        if hasattr(os, 'uname') and os.uname()[0] == 'SunOS':
            diff_cmd = ["gdiff", "-urNp", old_file, new_file]
        else:
            diff_cmd = ["diff", "-urNp", old_file, new_file]
        # Diff returns "1" if differences were found.
        dl = execute(diff_cmd, extra_ignore_errors=(1,2),
                     translate_newlines=False)

        # If the input file has ^M characters at end of line, lets ignore them.
        dl = dl.replace('\r\r\n', '\r\n')
        dl = dl.splitlines(True)

        cwd = os.getcwd()
        if depot_path.startswith(cwd):
            local_path = depot_path[len(cwd) + 1:]
        else:
            local_path = depot_path

        # Special handling for the output of the diff tool on binary files:
        #     diff outputs "Files a and b differ"
        # and the code below expects the output to start with
        #     "Binary files "
        if len(dl) == 1 and \
           dl[0].startswith('Files %s and %s differ' %
                            (old_file, new_file)):
            dl = ['Binary files %s and %s differ\n' % (old_file, new_file)]

        if dl == [] or dl[0].startswith("Binary files "):
            if dl == []:
                if ignore_unmodified:
                    return []
                else:
                    print "Warning: %s in your changeset is unmodified" % \
                        local_path

            dl.insert(0, "==== %s#%s ==%s== %s ====\n" % \
                (depot_path, base_revision, changetype_short, local_path))
            dl.append('\n')
        elif len(dl) > 1:
            m = re.search(r'(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)', dl[1])
            if m:
                timestamp = m.group(1)
            else:
                # Thu Sep  3 11:24:48 2007
                m = re.search(r'(\w+)\s+(\w+)\s+(\d+)\s+(\d\d:\d\d:\d\d)\s+(\d\d\d\d)', dl[1])
                if not m:
                    die("Unable to parse diff header: %s" % dl[1])

                month_map = {
                    "Jan": "01",
                    "Feb": "02",
                    "Mar": "03",
                    "Apr": "04",
                    "May": "05",
                    "Jun": "06",
                    "Jul": "07",
                    "Aug": "08",
                    "Sep": "09",
                    "Oct": "10",
                    "Nov": "11",
                    "Dec": "12",
                }
                month = month_map[m.group(2)]
                day = m.group(3)
                timestamp = m.group(4)
                year = m.group(5)

                timestamp = "%s-%s-%s %s" % (year, month, day, timestamp)

            dl[0] = "--- %s\t%s#%s\n" % (local_path, depot_path, base_revision)
            dl[1] = "+++ %s\t%s\n" % (local_path, timestamp)

            # Not everybody has files that end in a newline (ugh). This ensures
            # that the resulting diff file isn't broken.
            if dl[-1][-1] != '\n':
                dl.append('\n')
        else:
            die("ERROR, no valid diffs: %s" % dl[0])

        return dl

    def _write_file(self, depot_path, tmpfile):
        """
        Grabs a file from Perforce and writes it to a temp file. p4 print sets
        the file readonly and that causes a later call to unlink fail. So we
        make the file read/write.
        """
        debug('Writing "%s" to "%s"' % (depot_path, tmpfile))
        execute(["p4", "print", "-o", tmpfile, "-q", depot_path])
        os.chmod(tmpfile, stat.S_IREAD | stat.S_IWRITE)

    def _depot_to_local(self, depot_path):
        """
        Given a path in the depot return the path on the local filesystem to
        the same file.  If there are multiple results, take only the last
        result from the where command.
        """
        where_output = self._run_p4(['where', depot_path])

        try:
            return where_output[-1]['path']
        except:
            # XXX: This breaks on filenames with spaces.
            return where_output[-1]['data'].split(' ')[2].strip()


class MercurialClient(SCMClient):
    """
    A wrapper around the hg Mercurial tool that fetches repository
    information and generates compatible diffs.
    """

    def __init__(self):
        self.hgrc = {}
        self._type = 'hg'
        self._hg_root = ''
        self._remote_path = ()
        self._hg_env = {
            'HGRCPATH': os.devnull,
            'HGPLAIN': '1',
        }

        # `self._remote_path_candidates` is an ordered set of hgrc
        # paths that are checked if `parent_branch` option is not given
        # explicitly.  The first candidate found to exist will be used,
        # falling back to `default` (the last member.)
        self._remote_path_candidates = ['reviewboard', 'origin', 'parent',
                                        'default']

    def get_repository_info(self):
        if not check_install('hg --help'):
            return None

        self._load_hgrc()

        if not self.hg_root:
            # hg aborted => no mercurial repository here.
            return None

        svn_info = execute(["hg", "svn", "info"], ignore_errors=True)

        if (not svn_info.startswith('abort:') and
            not svn_info.startswith("hg: unknown command") and
            not svn_info.lower().startswith('not a child of')):
            return self._calculate_hgsubversion_repository_info(svn_info)

        self._type = 'hg'

        path = self.hg_root
        base_path = '/'

        if self.hgrc:
            self._calculate_remote_path()

            if self._remote_path:
                path = self._remote_path[1]
                base_path = ''

        return RepositoryInfo(path=path, base_path=base_path,
                              supports_parent_diffs=True)

    def _calculate_remote_path(self):
        for candidate in self._remote_path_candidates:

            rc_key = 'paths.%s' % candidate

            if (not self._remote_path and self.hgrc.get(rc_key)):
                self._remote_path = (candidate, self.hgrc.get(rc_key))
                debug('Using candidate path %r: %r' % self._remote_path)

                return

    def _calculate_hgsubversion_repository_info(self, svn_info):
        self._type = 'svn'
        m = re.search(r'^Repository Root: (.+)$', svn_info, re.M)

        if not m:
            return None

        path = m.group(1)
        m2 = re.match(r'^(svn\+ssh|http|https|svn)://([-a-zA-Z0-9.]*@)(.*)$',
                        path)
        if m2:
            path = '%s://%s' % (m2.group(1), m2.group(3))

        m = re.search(r'^URL: (.+)$', svn_info, re.M)

        if not m:
            return None

        base_path = m.group(1)[len(path):] or "/"
        return RepositoryInfo(path=path, base_path=base_path,
                              supports_parent_diffs=True)

    @property
    def hg_root(self):
        if not self._hg_root:
            root = execute(['hg', 'root'], env=self._hg_env,
                           ignore_errors=True)

            if not root.startswith('abort:'):
                self._hg_root = root.strip()
            else:
                return None

        return self._hg_root

    def _load_hgrc(self):
        for line in execute(['hg', 'showconfig'], split_lines=True):
            key, value = line.split('=', 1)
            self.hgrc[key] = value.strip()

    def extract_summary(self, revision):
        """
        Extracts the first line from the description of the given changeset.
        """
        return execute(['hg', 'log', '-r%s' % revision, '--template',
                        r'{desc|firstline}\n'], env=self._hg_env)

    def extract_description(self, rev1, rev2):
        """
        Extracts all descriptions in the given revision range and concatenates
        them, most recent ones going first.
        """
        numrevs = len(execute([
            'hg', 'log', '-r%s:%s' % (rev2, rev1),
            '--follow', '--template', r'{rev}\n'], env=self._hg_env
        ).strip().split('\n'))

        return execute(['hg', 'log', '-r%s:%s' % (rev2, rev1),
                        '--follow', '--template',
                        r'{desc}\n\n', '--limit',
                        str(numrevs - 1)], env=self._hg_env).strip()

    def diff(self, files):
        """
        Performs a diff across all modified files in a Mercurial repository.
        """
        files = files or []

        if self._type == 'svn':
            return self._get_hgsubversion_diff(files)
        else:
            return self._get_outgoing_diff(files)

    def _get_hgsubversion_diff(self, files):
        parent = execute(['hg', 'parent', '--svn', '--template',
                          '{node}\n']).strip()

        if options.parent_branch:
            parent = options.parent_branch

        if options.guess_summary and not options.summary:
            options.summary = self.extract_summary(".")

        if options.guess_description and not options.description:
            options.description = self.extract_description(parent, ".")

        return (execute(["hg", "diff", "--svn", '-r%s:.' % parent]), None)

    def _get_outgoing_diff(self, files):
        """
        When working with a clone of a Mercurial remote, we need to find
        out what the outgoing revisions are for a given branch.  It would
        be nice if we could just do `hg outgoing --patch <remote>`, but
        there are a couple of problems with this.

        For one, the server-side diff parser isn't yet equipped to filter out
        diff headers such as "comparing with..." and "changeset: <rev>:<hash>".
        Another problem is that the output of `outgoing` potentially includes
        changesets across multiple branches.

        In order to provide the most accurate comparison between one's local
        clone and a given remote -- something akin to git's diff command syntax
        `git diff <treeish>..<treeish>` -- we have to do the following:

            - get the name of the current branch
            - get a list of outgoing changesets, specifying a custom format
            - filter outgoing changesets by the current branch name
            - get the "top" and "bottom" outgoing changesets
            - use these changesets as arguments to `hg diff -r <rev> -r <rev>`


        Future modifications may need to be made to account for odd cases like
        having multiple diverged branches which share partial history -- or we
        can just punish developers for doing such nonsense :)
        """
        files = files or []

        remote = self._remote_path[0]

        if not remote and options.parent_branch:
            remote = options.parent_branch

        current_branch = execute(['hg', 'branch'], env=self._hg_env).strip()

        outgoing_changesets = \
            self._get_outgoing_changesets(current_branch, remote)

        top_rev, bottom_rev = \
            self._get_top_and_bottom_outgoing_revs(outgoing_changesets)

        if options.guess_summary and not options.summary:
            options.summary = self.extract_summary(top_rev).rstrip("\n")

        if options.guess_description and not options.description:
            options.description = self.extract_description(bottom_rev, top_rev)

        full_command = ['hg', 'diff', '-r', str(bottom_rev), '-r',
                        str(top_rev)] + files

        return (execute(full_command, env=self._hg_env), None)

    def _get_outgoing_changesets(self, current_branch, remote):
        """
        Given the current branch name and a remote path, return a list
        of outgoing changeset numbers.
        """
        outgoing_changesets = []
        raw_outgoing = execute(['hg', '-q', 'outgoing', '--template',
                                'b:{branches}\nr:{rev}\n\n', remote],
                               env=self._hg_env)

        for pair in raw_outgoing.split('\n\n'):
            if not pair.strip():
                continue

            branch, rev = pair.strip().split('\n')

            branch_name = branch[len('b:'):].strip()
            branch_name = branch_name or 'default'
            revno = rev[len('r:'):]

            if branch_name == current_branch and revno.isdigit():
                debug('Found outgoing changeset %s for branch %r'
                      % (revno, branch_name))
                outgoing_changesets.append(int(revno))

        return outgoing_changesets

    def _get_top_and_bottom_outgoing_revs(self, outgoing_changesets):
        # This is a classmethod rather than a func mostly just to keep the
        # module namespace clean.  Pylint told me to do it.
        top_rev = max(outgoing_changesets)
        bottom_rev = min(outgoing_changesets)

        parents = execute(["hg", "log", "-r", str(bottom_rev), "--template", "{parents}"],
                       env=self._hg_env)
        parents = parents.rstrip("\n").split(":")
        if (len(parents) > 1):
            bottom_rev = parents[0]
        else:
            bottom_rev = bottom_rev - 1

        bottom_rev = max([0, bottom_rev])

        return top_rev, bottom_rev

    def diff_between_revisions(self, revision_range, args, repository_info):
        """
        Performs a diff between 2 revisions of a Mercurial repository.
        """
        if self._type != 'hg':
            raise NotImplementedError

        r1, r2 = revision_range.split(':')

        if options.guess_summary and not options.summary:
            options.summary = self.extract_summary(r2)

        if options.guess_description and not options.description:
            options.description = self.extract_description(r1, r2)

        return (execute(["hg", "diff", "-r", r1, "-r", r2],
                        env=self._hg_env), None)

    def scan_for_server(self, repository_info):
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = \
            super(MercurialClient, self).scan_for_server(repository_info)

        if not server_url and self.hgrc.get('reviewboard.url'):
            server_url = self.hgrc.get('reviewboard.url').strip()

        if not server_url and self._type == "svn":
            # Try using the reviewboard:url property on the SVN repo, if it
            # exists.
            prop = SVNClient().scan_for_server_property(repository_info)

            if prop:
                return prop

        return server_url


class GitClient(SCMClient):
    """
    A wrapper around git that fetches repository information and generates
    compatible diffs. This will attempt to generate a diff suitable for the
    remote repository, whether git, SVN or Perforce.
    """
    def __init__(self):
        SCMClient.__init__(self)
        # Store the 'correct' way to invoke git, just plain old 'git' by default
        self.git = 'git'

    def _strip_heads_prefix(self, ref):
        """ Strips prefix from ref name, if possible """
        return re.sub(r'^refs/heads/', '', ref)

    def get_repository_info(self):
        if not check_install('git --help'):
            # CreateProcess (launched via subprocess, used by check_install)
            # does not automatically append .cmd for things it finds in PATH.
            # If we're on Windows, and this works, save it for further use.
            if sys.platform.startswith('win') and check_install('git.cmd --help'):
                self.git = 'git.cmd'
            else:
                return None

        git_dir = execute([self.git, "rev-parse", "--git-dir"],
                          ignore_errors=True).rstrip("\n")

        if git_dir.startswith("fatal:") or not os.path.isdir(git_dir):
            return None
        self.bare = execute([self.git, "config", "core.bare"]).strip() == 'true'

        # post-review in directories other than the top level of
        # of a work-tree would result in broken diffs on the server
        if not self.bare:
            os.chdir(os.path.dirname(os.path.abspath(git_dir)))

        self.head_ref = execute([self.git, 'symbolic-ref', '-q', 'HEAD']).strip()

        # We know we have something we can work with. Let's find out
        # what it is. We'll try SVN first, but only if there's a .git/svn
        # directory. Otherwise, it may attempt to create one and scan
        # revisions, which can be slow.
        git_svn_dir = os.path.join(git_dir, 'svn')

        if os.path.isdir(git_svn_dir) and len(os.listdir(git_svn_dir)) > 0:
            data = execute([self.git, "svn", "info"], ignore_errors=True)

            m = re.search(r'^Repository Root: (.+)$', data, re.M)

            if m:
                path = m.group(1)
                m = re.search(r'^URL: (.+)$', data, re.M)

                if m:
                    base_path = m.group(1)[len(path):] or "/"
                    m = re.search(r'^Repository UUID: (.+)$', data, re.M)

                    if m:
                        uuid = m.group(1)
                        self.type = "svn"

                        # Get SVN tracking branch
                        if options.parent_branch:
                            self.upstream_branch = options.parent_branch
                        else:
                            data = execute([self.git, "svn", "rebase", "-n"],
                                           ignore_errors=True)
                            m = re.search(r'^Remote Branch:\s*(.+)$', data, re.M)

                            if m:
                                self.upstream_branch = m.group(1)
                            else:
                                sys.stderr.write('Failed to determine SVN tracking '
                                                 'branch. Defaulting to "master"\n')
                                self.upstream_branch = 'master'

                        return SvnRepositoryInfo(path=path,
                                                 base_path=base_path,
                                                 uuid=uuid,
                                                 supports_parent_diffs=True)
            else:
                # Versions of git-svn before 1.5.4 don't (appear to) support
                # 'git svn info'.  If we fail because of an older git install,
                # here, figure out what version of git is installed and give
                # the user a hint about what to do next.
                version = execute([self.git, "svn", "--version"],
                                  ignore_errors=True)
                version_parts = re.search('version (\d+)\.(\d+)\.(\d+)',
                                          version)
                svn_remote = execute([self.git, "config", "--get",
                                      "svn-remote.svn.url"],
                                      ignore_errors=True)

                if (version_parts and
                    not self.is_valid_version((int(version_parts.group(1)),
                                               int(version_parts.group(2)),
                                               int(version_parts.group(3))),
                                              (1, 5, 4)) and
                    svn_remote):
                    die("Your installation of git-svn must be upgraded to "
                        "version 1.5.4 or later")

        # Okay, maybe Perforce.
        # TODO

        # Nope, it's git then.
        # Check for a tracking branch and determine merge-base
        short_head = self._strip_heads_prefix(self.head_ref)
        merge = execute([self.git, 'config', '--get',
                         'branch.%s.merge' % short_head],
                        ignore_errors=True).strip()
        remote = execute([self.git, 'config', '--get',
                          'branch.%s.remote' % short_head],
                         ignore_errors=True).strip()

        merge = self._strip_heads_prefix(merge)
        self.upstream_branch = ''

        if remote and remote != '.' and merge:
            self.upstream_branch = '%s/%s' % (remote, merge)

        url = None
        if options.repository_url:
            url = options.repository_url
        else:
            self.upstream_branch, origin_url = \
                self.get_origin(self.upstream_branch, True)

            if not origin_url or origin_url.startswith("fatal:"):
                self.upstream_branch, origin_url = self.get_origin()

            url = origin_url.rstrip('/')

        # Central bare repositories don't have origin URLs.
        # We return git_dir instead and hope for the best.
        url = origin_url.rstrip('/')

        if not url:
            url = os.path.abspath(git_dir)

            # There is no remote, so skip this part of upstream_branch.
            self.upstream_branch = self.upstream_branch.split('/')[-1]
        if url:
            self.type = "git"
            return RepositoryInfo(path=url, base_path='',
                                  supports_parent_diffs=True)

        return None

    def get_origin(self, default_upstream_branch=None, ignore_errors=False):
        """Get upstream remote origin from options or parameters.

        Returns a tuple: (upstream_branch, remote_url)
        """
        upstream_branch = options.tracking or default_upstream_branch or \
                          'origin/master'
        upstream_remote = upstream_branch.split('/')[0]
        origin_url = execute([self.git, "config", "--get",
                              "remote.%s.url" % upstream_remote],
                              ignore_errors=True).rstrip("\n")
        return (upstream_branch, origin_url)

    def is_valid_version(self, actual, expected):
        """
        Takes two tuples, both in the form:
            (major_version, minor_version, micro_version)
        Returns true if the actual version is greater than or equal to
        the expected version, and false otherwise.
        """
        return (actual[0] > expected[0]) or \
               (actual[0] == expected[0] and actual[1] > expected[1]) or \
               (actual[0] == expected[0] and actual[1] == expected[1] and \
                actual[2] >= expected[2])

    def scan_for_server(self, repository_info):
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = super(GitClient, self).scan_for_server(repository_info)

        if server_url:
            return server_url

        # TODO: Maybe support a server per remote later? Is that useful?
        url = execute([self.git, "config", "--get", "reviewboard.url"],
                      ignore_errors=True).strip()
        if url:
            return url

        if self.type == "svn":
            # Try using the reviewboard:url property on the SVN repo, if it
            # exists.
            prop = SVNClient().scan_for_server_property(repository_info)

            if prop:
                return prop

        return None

    def diff(self, args):
        """
        Performs a diff across all modified files in the branch, taking into
        account a parent branch.
        """
        parent_branch = options.parent_branch

        self.merge_base = execute([self.git, "merge-base", self.upstream_branch,
                                   self.head_ref]).strip()

        if parent_branch:
            diff_lines = self.make_diff(parent_branch)
            parent_diff_lines = self.make_diff(self.merge_base, parent_branch)
        else:
            diff_lines = self.make_diff(self.merge_base, self.head_ref)
            parent_diff_lines = None

        if options.guess_summary and not options.summary:
            options.summary = execute([self.git, "log", "--pretty=format:%s",
                                       "HEAD^.."], ignore_errors=True).strip()

        if options.guess_description and not options.description:
            options.description = execute(
                [self.git, "log", "--pretty=format:%s%n%n%b",
                 (parent_branch or self.merge_base) + ".."],
                ignore_errors=True).strip()

        return (diff_lines, parent_diff_lines)

    def make_diff(self, ancestor, commit=""):
        """
        Performs a diff on a particular branch range.
        """
        if commit:
            rev_range = "%s..%s" % (ancestor, commit)
        else:
            rev_range = ancestor

        if self.type == "svn":
            diff_lines = execute([self.git, "diff", "--no-color", "--no-prefix",
                                  "--no-ext-diff", "-r", "-u", rev_range],
                                 split_lines=True)
            return self.make_svn_diff(ancestor, diff_lines)
        elif self.type == "git":
            return execute([self.git, "diff", "--no-color", "--full-index",
                            "--no-ext-diff", rev_range])

        return None

    def make_svn_diff(self, parent_branch, diff_lines):
        """
        Formats the output of git diff such that it's in a form that
        svn diff would generate. This is needed so the SVNTool in Review
        Board can properly parse this diff.
        """
        rev = execute([self.git, "svn", "find-rev", parent_branch]).strip()

        if not rev:
            return None

        diff_data = ""
        filename = ""
        newfile = False

        for line in diff_lines:
            if line.startswith("diff "):
                # Grab the filename and then filter this out.
                # This will be in the format of:
                #
                # diff --git a/path/to/file b/path/to/file
                info = line.split(" ")
                diff_data += "Index: %s\n" % info[2]
                diff_data += "=" * 67
                diff_data += "\n"
            elif line.startswith("index "):
                # Filter this out.
                pass
            elif line.strip() == "--- /dev/null":
                # New file
                newfile = True
            elif line.startswith("--- "):
                newfile = False
                diff_data += "--- %s\t(revision %s)\n" % \
                             (line[4:].strip(), rev)
            elif line.startswith("+++ "):
                filename = line[4:].strip()
                if newfile:
                    diff_data += "--- %s\t(revision 0)\n" % filename
                    diff_data += "+++ %s\t(revision 0)\n" % filename
                else:
                    # We already printed the "--- " line.
                    diff_data += "+++ %s\t(working copy)\n" % filename
            elif line.startswith("new file mode"):
                # Filter this out.
                pass
            elif line.startswith("Binary files "):
                # Add the following so that we know binary files were added/changed
                diff_data += "Cannot display: file marked as a binary type.\n"
                diff_data += "svn:mime-type = application/octet-stream\n"
            else:
                diff_data += line

        return diff_data

    def diff_between_revisions(self, revision_range, args, repository_info):
        """Perform a diff between two arbitrary revisions"""

        # Make a parent diff to the first of the revisions so that we
        # never end up with broken patches:
        self.merge_base = execute([self.git, "merge-base", self.upstream_branch,
                                   self.head_ref]).strip()

        if ":" not in revision_range:
            # only one revision is specified

            # Check if parent contains the first revision and make a
            # parent diff if not:
            pdiff_required = execute([self.git, "branch", "-r",
                                      "--contains", revision_range])
            parent_diff_lines = None

            if not pdiff_required:
                parent_diff_lines = self.make_diff(self.merge_base, revision_range)

            if options.guess_summary and not options.summary:
                options.summary = execute(
                    [self.git, "log", "--pretty=format:%s", revision_range + ".."],
                    ignore_errors=True).strip()

            if options.guess_description and not options.description:
                options.description = execute(
                    [self.git, "log", "--pretty=format:%s%n%n%b", revision_range + ".."],
                    ignore_errors=True).strip()

            return (self.make_diff(revision_range), parent_diff_lines)
        else:
            r1, r2 = revision_range.split(":")
            # Check if parent contains the first revision and make a
            # parent diff if not:
            pdiff_required = execute([self.git, "branch", "-r",
                                      "--contains", r1])
            parent_diff_lines = None

            if not pdiff_required:
                parent_diff_lines = self.make_diff(self.merge_base, r1)

            if options.guess_summary and not options.summary:
                options.summary = execute(
                    [self.git, "log", "--pretty=format:%s", "%s..%s" % (r1, r2)],
                    ignore_errors=True).strip()

            if options.guess_description and not options.description:
                options.description = execute(
                    [self.git, "log", "--pretty=format:%s%n%n%b", "%s..%s" % (r1, r2)],
                    ignore_errors=True).strip()

            return (self.make_diff(r1, r2), parent_diff_lines)


class PlasticClient(SCMClient):
    """
    A wrapper around the cm Plastic tool that fetches repository
    information and generates compatible diffs
    """
    def get_repository_info(self):
        if not check_install('cm version'):
            return None

        # Get the repository that the current directory is from.  If there
        # is more than one repository mounted in the current directory,
        # bail out for now (in future, should probably enter a review
        # request per each repository.)
        split = execute(["cm", "ls", "--format={8}"], split_lines=True,
                        ignore_errors=True)
        m = re.search(r'^rep:(.+)$', split[0], re.M)

        if not m:
            return None

        # Make sure the repository list contains only one unique entry
        if len(split) != split.count(split[0]):
            # Not unique!
            die('Directory contains more than one mounted repository')

        path = m.group(1)

        # Get the workspace directory, so we can strip it from the diff output
        self.workspacedir = execute(["cm", "gwp", ".", "--format={1}"],
                                    split_lines=False,
                                    ignore_errors=True).strip()

        debug("Workspace is %s" % self.workspacedir)

        return RepositoryInfo(path,
                              supports_changesets=True,
                              supports_parent_diffs=False)

    def get_changenum(self, args):
        """ Extract the integer value from a changeset ID (cs:1234) """
        if len(args) == 1 and args[0].startswith("cs:"):
                try:
                    return str(int(args[0][3:]))
                except ValueError:
                    pass

        return None

    def sanitize_changenum(self, changenum):
        """ Return a "sanitized" change number.  Currently a no-op """
        return changenum

    def diff(self, args):
        """
        Performs a diff across all modified files in a Plastic workspace

        Parent diffs are not supported (the second value in the tuple).
        """
        changenum = self.get_changenum(args)

        if changenum is None:
            return self.branch_diff(args), None
        else:
            return self.changenum_diff(changenum), None

    def diff_between_revisions(self, revision_range, args, repository_info):
        """
        Performs a diff between 2 revisions of a Plastic repository.

        Assume revision_range is a branch specification (br:/main/task001)
        and hand over to branch_diff
        """
        return (self.branch_diff(revision_range), None)

    def changenum_diff(self, changenum):
        debug("changenum_diff: %s" % (changenum))
        files = execute(["cm", "log", "cs:" + changenum,
                         "--csFormat={items}",
                         "--itemFormat={shortstatus} {path} "
                         "rev:revid:{revid} rev:revid:{parentrevid} "
                         "src:{srccmpath} rev:revid:{srcdirrevid} "
                         "dst:{dstcmpath} rev:revid:{dstdirrevid}{newline}"],
                        split_lines = True)

        debug("got files: %s" % (files))

        # Diff generation based on perforce client
        diff_lines = []

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        for f in files:
            f = f.strip()

            if not f:
                continue

            m = re.search(r'(?P<type>[ACIMR]) (?P<file>.*) '
                          r'(?P<revspec>rev:revid:[-\d]+) '
                          r'(?P<parentrevspec>rev:revid:[-\d]+) '
                          r'src:(?P<srcpath>.*) '
                          r'(?P<srcrevspec>rev:revid:[-\d]+) '
                          r'dst:(?P<dstpath>.*) '
                          r'(?P<dstrevspec>rev:revid:[-\d]+)$',
                          f)
            if not m:
                die("Could not parse 'cm log' response: %s" % f)

            changetype = m.group("type")
            filename = m.group("file")

            if changetype == "M":
                # Handle moved files as a delete followed by an add.
                # Clunky, but at least it works
                oldfilename = m.group("srcpath")
                oldspec = m.group("srcrevspec")
                newfilename = m.group("dstpath")
                newspec = m.group("dstrevspec")

                self.write_file(oldfilename, oldspec, tmp_diff_from_filename)
                dl = self.diff_files(tmp_diff_from_filename, empty_filename,
                                     oldfilename, "rev:revid:-1", oldspec,
                                     changetype)
                diff_lines += dl

                self.write_file(newfilename, newspec, tmp_diff_to_filename)
                dl = self.diff_files(empty_filename, tmp_diff_to_filename,
                                     newfilename, newspec, "rev:revid:-1",
                                     changetype)
                diff_lines += dl
            else:
                newrevspec = m.group("revspec")
                parentrevspec = m.group("parentrevspec")

                debug("Type %s File %s Old %s New %s" % (changetype,
                                                         filename,
                                                         parentrevspec,
                                                         newrevspec))

                old_file = new_file = empty_filename

                if (changetype in ['A'] or
                    (changetype in ['C', 'I'] and
                     parentrevspec == "rev:revid:-1")):
                    # File was Added, or a Change or Merge (type I) and there
                    # is no parent revision
                    self.write_file(filename, newrevspec, tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                elif changetype in ['C', 'I']:
                    # File was Changed or Merged (type I)
                    self.write_file(filename, parentrevspec,
                                    tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                    self.write_file(filename, newrevspec, tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                elif changetype in ['R']:
                    # File was Removed
                    self.write_file(filename, parentrevspec,
                                    tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                else:
                    die("Don't know how to handle change type '%s' for %s" %
                        (changetype, filename))

                dl = self.diff_files(old_file, new_file, filename,
                                     newrevspec, parentrevspec, changetype)
                diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)

        return ''.join(diff_lines)

    def branch_diff(self, args):
        debug("branch diff: %s" % (args))

        if len(args) > 0:
            branch = args[0]
        else:
            branch = args

        if not branch.startswith("br:"):
            return None

        if not options.branch:
            options.branch = branch

        files = execute(["cm", "fbc", branch, "--format={3} {4}"],
                        split_lines = True)
        debug("got files: %s" % (files))

        diff_lines = []

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        for f in files:
            f = f.strip()

            if not f:
                continue

            m = re.search(r'^(?P<branch>.*)#(?P<revno>\d+) (?P<file>.*)$', f)

            if not m:
                die("Could not parse 'cm fbc' response: %s" % f)

            filename = m.group("file")
            branch = m.group("branch")
            revno = m.group("revno")

            # Get the base revision with a cm find
            basefiles = execute(["cm", "find", "revs", "where",
                                 "item='" + filename + "'", "and",
                                 "branch='" + branch + "'", "and",
                                 "revno=" + revno,
                                 "--format={item} rev:revid:{id} "
                                 "rev:revid:{parent}", "--nototal"],
                                split_lines = True)

            # We only care about the first line
            m = re.search(r'^(?P<filename>.*) '
                              r'(?P<revspec>rev:revid:[-\d]+) '
                              r'(?P<parentrevspec>rev:revid:[-\d]+)$',
                              basefiles[0])
            basefilename = m.group("filename")
            newrevspec = m.group("revspec")
            parentrevspec = m.group("parentrevspec")

            # Cope with adds/removes
            changetype = "C"

            if parentrevspec == "rev:revid:-1":
                changetype = "A"
            elif newrevspec == "rev:revid:-1":
                changetype = "R"

            debug("Type %s File %s Old %s New %s" % (changetype,
                                                     basefilename,
                                                     parentrevspec,
                                                     newrevspec))

            old_file = new_file = empty_filename

            if changetype == "A":
                # File Added
                self.write_file(basefilename, newrevspec,
                                tmp_diff_to_filename)
                new_file = tmp_diff_to_filename
            elif changetype == "R":
                # File Removed
                self.write_file(basefilename, parentrevspec,
                                tmp_diff_from_filename)
                old_file = tmp_diff_from_filename
            else:
                self.write_file(basefilename, parentrevspec,
                                tmp_diff_from_filename)
                old_file = tmp_diff_from_filename

                self.write_file(basefilename, newrevspec,
                                tmp_diff_to_filename)
                new_file = tmp_diff_to_filename

            dl = self.diff_files(old_file, new_file, basefilename,
                                 newrevspec, parentrevspec, changetype)
            diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)

        return ''.join(diff_lines)

    def diff_files(self, old_file, new_file, filename, newrevspec,
                   parentrevspec, changetype, ignore_unmodified=False):
        """
        Do the work of producing a diff for Plastic (based on the Perforce one)

        old_file - The absolute path to the "old" file.
        new_file - The absolute path to the "new" file.
        filename - The file in the Plastic workspace
        newrevspec - The revid spec of the changed file
        parentrevspecspec - The revision spec of the "old" file
        changetype - The change type as a single character string
        ignore_unmodified - If true, will return an empty list if the file
            is not changed.

        Returns a list of strings of diff lines.
        """
        if filename.startswith(self.workspacedir):
            filename = filename[len(self.workspacedir):]

        diff_cmd = ["diff", "-urN", old_file, new_file]
        # Diff returns "1" if differences were found.
        dl = execute(diff_cmd, extra_ignore_errors=(1,2),
                     translate_newlines = False)

        # If the input file has ^M characters at end of line, lets ignore them.
        dl = dl.replace('\r\r\n', '\r\n')
        dl = dl.splitlines(True)

        # Special handling for the output of the diff tool on binary files:
        #     diff outputs "Files a and b differ"
        # and the code below expects the output to start with
        #     "Binary files "
        if (len(dl) == 1 and
            dl[0].startswith('Files %s and %s differ' % (old_file, new_file))):
            dl = ['Binary files %s and %s differ\n' % (old_file, new_file)]

        if dl == [] or dl[0].startswith("Binary files "):
            if dl == []:
                if ignore_unmodified:
                    return []
                else:
                    print "Warning: %s in your changeset is unmodified" % \
                          filename

            dl.insert(0, "==== %s (%s) ==%s==\n" % (filename, newrevspec,
                                                    changetype))
            dl.append('\n')
        else:
            dl[0] = "--- %s\t%s\n" % (filename, parentrevspec)
            dl[1] = "+++ %s\t%s\n" % (filename, newrevspec)

            # Not everybody has files that end in a newline.  This ensures
            # that the resulting diff file isn't broken.
            if dl[-1][-1] != '\n':
                dl.append('\n')

        return dl

    def write_file(self, filename, filespec, tmpfile):
        """ Grabs a file from Plastic and writes it to a temp file """
        debug("Writing '%s' (rev %s) to '%s'" % (filename, filespec, tmpfile))
        execute(["cm", "cat", filespec, "--file=" + tmpfile])


SCMCLIENTS = (
    SVNClient(),
    CVSClient(),
    GitClient(),
    MercurialClient(),
    PerforceClient(),
    ClearCaseClient(),
    PlasticClient(),
)

def debug(s):
    """
    Prints debugging information if post-review was run with --debug
    """
    if DEBUG or options and options.debug:
        print ">>> %s" % s


def make_tempfile(content=None):
    """
    Creates a temporary file and returns the path. The path is stored
    in an array for later cleanup.
    """
    fd, tmpfile = mkstemp()
    if content:
        os.write(fd, content)
    os.close(fd)
    tempfiles.append(tmpfile)
    return tmpfile


def check_install(command):
    """
    Try executing an external command and return a boolean indicating whether
    that command is installed or not.  The 'command' argument should be
    something that executes quickly, without hitting the network (for
    instance, 'svn help' or 'git --version').
    """
    try:
        subprocess.Popen(command.split(' '),
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
        return True
    except OSError:
        return False


def check_gnu_diff():
    """Checks if GNU diff is installed, and informs the user if it's not."""
    has_gnu_diff = False

    try:
        result = execute(['diff', '--version'], ignore_errors=True)
        has_gnu_diff = 'GNU diffutils' in result
    except OSError:
        pass

    if not has_gnu_diff:
        sys.stderr.write('\n')
        sys.stderr.write('GNU diff is required for Subversion '
                         'repositories. Make sure it is installed\n')
        sys.stderr.write('and in the path.\n')
        sys.stderr.write('\n')

        if os.name == 'nt':
            sys.stderr.write('On Windows, you can install this from:\n')
            sys.stderr.write(GNU_DIFF_WIN32_URL)
            sys.stderr.write('\n')

        die()


def execute(command, env=None, split_lines=False, ignore_errors=False,
            extra_ignore_errors=(), translate_newlines=True, with_errors=True):
    """
    Utility function to execute a command and return the output.
    """
    if isinstance(command, list):
        debug(subprocess.list2cmdline(command))
    else:
        debug(command)

    if env:
        env.update(os.environ)
    else:
        env = os.environ.copy()

    env['LC_ALL'] = 'en_US.UTF-8'
    env['LANGUAGE'] = 'en_US.UTF-8'

    if with_errors:
        errors_output = subprocess.STDOUT
    else:
        errors_output = subprocess.PIPE

    if sys.platform.startswith('win'):
        p = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=errors_output,
                             shell=False,
                             universal_newlines=translate_newlines,
                             env=env)
    else:
        p = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=errors_output,
                             shell=False,
                             close_fds=True,
                             universal_newlines=translate_newlines,
                             env=env)
    if split_lines:
        data = p.stdout.readlines()
    else:
        data = p.stdout.read()
    rc = p.wait()
    if rc and not ignore_errors and rc not in extra_ignore_errors:
        die('Failed to execute command: %s\n%s' % (command, data))

    return data


def die(msg=None):
    """
    Cleanly exits the program with an error message. Erases all remaining
    temporary files.
    """
    for tmpfile in tempfiles:
        try:
            os.unlink(tmpfile)
        except:
            pass

    if msg:
        print msg

    sys.exit(1)


def walk_parents(path):
    """
    Walks up the tree to the root directory.
    """
    while os.path.splitdrive(path)[1] != os.sep:
        yield path
        path = os.path.dirname(path)


def load_config_files(homepath):
    """Loads data from .reviewboardrc files"""
    def _load_config(path):
        config = {
            'TREES': {},
        }

        filename = os.path.join(path, '.reviewboardrc')

        if os.path.exists(filename):
            try:
                execfile(filename, config)
            except SyntaxError, e:
                die('Syntax error in config file: %s\n'
                    'Line %i offset %i\n' % (filename, e.lineno, e.offset))

            return config

        return None

    for path in walk_parents(os.getcwd()):
        config = _load_config(path)

        if config:
            configs.append(config)

    globals()['user_config'] = _load_config(homepath)


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


def determine_client():
    repository_info = None
    tool = None

    # Try to find the SCM Client we're going to be working with.
    for tool in SCMCLIENTS:
        repository_info = tool.get_repository_info()

        if repository_info:
            break

    if not repository_info:
        if options.repository_url:
            print "No supported repository could be access at the supplied url."
        else:
            print "The current directory does not contain a checkout from a"
            print "supported source code repository."
        sys.exit(1)

    # Verify that options specific to an SCM Client have not been mis-used.
    if options.change_only and not repository_info.supports_changesets:
        sys.stderr.write("The --change-only option is not valid for the "
                         "current SCM client.\n")
        sys.exit(1)

    if options.parent_branch and not repository_info.supports_parent_diffs:
        sys.stderr.write("The --parent option is not valid for the "
                         "current SCM client.\n")
        sys.exit(1)

    if ((options.p4_client or options.p4_port) and \
        not isinstance(tool, PerforceClient)):
        sys.stderr.write("The --p4-client and --p4-port options are not valid "
                         "for the current SCM client.\n")
        sys.exit(1)

    return (repository_info, tool)


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
    load_config_files(homepath)

    args = parse_options(sys.argv[1:])

    debug('RBTools %s' % get_version_string())
    debug('Home = %s' % homepath)

    repository_info, tool = determine_client()

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
