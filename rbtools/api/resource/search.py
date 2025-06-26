"""Resource definition for the search resource.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import TypedDict

from rbtools.api.resource.base import ItemResource, resource_mimetype

if TYPE_CHECKING:
    from typelets.json import JSONList


class SearchGetParams(TypedDict, total=False):
    """Params for the search GET operation.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: Whether to include users whose full name includes the search text.
    fullname: bool

    #: A specific review request ID to search for.
    id: int

    #: The maximum number of results to return for each matching object type.
    #:
    #: By default, this is 25. There is an upper limit of 200.
    max_results: int

    #: The text to search for.
    q: str


@resource_mimetype('application/vnd.reviewboard.org.search')
class SearchResource(ItemResource):
    """Resource for performing searches.

    This corresponds to Review Board's :ref:`rb:webapi2.0-search-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The list of matching review groups.
    groups: JSONList

    #: The list of matching review requests.
    review_requests: JSONList

    #: The list of matching users.
    users: JSONList
