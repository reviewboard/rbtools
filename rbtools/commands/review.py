"""RBTools command to create and publish reviews.

Version Added: 3.0
"""

from __future__ import unicode_literals

import logging

from rbtools.api.errors import APIError
from rbtools.commands import (BaseSubCommand,
                              BaseMultiCommand,
                              Command,
                              CommandError,
                              Option,
                              OptionGroup)


logger = logging.getLogger(__file__)


class ReviewSubCommand(BaseSubCommand):
    """A subcommand for review actions."""

    needs_api = True

    #: Whether to create the review if it does not exist.
    #:
    #: Type:
    #:     bool
    create_review_if_missing = True

    def get_review_draft(self):
        """Return the review draft, creating if desired.

        Returrns:
            rbtools.api.resource.ItemResource:
            The review draft resource.
        """
        options = self.options

        try:
            review_draft = self.api_root.get_review_draft(
                review_request_id=options.review_request_id)

            if review_draft:
                logger.debug('RBTools found a pre-existing review draft for '
                             'review request %s',
                             options.review_request_id)
        except APIError:
            review_draft = None

        if not review_draft and self.create_review_if_missing:
            try:
                reviews = self.api_root.get_reviews(
                    review_request_id=options.review_request_id)
                review_draft = reviews.create()
            except APIError as e:
                raise CommandError(
                    'Error creating review draft for review request %s: %s'
                    % (options.review_request_id, e))

        return review_draft


class AddCommentSubCommand(ReviewSubCommand):
    """Base class for comment subcommands."""

    option_list = [
        OptionGroup(
            name='Comment Options',
            option_list=[
                Option('--open-issue',
                       dest='open_issue',
                       action='store_true',
                       default=False,
                       help='Open an issue with the comment.'),
                Option('-t', '--text',
                       dest='text',
                       metavar='TEXT',
                       required=True,
                       help='Text content of the comment.'),
                Option('--markdown',
                       dest='markdown',
                       action='store_true',
                       config_key='MARKDOWN',
                       help='Specifies if the comment should be interpreted '
                            'as Markdown-formatted text.'),
            ]),
    ]

    def add_comment(self, text_type):
        """Create the comment.

        Args:
            text_type (unicode):
                The text type to use.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred while performing API requests.
        """
        raise NotImplementedError

    def main(self):
        """Run the command."""
        if not self.options.text.strip():
            raise CommandError('Comment text must not be empty.')

        try:
            self.add_comment(self._get_text_type(self.options.markdown))
        except APIError as e:
            raise CommandError('Error when creating comment: %s' % e)


class AddDiffComment(AddCommentSubCommand):
    """Subcommand to add a diff comment to a draft review."""

    name = 'add-diff-comment'
    help_text = 'Add a comment to a diff as part of a draft review.'

    option_list = AddCommentSubCommand.option_list + [
        OptionGroup(
            name='Comment Options',
            option_list=[
                Option('--diff-revision',
                       dest='diff_revision',
                       metavar='REVISION',
                       required=False,
                       help='The revision of the diff to add the comment to. '
                            'If not specified, the comment will be added to '
                            'the latest revision of the diff.'),
                Option('-f', '--filename',
                       dest='filename',
                       metavar='FILENAME',
                       required=True,
                       help='The name of the file to add a comment to.'),
                Option('-l', '--line',
                       dest='line',
                       metavar='LINE',
                       required=True,
                       type=int,
                       help='The line number to add the diff comment to.'),
                Option('-n', '--num-lines',
                       dest='num_lines',
                       metavar='NUM_LINES',
                       type=int,
                       default=1,
                       required=False,
                       help='Number of lines to include in the comment. If '
                            'not specified, the comment will span one line.'),
            ]),
    ]

    def add_comment(self, text_type):
        """Create the comment.

        Args:
            text_type (unicode):
                The text type to use.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred while performing API requests.

            rbtools.commands.CommandError:
                Another error occurred while creating the comment.
        """
        options = self.options

        if options.line < 1:
            options.line = 1

        if options.num_lines <= 0:
            options.num_lines = 1

        if not options.diff_revision:
            diffs = self.api_root.get_diffs(
                review_request_id=options.review_request_id,
                counts_only=True)
            options.diff_revision = diffs.count

        diffset = self.api_root.get_diff(
            review_request_id=options.review_request_id,
            diff_revision=options.diff_revision)

        file_to_comment = None

        for file in diffset.get_files():
            if file.dest_file.endswith(options.filename):
                if file_to_comment:
                    raise CommandError(
                        'More than one file was found in the diff with name '
                        '"%s". Add additional path elements to clarify.'
                        % options.filename)

                file_to_comment = file

        if not file_to_comment:
            raise CommandError(
                'Could not find a file with name "%s" in the diff.'
                % options.filename)

        self.get_review_draft().get_diff_comments().create(
            filediff_id=file.id,
            text=options.text,
            text_type=text_type,
            issue_opened=options.open_issue,
            first_line=options.line,
            num_lines=options.num_lines)


