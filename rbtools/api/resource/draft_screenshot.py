"""Resource definitions for draft screenshots.

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


@resource_mimetype('application/vnd.reviewboard.org.draft-screenshot')
class DraftScreenshotItemResource(ItemResource):
    """Item resource for draft screenshots.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.draft-screenshots')
class DraftScreenshotListResource(ScreenshotUploadMixin,
                                  ListResource[DraftScreenshotItemResource]):
    """List resource for draft screenshots."""
