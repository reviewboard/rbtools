"""Resource definitions for repository branches.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, Optional

from rbtools.api.resource.base import (
    Resource,
    ItemResource,
    ListResource,
    resource_mimetype,
)


class RepositoryBranchItemResource(ItemResource):
    """Item resource for a repository branch.

    There's no MIME type associated with this because individual branches do
    not have their own endpoint.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The revision identifier of the commit at the branch head.
    #:
    #: The format depends on the repository type (it may be a number, SHA-1
    #: hash, or some other type). This should be treated as a relatively
    #: opaque value, but can be used as the ``start`` parameter to the
    #: repository commits resource.
    commit: str

    #: Whether this branch is the "tip" of the repository.
    #:
    #: This represents "master" or "main" for Git repositories, "trunk" for
    #: Subversion, etc.
    default: bool

    #: The ID of the branch.
    #:
    #: This is specific to the type of repository.
    id: str

    #: The name of the branch.
    name: str


@resource_mimetype('application/vnd.reviewboard.org.repository-branches')
class RepositoryBranchListResource(
    ListResource[RepositoryBranchItemResource]):
    """List resource for repository branches.

    Version Added:
        6.0
    """

    #: Resource type to instantiate for individual branches.
    #:
    #: This is necessary because individual branches don't have their own
    #: endpoint or MIME type.
    _item_resource_type: ClassVar[Optional[type[Resource]]] = \
        RepositoryBranchItemResource
