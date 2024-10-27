"""Resource definitions for file diffs.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import ItemResource, resource_mimetype
from rbtools.api.resource.mixins import GetPatchMixin


@resource_mimetype('application/vnd.reviewboard.org.file')
class FileDiffResource(GetPatchMixin, ItemResource):
    """The File Diff resource specific base class."""

    @request_method_decorator
    def get_diff_data(self, **kwargs):
        """Retrieves the actual raw diff data for the file."""
        return HttpRequest(self._url, query_args=kwargs, headers={
            'Accept': 'application/vnd.reviewboard.org.diff.data+json',
        })
