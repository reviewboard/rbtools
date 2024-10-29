"""Resource definitions for file diffs.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    request_method,
    resource_mimetype,
)
from rbtools.api.resource.mixins import GetPatchMixin

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs


@resource_mimetype('application/vnd.reviewboard.org.file')
class FileDiffItemResource(GetPatchMixin, ItemResource):
    """Item resource for file diffs.

    Version Changed:
        6.0:
        Renamed from FileDiffResource.
    """

    @request_method
    def get_diff_data(
        self,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Retrieve the actual raw diff data for the file.

        Args:
            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ItemResource:
            A resource wrapping the diff data.
        """
        return HttpRequest(self._url, query_args=kwargs, headers={
            'Accept': 'application/vnd.reviewboard.org.diff.data+json',
        })


@resource_mimetype('application/vnd.reviewboard.org.files')
class FileDiffListResource(ListResource):
    """List resource for file diffs.

    Version Added:
        6.0
    """
