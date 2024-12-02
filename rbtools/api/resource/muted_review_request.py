"""Resource definitions for muted review requests.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import resource_mimetype
from rbtools.api.resource.base_archived_object import (
    BaseArchivedObjectItemResource,
    BaseArchivedObjectListResource,
)

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs


@resource_mimetype('application/vnd.reviewboard.org.muted-review-request')
class MutedReviewRequestItemResource(BaseArchivedObjectItemResource):
    """Item resource for a muted review request.

    This cannot be used to get any information about the muted item, but
    using the :py:meth:`delete` method can un-archive a review request.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.archived-review-requests')
class MutedReviewRequestListResource(
    BaseArchivedObjectListResource[MutedReviewRequestItemResource]):
    """List resource for a muted review request.

    This cannot be used to get a list of the muted items, but using the
    :py:meth:`create` method can archive a review request.

    Version Added:
        6.0
    """

    def get_item(
        self,
        *,
        review_request_id: int,
        **kwargs: QueryArgs,
    ) -> MutedReviewRequestItemResource:
        """Get a muted review request item resource.

        Args:
            review_request_id (int):
                The review request.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.MutedReviewRequestItemResource:
            The muted review request item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        url = f'{self._links["self"]["href"]}{review_request_id}/'

        return MutedReviewRequestItemResource(
            transport=self._transport,
            payload={
                'muted_review_request': {},
            },
            url=url,
            token='muted_review_request',
        )
