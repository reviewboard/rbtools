"""Resource definitions for file attachment comments.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ListResource,
    api_stub,
    resource_mimetype,
)
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

    This corresponds to Review Board's
    :ref:`webapi2.0-review-file-attachment-comment-resource`.

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


class AllFileAttachmentCommentsGetListParams(BaseGetListParams, total=False):
    """Params for the all file attachment comments list resource GET operation.

    Version Added:
        6.0
    """

    #: The ID of the file attachment that comments must be on.
    file_attachment_id: int

    #: The filename of the file that comments must be on.
    file_name: str

    #: Whether to return file attachment comments that are replies.
    is_reply: bool

    #: The earliest date/time the comment could be last updated.
    #:
    #: This is compared against the comment's ``timestamp`` field. This must be
    #: a valid ISO-8601 date/time format.
    last_updated_from: str

    #: The latest date/time the review could be last updated.
    #:
    #: This is compared against the comment's ``timestamp`` field. This must be
    #: a valid ISO-8601 date/time format.
    last_updated_to: str

    #: The ID of the review that file attachment comments must belong to.
    review_id: str

    #: The ID of the review request that file attachment comments must belong
    #: to.
    review_request_id: str

    #: The username of the user that the reviews must be owned by.
    user: str


@resource_mimetype('application/vnd.reviewboard.org.file-attachment-comments')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-file-attachment-comments')
class FileAttachmentCommentListResource(
    ListResource[FileAttachmentCommentItemResource]):
    """List resource for file attachment comments.

    This corresponds to Review Board's
    :ref:`webapi2.0-review-file-attachment-comment-list-resource`.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[dict[str, str]] = {
        'file_attachment_id': 'file-attachment-id',
        'file_name': 'file-name',
        'is_reply': 'is-reply',
        'last_updated_from': 'last-updated-from',
        'last_updated_to': 'last-updated-to',
        'review_id': 'review-id',
        'review_request_id': 'review-request-id',
        **ListResource._httprequest_params_name_map,
    }
