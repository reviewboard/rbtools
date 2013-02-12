import logging
import os
import re
import sys
from urlparse import urljoin

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option
from rbtools.utils.diffs import get_diff


class Post(Command):
    """Create and update review requests."""
    name = "post"
    author = "The Review Board Project"
    description = "Uploads diffs to create and update review requests."
    args = "[changenum]"
    option_list = [
        Option("-r", "--review-request-id",
               dest="rid",
               metavar="ID",
               default=None,
               help="existing review request ID to update"),
        Option("--server",
               dest="server",
               metavar="SERVER",
               config_key="REVIEWBOARD_URL",
               default=None,
               help="specify a different Review Board server to use"),
        Option("--disable-proxy",
               action='store_false',
               dest='enable_proxy',
               config_key="ENABLE_PROXY",
               default=True,
               help="prevents requests from going through a proxy server"),
        Option('-p', '--publish',
               dest="publish",
               action="store_true",
               default=False,
               help="publish the review request immediately after submitting"),
        Option("-o", "--open",
               dest="open_browser",
               action="store_true",
               config_key='OPEN_BROWSER',
               default=False,
               help="open a web browser to the review request page"),
        Option("--target-groups",
               dest="target_groups",
               config_key="TARGET_GROUPS",
               default=None,
               help="names of the groups who will perform the review"),
        Option("--target-people",
               dest="target_people",
               config_key="TARGET_PEOPLE",
               default=None,
               help="names of the people who will perform the review"),
        Option("--summary",
               dest="summary",
               default=None,
               help="summary of the review "),
        Option("--description",
               dest="description",
               default=None,
               help="description of the review "),
        Option("--description-file",
               dest="description_file",
               default=None,
               help="text file containing a description of the review"),
        Option('-g', '--guess-fields',
               dest="guess_fields",
               action="store_true",
               config_key="GUESS_FIELDS",
               default=False,
               help="equivalent to --guess-summary --guess-description"),
        Option("--guess-summary",
               dest="guess_summary",
               action="store_true",
               config_key="GUESS_SUMMARY",
               default=False,
               help="guess summary from the latest commit "
                    "(bzr/git/hg/hgsubversion only)"),
        Option("--guess-description",
               dest="guess_description",
               action="store_true",
               config_key="GUESS_DESCRIPTION",
               default=False,
               help="guess description based on commits on this branch "
                    "(bzr/git/hg/hgsubversion only)"),
        Option("--testing-done",
               dest="testing_done",
               default=None,
               help="details of testing done "),
        Option("--testing-done-file",
               dest="testing_file",
               default=None,
               help="text file containing details of testing done "),
        Option("--branch",
               dest="branch",
               config_key="BRANCH",
               default=None,
               help="affected branch "),
        Option("--bugs-closed",
               dest="bugs_closed",
               default=None,
               help="list of bugs closed "),
        Option("--change-description",
               default=None,
               help="description of what changed in this revision of "
                    "the review request when updating an existing request"),
        Option("--revision-range",
               dest="revision_range",
               default=None,
               help="generate the diff for review based on given "
                    "revision range"),
        Option("--submit-as",
               dest="submit_as",
               metavar="USERNAME",
               config_key="SUBMIT_AS",
               default=None,
               help="user name to be recorded as the author of the "
                    "review request, instead of the logged in user"),
        Option("--username",
               dest="username",
               metavar="USERNAME",
               config_key="USERNAME",
               default=None,
               help="user name to be supplied to the Review Board server"),
        Option("--password",
               dest="password",
               metavar="PASSWORD",
               config_key="PASSWORD",
               default=None,
               help="password to be supplied to the Review Board server"),
        Option("--change-only",
               dest="change_only",
               action="store_true",
               default=False,
               help="updates info from changelist, but does "
                    "not upload a new diff (only available if your "
                    "repository supports changesets)"),
        Option("--parent",
               dest="parent_branch",
               metavar="PARENT_BRANCH",
               config_key="PARENT_BRANCH",
               default=None,
               help="the parent branch this diff should be against "
                    "(only available if your repository supports "
                    "parent diffs)"),
        Option("--tracking-branch",
               dest="tracking",
               metavar="TRACKING",
               config_key="TRACKING_BRANCH",
               default=None,
               help="Tracking branch from which your branch is derived "
                    "(git only, defaults to origin/master)"),
        Option("--p4-client",
               dest="p4_client",
               config_key="P4_CLIENT",
               default=None,
               help="the Perforce client name that the review is in"),
        Option("--p4-port",
               dest="p4_port",
               config_key="P4_PORT",
               default=None,
               help="the Perforce servers IP address that the review is on"),
        Option("--p4-passwd",
               dest="p4_passwd",
               config_key="P4_PASSWD",
               default=None,
               help="the Perforce password or ticket of the user "
                    "in the P4USER environment variable"),
        Option("--svn-changelist",
               dest="svn_changelist",
               default=None,
               help="generate the diff for review based on a local SVN "
                    "changelist"),
        Option("--repository-url",
               dest="repository_url",
               config_key="REPOSITORY",
               default=None,
               help="the url for a repository for creating a diff "
                    "outside of a working copy (currently only "
                    "supported by Subversion with --revision-range or "
                    "--diff-filename and ClearCase with relative "
                    "paths outside the view). For git, this specifies"
                    "the origin url of the current repository, "
                    "overriding the origin url supplied by the git "
                    "client."),
        Option("--diff-filename",
               dest="diff_filename",
               default=None,
               help="upload an existing diff file, instead of "
                    "generating a new diff"),
        Option("--http-username",
               dest="http_username",
               metavar="USERNAME",
               config_key="HTTP_USERNAME",
               default=None,
               help="username for HTTP Basic authentication"),
        Option("--http-password",
               dest="http_password",
               metavar="PASSWORD",
               config_key="HTTP_PASSWORD",
               default=None,
               help="password for HTTP Basic authentication"),
        Option("--basedir",
               dest="basedir",
               default=None,
               help="the absolute path in the repository the diff was "
                    "generated in. Will override the detected path."),
    ]

    def post_process_options(self):
        if self.options.description and self.options.description_file:
            raise CommandError("The --description and --description-file "
                               "options are mutually exclusive.\n")

        if self.options.description_file:
            if os.path.exists(self.options.description_file):
                fp = open(self.options.description_file, "r")
                self.options.description = fp.read()
                fp.close()
            else:
                raise CommandError(
                  "The description file %s does not exist.\n" %
                  self.options.description_file)

        if self.options.guess_fields:
            self.options.guess_summary = True
            self.options.guess_description = True

        if self.options.testing_done and self.options.testing_file:
            raise CommandError("The --testing-done and --testing-done-file "
                               "options are mutually exclusive.\n")

        if self.options.testing_file:
            if os.path.exists(self.options.testing_file):
                fp = open(self.options.testing_file, "r")
                self.options.testing_done = fp.read()
                fp.close()
            else:
                raise CommandError("The testing file %s does not exist.\n" %
                                   self.options.testing_file)

    def get_repository_path(self, repository_info, api_root):
        """Get the repository path from the server.

        This will compare the paths returned by the SCM client
        with those one the server, and return the first match.
        """
        if isinstance(repository_info.path, list):
            repositories = api_root.get_repositories()

            try:
                while True:
                    for repo in repositories:
                        if repo['path'] in repository_info.path:
                            repository_info.path = repo['path']
                            raise StopIteration()

                    repositories = repositories.get_next()
            except StopIteration:
                pass

        if isinstance(repository_info.path, list):
            error_str = [
                'There was an error creating this review request.\n',
                '\n',
                'There was no matching repository path found on the server.\n',
                'Unknown repository paths found:\n',
            ]

            for foundpath in repository_info.path:
                error_str.append('\t%s\n' % foundpath)

            error_str += [
                'Ask the administrator to add one of these repositories\n',
                'to the Review Board server.\n',
            ]

            raise CommandError(''.join(error_str))

        return repository_info.path

    def post_request(self, tool, repository_info, server_url, api_root,
                     changenum=None, diff_content=None,
                     parent_diff_content=None, submit_as=None, retries=3):
        """Creates or updates a review request, and uploads a diff.

        On success the review request id and url are returned.
        """
        if self.options.rid:
            # Retrieve the review request coresponding to the user
            # provided id.
            try:
                review_request = api_root.get_review_request(
                    review_request_id=self.options.rid)
            except APIError, e:
                raise CommandError("Error getting review request %s: %s" % (
                    self.options.rid, e))

            if review_request.status == 'submitted':
                raise CommandError(
                    "Review request %s is marked as %s. In order to update "
                    "it, please reopen the request and try again." % (
                        self.options.rid,
                        review_request.status))
        else:
            # The user did not provide a request id, so we will create
            # a new review request.
            try:
                repository = (
                    self.options.repository_url or
                    self.get_repository_path(repository_info, api_root))
                request_data = {
                    'repository': repository
                }

                if changenum:
                    request_data['changenum'] = changenum

                if submit_as:
                    request_data['submit_as'] = submit_as

                review_request = api_root.get_review_requests().create(
                    **request_data)
            except APIError, e:
                raise CommandError("Error creating review request: %s" % e)

        # Upload the diff if we're not using changesets.
        if (not repository_info.supports_changesets or
            not self.options.change_only):
            try:
                basedir = (self.options.basedir or
                           repository_info.base_path)
                review_request.get_diffs().upload_diff(
                    diff_content,
                    parent_diff=parent_diff_content,
                    base_dir=basedir)
            except APIError, e:
                error_msg = [
                    'Error uploading diff\n\n',
                ]

                if e.error_code == 101 and e.http_status == 403:
                    error_msg.append(
                        'You do not have permissions to modify '
                        'this review request\n')
                elif e.error_code == 105:
                    error_msg.append(
                        'The generated diff file was empty. This '
                        'usually means no files were\n'
                        'modified in this change.\n'
                        '\n'
                        'Your review request still exists, but the diff is '
                        'not attached. %s' % e)

                raise CommandError(''.join(error_msg))

        try:
            draft = review_request.get_draft()
        except APIError, e:
            raise CommandError("Error retrieving review request draft: %s" % e)

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
            draft = draft.update(**update_fields)
        except APIError, e:
            raise CommandError("Error updating review request draft: %s" % e)

        request_url = 'r/%s/' % review_request.id
        review_url = urljoin(server_url, request_url)

        if not review_url.startswith('http'):
            review_url = 'http://%s' % review_url

        return review_request.id, review_url

    def main(self, *args):
        """Create and update review requests."""
        self.post_process_options()
        origcwd = os.path.abspath(os.getcwd())
        repository_info, tool = self.initialize_scm_tool()
        server_url = self.get_server_url(repository_info, tool)
        api_root = self.get_root(server_url)
        self.setup_tool(tool, api_root=api_root)

        if self.options.diff_filename:
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
                    raise CommandError("Unable to open diff filename: %s" % e)
        else:
            diff, parent_diff = get_diff(
                tool,
                repository_info,
                revision_range=self.options.revision_range,
                svn_changelist=self.options.svn_changelist,
                files=args)

        if len(diff) == 0:
            raise CommandError("There don't seem to be any diffs!")

        if repository_info.supports_changesets:
            changenum = tool.sanitize_changenum(tool.get_changenum(args))
        else:
            changenum = None

        request_id, review_url = self.post_request(
            tool,
            repository_info,
            server_url,
            api_root,
            changenum=changenum,
            diff_content=diff,
            parent_diff_content=parent_diff,
            submit_as=self.options.submit_as)

        print "Review request #%s posted." % request_id
        print
        print review_url

        # Load the review up in the browser if requested to.
        if self.options.open_browser:
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
                logging.error('Error opening review URL: %s' % review_url)
