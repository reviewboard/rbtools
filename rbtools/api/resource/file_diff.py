"""Resource definitions for file diffs.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import Literal, Optional, TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    api_stub,
    request_method,
    resource_mimetype,
)
from rbtools.api.resource.mixins import GetPatchMixin

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.request import HttpRequest, QueryArgs
    from rbtools.api.resource.base import (
        BaseGetParams,
        ResourceExtraDataField,
    )
    from rbtools.api.resource.diff_comment import (
        DiffCommentGetListParams,
        DiffCommentListResource,
    )
    from rbtools.api.resource.file_attachment import FileAttachmentItemResource


@resource_mimetype('application/vnd.reviewboard.org.file')
class FileDiffItemResource(GetPatchMixin, ItemResource):
    """Item resource for file diffs.

    Version Changed:
        6.0:
        Renamed from FileDiffResource.
    """

    ######################
    # Instance variables #
    ######################

    #: Whether this represents a binary file.
    binary: bool

    #: Additional information of the destination file.
    #:
    #: This is parsed from the diff, but is usually not used for anything.
    dest_detail: Optional[str]

    #: The new name of the patched file.
    #:
    #: This may be the same as the source file.
    dest_file: Optional[str]

    #: The encoding of the original and patched file, if available.
    encoding: str

    #: Extra data as part of the diff.
    extra_data: ResourceExtraDataField

    #: The numeric ID of the file diff.
    id: int

    #: The original name of the file.
    source_file: str

    #: The revision of the file being modified.
    #:
    #: This is a valid revision in the repository.
    source_revision: str

    #: The status of the file.
    status: Literal['copied', 'deleted', 'modified', 'moved', 'unknown']

    @request_method
    def get_diff_data(
        self,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Retrieve the actual raw diff data for the file.

        Args:
            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ItemResource:
            A resource wrapping the diff data.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        return self._make_httprequest(
            url=self._url,
            query_args=kwargs,
            headers={
                'Accept': 'application/vnd.reviewboard.org.diff.data+json',
            })

    @api_stub
    def get_dest_attachment(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileAttachmentItemResource:
        """Get the file attachment for the modified file.

        For binary files where an uploaded attachment exists, this will return
        the modified version of the file.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentItemResource:
            The file attachment for the modified version.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_comments(
        self,
        **kwargs: Unpack[DiffCommentGetListParams],
    ) -> DiffCommentListResource:
        """Get the comments for this file diff.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentListResource:
            The comments on this file diff.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_source_attachment(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileAttachmentItemResource:
        """Get the file attachment for the original file.

        For binary files where an uploaded attachment exists, this will return
        the original version of the file.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentItemResource:
            The file attachment for the original version.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    # TODO get_original_file stub
    # TODO get_patched_file stub


@resource_mimetype('application/vnd.reviewboard.org.files')
class FileDiffListResource(ListResource[FileDiffItemResource]):
    """List resource for file diffs.

    Version Added:
        6.0
    """
