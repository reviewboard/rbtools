"""Resource definitions for watched review requests.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)


@resource_mimetype('application/vnd.reviewboard.org.watched-review-request')
class WatchedReviewRequestItemResource(ItemResource):
    """Item resource for watched review requests.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-watched-review-request-resource`.

    Version Added:
        6.0
    """


@resource_mimetype('application/vnd.reviewboard.org.watched-review-requests')
class WatchedReviewRequestListResource(
    ListResource[WatchedReviewRequestItemResource]):
    """List resource for watched review requests.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-watched-review-request-list-resource`.

    Version Added:
        6.0
    """
