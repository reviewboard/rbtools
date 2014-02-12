import logging
import os
import re
import sys

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option, OptionGroup
from rbtools.utils.console import confirm
from rbtools.utils.diffs import get_diff
from rbtools.utils.match_score import Score
from rbtools.utils.repository import get_repository_id
from rbtools.utils.users import get_user


class Post(Command):
    """Create and update review requests."""
    name = "post"
    author = "The Review Board Project"
    description = "Uploads diffs to create and update review requests."
    args = "[revisions]"
    option_list = [
        OptionGroup(
            name='Posting Options',
            description='Controls the behavior of a post, including what '
                        'review request gets posted and how, and what '
                        'happens after it is posted.',
            option_list=[
                Option('-r', '--review-request-id',
                       dest='rid',
                       metavar='ID',
                       default=None,
                       help='Specifies the existing review request ID to '
                            'update.'),
                Option('-u', '--update',
                       dest='update',
                       action='store_true',
                       default=False,
                       help='Automatically determines the existing review '
                            'request to update.'),
                Option('-p', '--publish',
                       dest='publish',
                       action='store_true',
                       default=False,
                       help='Immediately publishes the review request after '
                            'posting.'),
                Option('-o', '--open',
                       dest='open_browser',
                       action='store_true',
                       config_key='OPEN_BROWSER',
                       default=False,
                       help='Opens a web browser to the review request '
                            'after posting.'),
                Option('--submit-as',
                       dest='submit_as',
                       metavar='USERNAME',
                       config_key='SUBMIT_AS',
                       default=None,
                       help='The user name to use as the author of the '
                            'review request, instead of the logged in user.'),
                Option('--change-only',
                       dest='change_only',
                       action='store_true',
                       default=False,
                       help='Updates fields from the change description, '
                            'but does not upload a new diff '
                            '(Perforce/Plastic only).'),
                Option('--diff-only',
                       dest='diff_only',
                       action='store_true',
                       default=False,
                       help='Uploads a new diff, but does not update '
                            'fields from the change description '
                            '(Perforce/Plastic only).'),
            ]
        ),
        OptionGroup(
            name='Review Board Server Options',
            description='Options necessary to communicate and authenticate '
                        'with a Review Board server.',
            option_list=[
                Option('--server',
                       dest='server',
                       metavar='SERVER',
                       config_key='REVIEWBOARD_URL',
                       default=None,
                       help='Specifies the Review Board server to use.'),
                Option('--disable-proxy',
                       action='store_false',
                       dest='enable_proxy',
                       config_key='ENABLE_PROXY',
                       default=True,
                       help='Prevents requests from going through a proxy '
                            'server.'),
                Option('--username',
                       dest='username',
                       metavar='USERNAME',
                       config_key='USERNAME',
                       default=None,
                       help='The user name to be supplied to the Review Board '
                            'server.'),
                Option('--password',
                       dest='password',
                       metavar='PASSWORD',
                       config_key='PASSWORD',
                       default=None,
                       help='The password to be supplied to the Review Board '
                            'server.'),
            ]
        ),
        OptionGroup(
            name='Repository Options',
            option_list=[
                Option('--repository',
                       dest='repository_name',
                       config_key='REPOSITORY',
                       default=None,
                       help='The name of the repository configured on '
                            'Review Board that matches the local repository.'),
                Option('--repository-url',
                       dest='repository_url',
                       config_key='REPOSITORY_URL',
                       default=None,
                       help='The URL for a repository, used for creating '
                            'a diff outside of a working copy (currently only '
                            'supported by Subversion with specific revisions '
                            'or --diff-filename and ClearCase with relative '
                            'paths outside the view). For git, this specifies '
                            'the origin url of the current repository, '
                            'overriding the origin URL supplied by the git '
                            'client.'),
                Option('--repository-type',
                       dest='repository_type',
                       config_key='REPOSITORY_TYPE',
                       default=None,
                       help='The type of repository in the current directory. '
                            'In most cases this should be detected '
                            'automatically, but some directory structures '
                            'containing multiple repositories require this '
                            'option to select the proper type. The '
                            '`rbt list-repo-types` command can be used to '
                            'list the supported values.'),
            ]
        ),
        OptionGroup(
            name='Review Request Field Options',
            description='Options for setting the contents of fields in the '
                        'review request.',
            option_list=[
                Option('-g', '--guess-fields',
                       dest='guess_fields',
                       action='store_true',
                       config_key='GUESS_FIELDS',
                       default=False,
                       help='Short-hand for --guess-summary '
                            '--guess-description.'),
                Option('--guess-summary',
                       dest='guess_summary',
                       action='store_true',
                       config_key='GUESS_SUMMARY',
                       default=False,
                       help='Generates the Summary field based on the '
                            'commit messages (Bazaar/Git/Mercurial only).'),
                Option('--guess-description',
                       dest='guess_description',
                       action='store_true',
                       config_key='GUESS_DESCRIPTION',
                       default=False,
                       help='Generates the Description field based on the '
                            'commit messages (Bazaar/Git/Mercurial only).'),
                Option('--change-description',
                       default=None,
                       help='A description of what changed in this update '
                            'of the review request. This is ignored for new '
                            'review requests.'),
                Option('--summary',
                       dest='summary',
                       default=None,
                       help='The new contents for the Summary field.'),
                Option('--description',
                       dest='description',
                       default=None,
                       help='The new contents for the Description field.'),
                Option('--description-file',
                       dest='description_file',
                       default=None,
                       metavar='FILENAME',
                       help='A text file containing the new contents for the '
                            'Description field.'),
                Option('--testing-done',
                       dest='testing_done',
                       default=None,
                       help='The new contents for the Testing Done field.'),
                Option('--testing-done-file',
                       dest='testing_file',
                       default=None,
                       metavar='FILENAME',
                       help='A text file containing the new contents for the '
                            'Testing Done field.'),
                Option('--branch',
                       dest='branch',
                       config_key='BRANCH',
                       default=None,
                       help='The branch the change will be committed on.'),
                Option('--bugs-closed',
                       dest='bugs_closed',
                       default=None,
                       help='The comma-separated list of bug IDs closed.'),
                Option('--target-groups',
                       dest='target_groups',
                       config_key='TARGET_GROUPS',
                       default=None,
                       help='The names of the groups that should perform the '
                            'review.'),
                Option('--target-people',
                       dest='target_people',
                       config_key='TARGET_PEOPLE',
                       default=None,
                       help='The usernames of the people who should perform '
                            'the review.'),
                Option('--markdown',
                       dest='markdown',
                       action='store_true',
                       config_key='MARKDOWN',
                       default=False,
                       help='Specifies if the summary and description should '
                            'be interpreted as Markdown-formatted text '
                            '(Review Board 2.0+ only).'),
            ]
        ),
        OptionGroup(
            name='Diff Generation Options',
            description='Options for choosing what gets included in a diff, '
                        'and how the diff is generated.',
            option_list=[
                Option('--revision-range',
                       dest='revision_range',
                       default=None,
                       help='Generates a diff for the given revision range. '
                            '[DEPRECATED]'),
                Option('-I', '--include',
                       dest='include_files',
                       action='append',
                       help='Includes only the given file in the diff. '
                            'This can be used multiple times to specify '
                            'multiple files.'),
                Option('--parent',
                       dest='parent_branch',
                       metavar='BRANCH',
                       config_key='PARENT_BRANCH',
                       default=None,
                       help='The parent branch this diff should be generated '
                            'against (Bazaar/Git/Mercurial only).'),
                Option('--diff-filename',
                       dest='diff_filename',
                       default=None,
                       metavar='FILENAME',
                       help='Uploads an existing diff file, instead of '
                            'generating a new diff.'),
            ]
        ),
        OptionGroup(
            name='Git Options',
            description='Git-specific options for selecting revisions for '
                        'diff generation.',
            option_list=[
                Option('--tracking-branch',
                       dest='tracking',
                       metavar='BRANCH',
                       config_key='TRACKING_BRANCH',
                       default=None,
                       help='The remote tracking branch from which your '
                            'local branch is derived '
                            '(defaults to origin/master).'),
            ]
        ),
        OptionGroup(
            name='Perforce Options',
            description='Perforce-specific options for selecting the '
                        'Perforce client and communicating with the '
                        'repository.',
            option_list=[
                Option('--p4-client',
                       dest='p4_client',
                       config_key='P4_CLIENT',
                       default=None,
                       metavar='CLIENT_NAME',
                       help='The Perforce client name for the repository.'),
                Option('--p4-port',
                       dest='p4_port',
                       config_key='P4_PORT',
                       default=None,
                       metavar='PORT',
                       help='The IP address for the Perforce server.'),
                Option('--p4-passwd',
                       dest='p4_passwd',
                       config_key='P4_PASSWD',
                       default=None,
                       metavar='PASSWORD',
                       help='The Perforce password or ticket of the user '
                            'in the P4USER environment variable.'),
            ]
        ),
        OptionGroup(
            name='Subversion Options',
            description='Subversion-specific options for controlling diff '
                        'generation.',
            option_list=[
                Option('--basedir',
                       dest='basedir',
                       config_key='BASEDIR',
                       default=None,
                       metavar='PATH',
                       help='The path within the repository where the diff '
                            'was generated. This overrides the detected path. '
                            'Often used when passing --diff-filename.'),
                Option('--svn-show-copies-as-adds',
                       dest='svn_show_copies_as_adds',
                       metavar='y/n',
                       default=None,
                       help='Treat copied or moved files as new files.'),
                Option('--svn-changelist',
                       dest='svn_changelist',
                       default=None,
                       metavar='ID',
                       help='Generates the diff for review based on a '
                            'local changelist. [DEPRECATED]'),
            ]
        ),
    ]

    def post_process_options(self):
        # -g implies --guess-summary and --guess-description
        if self.options.guess_fields:
            self.options.guess_summary = True
            self.options.guess_description = True

        if self.options.revision_range:
            raise CommandError(
                'The --revision-range argument has been removed. To post a '
                'diff for one or more specific revisions, pass those '
                'revisions as arguments. For more information, see the '
                'RBTools 0.6 Release Notes.')

        if self.options.svn_changelist:
            raise CommandError(
                'The --svn-changelist argument has been removed. To use a '
                'Subversion changelist, pass the changelist name as an '
                'additional argument after the command.')

        # Only one of --description and --description-file can be used
        if self.options.description and self.options.description_file:
            raise CommandError("The --description and --description-file "
                               "options are mutually exclusive.\n")

        # If --description-file is used, read that file
        if self.options.description_file:
            if os.path.exists(self.options.description_file):
                fp = open(self.options.description_file, "r")
                self.options.description = fp.read()
                fp.close()
            else:
                raise CommandError(
                    "The description file %s does not exist.\n" %
                    self.options.description_file)

        # Only one of --testing-done and --testing-done-file can be used
        if self.options.testing_done and self.options.testing_file:
            raise CommandError("The --testing-done and --testing-done-file "
                               "options are mutually exclusive.\n")

        # If --testing-done-file is used, read that file
        if self.options.testing_file:
            if os.path.exists(self.options.testing_file):
                fp = open(self.options.testing_file, "r")
                self.options.testing_done = fp.read()
                fp.close()
            else:
                raise CommandError("The testing file %s does not exist.\n" %
                                   self.options.testing_file)

        # If we have an explicitly specified description, override
        # --guess-description
        if self.options.guess_description and self.options.description:
            self.options.guess_description = False

        # If we have an explicitly specified review request ID, override
        # --update
        if self.options.rid and self.options.update:
            self.options.update = False

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

    def get_draft_or_current_value(self, field_name, review_request):
        """Returns the draft or current field value from a review request.

        If a draft exists for the supplied review request, return the draft's
        field value for the supplied field name, otherwise return the review
        request's field value for the supplied field name.
        """
        if review_request.draft:
            fields = review_request.draft[0]
        else:
            fields = review_request

        return fields[field_name]

    def get_possible_matches(self, review_requests, summary, description,
                             limit=5):
        """Returns a sorted list of tuples of score and review request.

        Each review request is given a score based on the summary and
        description provided. The result is a sorted list of tuples containing
        the score and the corresponding review request, sorted by the highest
        scoring review request first.
        """
        candidates = []

        # Get all potential matches.
        try:
            while True:
                for review_request in review_requests:
                    summary_pair = (
                        self.get_draft_or_current_value(
                            'summary', review_request),
                        summary)
                    description_pair = (
                        self.get_draft_or_current_value(
                            'description', review_request),
                        description)
                    score = Score.get_match(summary_pair, description_pair)
                    candidates.append((score, review_request))

                review_requests = review_requests.get_next()
        except StopIteration:
            pass

        # Sort by summary and description on descending rank.
        sorted_candidates = sorted(
            candidates,
            key=lambda m: (m[0].summary_score, m[0].description_score),
            reverse=True
        )

        return sorted_candidates[:limit]

    def num_exact_matches(self, possible_matches):
        """Returns the number of exact matches in the possible match list."""
        count = 0

        for score, request in possible_matches:
            if score.is_exact_match():
                count += 1

        return count

    def guess_existing_review_request_id(self, repository_info, api_root,
                                         api_client, tool, revision_spec=[]):
        """Try to guess the existing review request ID if it is available.

        The existing review request is guessed by comparing the existing
        summary and description to the current post's summary and description,
        respectively. The current post's summary and description are guessed if
        they are not provided.

        If the summary and description exactly match those of an existing
        review request, the ID for which is immediately returned. Otherwise,
        the user is prompted to select from a list of potential matches,
        sorted by the highest ranked match first.
        """
        user = get_user(api_client, api_root, auth_required=True)
        repository_id = get_repository_id(
            repository_info, api_root, self.options.repository_name)

        try:
            # Get only pending requests by the current user for this
            # repository.
            review_requests = api_root.get_review_requests(
                repository=repository_id, from_user=user.username,
                status='pending', expand='draft')

            if not review_requests:
                raise CommandError('No existing review requests to update for '
                                   'user %s.'
                                   % user.username)
        except APIError, e:
            raise CommandError('Error getting review requests for user '
                               '%s: %s' % (user.username, e))

        try:
            revisions = tool.parse_revision_spec(revision_spec)

            summary = (getattr(self.options, 'summary', None) or
                       tool.extract_summary(revisions))
            description = (getattr(self.options, 'description', None) or
                           tool.extract_description(revisions))
        except NotImplementedError:
            raise CommandError('--summary and --description are required.')

        possible_matches = self.get_possible_matches(review_requests, summary,
                                                     description)
        exact_match_count = self.num_exact_matches(possible_matches)

        for score, review_request in possible_matches:
            # If the score is the only exact match, return the review request
            # ID without confirmation, otherwise prompt.
            if score.is_exact_match() and exact_match_count == 1:
                return review_request.id
            else:
                question = ("Update Review Request #%s: '%s'? "
                            % (review_request.id,
                               self.get_draft_or_current_value(
                                   'summary', review_request)))

                if confirm(question):
                    return review_request.id

        return None

    def post_request(self, tool, repository_info, server_url, api_root,
                     review_request_id=None, changenum=None, diff_content=None,
                     parent_diff_content=None, commit_id=None,
                     base_commit_id=None,
                     submit_as=None, retries=3):
        """Creates or updates a review request, and uploads a diff.

        On success the review request id and url are returned.
        """
        supports_posting_commit_ids = \
            tool.capabilities.has_capability('review_requests', 'commit_ids')

        if review_request_id:
            # Retrieve the review request corresponding to the provided id.
            try:
                review_request = api_root.get_review_request(
                    review_request_id=review_request_id)
            except APIError, e:
                raise CommandError("Error getting review request %s: %s"
                                   % (review_request_id, e))

            if review_request.status == 'submitted':
                raise CommandError(
                    "Review request %s is marked as %s. In order to update "
                    "it, please reopen the review request and try again."
                    % (review_request_id, review_request.status))
        else:
            # No review_request_id, so we will create a new review request.
            try:
                repository = (
                    self.options.repository_url or
                    self.options.repository_name or
                    self.get_repository_path(repository_info, api_root))
                request_data = {
                    'repository': repository
                }

                if changenum:
                    request_data['changenum'] = changenum
                elif commit_id and supports_posting_commit_ids:
                    request_data['commit_id'] = commit_id

                if submit_as:
                    request_data['submit_as'] = submit_as

                review_request = api_root.get_review_requests().create(
                    **request_data)
            except APIError, e:
                if e.error_code == 204:  # Change number in use.
                    rid = e.rsp['review_request']['id']
                    review_request = api_root.get_review_request(
                        review_request_id=rid)

                    if not self.options.diff_only:
                        review_request = review_request.update(
                            changenum=changenum)
                else:
                    raise CommandError("Error creating review request: %s" % e)

        if (not repository_info.supports_changesets or
            not self.options.change_only):
            try:
                diff_kwargs = {
                    'parent_diff': parent_diff_content,
                    'base_dir': (self.options.basedir or
                                 repository_info.base_path),
                }

                if (base_commit_id and
                    tool.capabilities.has_capability('diffs',
                                                     'base_commit_ids')):
                    # Both the Review Board server and SCMClient support
                    # base commit IDs, so pass that along when creating
                    # the diff.
                    diff_kwargs['base_commit_id'] = base_commit_id

                review_request.get_diffs().upload_diff(diff_content,
                                                       **diff_kwargs)
            except APIError, e:
                error_msg = [
                    'Error uploading diff\n\n',
                ]

                if e.error_code == 101 and e.http_status == 403:
                    error_msg.append(
                        'You do not have permissions to modify '
                        'this review request\n')
                elif e.error_code == 219:
                    error_msg.append(
                        'The generated diff file was empty. This '
                        'usually means no files were\n'
                        'modified in this change.\n')
                else:
                    error_msg.append(str(e) + '\n')

                error_msg.append(
                    'Your review request still exists, but the diff is '
                    'not attached.\n')

                raise CommandError('\n'.join(error_msg))

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
            bug_set = (set(re.split("[, ]+", self.options.bugs_closed)) |
                       set(review_request.bugs_closed))
            self.options.bugs_closed = ",".join(bug_set)
            update_fields['bugs_closed'] = self.options.bugs_closed

        if self.options.description:
            update_fields['description'] = self.options.description

        if self.options.testing_done:
            update_fields['testing_done'] = self.options.testing_done

        if ((self.options.description or self.options.testing_done) and
            self.options.markdown and
            tool.capabilities.has_capability('text', 'markdown')):
            # The user specified that their Description/Testing Done are
            # valid Markdown, so tell the server so it won't escape the text.
            update_fields['text_type'] = 'markdown'

        if self.options.change_description:
            update_fields['changedescription'] = \
                self.options.change_description

        if self.options.publish:
            update_fields['public'] = True

        if supports_posting_commit_ids and commit_id != draft.commit_id:
            update_fields['commit_id'] = commit_id or ''

        if update_fields:
            try:
                draft = draft.update(**update_fields)
            except APIError, e:
                raise CommandError(
                    "Error updating review request draft: %s" % e)

        return review_request.id, review_request.absolute_url

    def main(self, *args):
        """Create and update review requests."""
        # The 'args' tuple must be made into a list for some of the
        # SCM Clients code. The way arguments were structured in
        # post-review meant this was a list, and certain parts of
        # the code base try and concatenate args to the end of
        # other lists. Until the client code is restructured and
        # cleaned up we will satisfy the assumption here.
        args = list(args)

        self.post_process_options()
        origcwd = os.path.abspath(os.getcwd())
        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(tool, api_root=api_root)

        if self.options.diff_filename:
            parent_diff = None
            base_commit_id = None
            commit_id = None

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
            diff_info = get_diff(
                tool,
                repository_info,
                revision_spec=args,
                files=self.options.include_files)

            diff = diff_info['diff']
            parent_diff = diff_info.get('parent_diff')
            base_commit_id = diff_info.get('base_commit_id')
            commit_id = diff_info.get('commit_id')

        if len(diff) == 0:
            raise CommandError("There don't seem to be any diffs!")

        if repository_info.supports_changesets and 'changenum' in diff_info:
            changenum = diff_info['changenum']
            commit_id = changenum
        else:
            changenum = None

        if self.options.update:
            self.options.rid = self.guess_existing_review_request_id(
                repository_info, api_root, api_client, tool, args)

            if not self.options.rid:
                raise CommandError('Could not determine the existing review '
                                   'request to update.')

        request_id, review_url = self.post_request(
            tool,
            repository_info,
            server_url,
            api_root,
            self.options.rid,
            changenum=changenum,
            diff_content=diff,
            parent_diff_content=parent_diff,
            commit_id=commit_id,
            base_commit_id=base_commit_id,
            submit_as=self.options.submit_as)

        diff_review_url = review_url + 'diff/'

        print "Review request #%s posted." % request_id
        print
        print "Review request: " + review_url
        print
        print "Diff:           " + diff_review_url
        print

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
