"""Resource definitions for remote repositories.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, Optional, TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ItemResource,
    ListResource,
    resource_mimetype,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


@resource_mimetype('application/vnd.reviewboard.org.remote-repository')
class RemoteRepositoryItemResource(ItemResource):
    """Item resource for remote repositories.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The unique ID for this repository.
    id: str

    #: A secondary path that can be used to reach the repository.
    mirror_path: Optional[str]

    #: The name of the repository.
    name: str

    #: The owner of the repository.
    #:
    #: This may be a user account or organization, depending on the service.
    owner: str

    #: The repository path.
    path: str

    #: The type of repository, mapping to registered SCMTools on Review Board.
    scm_type: str


class RemoteRepositoryGetListParams(BaseGetListParams, total=False):
    """Params for the remote repository list GET operation.

    Version Added:
        6.0
    """

    #: Filters the list of results.
    #:
    #: Allowed values are dependent on the hosting service. Unexpected values
    #: will be ignored.
    filter_type: str

    #: The owner (user account or organization) to look up repositories for.
    #:
    #: Defaults to the owner of the hosting service account.
    owner: str

    #: Indicates what sort of account the owner represents.
    #:
    #: This may be required by some services, and the values are dependent on
    #: that service.
    owner_type: str


@resource_mimetype('application/vnd.reviewboard.org.remote-repositories')
class RemoteRepositoryListResource(ListResource[RemoteRepositoryItemResource]):
    """List resource for remote repositories.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[Mapping[str, str]] = {
        'filter_type': 'filter-type',
        'owner_type': 'owner-type',
        **ListResource._httprequest_params_name_map,
    }
