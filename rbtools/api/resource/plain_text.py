"""Resource definitions for plain text.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import ItemResource, resource_mimetype


@resource_mimetype('text/plain')
class PlainTextResource(ItemResource):
    """Resource for endpoints that return plain text.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The response data.
    data: bytes
