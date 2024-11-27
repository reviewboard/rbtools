"""Resource definitions for users.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import api_stub, resource_mimetype
from rbtools.api.resource.base_user import (
    BaseUserItemResource,
    BaseUserListResource,
)

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.api_token import APITokenListResource
    from rbtools.api.resource.base import BaseGetListParams, BaseGetParams
    from rbtools.api.resource.user_file_attachment import \
        UserFileAttachmentListResource
    from rbtools.api.resource.watched import WatchedResource


@resource_mimetype('application/vnd.reviewboard.org.user')
class UserItemResource(BaseUserItemResource):
    """Item resource for users.

    Version Added:
        6.0
    """

    @api_stub
    def get_api_tokens(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> APITokenListResource:
        """Get an API token list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.APITokenListResource:
            The API token list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_user_file_attachments(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> UserFileAttachmentListResource:
        """Get the user file attachments list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.UserFileAttachmentListResource:
            The user file attachment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        ...

    @api_stub
    def get_watched(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> WatchedResource:
        """Get the watched resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WatchedResource:
            The watched resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    # TODO get_archived_review_requests stub
    # TODO get_muted_review_requests stub


@resource_mimetype('application/vnd.reviewboard.org.users')
class UserListResource(BaseUserListResource[UserItemResource]):
    """List resource for users.

    Version Added:
        6.0
    """
