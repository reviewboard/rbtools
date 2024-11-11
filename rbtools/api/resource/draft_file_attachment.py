"""Resource definitions for draft file attachments.

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
from rbtools.api.resource.mixins import AttachmentUploadMixin


@resource_mimetype('application/vnd.reviewboard.org.draft-file-attachment')
class DraftFileAttachmentItemResource(ItemResource):
    """Item resource for draft file attachments.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.draft-file-attachments')
class DraftFileAttachmentListResource(
    AttachmentUploadMixin,
    ListResource[DraftFileAttachmentItemResource]):
    """List resource for draft file attachments."""
