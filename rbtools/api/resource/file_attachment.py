"""Resource definitions for file attachments.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import Optional

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import ListResource, resource_mimetype


@resource_mimetype('application/vnd.reviewboard.org.file-attachments')
@resource_mimetype('application/vnd.reviewboard.org.user-file-attachments')
class FileAttachmentListResource(ListResource):
    """The File Attachment List resource specific base class."""

    @request_method_decorator
    def upload_attachment(
        self,
        filename: str,
        content: bytes,
        caption: Optional[str] = None,
        attachment_history: Optional[str] = None,
        **kwargs,
    ) -> HttpRequest:
        """Upload a new attachment.

        Args:
            filename (str):
                The name of the file.

            content (bytes):
                The content of the file to upload.

            caption (str, optional):
                The caption to set on the file attachment.

            attachment_history (str, optional):
                The ID of the FileAttachmentHistory to add this attachment to.

            **kwargs (dict):
                Additional keyword arguments to add to the request.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)
        request.add_file('path', filename, content)

        if caption:
            request.add_field('caption', caption)

        if attachment_history:
            request.add_field('attachment_history', attachment_history)

        return request
