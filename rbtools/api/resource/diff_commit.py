"""Resource definitions for diff commits.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)
from rbtools.api.resource.mixins import GetPatchMixin


@resource_mimetype('application/vnd.reviewboard.org.commit')
class DiffCommitItemResource(GetPatchMixin, ItemResource):
    """Item resource for diff commits."""


@resource_mimetype('application/vnd.reviewboard.org.commits')
class DiffCommitListResource(GetPatchMixin,
                             ListResource[DiffCommitItemResource]):
    """List resource for diff commits.

    Version Added:
        6.0
    """
