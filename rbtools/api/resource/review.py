"""Resource definitions for reviews.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ListResource,
    api_stub,
    resource_mimetype,
)
from rbtools.api.resource.base_review import BaseReviewItemResource

if TYPE_CHECKING:
    from typing import ClassVar

    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetParams
    from rbtools.api.resource.review_reply import ReviewReplyListResource


@resource_mimetype('application/vnd.reviewboard.org.review')
class ReviewItemResource(BaseReviewItemResource):
    """Item resource for reviews.

    This corresponds to Review Board's :ref:`rb:webapi2.0-review-resource`.

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


class AllReviewsGetListParams(BaseGetListParams, total=False):
    """Params for the all reviews list resource GET operation.

    Version Added:
        6.0
    """

    #: The earliest date/time the review could be last updated.
    #:
    #: This is compared against the review's ``timestamp`` field. This must be
    #: a valid ISO-8601 date/time format.
    last_updated_from: str

    #: The latest date/time the review could be last updated.
    #:
    #: This is compared against the review's ``timestamp`` field. This must be
    #: a valid ISO-8601 date/time format.
    last_updated_to: str

    #: Whether to filter for public (published) reviews.
    #:
    #: If not set, both published and accessible unpublished reviews will be
    #: included.
    public: bool

    #: The repository name that the review requests of the reviews must be on.
    repository: str

    #: The group name of users that the reviews must be owned by.
    review_group: str

    #: The username of the user that the reviews must be owned by.
    user: str


@resource_mimetype('application/vnd.reviewboard.org.reviews')
class ReviewListResource(ListResource[ReviewItemResource]):
    """List resource for reviews.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-list-resource`.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[dict[str, str]] = {
        'last_updated_from': 'last-updated-from',
        'last_updated_to': 'last-updated-to',
        'review_group': 'review-group',
        **ListResource._httprequest_params_name_map,
    }

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
