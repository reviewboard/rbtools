"""Resource definitions for diff file attachments.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ItemResource,
    ListResource,
    api_stub,
    request_method_returns,
    resource_mimetype,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import ClassVar

    from typing_extensions import Unpack

    from rbtools.api.request import HttpRequest, QueryArgs
    from rbtools.api.resource.base import (
        BaseGetParams,
        ResourceExtraDataField,
    )
    from rbtools.api.resource.file_diff import FileDiffItemResource


@resource_mimetype('application/vnd.reviewboard.org.diff-file-attachment')
class DiffFileAttachmentItemResource(ItemResource):
    """Item resource for diff file attachments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-diff-file-attachment-resource`.

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

    #: The file path inside the repository for this file attachment.
    repository_file_path: str

    #: The revision that introduced this version of the file.
    repository_revision: str

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

    @api_stub
    def get_added_in_filediff(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileDiffItemResource:
        """Get the file diff that this attachment was added in.

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


class DiffFileAttachmentGetListParams(BaseGetListParams, total=False):
    """Params for the diff file attachment list GET operation.

    Version Added:
        6.0
    """

    #: Return only file attachments with the given mimetype.
    mimetype: str

    #: Filter file attachments with the given path in the repository.
    repository_file_path: str

    #: Filter file attachments with the given revision in the repository.
    repository_revision: str


@resource_mimetype('application/vnd.reviewboard.org.diff-file-attachments')
class DiffFileAttachmentListResource(
    ListResource[DiffFileAttachmentItemResource]):
    """List resource for diff file attachments.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-diff-file-attachment-list-resource`.

    Version Added:
        5.0
    """

    _httprequest_params_name_map: ClassVar[Mapping[str, str]] = {
        'repository_file_path': 'repository-file-path',
        'repository_revision': 'repository-revision',
        **ListResource._httprequest_params_name_map,
    }

    @request_method_returns[DiffFileAttachmentItemResource]()
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

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        request = self.create(query_args=kwargs, internal=True)
        request.add_file('path', filename, content)
        request.add_field('filediff', filediff_id)

        if source_file:
            request.add_field('source_file', '1')

        return request