class AddFileAttachmentComment(AddCommentSubCommand):
    """Subcommand to add a file attachment comment to a review draft."""

    name = 'add-file-attachment-comment'
    help_text = ('Add a comment to a file attachment as part of a '
                 'draft review.')

    option_list = AddCommentSubCommand.option_list + [
        OptionGroup(
            name='Comment Options',
            option_list=[
                Option('--file-attachment-id',
                       dest='fid',
                       metavar='ID',
                       required=True,
                       help='The ID of the file attachment to add a '
                            'comment to.'),
            ]),
    ]

    def add_comment(self, text_type):
        """Create the comment.

        Args:
            text_type (unicode):
                The text type to use.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred while performing API requests.
        """
        options = self.options

        # Sanity check the file attachment first.
        try:
            self.api_root.get_file_attachment(
                review_request_id=options.review_request_id,
                file_attachment_id=options.fid)
        except APIError:
            raise CommandError(
                'Unable to find file attachment with ID %s on review '
                'request "%s".'
                % (options.fid, options.review_request_id))

        self.get_review_draft().get_file_attachment_comments().create(
            text=options.text,
            text_type=text_type,
            issue_opened=options.open_issue,
            file_attachment_id=options.fid)


class AddGeneralComment(AddCommentSubCommand):
    """Subcommand to add a general comment to a review draft."""

    name = 'add-general-comment'
    help_text = 'Add a general comment as part of a draft review.'

    def add_comment(self, text_type):
        """Create the comment.

        Args:
            text_type (unicode):
                The text type to use.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred while performing API requests.
        """
        self.get_review_draft().get_general_comments().create(
            text=self.options.text,
            text_type=text_type,
            issue_opened=self.options.open_issue)


class Discard(ReviewSubCommand):
    """Subcommand to discard a draft review."""

    name = 'discard'
    help_text = 'Discard a draft review.'
    create_review_if_missing = False

    def main(self):
        """Run the ``review discard`` command."""
        review_draft = self.get_review_draft()

        if not review_draft:
            raise CommandError(
                'Could not find a draft review for review request %s.'
                % self.options.review_request_id)

        try:
            review_draft.delete()
        except APIError as e:
            raise CommandError(
                'Error discarding review draft: %s' % e)


class Edit(ReviewSubCommand):
    """Subcommand to create or edit draft reviews."""

    name = 'edit'
    help_text = 'Create or edit a draft review.'

    option_list = [
        OptionGroup(
            name='Review Options',
            option_list=[
                Option('--header',
                       dest='review_header',
                       required=False,
                       default='',
                       help='Content for the review header field.'),
                Option('--footer',
                       dest='review_footer',
                       required=False,
                       default='',
                       help='Content for the review footer field.'),
                Option('--markdown',
                       dest='markdown',
                       action='store_true',
                       config_key='MARKDOWN',
                       help='Specifies if the comment should be interpreted '
                            'as Markdown-formatted text.'),
                Option('--ship-it',
                       dest='ship_it',
                       action='store_true',
                       required=False,
                       default=None,
                       help='Add a ship-it label to the review.'),
                Option('--no-ship-it',
                       dest='ship_it',
                       action='store_false',
                       required=False,
                       default=None,
                       help='Remove a ship-it label from the review.'),
            ],
        ),
    ]

    def main(self):
        """Run the ``review edit`` command."""
        options = self.options

        text_type = self._get_text_type(self.options.markdown)

        update_fields = {}

        if options.review_header is not None:
            update_fields['body_top'] = options.review_header
            update_fields['body_top_text_type'] = text_type

        if options.review_footer is not None:
            update_fields['body_bottom'] = options.review_footer
            update_fields['body_bottom_text_type'] = text_type

        if options.ship_it is not None:
            update_fields['ship_it'] = options.ship_it

        if update_fields:
            try:
                self.get_review_draft().update(**update_fields)
            except APIError as e:
                raise CommandError(
                    'Error updating review request draft: %s\n\n'
                    'Your review draft still exists, but may not contain the '
                    'desired information.'
                    % e)


class Publish(ReviewSubCommand):
    """Subcommand for publishing a review draft."""

    name = 'publish'
    help_text = 'Publish a draft review.'
    create_review_if_missing = False

    def main(self):
        """Run the ``review publish`` command."""
        review_draft = self.get_review_draft()

        if not review_draft:
            raise CommandError(
                'Could not find a draft review for review request %s.'
                % self.options.review_request_id)

        try:
            review_draft.update(public=True)
        except APIError as e:
            raise CommandError('Unable to publish review draft: %s' % e)


class Review(BaseMultiCommand):
    """RBTools command to create and publish reviews."""

    name = 'review'
    author = 'The Review Board Project'
    description = 'Creates, updates, and edits reviews.'

    # These are listed in this order intentionally in order to show up like
    # this in the help output.
    subcommands = [
        Edit,
        Publish,
        AddDiffComment,
        AddGeneralComment,
        AddFileAttachmentComment,
        Discard,
    ]

    common_subcommand_option_list = [
        OptionGroup(
            name='Review Options',
            option_list=[
                Option('-r', '--review-request-id',
                       dest='review_request_id',
                       required=True,
                       help='Specifies the ID of the review request to '
                            'review.'),
            ]),
        Command.server_options,
    ]
