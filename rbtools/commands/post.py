import getpass
import logging
from optparse import make_option
import os
import re
import sys
from urlparse import urljoin, urlparse

from rbtools.api.client import RBClient
from rbtools.api.errors import APIError, ServerInterfaceError
from rbtools.clients import scan_usable_client
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.plastic import PlasticClient
from rbtools.commands import Command
from rbtools.utils.filesystem import get_home_path
from rbtools.utils.process import die


class Post(Command):
    """Create and update review requests."""
    name = "post"
    author = "The Review Board Project"
    option_list = [
        make_option("-r", "--review-request-id",
                    dest="rid", metavar="ID", default=None,
                    help="existing review request ID to update"),
        make_option("--server",
                    dest="server",
                    metavar="SERVER",
                    help="specify a different Review Board server to use"),
        make_option("--disable-proxy",
                    action='store_true',
                    dest='disable_proxy',
                    help="prevents requests from going through a proxy "
                         "server"),
        make_option('-p', '--publish',
                    dest="publish", action="store_true", default=False,
                    help="publish the review request immediately after "
                         "submitting"),
        make_option("--target-groups",
                    dest="target_groups",
                    help="names of the groups who will perform "
                          "the review"),
        make_option("--target-people",
                    dest="target_people",
                    help="names of the people who will perform "
                         "the review"),
        make_option("--summary",
                    dest="summary", default=None,
                    help="summary of the review "),
        make_option("--description",
                    dest="description", default=None,
                    help="description of the review "),
        make_option("--description-file",
                    dest="description_file", default=None,
                    help="text file containing a description of the review"),
        make_option('-g', '--guess-fields',
                    dest="guess_fields", action="store_true",
                    help="equivalent to --guess-summary --guess-description"),
        make_option("--guess-summary",
                    dest="guess_summary", action="store_true",
                    help="guess summary from the latest commit (git/"
                         "hg/hgsubversion only)"),
        make_option("--guess-description",
                    dest="guess_description", action="store_true",
                    help="guess description based on commits on this branch "
                         "(git/hg/hgsubversion only)"),
        make_option("--testing-done",
                    dest="testing_done", default=None,
                    help="details of testing done "),
        make_option("--testing-done-file",
                    dest="testing_file", default=None,
                    help="text file containing details of testing done "),
        make_option("--branch",
                    dest="branch",
                    help="affected branch "),
        make_option("--bugs-closed",
                    dest="bugs_closed", default=None,
                    help="list of bugs closed "),
        make_option("--change-description", default=None,
                    help="description of what changed in this revision of "
                    "the review request when updating an existing request"),
        make_option("--revision-range",
                    dest="revision_range", default=None,
                    help="generate the diff for review based on given "
                         "revision range"),
        make_option("--submit-as",
                    dest="submit_as",
                    metavar="USERNAME",
                    help="user name to be recorded as the author of the "
                         "review request, instead of the logged in user"),
        make_option("--username",
                    dest="username",
                    metavar="USERNAME",
                    help="user name to be supplied to the reviewboard "
                         "server"),
        make_option("--password",
                    dest="password",
                    metavar="PASSWORD",
                    help="password to be supplied to the reviewboard server"),
        make_option("--change-only",
                    dest="change_only", action="store_true",
                    default=False,
                    help="updates info from changelist, but does "
                         "not upload a new diff (only available if your "
                         "repository supports changesets)"),
        make_option("--parent",
                    dest="parent_branch",
                    metavar="PARENT_BRANCH",
                    help="the parent branch this diff should be against "
                         "(only available if your repository supports "
                         "parent diffs)"),
        make_option("--tracking-branch",
                    dest="tracking",
                    metavar="TRACKING",
                    help="Tracking branch from which your branch is derived "
                         "(git only, defaults to origin/master)"),
        make_option("--p4-client",
                    dest="p4_client",
                    help="the Perforce client name that the review is in"),
        make_option("--p4-port",
                    dest="p4_port",
                    help="the Perforce servers IP address that the review "
                         "is on"),
        make_option("--p4-passwd",
                    dest="p4_passwd",
                    help="the Perforce password or ticket of the user "
                         "in the P4USER environment variable"),
        make_option('--svn-changelist', dest='svn_changelist', default=None,
                    help='generate the diff for review based on a local SVN '
                         'changelist'),
        make_option("--repository-url",
                    dest="repository_url",
                    help="the url for a repository for creating a diff "
                         "outside of a working copy (currently only "
                         "supported by Subversion with --revision-range or "
                         "--diff-filename and ClearCase with relative "
                         "paths outside the view). For git, this specifies"
                         "the origin url of the current repository, "
                         "overriding the origin url supplied by the git "
                         "client."),
        make_option("-d", "--debug",
                    action="store_true", dest="debug",
                    help="display debug output"),
        make_option("--diff-filename",
                    dest="diff_filename", default=None,
                    help='upload an existing diff file, instead of '
                         'generating a new diff'),
        make_option('--http-username',
                    dest='http_username',
                    metavar='USERNAME',
                    help='username for HTTP Basic authentication'),
        make_option('--http-password',
                    dest='http_password',
                    metavar='PASSWORD',
                    help='password for HTTP Basic authentication'),
        make_option('--basedir',
                    dest='basedir',
                    default=None,
                    help='the absolute path in the repository the diff was '
                         'generated in. Will override the path detected '
                         'by post-review.'),
    ]

    def __init__(self):
        super(Post, self).__init__()

        self.option_defaults = {
            'server': self.config.get('REVIEWBOARD_URL', None),
            'disable_proxy': not self.config.get('ENABLE_PROXY', True),
            'target_groups': self.config.get('TARGET_GROUPS', None),
            'target_people': self.config.get('TARGET_PEOPLE', None),
            'guess_fields': self.config.get('GUESS_FIELDS', False),
            'guess_summary': self.config.get('GUESS_SUMMARY', False),
            'guess_description': self.config.get('GUESS_DESCRIPTION', False),
            'branch': self.config.get('BRANCH', None),
            'submit_as': self.config.get('SUBMIT_AS', None),
            'username': self.config.get('USERNAME', None),
            'password': self.config.get('PASSWORD', None),
            'parent_branch': self.config.get('PARENT_BRANCH', None),
            'tracking': self.config.get('TRACKING_BRANCH', None),
            'p4_client': self.config.get('P4_CLIENT', None),
            'p4_port': self.config.get('P4_PORT', None),
            'p4_passwd': self.config.get('P4_PASSWD', None),
            'repository_url': self.config.get('REPOSITORY', None),
            'debug': self.config.get('DEBUG', False),
            'http_username': self.config.get('HTTP_USERNAME', None),
            'http_password': self.config.get('HTTP_PASSWORD', None),
        }

    def post_process_options(self):
        if self.options.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        if self.options.description and self.options.description_file:
            sys.stderr.write("The --description and --description-file "
                             "options are mutually exclusive.\n")
            sys.exit(1)

        if self.options.description_file:
            if os.path.exists(self.options.description_file):
                fp = open(self.options.description_file, "r")
                self.options.description = fp.read()
                fp.close()
            else:
                sys.stderr.write("The description file %s does not exist.\n" %
                                 self.options.description_file)
                sys.exit(1)

        if self.options.guess_fields:
            self.options.guess_summary = True
            self.options.guess_description = True

        if self.options.testing_done and self.options.testing_file:
            sys.stderr.write("The --testing-done and --testing-done-file "
                             "options are mutually exclusive.\n")
            sys.exit(1)

        if self.options.testing_file:
            if os.path.exists(self.options.testing_file):
                fp = open(self.options.testing_file, "r")
                self.options.testing_done = fp.read()
                fp.close()
            else:
                sys.stderr.write("The testing file %s does not exist.\n" %
                                 self.options.testing_file)
                sys.exit(1)

    def initialize_scm_tool(self):
        """Initialize the SCM tool for the current working directory."""
        repository_info, tool = scan_usable_client(self.options)
        tool.user_config = self.config
        tool.configs = [self.config]
        tool.check_options()
        return repository_info, tool

    def get_server_url(self):
        """Returns the Review Board server url"""
        if self.options.server:
            server_url = self.options.server
        else:
            server_url = self.tool.scan_for_server(self.repository_info)

        if not server_url:
            print ("Unable to find a Review Board server "
                   "for this source code tree.")
            sys.exit(1)

        return server_url

    def get_repository_path(self):
        """Get the repository path from the server.

        This will compare the paths returned by the SCM client
        with those one the server, and return the first match.
        """
        if isinstance(self.repository_info.path, list):
            repositories = self.api_root.get_repositories()

            try:
                while True:
                    for repo in repositories:
                        if repo['path'] in self.repository_info.path:
                            self.repository_info.path = repo['path']
                            raise StopIteration()

                    repositories = repositories.get_next()
            except StopIteration:
                pass

        if isinstance(self.repository_info.path, list):
            sys.stderr.write('\n')
            sys.stderr.write('There was an error creating this review '
                             'request.\n')
            sys.stderr.write('\n')
            sys.stderr.write('There was no matching repository path'
                             'found on the server.\n')

            sys.stderr.write('Unknown repository paths found:\n')

            for foundpath in self.repository_info.path:
                sys.stderr.write('\t%s\n' % foundpath)

            sys.stderr.write('Ask the administrator to add one of '
                             'these repositories\n')
            sys.stderr.write('to the Review Board server.\n')
            die()

        return self.repository_info.path

    def post_request(self, tool, changenum=None, diff_content=None,
                     parent_diff_content=None, submit_as=None, retries=3):
        """Creates or updates a review request, and uploads a diff.

        On success the review request id and url are returned.
        """
        if self.options.rid:
            # Retrieve the review request coresponding to the user
            # provided id.
            try:
                review_request = self.api_root.get_review_request(
                    review_request_id=self.options.rid)
            except APIError, e:
                die("Error getting review request %s: %s" % (self.options.rid,
                                                             e))

            if review_request.status == 'submitted':
                die("Review request %s is marked as %s. In order to "
                    "update it, please reopen the request and try again." % (
                        self.options.rid,
                        review_request.status))
        else:
            # The user did not provide a request id, so we will create
            # a new review request.
            try:
                repository = \
                    self.options.repository_url or self.get_repository_path()
                request_data = {
                    'repository': repository
                }

                if changenum:
                    request_data['changenum'] = changenum

                if submit_as:
                    request_data['submit_as'] = submit_as

                review_request = self.api_root.get_review_requests().create(
                    data=request_data)
            except APIError, e:
                die("Error creating review request: %s" % e)

        # Upload the diff if we're not using changesets.
        if (not self.repository_info.supports_changesets or
            not self.options.change_only):
            try:
                basedir = (self.options.basedir or
                           self.repository_info.base_path)
                review_request.get_diffs().upload_diff(
                    diff_content,
                    parent_diff=parent_diff_content,
                    base_dir=basedir)
            except APIError, e:
                sys.stderr.write('\n')
                sys.stderr.write('Error uploading diff\n')
                sys.stderr.write('\n')

                if e.error_code == 101 and e.http_status == 403:
                    die('You do not have permissions to modify '
                        'this review request\n')
                elif e.error_code == 105:
                    sys.stderr.write('The generated diff file was empty. This '
                                     'usually means no files were\n')
                    sys.stderr.write('modified in this change.\n')
                    sys.stderr.write('\n')

                die("Your review request still exists, but the diff is not "
                    "attached. %s" % e)

        try:
            draft = review_request.get_draft()
        except APIError, e:
            die("Error retrieving review request draft: %s" % e)

        # Update the review request draft fields based on options set
        # by the user, or configuration.
        update_fields = {}

        if self.options.target_groups:
            update_fields['target_groups'] = self.options.target_groups

        if self.options.target_people:
            update_fields['target_people'] = self.options.target_people

        if self.options.summary:
            update_fields['summary'] = self.options.summary

        if self.options.branch:
            update_fields['branch'] = self.options.branch

        if self.options.bugs_closed:
            # Append to the existing list of bugs.
            self.options.bugs_closed = self.options.bugs_closed.strip(", ")
            bug_set = set(re.split("[, ]+", self.options.bugs_closed)) | \
                      set(review_request.bugs_closed)
            self.options.bugs_closed = ",".join(bug_set)
            update_fields['bugs_closed'] = self.options.bugs_closed

        if self.options.description:
            update_fields['description'] = self.options.description

        if self.options.testing_done:
            update_fields['testing_done'] = self.options.testing_done

        if self.options.change_description:
            update_fields['changedescription'] = \
                self.options.change_description

        if self.options.publish:
            update_fields['public'] = True

        try:
            draft = draft.update(data=update_fields)
        except APIError, e:
            die("Error updating review request draft: %s" % e)

        request_url = 'r/%s/' % review_request.id
        review_url = urljoin(self.server_url, request_url)

        if not review_url.startswith('http'):
            review_url = 'http://%s' % review_url

        return review_request.id, review_url

    def credentials_prompt(self, realm, uri, *args, **kwargs):
        """Prompt the user for credentials using the command line.

        This will prompt the user, and then return the provided
        username and password. This is used as a callback in the
        API when the user requires authorization.
        """
        if self.options.diff_filename == '-':
            die('HTTP authentication is required, but cannot be '
                'used with --diff-filename=-')

        print "==> HTTP Authentication Required"
        print 'Enter authorization information for "%s" at %s' % \
            (realm, urlparse(uri)[1])
        username = raw_input('Username: ')
        password = getpass.getpass('Password: ')

        return username, password

    def main(self, *args):
        """Create and update review requests."""
        self.post_process_options()

        origcwd = os.path.abspath(os.getcwd())

        # If we end up creating a cookie file, make sure it's only
        # readable by the user.
        os.umask(0077)

        # Generate a path to the cookie file.
        cookie_file = os.path.join(get_home_path(), ".post-review-cookies.txt")

        self.repository_info, self.tool = self.initialize_scm_tool()
        self.server_url = self.get_server_url()
        self.rb_api = RBClient(self.server_url,
                               cookie_file=cookie_file,
                               username=self.options.username,
                               password=self.options.password,
                               auth_callback=self.credentials_prompt)

        try:
            self.api_root = self.rb_api.get_root()
        except ServerInterfaceError, e:
            die("Could not reach the review board server at %s" %
                self.server_url)
        except APIError, e:
            die("Error: %s" % e)

        if self.repository_info.supports_changesets:
            changenum = self.tool.get_changenum(args)
        else:
            changenum = None

        if self.options.revision_range:
            diff, parent_diff = self.tool.diff_between_revisions(
                self.options.revision_range,
                args,
                self.repository_info)
        elif self.options.svn_changelist:
            diff, parent_diff = self.tool.diff_changelist(
                self.options.svn_changelist)
        elif self.options.diff_filename:
            parent_diff = None

            if self.options.diff_filename == '-':
                diff = sys.stdin.read()
            else:
                try:
                    diff_path = os.path.join(origcwd,
                                             self.options.diff_filename)
                    fp = open(diff_path, 'r')
                    diff = fp.read()
                    fp.close()
                except IOError, e:
                    die("Unable to open diff filename: %s" % e)
        else:
            diff, parent_diff = self.tool.diff(args)

        if len(diff) == 0:
            die("There don't seem to be any diffs!")

        if (isinstance(self.tool, PerforceClient) or
            isinstance(self.tool, PlasticClient)) and changenum is not None:
            changenum = self.tool.sanitize_changenum(changenum)

        request_id, review_url = self.post_request(
            self.tool,
            changenum=changenum,
            diff_content=diff,
            parent_diff_content=parent_diff,
            submit_as=self.options.submit_as)

        print "Review request #%s posted." % request_id
        print
        print review_url
