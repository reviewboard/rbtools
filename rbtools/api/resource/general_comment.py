"""Resource definitions for general comments.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import ListResource, resource_mimetype
from rbtools.api.resource.base_comment import BaseCommentItemResource


@resource_mimetype('application/vnd.reviewboard.org.general-comment')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-general-comment')
class GeneralCommentItemResource(BaseCommentItemResource):
    """Item resource for general comments.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.general-comments')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-general-comments')
class GeneralCommentListResource(ListResource[BaseCommentItemResource]):
    """List resource for general comments.

    Version Added:
        6.0
    """
