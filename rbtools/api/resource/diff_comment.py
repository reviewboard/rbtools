"""Resource definitions for diff comments.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ListResource,
    api_stub,
    resource_mimetype,
)
from rbtools.api.resource.base_comment import BaseCommentItemResource

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import ClassVar

    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetParams
    from rbtools.api.resource.file_diff import FileDiffItemResource


@resource_mimetype('application/vnd.reviewboard.org.review-diff-comment')
@resource_mimetype('application/vnd.reviewboard.org.review-reply-diff-comment')
class DiffCommentItemResource(BaseCommentItemResource):
    """Item resource for diff comments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-diff-comment-resource` and
    :ref:`rb:webapi2.0-review-reply-diff-comment-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The line number that the comment starts at.
    #:
    #: This refers to the row number of the two-column diff, not a line number
    #: in a file.
    first_line: int

    #: The number of lines the comment spans.
    num_lines: int

    @api_stub
    def get_filediff(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileDiffItemResource:
        """Get the filediff for this comment.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffItemResource:
            The file diff item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_interfilediff(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileDiffItemResource:
        """Get the interfilediff for this comment.

        This will only be present when the comment is on an interdiff.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffItemResource:
            The file diff item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


class DiffCommentGetListParams(BaseGetListParams, total=False):
    """Params for the diff comment list GET operation.

    Version Added:
        6.0
    """

    #: The second revision in an interdiff revision range.
    #:
    #: Returned comments will be limited to this range.
    interdiff_revision: int

    #: The line number that each comment must start on.
    #:
    #: This refers to the row number of the two-column diff, not a line number
    #: in a file.
    line: int

    #: A comma-separated list of fields to order by.
    order_by: str


class AllDiffCommentsGetListParams(DiffCommentGetListParams, total=False):
    """Params for the all diff comments list resource GET operation.

    Version Added:
        6.0
    """

    #: The file diff ID that the diff comments must be on.
    file_diff_id: int

    #: Whether to return diff comments that are replies.
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

    #: The ID of the review that diff comments must belong to.
    review_id: str

    #: The ID of the review request that diff comments must belong to.
    review_request_id: str

    #: The username of the user that the reviews must be owned by.
    user: str


@resource_mimetype('application/vnd.reviewboard.org.file-diff-diff-comments')
@resource_mimetype('application/vnd.reviewboard.org.review-diff-comments')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-diff-comments')
class DiffCommentListResource(ListResource[DiffCommentItemResource]):
    """List resource for diff comments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-diff-comment-list-resource` and
    :ref:`rb:webapi2.0-review-reply-diff-comment-list-resource`.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[Mapping[str, str]] = {
        'interdiff_revision': 'interdiff-revision',
        'is_reply': 'is-reply',
        'last_updated_from': 'last-updated-from',
        'last_updated_to': 'last-updated-to',
        'order_by': 'order-by',
        'review_id': 'review-id',
        'review_request_id': 'review-request-id',
        **ListResource._httprequest_params_name_map,
    }
