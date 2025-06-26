"""Resource definitions for general comments.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar

from rbtools.api.resource.base import (
    BaseGetListParams,
    ListResource,
    resource_mimetype,
)
from rbtools.api.resource.base_comment import BaseCommentItemResource


@resource_mimetype('application/vnd.reviewboard.org.general-comment')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-general-comment')
class GeneralCommentItemResource(BaseCommentItemResource):
    """Item resource for general comments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-general-comment-resource` and
    :ref:`rb:webapi2.0-review-reply-general-comment-resource`.

    Version Added:
        6.0
    """


class AllGeneralCommentsGetListParams(BaseGetListParams, total=False):
    """Params for the all general comments list resource GET operation.

    Version Added:
        6.0
    """

    #: Whether to return general comments that are replies.
    is_reply: bool

    #: The earliest date/time the comment could be last updated.
    #:
    #: This is compared against the comment's ``timestamp`` field. This must be
    #: a valid ISO-8601 date/time format.
    last_updated_from: str

    #: The latest date/time the review could be last updated.
    #:
    #: This is compared against the comment's ``timestamp`` field. This must be
    #: a valid ISO-8601 date/time format.
    last_updated_to: str

    #: The ID of the review that general comments must belong to.
    review_id: str

    #: The ID of the review request that diff comments must belong to.
    review_request_id: str

    #: The username of the user that the reviews must be owned by.
    user: str


@resource_mimetype('application/vnd.reviewboard.org.general-comments')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-general-comments')
class GeneralCommentListResource(ListResource[BaseCommentItemResource]):
    """List resource for general comments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-general-comment-list-resource`. and
    :ref:`rb:webapi2.0-review-reply-general-comment-list-resource`.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[dict[str, str]] = {
        'is_reply': 'is-reply',
        'last_updated_from': 'last-updated-from',
        'last_updated_to': 'last-updated-to',
        'review_id': 'review-id',
        'review_request_id': 'review-request-id',
        **ListResource._httprequest_params_name_map,
    }
