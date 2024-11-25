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

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.screenshot-comments')
class ScreenshotCommentListResource(
    ListResource[ScreenshotCommentItemResource]):
    """List resource for screenshot comments.

    Version Added:
        6.0
    """
