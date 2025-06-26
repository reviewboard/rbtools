"""Resource definitions for screenshot comments.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import ListResource, resource_mimetype
from rbtools.api.resource.base_comment import BaseCommentItemResource


@resource_mimetype('application/vnd.reviewboard.org.screenshot-comment')
class ScreenshotCommentItemResource(BaseCommentItemResource):
    """Item resource for screenshot comments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-screenshot-comment-resource` and
    :ref:`rb:webapi2.0-review-reply-screenshot-comment-resource`.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.screenshot-comments')
class ScreenshotCommentListResource(
    ListResource[ScreenshotCommentItemResource]):
    """List resource for screenshot comments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-screenshot-comment-list-resource` and
    :ref:`rb:webapi2.0-review-reply-screenshot-comment-list-resource`.

    Version Added:
        6.0
    """
