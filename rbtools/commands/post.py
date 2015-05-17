from __future__ import print_function, unicode_literals

import logging
import os
import re
import sys

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option, OptionGroup
from rbtools.utils.commands import (AlreadyStampedError,
                                    get_review_request,
                                    stamp_commit_with_review_url)
from rbtools.utils.console import confirm
from rbtools.utils.review_request import (get_draft_or_current_value,
                                          get_revisions,
                                          guess_existing_review_request)

class Post(Command):
    """Create and update review requests."""
    name = 'post'
    author = 'The Review Board Project'
    description = 'Uploads diffs to create and update review requests.'
    args = '[revisions]'

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
                Option('-u', '--update',
                       dest='update',
                       action='store_true',
                       default=False,
                       help='Automatically determines the existing review '
                            'request to update.',
                       added_in='0.5.3'),
                Option('-r', '--review-request-id',
                       dest='rid',
                       metavar='ID',
                       default=None,
                       help='Specifies the existing review request ID to '
                            'update.'),
                Option('-p', '--publish',
                       dest='publish',
                       action='store_true',
                       default=False,
                       config_key='PUBLISH',
                       help='Publishes the review request immediately after '
                            'posting.'
                            '\n'
                            'All required fields must already be filled in '
                            'on the review request or must be provided when '
                            'posting.'),
                Option('-o', '--open',
                       dest='open_browser',
                       action='store_true',
                       config_key='OPEN_BROWSER',
                       default=False,
                       help='Opens a web browser to the review request '
                            'after posting.'),
                Option('-s', '--stamp',
                       dest='stamp_when_posting',
                       action='store_true',
                       config_key='STAMP_WHEN_POSTING',
                       default=False,
                       help='Stamps the commit message with the review '
                            'request URL while posting the review.'),
                Option('--submit-as',
                       dest='submit_as',
                       metavar='USERNAME',
                       config_key='SUBMIT_AS',
                       default=None,
                       help='The username to use as the author of the '
                            'review request, instead of the logged in user.',
                       extended_help=(
                           "This is useful when used in a repository's "
                           "post-commit script to update or create review "
                           "requests. See :ref:`automating-rbt-post` for "
                           "more information on this use case."
                       )),
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
                       help='Equivalent to setting both --guess-summary '
                            'and --guess-description.',
                       extended_help=(
                           'This can optionally take a value to control the '
                           'guessing behavior. See :ref:`guessing-behavior` '
                           'for more information.'
                       )),
                Option('--guess-summary',
                       dest='guess_summary',
                       action='store',
                       config_key='GUESS_SUMMARY',
                       nargs='?',
                       default=GUESS_AUTO,
                       const=GUESS_YES,
                       choices=GUESS_CHOICES,
                       help='Generates the Summary field based on the '
                            'commit messages (Bazaar/Git/Mercurial only).',
                       extended_help=(
                           'This can optionally take a value to control the '
                           'guessing behavior. See :ref:`guessing-behavior` '
                           'for more information.'
                       )),
                Option('--guess-description',
                       dest='guess_description',
                       action='store',
                       config_key='GUESS_DESCRIPTION',
                       nargs='?',
                       default=GUESS_AUTO,
                       const=GUESS_YES,
                       choices=GUESS_CHOICES,
                       help='Generates the Description field based on the '
                            'commit messages (Bazaar/Git/Mercurial only).',
                       extended_help=(
                           'This can optionally take a value to control the '
                           'guessing behavior. See :ref:`guessing-behavior` '
                           'for more information.'
                       )),
                Option('--change-description',
                       default=None,
                       metavar='TEXT',
                       help='A description of what changed in this update '
                            'of the review request. This is ignored for new '
                            'review requests.'),
                Option('--summary',
                       dest='summary',
                       metavar='TEXT',
                       default=None,
                       help='The new contents for the Summary field.'),
                Option('--description',
                       dest='description',
                       metavar='TEXT',
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
                       metavar='TEXT',
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
                       metavar='BRANCH',
                       default=None,
                       help='The branch the change will be committed on or '
                            'affects. This is a free-form field and does not '
                            'control any behavior.'),
                Option('--bugs-closed',
                       dest='bugs_closed',
                       metavar='BUG_ID[,...]',
                       default=None,
                       help='The comma-separated list of bug IDs closed.'),
                Option('--target-groups',
                       dest='target_groups',
                       config_key='TARGET_GROUPS',
                       metavar='NAME[,...]',
                       default=None,
                       help='The names of the groups that should perform the '
                            'review.'),
                Option('--target-people',
                       dest='target_people',
                       metavar='USERNAME[,...]',
                       config_key='TARGET_PEOPLE',
                       default=None,
                       help='The usernames of the people who should perform '
                            'the review.'),
                Option('--depends-on',
                       dest='depends_on',
                       config_key='DEPENDS_ON',
                       metavar='ID[,...]',
                       default=None,
                       help='A comma-separated list of review request IDs '
                            'that this review request will depend on.',
                       added_in='0.6.1'),
                Option('--markdown',
                       dest='markdown',
                       action='store_true',
                       config_key='MARKDOWN',
                       default=False,
                       help='Specifies if the summary and description should '
                            'be interpreted as Markdown-formatted text.'
                            '\n'
                            'This is only supported in Review Board 2.0+.',
                       added_in='0.6'),
            ]
        ),
        Command.diff_options,
        Command.perforce_options,
        Command.subversion_options,
        Command.tfs_options,
    ]

    def post_process_options(self):
        super(Post, self).post_process_options()

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
            raise CommandError('The --description and --description-file '
                               'options are mutually exclusive.\n')

        # If --description-file is used, read that file
        if self.options.description_file:
            if os.path.exists(self.options.description_file):
                with open(self.options.description_file, 'r') as fp:
                    self.options.description = fp.read()
            else:
                raise CommandError(
                    'The description file %s does not exist.\n' %
                    self.options.description_file)

        # Only one of --testing-done and --testing-done-file can be used
        if self.options.testing_done and self.options.testing_file:
            raise CommandError('The --testing-done and --testing-done-file '
                               'options are mutually exclusive.\n')

        # If --testing-done-file is used, read that file
        if self.options.testing_file:
            if os.path.exists(self.options.testing_file):
                with open(self.options.testing_file, 'r') as fp:
                    self.options.testing_done = fp.read()
            else:
                raise CommandError('The testing file %s does not exist.\n' %
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
            repositories = api_root.get_repositories(only_fields='path',
                                                     only_links='')

            for repo in repositories.all_items:
                if repo['path'] in repository_info.path:
                    repository_info.path = repo['path']
                    break

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

    def post_request(self, repository_info, repository, server_url, api_root,
                     review_request_id=None, changenum=None, diff_content=None,
                     parent_diff_content=None, commit_id=None,
                     base_commit_id=None,
                     submit_as=None, retries=3, base_dir=None):
        """Creates or updates a review request, and uploads a diff.

        On success the review request id and url are returned.
        """
        supports_posting_commit_ids = \
            self.tool.capabilities.has_capability('review_requests',
                                                  'commit_ids')

        if review_request_id:
            review_request = get_review_request(
                review_request_id, api_root,
                only_fields='absolute_url,bugs_closed,id,status',
                only_links='diffs,draft')

            if review_request.status == 'submitted':
                raise CommandError(
                    'Review request %s is marked as %s. In order to update '
                    'it, please reopen the review request and try again.'
                    % (review_request_id, review_request.status))
        else:
            # No review_request_id, so we will create a new review request.
            try:
                request_data = {
                    'repository': repository
                }

                if changenum:
                    request_data['changenum'] = changenum
                elif commit_id and supports_posting_commit_ids:
                    request_data['commit_id'] = commit_id

                if submit_as:
                    request_data['submit_as'] = submit_as

                review_requests = api_root.get_review_requests(
                    only_fields='',
                    only_links='create')
                review_request = review_requests.create(**request_data)
            except APIError as e:
                if e.error_code == 204 and changenum:
                    # The change number is already in use. Get the review
                    # request for that change and update it instead.
                    rid = e.rsp['review_request']['id']
                    review_request = api_root.get_review_request(
                        review_request_id=rid,
                        only_fields='absolute_url,bugs_closed,id,status',
                        only_links='diffs,draft')

                    if not self.options.diff_only:
                        review_request = review_request.update(
                            changenum=changenum)
                else:
                    raise CommandError('Error creating review request: %s' % e)

        if (not repository_info.supports_changesets or
            not self.options.change_only):
            try:
                diff_kwargs = {
                    'parent_diff': parent_diff_content,
                    'base_dir': base_dir,
                }

                if (base_commit_id and
                    self.tool.capabilities.has_capability('diffs',
                                                          'base_commit_ids')):
                    # Both the Review Board server and SCMClient support
                    # base commit IDs, so pass that along when creating
                    # the diff.
                    diff_kwargs['base_commit_id'] = base_commit_id

                review_request.get_diffs(only_fields='').upload_diff(
                    diff_content, **diff_kwargs)
            except APIError as e:
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
                    error_msg.append(str(e).decode('utf-8') + u'\n')

                error_msg.append(
                    u'Your review request still exists, but the diff is '
                    u'not attached.\n')

                error_msg.append(u'%s\n' % review_request.absolute_url)

                raise CommandError(u'\n'.join(error_msg))

        try:
            draft = review_request.get_draft(only_fields='commit_id')
        except APIError as e:
            raise CommandError('Error retrieving review request draft: %s' % e)

        # Stamp the commit message with the review request URL before posting
        # the review, so that we can use the stamped commit message when
        # guessing the description. This enables the stamped message to be
        # present on the review if the user has chosen to publish immediately
        # upon posting.
        if self.options.stamp_when_posting:
            if not self.tool.can_amend_commit:
                print('Cannot stamp review URL onto the commit message; '
                      'stamping is not supported with %s.' % self.tool.name)

            else:
                try:
                    stamp_commit_with_review_url(self.revisions,
                                                 review_request.absolute_url,
                                                 self.tool)
                    print('Stamped review URL onto the commit message.')
                except AlreadyStampedError:
                    print('Commit message has already been stamped')
                except Exception as e:
                    logging.debug('Caught exception while stamping the '
                                  'commit message. Proceeding to post '
                                  'without stamping.', exc_info=True)
                    print('Could not stamp review URL onto the commit '
                          'message.')

        # If the user has requested to guess the summary or description,
        # get the commit message and override the summary and description
        # options. The guessing takes place after stamping so that the
        # guessed description matches the commit when rbt exits.
        if not self.options.diff_filename:
            self.check_guess_fields()

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
            self.options.bugs_closed = self.options.bugs_closed.strip(', ')
            bug_set = (set(re.split('[, ]+', self.options.bugs_closed)) |
                       set(review_request.bugs_closed))
            self.options.bugs_closed = ','.join(bug_set)
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
            except APIError as e:
                raise CommandError(u'\n'.join([
                    u'Error updating review request draft: %s\n' % e,
                    u'Your review request still exists, but the diff is '
                    u'not attached.\n',
                    u'%s\n' % review_request.absolute_url,
                ]))

        return review_request.id, review_request.absolute_url

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

        if self.revisions and (guess_summary or guess_description):
            try:
                commit_message = self.tool.get_commit_message(self.revisions)

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

    def _ask_review_request_match(self, review_request):
        question = ("Update Review Request #%s: '%s'? "
                    % (review_request.id,
                       get_draft_or_current_value(
                           'summary', review_request)))

        return confirm(question)

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

        if (self.options.exclude_patterns and
            not self.tool.supports_diff_exclude_patterns):

            raise CommandError(
                'The %s backend does not support excluding files via the '
                '-X/--exclude commandline options or the EXCLUDE_PATTERNS '
                '.reviewboardrc option.' % self.tool.name)

        # Check if repository info on reviewboard server match local ones.
        repository_info = repository_info.find_server_repository_info(api_root)

        if self.options.diff_filename:
            self.revisions = None
            parent_diff = None
            base_commit_id = None
            commit_id = None

            if self.options.diff_filename == '-':
                if hasattr(sys.stdin, 'buffer'):
                    # Make sure we get bytes on Python 3.x
                    diff = sys.stdin.buffer.read()
                else:
                    diff = sys.stdin.read()
            else:
                try:
                    diff_path = os.path.join(origcwd,
                                             self.options.diff_filename)
                    with open(diff_path, 'rb') as fp:
                        diff = fp.read()
                except IOError as e:
                    raise CommandError('Unable to open diff filename: %s' % e)
        else:
            self.revisions = get_revisions(self.tool, self.cmd_args)

            if self.revisions:
                extra_args = None
            else:
                extra_args = self.cmd_args

            # Generate a diff against the revisions or arguments, filtering
            # by the requested files if provided.
            diff_info = self.tool.diff(
                revisions=self.revisions,
                include_files=self.options.include_files or [],
                exclude_patterns=self.options.exclude_patterns or [],
                extra_args=extra_args)

            diff = diff_info['diff']
            parent_diff = diff_info.get('parent_diff')
            base_commit_id = diff_info.get('base_commit_id')
            commit_id = diff_info.get('commit_id')

        repository = (
            self.options.repository_name or
            self.options.repository_url or
            self.get_repository_path(repository_info, api_root))

        base_dir = self.options.basedir or repository_info.base_path

        if repository is None:
            raise CommandError('Could not find the repository on the Review '
                               'Board server.')

        if len(diff) == 0:
            raise CommandError("There don't seem to be any diffs!")

        # Validate the diffs to ensure that they can be parsed and that
        # all referenced files can be found.
        #
        # Review Board 2.0.14+ (with the diffs.validation.base_commit_ids
        # capability) is required to successfully validate against hosting
        # services that need a base_commit_id. This is basically due to
        # the limitations of a couple Git-specific hosting services
        # (Beanstalk, Bitbucket, and Unfuddle).
        #
        # In order to validate, we need to either not be dealing with a
        # base commit ID (--diff-filename), or be on a new enough version
        # of Review Board, or be using a non-Git repository.
        can_validate_base_commit_ids = \
            self.tool.capabilities.has_capability('diffs', 'validation',
                                                  'base_commit_ids')

        if (not base_commit_id or
            can_validate_base_commit_ids or
            self.tool.name != 'Git'):
            # We can safely validate this diff before posting it, but we
            # need to ensure we only pass base_commit_id if the capability
            # is set.
            validate_kwargs = {}

            if can_validate_base_commit_ids:
                validate_kwargs['base_commit_id'] = base_commit_id

            try:
                diff_validator = api_root.get_diff_validation()
                diff_validator.validate_diff(
                    repository,
                    diff,
                    parent_diff=parent_diff,
                    base_dir=base_dir,
                    **validate_kwargs)
            except APIError as e:
                msg_prefix = ''

                if e.error_code == 207:
                    msg_prefix = '%s: ' % e.rsp['file']

                raise CommandError('Error validating diff\n\n%s%s' %
                                   (msg_prefix, e))
            except AttributeError:
                # The server doesn't have a diff validation resource. Post as
                # normal.
                pass

        if repository_info.supports_changesets and 'changenum' in diff_info:
            changenum = diff_info['changenum']
            commit_id = changenum
        else:
            changenum = None

        if self.options.update and self.revisions:
            review_request = guess_existing_review_request(
                repository_info, self.options.repository_name, api_root,
                api_client, self.tool, self.revisions,
                guess_summary=False, guess_description=False,
                is_fuzzy_match_func=self._ask_review_request_match,
                submit_as=self.options.submit_as)

            if not review_request or not review_request.id:
                raise CommandError('Could not determine the existing review '
                                   'request to update.')

            self.options.rid = review_request.id

        # If only certain files within a commit are being submitted for review,
        # do not include the commit id. This prevents conflicts if multiple
        # files from the same commit are posted for review separately.
        if self.options.include_files or self.options.exclude_patterns:
            commit_id = None

        request_id, review_url = self.post_request(
            repository_info,
            repository,
            server_url,
            api_root,
            self.options.rid,
            changenum=changenum,
            diff_content=diff,
            parent_diff_content=parent_diff,
            commit_id=commit_id,
            base_commit_id=base_commit_id,
            submit_as=self.options.submit_as,
            base_dir=base_dir)

        diff_review_url = review_url + 'diff/'

        print('Review request #%s posted.' % request_id)
        print()
        print(review_url)
        print(diff_review_url)

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
