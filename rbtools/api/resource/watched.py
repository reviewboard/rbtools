"""Resource definitions for the watched list.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    api_stub,
    resource_mimetype,
)

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetListParams
    from rbtools.api.resource.watched_review_group import \
        WatchedReviewGroupListResource
    from rbtools.api.resource.watched_review_request import \
        WatchedReviewRequestListResource


@resource_mimetype('application/vnd.reviewboard.org.watched')
class WatchedResource(ItemResource):
    """The watched list resource.

    This corresponds to Review Board's :ref:`rb:webapi2.0-watched-resource`.

    Version Added:
        6.0
    """

    @api_stub
    def get_watched_review_groups(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> WatchedReviewGroupListResource:
        """Get the watched review group list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WatchedReviewGroupListResource:
            The watched review group list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_watched_review_requests(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> WatchedReviewRequestListResource:
        """Get the watched review request list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WatchedReviewRequestListResource:
            The watched review request list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError
