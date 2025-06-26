"""Resource definitions for repository groups.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import resource_mimetype
from rbtools.api.resource.base_review_group import (
    BaseReviewGroupItemResource,
    BaseReviewGroupListResource,
)


@resource_mimetype('application/vnd.reviewboard.org.repository-group')
class RepositoryGroupItemResource(BaseReviewGroupItemResource):
    """Item resource for repository groups.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-repository-group-resource`.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.repository-groups')
class RepositoryGroupListResource(
    BaseReviewGroupListResource[RepositoryGroupItemResource]):
    """List resource for repository groups.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-repository-group-list-resource`.

    Version Added:
        6.0
    """
