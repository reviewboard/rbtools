"""Resource definitions for reviews.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import ListResource, api_stub, resource_mimetype
from rbtools.api.resource.base_review import BaseReviewItemResource

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetParams, BaseGetListParams
    from rbtools.api.resource.review_reply import ReviewReplyListResource


@resource_mimetype('application/vnd.reviewboard.org.review')
class ReviewItemResource(BaseReviewItemResource):
    """Item resource for reviews.

    Version Added:
        6.0
    """

    @api_stub
    def get_replies(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ReviewReplyListResource:
        """Get the replies to this review.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyListResource:
            The review reply list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


@resource_mimetype('application/vnd.reviewboard.org.reviews')
class ReviewListResource(ListResource[ReviewItemResource]):
    """List resource for reviews.

    Version Added:
        6.0
    """

    @api_stub
    def get_review_draft(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewItemResource:
        """Get the review draft, if one exists.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewItemResource:
            The review item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError
