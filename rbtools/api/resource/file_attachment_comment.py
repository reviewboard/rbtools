"""Resource definitions for file attachment comments.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import ListResource, api_stub, resource_mimetype
from rbtools.api.resource.base_comment import BaseCommentItemResource

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetParams
    from rbtools.api.resource.file_attachment import FileAttachmentItemResource


@resource_mimetype('application/vnd.reviewboard.org.file-attachment-comment')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-file-attachment-comment')
class FileAttachmentCommentItemResource(BaseCommentItemResource):
    """Item resource for file attachment comments.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The text used to describe a link to the file.
    link_text: str

    #: The URL to the review UI for the comment on this file attachment.
    review_url: str

    #: The HTML representing a thumbnail, if any, for this comment.
    thumbnail_url: str

    @api_stub
    def get_diff_against_file_attachment(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileAttachmentItemResource:
        """Get the original (left-hand) file when the comment was on a diff.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentItemResource:
            The file attachment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_attachment(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileAttachmentItemResource:
        """Get the file that the comment was on.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentItemResource:
            The file attachment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


@resource_mimetype('application/vnd.reviewboard.org.file-attachment-comments')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-file-attachment-comments')
class FileAttachmentCommentListResource(
    ListResource[FileAttachmentCommentItemResource]):
    """List resource for file attachment comments.

    Version Added:
        6.0
    """
