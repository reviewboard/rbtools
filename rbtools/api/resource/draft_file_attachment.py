"""Resource definitions for draft file attachments.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)
from rbtools.api.resource.mixins import AttachmentUploadMixin

if TYPE_CHECKING:
    from rbtools.api.resource.base import ResourceExtraDataField


@resource_mimetype('application/vnd.reviewboard.org.draft-file-attachment')
class DraftFileAttachmentItemResource(ItemResource):
    """Item resource for draft file attachments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-draft-file-attachment-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The absolute URL of the file, for downloading purposes.
    absolute_url: str

    #: The ID of the file attachment history.
    attachment_history_id: int

    #: The file's descriptive caption.
    caption: str

    #: Extra data as part of the file attachment.
    extra_data: ResourceExtraDataField

    #: The name of the file.
    filename: str

    #: The URL to a 24x24 icon representing the file.
    #:
    #: The use of these icons is deprecated and this property may be removed in
    #: a future version of Review Board.
    icon_url: str

    #: The numeric ID of the file.
    id: int

    #: The mimetype for the file.
    mimetype: str

    #: The URL to a review UI for this file.
    review_url: str

    #: The revision of the file attachment.
    revision: int

    #: A thumbnail representing this file.
    thumbnail: str

    #: The URL of the file, for downloading purposes.
    #:
    #: This is deprecated in favor of the ``absolute_url`` attribute.
    url: str


@resource_mimetype('application/vnd.reviewboard.org.draft-file-attachments')
class DraftFileAttachmentListResource(
    AttachmentUploadMixin,
    ListResource[DraftFileAttachmentItemResource]):
    """List resource for draft file attachments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-draft-file-attachment-list-resource`.
    """
