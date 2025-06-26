"""Resource definitions for user file attachments.

Version Added:
    6.0:
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


@resource_mimetype('application/vnd.reviewboard.org.user-file-attachment')
class UserFileAttachmentItemResource(ItemResource):
    """Item resource for file attachments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-user-file-attachment-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The absolute URL of the file, for downloading purposes.
    absolute_url: str

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

    #: A thumbnail representing this file.
    thumbnail: str


@resource_mimetype('application/vnd.reviewboard.org.user-file-attachments')
class UserFileAttachmentListResource(
    AttachmentUploadMixin,
    ListResource[UserFileAttachmentItemResource]):
    """List resource for user file attachments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-user-file-attachment-list-resource`.

    Version Added:
        6.0
    """
