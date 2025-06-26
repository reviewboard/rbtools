"""Resource definitions for review groups.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import api_stub, resource_mimetype
from rbtools.api.resource.base_review_group import (
    BaseReviewGroupItemResource,
    BaseReviewGroupListResource,
)

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base_user import UserGetListParams
    from rbtools.api.resource.review_group_user import \
        ReviewGroupUserListResource


@resource_mimetype('application/vnd.reviewboard.org.review-group')
class ReviewGroupItemResource(BaseReviewGroupItemResource):
    """Item resource for review groups.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-group-resource`.

    Version Added:
        6.0
    """

    @api_stub
    def get_review_group_users(
        self,
        **kwargs: Unpack[UserGetListParams],
    ) -> ReviewGroupUserListResource:
        """Get the users for the review group.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewGroupUserListResource:
            The review group user list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


@resource_mimetype('application/vnd.reviewboard.org.review-groups')
class ReviewGroupListResource(
    BaseReviewGroupListResource[ReviewGroupItemResource]):
    """List resource for review groups.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-group-list-resource`.

    Version Added:
        6.0
    """
