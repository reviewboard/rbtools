"""Implementation of rbt publish."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.errors import APIError
from rbtools.commands.base import BaseCommand, CommandError, Option

if TYPE_CHECKING:
    from typing import Any


class Publish(BaseCommand):
    """Publish a specific review request from a draft."""

    name = 'publish'
    author = 'The Review Board Project'

    needs_api = True

    args = '<review-request-id>'
    option_list = [
        BaseCommand.server_options,
        BaseCommand.repository_options,
        Option('-t', '--trivial',
               dest='trivial_publish',
               action='store_true',
               default=False,
               help='Publish the review request without sending an e-mail '
                    'notification.',
               added_in='1.0'),
        Option('--markdown',
               dest='markdown',
               action='store_true',
               config_key='MARKDOWN',
               default=False,
               help='Specifies if the change description should should be '
                    'interpreted as Markdown-formatted text.',
               added_in='1.0'),
        Option('-m', '--change-description',
               dest='change_description',
               default=None,
               help='The change description to use for the publish.',
               added_in='1.0'),
    ]

    def main(
        self,
        review_request_id: int,
    ) -> None:
        """Run the command.

        Args:
            review_request_id (int):
                The ID of the review request to publish.

        Raises:
            rbtools.commands.base.errors.CommandError:
                An error occurred while publishing.
        """
        assert self.api_root is not None
        assert self.capabilities is not None

        try:
            review_request = self.api_root.get_review_request(
                review_request_id=review_request_id,
                only_fields='absolute_url,id,public',
                only_links='draft')
        except APIError as e:
            raise CommandError(
                f'Error getting review request {review_request_id}: {e}'
            )

        update_fields: dict[str, Any] = {
            'public': True,
        }

        if (self.options.trivial_publish and
            self.capabilities.has_capability('review_requests',
                                             'trivial_publish')):
            update_fields['trivial'] = True

        if self.options.change_description is not None:
            if review_request.public:
                update_fields['changedescription'] = \
                    self.options.change_description
                update_fields['changedescription_text_type'] = \
                    self._get_text_type(self.options.markdown)
            else:
                self.log.error(
                    'The change description field can only be set when '
                    'publishing an update.')

        try:
            draft = review_request.get_draft(only_fields='')
            draft.update(**update_fields)
        except APIError as e:
            raise CommandError(
                f'Error publishing review request (it may already be '
                f'published): {e}')

        self.console.print_success(
            f'Review request #{review_request_id} is published.'
        )
        self.json.add('review_request_id', review_request.id)
        self.json.add('review_request_url', review_request.absolute_url)
