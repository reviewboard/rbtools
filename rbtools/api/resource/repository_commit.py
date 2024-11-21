"""Resource definitions for repository commits.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, Optional

from rbtools.api.resource.base import (
    BaseGetParams,
    Resource,
    ItemResource,
    ListResource,
    resource_mimetype,
)


class RepositoryCommitItemResource(ItemResource):
    """Item resource for a repository commit.

    There's no MIME type associated with this because individual commits do not
    have their own endpoint.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The real name or username of the author who made the commit.
    author_name: str

    #: The date and time of the commit in ISO-8601 format.
    date: str

    #: The revision identifier of the commit.
    #:
    #: The format depends on the repository type (it may be a number, SHA-1
    #: hash, or some other type). This should be treated as relatively opaque.
    id: str

    #: The commit message, if any.
    message: str

    #: The revision of the parent commit.
    #:
    #: This may be an empty string if this is the first revision in the
    #: commit history for a repository or branch.
    parent: str


class RepositoryCommitGetListParams(BaseGetParams, total=False):
    """Parameters for the repository commit list GET operation.

    Version Added:
        6.0
    """

    #: The branch name to fetch commits for.
    branch: str

    #: The commit ID to start at.
    start: str


@resource_mimetype('application/vnd.reviewboard.org.repository-commits')
class RepositoryCommitListResource(ListResource[RepositoryCommitItemResource]):
    """Resource for the repository commits API.

    Version Added:
        6.0
    """

    #: Resource type to instantiate for individual commits.
    #:
    #: This is necessary because individual commits don't have their own
    #: endpoint or MIME type.
    _item_resource_type: ClassVar[Optional[type[Resource]]] = \
        RepositoryCommitItemResource
