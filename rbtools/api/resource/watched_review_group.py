"""Resource definitions for watched review groups.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)


@resource_mimetype('application/vnd.reviewboard.org.watched-review-group')
class WatchedReviewGroupItemResource(ItemResource):
    """Item resource for watched review groups.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-watched-review-group-resource`.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.watched-review-groups')
class WatchedReviewGroupListResource(
    ListResource[WatchedReviewGroupItemResource]):
    """List resource for watched review groups.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-watched-review-group-list-resource`.

    Version Added:
        6.0
    """
