"""Resource definitions for screenshots.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs


@resource_mimetype('application/vnd.reviewboard.org.screenshot')
class ScreenshotItemResource(ItemResource):
    """Item resource for screenshots.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.screenshots')
class ScreenshotListResource(ListResource):
    """List resource for screenshots."""

    @request_method_decorator
    def upload_screenshot(
        self,
        filename: str,
        content: bytes,
        caption: Optional[str] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Upload a new screenshot.

        The content argument should contain the body of the screenshot
        to be uploaded, in string format.

        Args:
            filename (str):
                The filename of the screenshot.

            content (bytes):
                The image file content.

            caption (str, optional):
                The caption to add to the screenshot.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            ScreenshotItemResource:
            The newly-created screenshot.
        """
        assert self._url is not None

        request = HttpRequest(self._url, method='POST', query_args=kwargs)
        request.add_file('path', filename, content)

        if caption:
            request.add_field('caption', caption)

        return request
