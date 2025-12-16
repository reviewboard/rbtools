"""Resource definitions for the review request last update.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import ItemResource, resource_mimetype

if TYPE_CHECKING:
    from typing import Literal


@resource_mimetype('application/vnd.reviewboard.org.last-update')
class LastUpdateResource(ItemResource):
    """Review request last update resource.

    This corresponds to Review Board`s
    :ref:`rb:webapi2.0-review-request-last-update-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: A short summary of the update.
    #:
    #: This should be one of:
    #: * "Review Request updated"
    #: * "Diff updated",
    #: * "New reply"
    #: * "New review".
    summary: str

    #: The timestamp of the update.
    timestamp: str

    #: The type of last update.
    #:
    #: ``review-request`` means the last update was an update of the review
    #: request's information.
    #:
    #: ``diff`` means a new diff was uploaded.
    #:
    #: ``reply`` means a reply was made to an existing review.
    #:
    #: ``review`` means a new review was posted.
    type: Literal['review-request', 'diff', 'reply', 'review']

    #: The username of the user who made the last update.
    user: str
