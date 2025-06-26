"""Resource definitions for archived review requests.

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


@resource_mimetype('application/vnd.reviewboard.org.archived-review-request')
class ArchivedReviewRequestItemResource(BaseArchivedObjectItemResource):
    """Item resource for an archived review request.

    This cannot be used to get any information about the archived item, but
    using the :py:meth:`delete` method can un-archive a review request.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-archived-review-request-resource`.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.archived-review-requests')
class ArchivedReviewRequestListResource(
    BaseArchivedObjectListResource[ArchivedReviewRequestItemResource]):
    """List resource for an archived review request.

    This cannot be used to get a list of the archived items, but using the
    :py:meth:`create` method can archive a review request.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-archived-review-request-list-resource`.

    Version Added:
        6.0
    """

    def get_item(
        self,
        *,
        review_request_id: int,
        **kwargs: QueryArgs,
    ) -> ArchivedReviewRequestItemResource:
        """Get an archived review request item resource.

        Args:
            review_request_id (int):
                The review request.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ArchivedReviewRequestListResource:
            The archived review request list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        url = f'{self._links["self"]["href"]}{review_request_id}/'

        return ArchivedReviewRequestItemResource(
            transport=self._transport,
            payload={
                'archived_review_request': {},
            },
            url=url,
            token='archived_review_request',
        )
