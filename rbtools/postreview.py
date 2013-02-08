#!/usr/bin/env python
import os
import platform
import sys
from urlparse import urljoin

from pkg_resources import parse_version
from rbtools import get_version_string
from rbtools.api.errors import APIError
from rbtools.clients import scan_usable_client
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.plastic import PlasticClient
from rbtools.utils.filesystem import load_config_files
from rbtools.utils.process import die
from reviewboard.custom_http import HTTPPasswordMgr, PresetHTTPAuthHandler

from reviewboard.option_parser_factory import get_script_option_parser
from reviewboard.post_review_options import PostReviewOptions
from reviewboard.reviewboard_server import ReviewBoardServer

try:
    # Specifically import json_loads, to work around some issues with
    # installations containing incompatible modules named "json".
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads

options = None
def set_global_options(options):
    globals()["options"] = PostReviewOptions(options)

def main():
    homepath = get_homepath()
    cookie_file = get_cookie_file(homepath)
    user_config, configs = load_config_files(homepath)
    option_parser = get_script_option_parser(configs)
    (options, args) = parse_options(option_parser)
    set_global_options(options)

    debug('RBTools %s' % get_version_string())
    debug('Python %s' % sys.version)
    debug('Running on %s' % (platform.platform()))
    debug('Home = %s' % homepath)
    debug('Current Directory = %s' % os.getcwd())
    debug("args %s" % args)
    debug('Checking the repository type. Errors shown below are mostly harmless.')

    # Get the SCM Product Info
    repository_info, tool = prepare_scm_tool_and_repository(configs, user_config)
    server_url = get_server_url(repository_info, tool)

    # Set up the HTTP libraries to support all of the features we need.
    password_mgr = HTTPPasswordMgr(server_url, options, options.username, options.password)
    preset_auth_handler = PresetHTTPAuthHandler(server_url, password_mgr, options)
    server = get_rb_server(cookie_file, password_mgr, preset_auth_handler, repository_info, server_url)

    # Get the Change Details
    diff, parent_diff = get_diff_info(args, repository_info, tool)
    changenum = get_changenum(args, repository_info, server, tool)

    # Let's begin.
    check_for_diff_only(diff)
    server.login()
    review_url = tempt_fate(server, tool, changenum,
                            diff_content=diff,
                            parent_diff_content=parent_diff,
                            submit_as=options.submit_as)

    if options.open_browser:
        open_in_browser(review_url)

def get_homepath():
    if 'APPDATA' in os.environ:
        homepath = os.environ['APPDATA']
    elif 'HOME' in os.environ:
        homepath = os.environ["HOME"]
    else:
        homepath = ''
    return homepath

def get_cookie_file(homepath):
    # If we end up creating a cookie file, make sure it's only readable by the
    # user.
    os.umask(0077)
    # Load the config and cookie files
    cookie_file = os.path.join(homepath, ".post-review-cookies.txt")
    return cookie_file

def parse_options(parser):
    args = sys.argv[1:]
    (options, args) = parser.parse_args(args)
    options = PostReviewOptions(options)
    exit_if_failure_message(options.validate())
    return (options, args)

def exit_if_failure_message(failure_message):
    if (is_string_not_blank(failure_message)):
        die(failure_message)

def is_string_not_blank(value):
    return value is not None and len(value) > 0

def prepare_scm_tool_and_repository(configs, user_config):
    repository_info, tool = scan_usable_client(options)
    debug('Finished checking the repository type.')
    tool.user_config = user_config
    tool.configs = configs
    # Verify that options specific to an SCM Client have not been mis-used.
    tool.check_options()
    return repository_info, tool

def get_rb_server(cookie_file, password_mgr, preset_auth_handler, repository_info, server_url):
    server = ReviewBoardServer(server_url, repository_info, cookie_file, password_mgr, preset_auth_handler, options)

    # Handle the case where /api/ requires authorization (RBCommons).
    if not server.check_api_version():
        die("Unable to log in with the supplied username and password.")

    return server

