"""Implementation of rbt close."""

from __future__ import annotations

from rbtools.api.errors import APIError
from rbtools.commands.base import BaseCommand, CommandError, Option


COMPLETED = 'completed'
SUBMITTED = 'submitted'
DISCARDED = 'discarded'


class Close(BaseCommand):
    """Close a specific review request as discarded or submitted.

    By default, the command will change the status to submitted. The
    user can provide an optional description for this action.
    """

    name = 'close'
    author = 'The Review Board Project'

    needs_api = True

    args = '<review-request-id>'
    option_list = [
        Option('--close-type',
               dest='close_type',
               default=COMPLETED,
               help='Either `completed` or `discarded`.'),
        Option('--description',
               dest='description',
               default=None,
               help='An optional description accompanying the change.'),
        BaseCommand.server_options,
        BaseCommand.repository_options,
    ]

    def main(
        self,
        review_request_id: int,
    ) -> None:
        """Run the command.

        Args:
            review_request_id (int):
                The ID of the review request to close.
        """
        close_type = self.options.close_type
        close_type_label = close_type

        if close_type not in {COMPLETED, SUBMITTED, DISCARDED}:
            raise CommandError(
                f'{close_type} is not valid type. Try "{COMPLETED}" or '
                f'"{DISCARDED}"'
            )

        # Map the newer "completed" onto the legacy "submitted" value that the
        # API uses. close_type_label will be left saying "completed" for use in
        # user-visible output.
        if close_type == COMPLETED:
            close_type = SUBMITTED

        try:
            assert self.api_root is not None
            review_request = self.api_root.get_review_request(
                review_request_id=review_request_id)
        except APIError as e:
            raise CommandError(
                f'Error getting review request {review_request_id}: {e}'
            )

        if review_request.status == close_type:
            # Use self.options.close_type here to show "completed".
            raise CommandError(
                f'Review request #{review_request_id} is already closed as '
                f'{close_type_label}'
            )

        description = self.options.description

        if description:
            review_request = review_request.update(
                status=close_type,
                description=description)
        else:
            review_request = review_request.update(status=close_type)

        self.console.print_success(
            f'Review request #{review_request_id} is set to '
            f'{close_type_label}.'
        )

        self.json.add('close_type', review_request.status)
        self.json.add('description', description)
        self.json.add('review_request_id', review_request_id)
        self.json.add('review_request_url', review_request.absolute_url)
