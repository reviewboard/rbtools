"""Resource definitions for diff file attachments.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.decorators import request_method_decorator
from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)

if TYPE_CHECKING:
    from rbtools.api.request import HttpRequest, QueryArgs


@resource_mimetype('application/vnd.reviewboard.org.diff-file-attachment')
class DiffFileAttachmentItemResource(ItemResource):
    """Item resource for diff file attachments.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.diff-file-attachments')
class DiffFileAttachmentListResource(ListResource):
    """List resource for diff file attachments.

    Version Added:
        5.0
    """

    @request_method_decorator
    def upload_attachment(
        self,
        *,
        filename: str,
        content: bytes,
        filediff_id: str,
        source_file: bool = False,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Upload a new attachment.

        Args:
            filename (str):
                The name of the file.

            content (bytes):
                The content of the file to upload.

            filediff_id (str):
                The ID of the filediff to attach the file to.

            source_file (bool, optional):
                Whether to upload the source version of a file.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            DiffFileAttachmentItemResource:
            The newly created diff file attachment.
        """
        request = self.create(query_args=kwargs, internal=True)
        request.add_file('path', filename, content)
        request.add_field('filediff', filediff_id)

        if source_file:
            request.add_field('source_file', '1')

        return request
