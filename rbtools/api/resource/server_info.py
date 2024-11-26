"""Resource definition for the server info resource.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import ItemResource, resource_mimetype


@resource_mimetype('application/vnd.reviewboard.org.server-info')
class ServerInfoResource(ItemResource):
    """Server info resource.

    Version Added:
        6.0
    """
