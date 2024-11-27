"""Resource definitions for hosting service accounts.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ItemResource,
    ListResource,
    api_stub,
    resource_mimetype,
)
from rbtools.api.resource.hosting_service import HostingServiceItemResource

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.remote_repository import (
        RemoteRepositoryGetListParams,
        RemoteRepositoryListResource,
    )


@resource_mimetype('application/vnd.reviewboard.org.hosting-service-account')
class HostingServiceAccountItemResource(ItemResource):
    """Item resource for hosting service accounts.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The numeric ID of the hosting service account.
    id: int

    #: The ID of the service this account is on.
    service: str

    #: The username of the account.
    username: str

    @api_stub
    def get_remote_repositories(
        self,
        **kwargs: Unpack[RemoteRepositoryGetListParams],
    ) -> RemoteRepositoryListResource:
        """Get the remote repositories for this hosting service.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RemoteRepositoryListResource:
            The remote repository list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


class HostingServiceAccountGetListParams(BaseGetListParams, total=False):
    """Params for the hosting service account list GET operation

    Version Added:
        6.0
    """

    #: Filter accounts by the hosting service ID.
    service: str

    #: Filter accounts by username.
    username: str


@resource_mimetype('application/vnd.reviewboard.org.hosting-service-accounts')
class HostingServiceAccountListResource(
    ListResource[HostingServiceItemResource]):
    """List resource for hosting service accounts.

    Version Added:
        6.0
    """
