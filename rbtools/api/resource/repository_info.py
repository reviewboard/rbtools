"""Resource definitions for repository info.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import ItemResource, resource_mimetype


@resource_mimetype('application/vnd.reviewboard.org.repository-info')
class RepositoryInfoResource(ItemResource):
    """Resource for repository info.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-repository-info-resource`.

    Version Added:
        6.0
    """