def get_diff_info(args, repository_info, tool):
    cwd = get_cwd()

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
                fp = open(os.path.join(cwd, options.diff_filename), 'r')
                diff = fp.read()
                fp.close()
            except IOError, e:
                die("Unable to open diff filename: %s" % e)
    else:
        diff, parent_diff = tool.diff(args)

    if len(diff) == 0:
        die("There don't seem to be any diffs!")
    return diff, parent_diff

def get_cwd():
    return os.path.abspath(os.getcwd())

def get_changenum(args, repository_info, server, tool):
    if repository_info.supports_changesets:
        changenum = tool.get_changenum(args)
    else:
        changenum = None

    return check_for_deprecated_api(changenum, server, tool)

def check_for_deprecated_api(changenum, server, tool):
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
    return changenum

def check_for_diff_only(diff):
    if options.output_diff_only:
        # The comma here isn't a typo, but rather suppresses the extra newline
        print diff,
        sys.exit(0)

def tempt_fate(server, tool, changenum, diff_content=None,
               parent_diff_content=None, submit_as=None, retries=3):
    """
    Attempts to create a review request on a Review Board server and upload
    a diff. On success, the review request path is displayed.
    """
    try:
        review_request = get_review_request(server, changenum, submit_as)
        options.process_request(review_request, server)
    except APIError, e:
        if e.error_code == 103 and retries >= 0: # Not logged in
            # We had an odd issue where the server ended up a couple of
            # years in the future. Login succeeds but the cookie date was
            # "odd" so use of the cookie appeared to fail and eventually
            # ended up at max recursion depth :-(. Check for a maximum
            # number of retries.
            server.login(force=True)
            return tempt_fate(server, tool, changenum, diff_content, parent_diff_content, submit_as, retries=retries - 1)

        die_error_composing_review(e)

    upload_diff(diff_content, parent_diff_content, review_request, server)

    if options.reopen:
        server.reopen(review_request)

    if options.publish:
        server.publish(review_request)

    review_url = get_review_url(review_request, server)
    print_review_url(review_request, review_url)
    return review_url

def get_review_request(server, changenum, submit_as):
    if options.rid:
        review_request = server.get_review_request(options.rid)
        status = review_request['status']

        if status == 'submitted':
            die("Review request %s is marked as %s. In order to "
                "update it, please reopen the request using the web "
                "interface and try again." % (options.rid, status))
    else:
        review_request = server.new_review_request(changenum, submit_as)
    return review_request

def die_error_composing_review(e):
    if options.rid:
        die("Error getting review request %s: %s" % (options.rid, e))
    else:
        die("Error creating review request: %s" % e)

def print_review_url(review_request, review_url):
    print "Review request #%s posted." % (review_request['id'],)
    print
    print review_url

def upload_diff(diff_content, parent_diff_content, review_request, server):
    if not server.info.supports_changesets or not options.change_only:
        try:
            server.upload_diff(review_request, diff_content, parent_diff_content)
        except APIError, e:
            handle_diff_upload_error(e)

def handle_diff_upload_error(e):
    sys.stderr.write('\nError uploading diff\n\n')
    if e.error_code == 101 and e.http_status == 403:
        die('You do not have permissions to modify this review request\n')
    elif e.error_code == 105:
        sys.stderr.write('The generated diff file was empty. This usually means no files were\n')
        sys.stderr.write('modified in this change.\n\n')
        sys.stderr.write('Try running with --output-diff and --debug for more information.\n\n')
    die("Your review request still exists, but the diff is not attached.")

def get_review_url(review_request, server):
    request_url = 'r/' + str(review_request['id']) + '/'
    review_url = urljoin(server.url, request_url)
    if not review_url.startswith('http'):
        review_url = 'http://%s' % review_url
    return review_url

def get_server_url(repository_info, tool):
    if options.server:
        server_url = options.server
    else:
        server_url = tool.scan_for_server(repository_info)

    if server_url[-1] != '/':
        server_url += '/'

    if not server_url:
        die("Unable to find a Review Board server for this source code tree.")

    return server_url

def open_in_browser(review_url):
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

def debug(s):
    """
    Prints debugging information if post-review was run with --debug
    """
    if options and options.debug:
        print ">>> %s" % s

#
# Script Entry Point
#
if __name__ == "__main__":
    main()