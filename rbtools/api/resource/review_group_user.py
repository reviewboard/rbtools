"""Resource definitions for review group users.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import resource_mimetype
from rbtools.api.resource.base_user import (
    BaseUserItemResource,
    BaseUserListResource,
)


@resource_mimetype('application/vnd.reviewboard.org.review-group-user')
class ReviewGroupUserItemResource(BaseUserItemResource):
    """Item resource for review group users.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-group-user-resource`.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.review-group-users')
class ReviewGroupUserListResource(
    BaseUserListResource[ReviewGroupUserItemResource]):
    """List resource for review group users.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-group-user-list-resource`.

    Version Added:
        6.0
    """
