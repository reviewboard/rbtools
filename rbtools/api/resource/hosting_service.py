"""Resource definitions for hosting services.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    api_stub,
    resource_mimetype,
)

if TYPE_CHECKING:
    from typelets.json import JSONDict
    from typing_extensions import Unpack

    from rbtools.api.resource.hosting_service_account import (
        HostingServiceAccountGetListParams,
        HostingServiceAccountListResource,
    )
    from rbtools.api.resource.repository import (
        RepositoryGetListParams,
        RepositoryListResource,
    )


@resource_mimetype('application/vnd.reviewboard.org.hosting-service')
class HostingServiceItemResource(ItemResource):
    """Item resource for hosting services.

    This corresponds to Review Board`s
    :ref:`rb:webapi2.0-hosting-service-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The hosting service's unique ID.
    id: str

    #: The name of the hosting service.
    name: str

    #: Whether an account must be authorized and linked to use this service.
    needs_authorization: bool

    #: Information on account configuration plans supported by the service.
    #:
    #: These correspond to the ``repository_plan`` field used when creating or
    #: updating a repository. This is not used for all services.
    plans: JSONDict

    #: Whether the service is meant to be self-hosted in the network.
    self_hosted: bool

    #: A list of repository types supported by the service.
    #:
    #: Each of these is a registered SCMTool ID or human-readable name.
    #: Some of these may be obsolete and no longer supported by the service.
    #: See :py:attr:`visible_scmtools`.
    supported_scmtools: list[str]

    #: Whether this hosting service supports bug tracking.
    supports_bug_trackers: bool

    #: Whether remote repositories can be listed through the API.
    supports_list_remote_repositories: bool

    #: Whether this hosting service supports repositories.
    supports_repositories: bool

    #: Whether two-factor authentication is supported when linking an account.
    supports_two_factor_auth: bool

    #: The list of repository types that can be configured.
    #:
    #: Each of these is a registered SCMTool ID or human-readable name.
    visible_scmtools: list[str]

    @api_stub
    def get_accounts(
        self,
        **kwargs: Unpack[HostingServiceAccountGetListParams],
    ) -> HostingServiceAccountListResource:
        """Get the hosting service account list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.HostingServiceAccountListResource:
            The hosting service account list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repositories(
        self,
        **kwargs: Unpack[RepositoryGetListParams],
    ) -> RepositoryListResource:
        """Get the repositories that use this hosting service.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryListResource:
            The repository list.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


@resource_mimetype('application/vnd.reviewboard.org.hosting-services')
class HostingServiceListResource(ListResource[HostingServiceItemResource]):
    """List resource for hosting services.

    This corresponds to Review Board`s
    :ref:`rb:webapi2.0-hosting-service-list-resource`.

    Version Added:
        6.0
    """
