"""Resource definitions for screenshots.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    api_stub,
    resource_mimetype,
)
from rbtools.api.resource.mixins import ScreenshotUploadMixin

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetListParams
    from rbtools.api.resource.screenshot_comment import \
        ScreenshotCommentListResource


@resource_mimetype('application/vnd.reviewboard.org.screenshot')
class ScreenshotItemResource(ItemResource):
    """Item resource for screenshots.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-screenshot-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The absolute URL of the screenshot file, for downloading purposes.
    absolute_url: str

    #: The screenshot's descriptive caption.
    caption: str

    #: The name of the screenshot file.
    filename: str

    #: The numeric ID of the screenshot.
    id: int

    #: The path of the screenshot's image file.
    #:
    #: This is relative to the configured media directory on the Review Board
    #: server.
    path: str

    #: The URL to the review UI for this screenshot
    review_url: str

    #: The URL of the screenshot's thumbnail file.
    #:
    #: If this is not an absolute URL, it is relative to the Review Board
    #: server URL.
    thumbnail_url: str

    #: The URL of the screenshot file.
    #:
    #: This is deprecated in favor of the ``absolute_url`` attribute.
    url: str

    @api_stub
    def get_screenshot_comments(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ScreenshotCommentListResource:
        """Get the comments on the screenshot.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotCommentListResource:
            The screenshot comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


@resource_mimetype('application/vnd.reviewboard.org.screenshots')
class ScreenshotListResource(ScreenshotUploadMixin,
                             ListResource[ScreenshotItemResource]):
    """List resource for screenshots.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-screenshot-list-resource`.
    """
