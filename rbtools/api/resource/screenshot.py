"""Resource definitions for screenshots.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)
from rbtools.api.resource.mixins import ScreenshotUploadMixin


@resource_mimetype('application/vnd.reviewboard.org.screenshot')
class ScreenshotItemResource(ItemResource):
    """Item resource for screenshots.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.screenshots')
class ScreenshotListResource(ScreenshotUploadMixin,
                             ListResource[ScreenshotItemResource]):
    """List resource for screenshots."""
