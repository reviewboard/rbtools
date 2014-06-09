import logging
import os
import re
import sys

from rbtools.api.errors import APIError
from rbtools.clients.errors import InvalidRevisionSpecError
from rbtools.commands import Command, CommandError, Option, OptionGroup
from rbtools.utils.console import confirm
from rbtools.utils.match_score import Score
from rbtools.utils.repository import get_repository_id
from rbtools.utils.users import get_user


class Post(Command):
    """Create and update review requests."""
    name = "post"
    author = "The Review Board Project"
    description = "Uploads diffs to create and update review requests."
    args = "[revisions]"

    GUESS_AUTO = 'auto'
    GUESS_YES = 'yes'
    GUESS_NO = 'no'
    GUESS_YES_INPUT_VALUES = (True, 'yes', 1, '1')
    GUESS_NO_INPUT_VALUES = (False, 'no', 0, '0')
    GUESS_CHOICES = (GUESS_AUTO, GUESS_YES, GUESS_NO)

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
                       config_key='PUBLISH',
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
        Command.server_options,
        Command.repository_options,
        OptionGroup(
            name='Review Request Field Options',
            description='Options for setting the contents of fields in the '
                        'review request.',
            option_list=[
                Option('-g', '--guess-fields',
                       dest='guess_fields',
                       action='store',
                       config_key='GUESS_FIELDS',
                       nargs='?',
                       default=GUESS_AUTO,
                       const=GUESS_YES,
                       choices=GUESS_CHOICES,
                       help='Short-hand for --guess-summary '
                            '--guess-description.'),
                Option('--guess-summary',
                       dest='guess_summary',
                       action='store',
                       config_key='GUESS_SUMMARY',
                       nargs='?',
                       default=GUESS_AUTO,
                       const=GUESS_YES,
                       choices=GUESS_CHOICES,
                       help='Generates the Summary field based on the '
                            'commit messages (Bazaar/Git/Mercurial only).'),
                Option('--guess-description',
                       dest='guess_description',
                       action='store',
                       config_key='GUESS_DESCRIPTION',
                       nargs='?',
                       default=GUESS_AUTO,
                       const=GUESS_YES,
                       choices=GUESS_CHOICES,
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
                Option('--depends-on',
                       dest='depends_on',
                       config_key='DEPENDS_ON',
                       default=None,
                       help='The new contents for the Depends On field.'),
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
        Command.diff_options,
        Command.perforce_options,
        Command.subversion_options,
    ]

    def post_process_options(self):
        # -g implies --guess-summary and --guess-description
        if self.options.guess_fields:
            self.options.guess_fields = self.normalize_guess_value(
                self.options.guess_fields, '--guess-fields')

            self.options.guess_summary = self.options.guess_fields
            self.options.guess_description = self.options.guess_fields

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

        # If we have an explicitly specified summary, override
        # --guess-summary
        if self.options.summary:
            self.options.guess_summary = self.GUESS_NO
        else:
            self.options.guess_summary = self.normalize_guess_value(
                self.options.guess_summary, '--guess-summary')

        # If we have an explicitly specified description, override
        # --guess-description
        if self.options.description:
            self.options.guess_description = self.GUESS_NO
        else:
            self.options.guess_description = self.normalize_guess_value(
                self.options.guess_description, '--guess-description')

        # If we have an explicitly specified review request ID, override
        # --update
        if self.options.rid and self.options.update:
            self.options.update = False

    def normalize_guess_value(self, guess, arg_name):
        if guess in self.GUESS_YES_INPUT_VALUES:
            return self.GUESS_YES
        elif guess in self.GUESS_NO_INPUT_VALUES:
            return self.GUESS_NO
        elif guess == self.GUESS_AUTO:
            return guess
        else:
            raise CommandError('Invalid value "%s" for argument "%s"'
                               % (guess, arg_name))

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
                                         api_client):
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

        summary = self.options.summary
        description = self.options.description

        if not summary or not description:
            try:
                commit_message = self.get_commit_message()

                if commit_message:
                    if not summary:
                        summary = commit_message['summary']

                    if not description:
                        description = commit_message['description']
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

    def post_request(self, repository_info, server_url, api_root,
                     review_request_id=None, changenum=None, diff_content=None,
                     parent_diff_content=None, commit_id=None,
                     base_commit_id=None,
                     submit_as=None, retries=3):
        """Creates or updates a review request, and uploads a diff.

        On success the review request id and url are returned.
        """
        supports_posting_commit_ids = \
            self.tool.capabilities.has_capability('review_requests',
                                                  'commit_ids')

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
                    self.options.repository_name or
                    self.options.repository_url or
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
                if e.error_code == 204 and changenum:  # Change number in use.
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
                    self.tool.capabilities.has_capability('diffs',
                                                          'base_commit_ids')):
                    # Both the Review Board server and SCMClient support
                    # base commit IDs, so pass that along when creating
                    # the diff.
                    diff_kwargs['base_commit_id'] = base_commit_id

                review_request.get_diffs().upload_diff(diff_content,
                                                       **diff_kwargs)
            except APIError, e:
                error_msg = [
                    u'Error uploading diff\n\n',
                ]

                if e.error_code == 101 and e.http_status == 403:
                    error_msg.append(
                        u'You do not have permissions to modify '
                        u'this review request\n')
                elif e.error_code == 219:
                    error_msg.append(
                        u'The generated diff file was empty. This '
                        u'usually means no files were\n'
                        u'modified in this change.\n')
                else:
                    error_msg.append(e.decode('utf-8') + u'\n')

                error_msg.append(
                    u'Your review request still exists, but the diff is '
                    u'not attached.\n')

                error_msg.append(u'%s\n' % review_request.absolute_url)

                raise CommandError(u'\n'.join(error_msg))

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

        if self.options.depends_on:
            update_fields['depends_on'] = self.options.depends_on

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
            self.tool.capabilities.has_capability('text', 'markdown')):
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

    def get_revisions(self):
        """Returns the parsed revisions from the command line arguments.

        These revisions are used for diff generation and commit message
        extraction. They will be cached for future calls.
        """
        # Parse the provided revisions from the command line and generate
        # a spec or set of specialized extra arguments that the SCMClient
        # can use for diffing and commit lookups.
        if not hasattr(self, '_revisions'):
            try:
                self._revisions = self.tool.parse_revision_spec(self.cmd_args)
            except InvalidRevisionSpecError:
                if not self.tool.supports_diff_extra_args:
                    raise

                self._revisions = None

        return self._revisions

    def check_guess_fields(self):
        """Checks and handles field guesses for the review request.

        This will attempt to guess the values for the summary and
        description fields, based on the contents of the commit message
        at the provided revisions, if requested by the caller.

        If the backend doesn't support guessing, or if guessing isn't
        requested, or if explicit values were set in the options, nothing
        will be set for the fields.
        """
        is_new_review_request = (not self.options.rid and
                                 not self.options.update)

        guess_summary = (
            self.options.guess_summary == self.GUESS_YES or
            (self.options.guess_summary == self.GUESS_AUTO and
             is_new_review_request))
        guess_description = (
            self.options.guess_description == self.GUESS_YES or
            (self.options.guess_description == self.GUESS_AUTO and
             is_new_review_request))

        if guess_summary or guess_description:
            try:
                commit_message = self.get_commit_message()

                if commit_message:
                    if guess_summary:
                        self.options.summary = commit_message['summary']

                    if guess_description:
                        self.options.description = \
                            commit_message['description']
            except NotImplementedError:
                # The SCMClient doesn't support getting commit messages,
                # so we can't provide the guessed versions.
                pass

    def get_commit_message(self):
        """Returns the commit message for the parsed revisions.

        If the SCMClient supports getting a commit message, this will fetch
        and store the message for future lookups.

        This is used for guessing the summary and description fields, and
        updating exising review requests using -u.
        """
        if not hasattr(self, '_commit_message'):
            self._commit_message = \
                self.tool.get_commit_message(self.get_revisions())

        return self._commit_message

    def main(self, *args):
        """Create and update review requests."""
        # The 'args' tuple must be made into a list for some of the
        # SCM Clients code. The way arguments were structured in
        # post-review meant this was a list, and certain parts of
        # the code base try and concatenate args to the end of
        # other lists. Until the client code is restructured and
        # cleaned up we will satisfy the assumption here.
        self.cmd_args = list(args)

        self.post_process_options()
        origcwd = os.path.abspath(os.getcwd())
        repository_info, self.tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, self.tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(self.tool, api_root=api_root)

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
            revisions = self.get_revisions()

            if revisions:
                extra_args = None
            else:
                extra_args = self.cmd_args

            # Generate a diff against the revisions or arguments, filtering
            # by the requested files if provided.
            diff_info = self.tool.diff(
                revisions=revisions,
                files=self.options.include_files or [],
                extra_args=extra_args)

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

        if not self.options.diff_filename:
            # If the user has requested to guess the summary or description,
            # get the commit message and override the summary and description
            # options.
            self.check_guess_fields()

        if self.options.update:
            self.options.rid = self.guess_existing_review_request_id(
                repository_info, api_root, api_client)

            if not self.options.rid:
                raise CommandError('Could not determine the existing review '
                                   'request to update.')

        # If only certain files within a commit are being submitted for review,
        # do not include the commit id. This prevents conflicts if mutliple
        # files from the same commit are posted for review separately.
        if self.options.include_files:
            commit_id = None

        request_id, review_url = self.post_request(
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
        print review_url
        print diff_review_url

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
