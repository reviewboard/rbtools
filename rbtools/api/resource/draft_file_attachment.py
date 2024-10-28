"""Resource definitions for draft file attachments.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from rbtools.api.resource.base import ItemResource, resource_mimetype
from rbtools.api.resource.file_attachment import FileAttachmentListResource


@resource_mimetype('application/vnd.reviewboard.org.draft-file-attachment')
class DraftFileAttachmentItemResource(ItemResource):
    """Item resource for draft file attachments.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.draft-file-attachments')
class DraftFileAttachmentListResource(FileAttachmentListResource):
    """List resource for draft file attachments."""
