"""Resource definitions for review replies.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import ListResource, api_stub, resource_mimetype
from rbtools.api.resource.base_review import BaseReviewItemResource

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetParams


@resource_mimetype('application/vnd.reviewboard.org.review-reply')
class ReviewReplyItemResource(BaseReviewItemResource):
    """Item resource for review replies.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-reply-resource`.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.review-replies')
class ReviewReplyListResource(ListResource[ReviewReplyItemResource]):
    """List resource for review replies.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-reply-list-resource`.

    Version Added:
        6.0
    """

    @api_stub
    def get_review_reply_draft(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewReplyItemResource:
        """Get the review reply draft, if one exists.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyItemResource:
            The review reply item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_reply_draft(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewReplyItemResource:
        """Get the reply draft, if any.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyItemResource:
            The reply item resource for the draft reply.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError
