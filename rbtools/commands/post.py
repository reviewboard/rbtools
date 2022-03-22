from __future__ import unicode_literals

import logging
import os
import platform
import re
import sys
from collections import namedtuple

import six
from six.moves import zip
from tqdm import tqdm

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option, OptionGroup
from rbtools.utils.commands import (AlreadyStampedError,
                                    stamp_commit_with_review_url)
from rbtools.utils.console import confirm
from rbtools.utils.encoding import force_unicode
from rbtools.utils.review_request import (get_draft_or_current_value,
                                          get_revisions,
                                          guess_existing_review_request)


#: A squashed diff that may be the product of one or more revisions.
#:
#: Attributes:
#:     diff (bytes):
#:         The contents of the diff.
#:
#:     parent_diff (bytes):
#:         The contents of the parent diff.
#:
#:     base_commit_id (unicode):
#:         The ID of the commit that the diff and parent diff are relative to.
#:         This is required for SCMs like Mercurial that do not use blob IDs
#:         for files.
#:
#:     base_dir (unicode):
#:         The directory that the diff is relative to.
#:
#:     commit_id (unicode):
#:         The ID of the commit the diff corresponds to (if applicable).
#:
#:     changenum (unicode):
#:         For SCMs such as Perforce, this is the change number that the diff
#:         corresponds to. This is ``None`` for other SCMs.
SquashedDiff = namedtuple(
    'SquashedDiff', (
        'diff',
        'parent_diff',
        'base_commit_id',
        'base_dir',
        'commit_id',
        'changenum',
    ))


#: A series of diffs that each correspond to a single revision.
#:
#: Attributes:
#:     entries (list of dict):
#:         A list of the history entries. Each of these is a dict with the
#:         following keys:
#:
#:         ``commit_id`` (:py:class:`unicode`):
#:             The unique identifier for the commit. For an SCM like Git, this
#:             is a SHA-1 hash.
#:
#:         ``parent_id`` (:py:class:`unicode`):
#:             The unique identifier of the parent commit.
#:
#:         ``diff`` (:py:class:`bytes`):
#:             The contents of the diff.
#:
#:         ``commit_message`` (:py:class:`unicode`):
#:             The message associated with the commit.
#:
#:         ``author_name`` (:py:class:`unicode`):
#:             The name of the author.
#:
#:         ``author_email`` (:py:class:`unicode`):
#:             The e-mail address of the author.
#:
#:         ``author_date`` (:py:class:`unicode`):
#:             The date and time the commit was authored in ISO 8601 format.
#:
#:         ``committer_name`` (:py:class:`unicode`):
#:             The name of the committer (if applicable).
#:
#:         ``committer_email`` (:py:class:`unicode`):
#:             The e-mail address of the committer (if applicable).
#:
#:         ``committer_date`` (:py:class:`unicode`):
#:             The date and time the commit was committed in ISO 8601 format
#:             (if applicable).
#:
#:     parent_diff (bytes):
#:             The contents of the parent diff.
#:
#:     base_commit_id (unicode):
#:         The ID of the commit that the diff and parent diff are relative to.
#:         This is required for SCMs like Mercurial that do not use blob IDs
#:         for files.
#:
#:     validation_info (list of unicode):
#:         Validation metadata from the commit validation resource.
#:
#:     cumulative_diff (bytes):
#:         The cumulative diff of the entire history.
DiffHistory = namedtuple(
    'History', (
        'entries',
        'parent_diff',
        'base_commit_id',
        'validation_info',
        'cumulative_diff',
    ))


class Post(Command):
    """Create and update review requests."""

    name = 'post'
    author = 'The Review Board Project'
    description = 'Uploads diffs to create and update review requests.'

    needs_api = True
    needs_scm_client = True
    needs_repository = True

    #: Reserved built-in fields that can be set using the ``--field`` argument.
    reserved_fields = ('description', 'testing-done', 'summary')

    GUESS_AUTO = 'auto'
    GUESS_YES = 'yes'
    GUESS_NO = 'no'
    GUESS_YES_INPUT_VALUES = (True, 'yes', 1, '1')
    GUESS_NO_INPUT_VALUES = (False, 'no', 0, '0')
    GUESS_CHOICES = (GUESS_AUTO, GUESS_YES, GUESS_NO)

    args = '[revisions]'
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
                Option('-t', '--trivial-publish',
                       dest='trivial_publish',
                       action='store_true',
                       default=False,
                       help='Publish the review request immediately after '
                            'posting, but without sending an e-mail '
                            'notification.',
                       added_in='1.0'),
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
                            'request URL while posting the review.',
                       added_in='0.7.3'),
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
                       help='Uploads a new diff, but does not automatically '
                            'update fields from the commit message/change '
                            'description. Fields explicitly provided by '
                            'other options will be ignored.'),
                Option('-S', '--squash-history',
                       dest='squash_history',
                       action='store_true',
                       config_key='SQUASH_HISTORY',
                       default=False,
                       help='Force the review request to be created without '
                            'history, even if the server supports it. '
                            'Uploaded diffs will be squashed together.',
                       added_in='2.0'),
                Option('-H', '--with-history',
                       dest='with_history',
                       action='store_true',
                       default=False,
                       help='Force the review request to be created with '
                            'history if the server supports it.\n\n'
                            'This option overrides the SQUASH_HISTORY '
                            '.reviewboardrc option and the -S command line '
                            'option.',
                       added_in='2.0'),
            ]
        ),
        Command.server_options,
        Command.repository_options,
        OptionGroup(
            name='Review Request Field Options',
            description='Options for setting the contents of fields in the '
                        'review request.',
            option_list=[
                Option('-f', '--field',
                       dest='fields',
                       action='append',
                       default=None,
                       metavar='FIELD_NAME=VALUE',
                       help='Sets custom fields into the extra_data of a '
                            'review request. Can also be used to set '
                            'built-in fields like description, summary, '
                            'testing-done.'),
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
                       default=None,
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
                       default=None,
                       const=GUESS_YES,
                       choices=GUESS_CHOICES,
                       help='Generates the Description field based on the '
                            'commit messages (Bazaar/Git/Mercurial only).',
                       extended_help=(
                           'This can optionally take a value to control the '
                           'guessing behavior. See :ref:`guessing-behavior` '
                           'for more information.'
                       )),
                Option('-m', '--change-description',
                       dest='change_description',
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
                       metavar='NAME[,...]',
                       default=None,
                       help='The names of the groups that should perform the '
                            'review.'),
                Option('--target-people',
                       dest='target_people',
                       metavar='USERNAME[,...]',
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
                       help='Specifies if the summary, description, and '
                            'change description should should be interpreted '
                            'as Markdown-formatted text.'
                            '\n'
                            'This is only supported in Review Board 2.0+.',
                       added_in='0.6'),
            ]
        ),
        Command.diff_options,
        Command.branch_options,
        Command.git_options,
        Command.perforce_options,
        Command.subversion_options,
        Command.tfs_options,
    ]

    def post_process_options(self):
        super(Post, self).post_process_options()

        extra_fields = {}

        if self.options.fields is None:
            self.options.fields = []

        for field in self.options.fields:
            key_value_pair = field.split('=', 1)

            if len(key_value_pair) != 2:
                raise CommandError(
                    'The --field argument should be in the form of: '
                    '--field name=value; got "%s" instead.'
                    % field
                )

            key, value = key_value_pair

            if key in self.reserved_fields:
                key_var = key.replace('-', '_')

                if getattr(self.options, key_var):
                    raise CommandError(
                        'The "{0}" field was provided by both --{0}= '
                        'and --field {0}=. Please use --{0} instead.'
                        .format(key)
                    )

                setattr(self.options, key_var, value)
            else:
                extra_fields['extra_data.%s' % key] = value

        self.options.extra_fields = extra_fields

        # Only use default target-users / groups when creating a new review
        # request. Otherwise we'll overwrite any user changes.
        if not self.options.update and self.options.rid is None:
            if (self.options.target_groups is None and
               'TARGET_GROUPS' in self.config):
                self.options.target_groups = self.config['TARGET_GROUPS']

            if (self.options.target_people is None and
               'TARGET_PEOPLE' in self.config):
                self.options.target_people = self.config['TARGET_PEOPLE']

        # -g implies --guess-summary and --guess-description
        self.options.guess_fields = self.normalize_guess_value(
            self.options.guess_fields, '--guess-fields')

        for field_name in ('guess_summary', 'guess_description'):
            # We want to ensure we only override --guess-{field} with
            # --guess-fields when --guess-{field} is not provided.
            # to the default (auto).
            if getattr(self.options, field_name) is None:
                setattr(self.options, field_name, self.options.guess_fields)

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
                               'options are mutually exclusive.')

        # If --description-file is used, read that file
        if self.options.description_file:
            if os.path.exists(self.options.description_file):
                with open(self.options.description_file, 'r') as fp:
                    self.options.description = fp.read()
            else:
                raise CommandError(
                    'The description file %s does not exist.'
                    % self.options.description_file)

        # Only one of --testing-done and --testing-done-file can be used
        if self.options.testing_done and self.options.testing_file:
            raise CommandError('The --testing-done and --testing-done-file '
                               'options are mutually exclusive.')

        # If --testing-done-file is used, read that file
        if self.options.testing_file:
            if os.path.exists(self.options.testing_file):
                with open(self.options.testing_file, 'r') as fp:
                    self.options.testing_done = fp.read()
            else:
                raise CommandError('The testing file %s does not exist.'
                                   % self.options.testing_file)

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

        # If the --diff-filename argument is used, we can't do automatic
        # updating.
        if self.options.diff_filename and self.options.update:
            raise CommandError('The --update option cannot be used when '
                               'using --diff-filename.')

        # If we have an explicitly specified review request ID, override
        # --update
        if self.options.rid and self.options.update:
            self.options.update = False

        if self.options.trivial_publish:
            self.options.publish = True

        if self.options.with_history:
            if self.options.diff_filename:
                raise CommandError(
                    'The -H/--with-history and --diff-filename options '
                    'cannot both be provided.')
            elif self.options.basedir:
                raise CommandError(
                    'The -H/--with-history and --basedir options cannot both '
                    'be provided.')
            elif self.options.stamp_when_posting:
                raise CommandError(
                    'The -H/--with-history and -s/--stamp options cannot both '
                    'be provided.')

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

    def post_request(self,
                     review_request=None,
                     diff_history=None,
                     squashed_diff=None,
                     submit_as=None):
        """Create or update a review request, uploading a diff in the process.

        Args:
            review_request (rbtools.api.resources.ReviewRequestResource,
                            optional):
                The review request to update.

                If not provided, a new review request will be created.

            diff_history (DiffHistory, optional):
                The diff history to post for multi-commit review requests.

                Exactly one of ``diff_history`` and ``squashed_diff` must be
                specified.

            squashed_diff (SquashedDiff, optional):
                The squashed diff information to upload when uploading a
                traditional-style review request.

                Exactly one of ``diff_history`` and ``squashed_diff` must be
                specified.

            submit_as (unicode, optional):
                The username to submit the review request as.

        Returns:
            tuple:
            A 2-tuple of:

            * The review request ID.
            * The review request URL.

        Raises:
            rbtools.commands.CommandError:
                An error ocurred while posting the review request.
        """
        if ((diff_history is not None and squashed_diff is not None) or
            (diff_history is None and squashed_diff is None)):
            raise ValueError(
                'Exactly one of "diff_history" or "squashed_diff" must be '
                'provided to "Post.post_request()".')

        supports_posting_commit_ids = \
            self.capabilities.has_capability('review_requests', 'commit_ids')

        if not review_request:
            try:
                request_data = {
                    'repository': self.repository.id,
                }

                if squashed_diff:
                    if squashed_diff.changenum:
                        request_data['changenum'] = squashed_diff.changenum
                    elif (squashed_diff.commit_id and
                          supports_posting_commit_ids):
                        request_data['commit_id'] = squashed_diff.commit_id
                else:
                    request_data['create_with_history'] = True


                if submit_as:
                    request_data['submit_as'] = submit_as

                if self.tool.can_bookmark:
                    bookmark = self.tool.get_current_bookmark()
                    request_data['extra_data__local_bookmark'] = bookmark
                elif self.tool.can_branch:
                    branch = self.tool.get_current_branch()
                    request_data['extra_data__local_branch'] = branch

                review_requests = self.api_root.get_review_requests(
                    only_fields='',
                    only_links='create')
                review_request = review_requests.create(**request_data)
            except APIError as e:
                if (e.error_code == 204 and
                    squashed_diff and
                    squashed_diff.changenum):
                    # The change number is already in use. Get the review
                    # request for that change and update it instead.
                    #
                    # Since this tool is using a changenum, we know it doesn't
                    # use DVCS support, so we don't have to check if the review
                    # request was created with history.
                    review_request_id = e.rsp['review_request']['id']

                    try:
                        review_request = self.api_root.get_review_request(
                            review_request_id=review_request_id,
                            only_fields='absolute_url,bugs_closed,id,status',
                            only_links='diffs,draft')
                    except APIError as e:
                        raise CommandError(
                            'Error getting review request %s: %s'
                            % (review_request_id, e))
                else:
                    raise CommandError('Error creating review request: %s' % e)

        try:
            if diff_history:
                self._post_diff_history(review_request, diff_history)
            elif (not self.tool.supports_changesets or
                  not self.options.change_only):
                diff_kwargs = {
                    'parent_diff': squashed_diff.parent_diff,
                    'base_dir': squashed_diff.base_dir,
                }

                if (squashed_diff.base_commit_id and
                    self.capabilities.has_capability('diffs',
                                                     'base_commit_ids')):
                    # Both the Review Board server and SCMClient support
                    # base commit IDs, so pass that along when creating
                    # the diff.
                    diff_kwargs['base_commit_id'] = \
                        squashed_diff.base_commit_id

                review_request.get_diffs(only_fields='').upload_diff(
                    squashed_diff.diff, **diff_kwargs)
        except APIError as e:
            error_msg = [
                'Error uploading diff\n',
            ]

            if e.error_code == 101 and e.http_status == 403:
                error_msg.append(
                    'You do not have permissions to modify '
                    'this review request')
            elif e.error_code == 219:
                error_msg.append(
                    'The generated diff file was empty. This '
                    'usually means no files were'
                    'modified in this change.')
            else:
                error_msg.append(force_unicode(str(e)))

            error_msg.append(
                'Your review request still exists, but the diff is '
                'not attached.')

            error_msg.append('%s' % review_request.absolute_url)

            raise CommandError('\n'.join(error_msg))

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
            if diff_history:
                err = ('Cannot stamp review request URL when posting with '
                       'history.')
                self.stdout.write(err)
                self.json.add_error(err)
            elif not self.tool.can_amend_commit:
                err = ('Cannot stamp review request URL onto the commit '
                       'message; stamping is not supported with %s.'
                       % self.tool.name)
                self.stdout.write(err)
                self.json.add_error(err)

            else:
                try:
                    stamp_commit_with_review_url(self.revisions,
                                                 review_request.absolute_url,
                                                 self.tool)
                    self.stdout.write('Stamped review URL onto the '
                                      'commit message.')
                except AlreadyStampedError:
                    err = ('Commit message has already been stamped with '
                           'the review request URL.')
                    self.stdout.write(err)
                    self.json.add_error(err)
                except Exception as e:
                    logging.debug('Caught exception while stamping the '
                                  'commit message. Proceeding to post '
                                  'without stamping.', exc_info=True)
                    err = ('Could not stamp review request URL onto the '
                           'commit message.')
                    self.stdout.write(err)
                    self.json.add_error(err)

        # Update the review request draft fields based on options set
        # by the user, or configuration.
        update_fields = {}

        if self.options.publish:
            update_fields['public'] = True

            if (self.options.trivial_publish and
                self.capabilities.has_capability('review_requests',
                                                 'trivial_publish')):
                update_fields['trivial'] = True

        if not self.options.diff_only:
            # If the user has requested to guess the summary or description,
            # get the commit message and override the summary and description
            # options, which we'll fill in below. The guessing takes place
            # after stamping so that the guessed description matches the commit
            # when rbt exits.
            if not self.options.diff_filename:
                self.check_guess_fields()

            update_fields.update(self.options.extra_fields)

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

            text_type = self._get_text_type(self.options.markdown)

            if self.options.description or self.options.testing_done:
                # The user specified that their Description/Testing Done are
                # valid Markdown, so tell the server so it won't escape the
                # text.
                update_fields['text_type'] = text_type

            if self.options.change_description is not None:
                if review_request.public:
                    update_fields['changedescription'] = \
                        self.options.change_description
                    update_fields['changedescription_text_type'] = \
                        text_type
                else:
                    logging.error(
                        'The change description field can only be set when '
                        'publishing an update. Use --description instead.')

            if (squashed_diff and supports_posting_commit_ids and
                squashed_diff.commit_id != draft.commit_id):
                update_fields['commit_id'] = squashed_diff.commit_id or ''

        if update_fields:
            try:
                draft = draft.update(**update_fields)
            except APIError as e:
                raise CommandError(
                    'Error updating review request draft: %s\n\n'
                    'Your review request still exists, but the diff is not '
                    'attached.\n\n'
                    '%s\n'
                    % (e, review_request.absolute_url))

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
                    guessed_summary = commit_message['summary']
                    guessed_description = commit_message['description']

                    if guess_summary and guess_description:
                        self.options.summary = guessed_summary
                        self.options.description = guessed_description
                    elif guess_summary:
                        self.options.summary = guessed_summary
                    elif guess_description:
                        # If we're guessing the description but not the summary
                        # (for example, if --summary was included), we probably
                        # don't want to strip off the summary line of the
                        # commit message.
                        if guessed_description.startswith(guessed_summary):
                            self.options.description = guessed_description
                        else:
                            self.options.description = \
                                guessed_summary + '\n\n' + guessed_description
            except NotImplementedError:
                # The SCMClient doesn't support getting commit messages,
                # so we can't provide the guessed versions.
                pass

    def _ask_review_request_match(self, review_request):
        question = ('Update Review Request #%s: "%s"? '
                    % (review_request.id,
                       get_draft_or_current_value(
                           'summary', review_request)))

        return confirm(question)

    def main(self, *args):
        """Create and update review requests.

        Args:
            *args (tuple):
                Command line arguments.

        Raises:
            rbtools.commands.CommandError:
                An error occurred while posting.
        """
        # The 'args' tuple must be made into a list for some of the
        # SCM Clients code. The way arguments were structured in
        # post-review meant this was a list, and certain parts of
        # the code base try and concatenate args to the end of
        # other lists. Until the client code is restructured and
        # cleaned up we will satisfy the assumption here.
        self.cmd_args = list(args)

        self.post_process_options()

        orig_cwd = os.path.abspath(os.getcwd())

        if (self.options.exclude_patterns and
            not self.tool.supports_diff_exclude_patterns):
            raise CommandError(
                'The %s backend does not support excluding files via the '
                '-X/--exclude command line options or the EXCLUDE_PATTERNS '
                '.reviewboardrc option.' % self.tool.name)

        self.repository_info = \
            self.repository_info.find_server_repository_info(self.api_root)

        if self.repository is None:
            raise CommandError('Could not find the repository on the Review '
                               'Board server.')

        server_supports_history = self.capabilities.has_capability(
            'review_requests', 'supports_history')

        # If we are passing --diff-filename, we attempt to read the diff before
        # we normally would. This allows us to exit early if the file does not
        # exist or cannot be read and save several network requests.
        if self.options.diff_filename:
            if self.options.diff_filename == '-':
                if hasattr(sys.stdin, 'buffer'):
                    # Make sure we get bytes on Python 3.x.
                    diff = sys.stdin.buffer.read()
                else:
                    diff = sys.stdin.read()
            else:
                diff_path = os.path.join(orig_cwd,
                                         self.options.diff_filename)

                try:
                    with open(diff_path, 'rb') as f:
                        diff = f.read()
                except IOError as e:
                    raise CommandError('Unable to open diff filename: %s' % e)

            squashed_diff = SquashedDiff(
                diff=diff,
                parent_diff=None,
                base_commit_id=None,
                commit_id=None,
                changenum=None,
                base_dir=(self.options.basedir or
                          self.repository_info.base_path))
        else:
            self.revisions = get_revisions(self.tool, self.cmd_args)

        review_request = self._get_review_request_to_update(
            server_supports_history=server_supports_history)

        if server_supports_history and review_request:
            with_history = review_request.created_with_history

            if self.options.with_history:
                if review_request.created_with_history:
                    logging.info(
                        'The -H/--with-history option is not required when '
                        'updating an existing review request.')
                else:
                    logging.warning(
                        'The review request was not created with history. The '
                        'uploaded diff will be squashed.')
        elif server_supports_history:
            with_history = self._should_post_with_history(
                server_supports_history=server_supports_history)
        else:
            with_history = False

        diff_history = None

        # We now have enough information to generate our diff.
        #
        # If we provided --diff-filename, we already computed the diff above
        # so that we could save round trips to the server in case of IO errors.
        if not self.options.diff_filename:
            if self.revisions:
                extra_args = None
            else:
                extra_args = self.cmd_args

            if with_history:
                squashed_diff = None
                diff_history = self._get_diff_history(extra_args)
                parent_diff = (diff_history.entries and
                               diff_history.entries[0].get('parent_diff'))
            else:
                squashed_diff = self._get_squashed_diff(extra_args)
                diff_history = None
                parent_diff = squashed_diff.parent_diff

            if parent_diff:
                logging.debug('Generated parent diff size: %d bytes',
                              len(parent_diff))

        if squashed_diff is not None:
            if not squashed_diff.diff:
                raise CommandError("There don't seem to be any diffs!")
        else:
            for entry in diff_history.entries:
                if not entry['diff']:
                    raise CommandError(
                        'Your history contains an empty diff at commit %s, '
                        'which is not supported.'
                        % entry['commit_id'])

        try:
            if squashed_diff:
                self._validate_squashed_diff(squashed_diff)
            else:
                diff_history = self._validate_diff_history(diff_history)
        except APIError as e:
            msg_prefix = ''

            if e.error_code == 207:
                msg_prefix = '%s: ' % e.rsp['file']

            raise CommandError('Error validating diff\n\n%s%s'
                               % (msg_prefix, e))

        review_request_id, review_request_url = self.post_request(
            review_request=review_request,
            diff_history=diff_history,
            squashed_diff=squashed_diff,
            submit_as=self.options.submit_as)

        self.stdout.write('Review request #%s posted.' % review_request_id)
        self.stdout.new_line()
        self.stdout.write(review_request_url)
        self.stdout.write('%sdiff/' % review_request_url)

        self.json.add('review_request_id', review_request_id)
        self.json.add('review_request_url', review_request_url)
        self.json.add('diff_url', '%sdiff/' % review_request_url)

        # Load the review up in the browser if requested to.
        if self.options.open_browser:
            try:
                if (sys.platform == 'darwin' and
                    platform.mac_ver()[0] == '10.12.5'):
                    # The 'webbrowser' module currently does a bunch of stuff
                    # with AppleScript, which is broken on macOS 10.12.5. This
                    # was fixed in 10.12.6. See
                    # https://bugs.python.org/issue30392 for more discussion.
                    open(['open', review_request_url])
                else:
                    import webbrowser
                    webbrowser.open_new_tab(review_request_url)
            except Exception as e:
                logging.exception('Error opening review URL %s: %s',
                                  review_request_url, e)

    def _should_post_with_history(self, server_supports_history=False):
        """Determine whether or not we should post with history.

        Args:
            server_supports_history (bool, optional):
                Whether or not the Review Board server supports posting with
                history.

        Returns:
            bool:
            Whether or not we should post with history.

        Raises:
            rbtools.commands.CommandError:
                Using history has been specifically requested, but either the
                server or the tool does not support it.
        """
        with_history = False

        if self.tool.supports_commit_history:
            if self.options.with_history and not server_supports_history:
                raise CommandError(
                    'The Review Board server at %s does not support posting '
                    'with the -H/--with-history command line option. Re-run  '
                    'this command without it.')

            with_history = (
                server_supports_history and
                (not self.options.squash_history or
                 self.options.with_history)
            )
        elif self.options.with_history:
            # We have specifically requested to use history, but the tool does
            # not support it.
            raise CommandError(
                'The %s backend does not support review requests with history '
                'using the -H/--with-history command line option.')

        return with_history

    def _get_review_request_to_update(self, server_supports_history=False):
        """Retrieve and return the review request to update.

        Args:
            server_supports_history (bool, optional):
                Whether or not the server supports posting with history.

        Returns:
            rbtools.api.resources.ReviewRequestResource:
            The review request to update, or ``None`` if we are not updating an
            existing review request.

        Raises:
            rbtools.commands.CommandError:
                An error occurred while posting.
        """
        review_request = None
        additional_fields = []

        # If we are updating an existing review request, we need to know
        # whether or not it was created with history support so that we can
        # either (1) generate a list of history (if it was) or (2) generate
        # just a diff.
        if server_supports_history:
            additional_fields.append('created_with_history')

        if self.options.update and self.revisions:
            try:
                review_request = guess_existing_review_request(
                    api_root=self.api_root,
                    api_client=self.api_client,
                    tool=self.tool,
                    revisions=self.revisions,
                    guess_summary=False,
                    guess_description=False,
                    is_fuzzy_match_func=self._ask_review_request_match,
                    submit_as=self.options.submit_as,
                    additional_fields=additional_fields,
                    repository_id=self.repository.id)
            except ValueError as e:
                raise CommandError(six.text_type(e))

            if not review_request or not review_request.id:
                raise CommandError('Could not determine existing review '
                                   'request to update.')

            # We found a match, but the review request object we got back only
            # has partial information. We now need to re-fetch the review
            # request. To do so, we're going to plug the resulting ID back
            # into the options and query the way we would if -r was passed on
            # the command line.
            self.options.rid = review_request.id

        if self.options.rid:
            only_fields = [
                'absolute_url',
                'bugs_closed',
                'id',
                'status',
                'public',
            ]
            only_fields += additional_fields

            try:
                review_request = self.api_root.get_review_request(
                    review_request_id=self.options.rid,
                    only_fields=','.join(only_fields),
                    only_links='diffs,draft')
            except APIError as e:
                raise CommandError('Error getting review request %s: %s'
                                   % (self.options.rid, e))

        if review_request and review_request.status == 'submitted':
            raise CommandError(
                'Review request %s is marked as submitted. In order to '
                'update it, please re-open the review request and try '
                'again.'
                % review_request.id)

        return review_request

    def _get_diff_history(self, extra_args):
        """Compute and return the diff history of the selected revisions.

        Args:
            extra_args (list):
                Extra arguments to pass to the underlying tool.

        Returns:
            DiffHistory:
            The computed history.

        Raises:
            rbtools.commands.CommandError:
                The diff history is empty.
        """
        history_entries = self.tool.get_commit_history(self.revisions)

        if history_entries is None:
            raise CommandError("There don't seem to be any diffs.")

        diff_kwargs = {}

        if self.options.git_find_renames_threshold is not None:
            diff_kwargs['git_find_renames_threshold'] = \
                self.options.git_find_renames_threshold

        cumulative_diff_info = self.tool.diff(
            revisions=self.revisions,
            repository_info=self.repository_info,
            extra_args=extra_args,
            include_files=self.options.include_files or [],
            exclude_patterns=self.options.exclude_patterns or [],
            **diff_kwargs)

        for i, history_entry in enumerate(history_entries):
            revisions = {
                'base': history_entry['parent_id'],
                'tip': history_entry['commit_id'],
            }

            # Generate a diff against the revisions or arguments, filtering
            # by the requested files if provided.
            diff_info = self.tool.diff(
                revisions=revisions,
                include_files=self.options.include_files or [],
                exclude_patterns=self.options.exclude_patterns or [],
                with_parent_diff=False,
                repository_info=self.repository_info,
                extra_args=extra_args,
                **diff_kwargs)

            history_entry['diff'] = diff_info['diff']

        return DiffHistory(
            base_commit_id=cumulative_diff_info.get('base_commit_id'),
            cumulative_diff=cumulative_diff_info['diff'],
            entries=history_entries,
            parent_diff=cumulative_diff_info.get('parent_diff'),
            validation_info=None)

    def _get_squashed_diff(self, extra_args):
        """Return the squashed diff for the requested revisions.

        Args:
            extra_args (list):
                Extra arguments to pass to the underlying tool.

        Returns:
            SquashedDiff:
            The squashed diff and associated metadata.
        """
        diff_kwargs = {}

        if self.options.git_find_renames_threshold is not None:
            diff_kwargs['git_find_renames_threshold'] = \
                self.options.git_find_renames_threshold

        diff_info = self.tool.diff(
            revisions=self.revisions,
            include_files=self.options.include_files or [],
            exclude_patterns=self.options.exclude_patterns or [],
            repository_info=self.repository_info,
            extra_args=extra_args,
            **diff_kwargs)

        # If only certain files within a commit are being submitted for review,
        # do not include the commit id. This prevents conflicts if multiple
        # files from the same commit are posted for review separately.
        if self.options.include_files or self.options.exclude_patterns:
            diff_info['commit_id'] = None

        if (self.tool.supports_changesets and
            not self.options.diff_filename and
            'changenum' in diff_info):
            changenum = diff_info['changenum']
        else:
            changenum = self.tool.get_changenum(self.revisions)

        return SquashedDiff(
            diff=diff_info['diff'],
            parent_diff=diff_info.get('parent_diff'),
            base_commit_id=diff_info.get('base_commit_id'),
            commit_id=diff_info.get('commit_id'),
            changenum=changenum,
            base_dir=self.options.basedir or self.repository_info.base_path)

    def _post_diff_history(self, review_request, diff_history):
        """Post the diff history to the review request.

        Args:
            review_request (rbtools.api.resource.ReviewRequestResource):
                The review request to upload the diffs to.

            diff_history (DiffHistory):
                The diff history.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred while communicating with the API.
        """
        draft = review_request.get_or_create_draft(only_fields='',
                                                   only_links='draft_diffs')
        diffs = draft.get_draft_diffs(only_fields='', only_links='')

        if self.capabilities.has_capability('diffs', 'base_commit_ids'):
            base_commit_id = diff_history.base_commit_id
        else:
            base_commit_id = None

        diff = diffs.create_empty(base_commit_id=base_commit_id,
                                  only_fields='',
                                  only_links='self,draft_commits')
        commits = diff.get_draft_commits()

        iterable = self._show_progress(
            iterable=zip(diff_history.entries,
                         diff_history.validation_info),
            desc='Uploading commits... ',
            total=len(diff_history.entries))

        for history_entry, validation_info in iterable:
            commits.upload_commit(validation_info,
                                  parent_diff=diff_history.parent_diff,
                                  **history_entry)

        diff.finalize_commit_series(
            cumulative_diff=diff_history.cumulative_diff,
            parent_diff=diff_history.parent_diff,
            validation_info=diff_history.validation_info[-1])

    def _validate_squashed_diff(self, squashed_diff):
        """Validate the diff to ensure that it can be parsed and files exist.

        Args:
            squashed_diff (SquashedDiff):
                The squashed diff and metadata.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred during validation.
        """
        # Review Board 2.0.14+ (with the diffs.validation.base_commit_ids
        # capability) is required to successfully validate against hosting
        # services that need a base_commit_id. This is basically due to
        # the limitations of a couple Git-specific hosting services
        # (Beanstalk, Bitbucket, and Unfuddle).
        #
        # In order to validate, we need to either not be dealing with a
        # base commit ID (--diff-filename), or be on a new enough version
        # of Review Board, or be using a non-Git repository.
        can_validate_base_commit_ids = self.capabilities.has_capability(
            'diffs', 'validation', 'base_commit_ids')

        if (not squashed_diff.base_commit_id or
            can_validate_base_commit_ids or
            self.tool.name != 'Git'):
            # We can safely validate this diff before posting it, but we
            # need to ensure we only pass base_commit_id if the capability
            # is set.
            validate_kwargs = {}

            try:
                validator = self.api_root.get_diff_validation()
            except AttributeError:
                # The server doesn't have a diff validation resource.
                return

            if can_validate_base_commit_ids:
                validate_kwargs['base_commit_id'] = \
                    squashed_diff.base_commit_id

            validator.validate_diff(
                self.repository.id,
                squashed_diff.diff,
                parent_diff=squashed_diff.parent_diff,
                base_dir=squashed_diff.base_dir,
                **validate_kwargs)

    def _validate_diff_history(self, diff_history):
        """Validate the diffs.

        This will ensure that the diffs can be parsed and that all files
        mentioned exist.

        Args:
            diff_history (DiffHistory):
                The history to validate.

        Returns:
            diff_history:
            The updated history, with validation information.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred during validation.
        """
        validator = self.api_root.get_commit_validation()
        validation_info = None
        validation_info_list = [None]

        for history_entry in self._show_progress(iterable=diff_history.entries,
                                                 desc='Validating commits...'):
            validation_rsp = validator.validate_commit(
                repository=self.repository.id,
                diff=history_entry['diff'],
                commit_id=history_entry['commit_id'],
                parent_id=history_entry['parent_id'],
                parent_diff=diff_history.parent_diff,
                base_commit_id=diff_history.base_commit_id,
                validation_info=validation_info)

            validation_info = validation_rsp.validation_info
            validation_info_list.append(validation_info)

        return diff_history._replace(validation_info=validation_info_list)

    def _show_progress(self, iterable, desc, total=None):
        """Show a progress bar for commit validation and upload.

        Args:
            iterable (iterable of object):
                What will be iterated.

            desc (unicode):
                The bar description.

            total (int, optional):
                The size of the iterable, which is used to determine progress.
                This is only required if ``iterable`` does not imp;ement
                ``__len__``.

        Returns:
            tqdm.tqdm:
            The progress bar.
        """
        if total is None:
            try:
                total = len(iterable)
            except TypeError:
                pass

        return tqdm(**{
            'iterable': iterable,
            'bar_format': '{desc} {bar} [{n_fmt}/{total_fmt}]',
            'desc': desc,
            'ncols': 80,
            'total': total,
        })
