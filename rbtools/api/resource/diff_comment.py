"""Resource definitions for diff comments.

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
    from collections.abc import Mapping

    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetParams
    from rbtools.api.resource.file_diff import FileDiffItemResource


@resource_mimetype('application/vnd.reviewboard.org.review-diff-comment')
@resource_mimetype('application/vnd.reviewboard.org.review-reply-diff-comment')
class DiffCommentItemResource(BaseCommentItemResource):
    """Item resource for diff comments.

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


@resource_mimetype('application/vnd.reviewboard.org.file-diff-diff-comments')
@resource_mimetype('application/vnd.reviewboard.org.review-diff-comments')
@resource_mimetype(
    'application/vnd.reviewboard.org.review-reply-diff-comments')
class DiffCommentListResource(ListResource[DiffCommentItemResource]):
    """List resource for diff comments.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[Mapping[str, str]] = {
        'interdiff_revision': 'interdiff-revision',
        'order_by': 'order-by',
        **ListResource._httprequest_params_name_map,
    }
