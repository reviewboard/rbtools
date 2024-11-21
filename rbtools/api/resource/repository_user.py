"""Resource definitions for repository users.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import resource_mimetype
from rbtools.api.resource.base_user import (
    BaseUserItemResource,
    BaseUserListResource,
)


@resource_mimetype('application/vnd.reviewboard.org.repository-user')
class RepositoryUserItemResource(BaseUserItemResource):
    """Item resource for repository users.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.repository-users')
class RepositoryUserListResource(
    BaseUserListResource[RepositoryUserItemResource]):
    """List resource for repository users.

    Version Added:
        6.0
    """
