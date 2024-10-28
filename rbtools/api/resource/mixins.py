"""Mixins for API resources.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import request_method

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs


class DiffUploaderMixin:
    """A mixin for uploading diffs to a resource."""

    _url: str

    def prepare_upload_diff_request(
        self,
        diff: bytes,
        parent_diff: Optional[bytes] = None,
        base_dir: Optional[str] = None,
        base_commit_id: Optional[str] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Create a request that can be used to upload a diff.

        The diff and parent_diff arguments should be strings containing the
        diff output.

        Args:
            diff (bytes):
                The diff content.

            parent_diff (bytes, optional):
                The parent diff content, if present.

            base_dir (str, optional):
                The base directory for the diff, if present.

            base_commit_id (str, optional):
                The ID of the commit that the diff is against, if present.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.request.HttpRequest:
            The API request.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)
        request.add_file('path', 'diff', diff)

        if parent_diff:
            request.add_file('parent_diff_path', 'parent_diff', parent_diff)

        if base_dir:
            request.add_field('basedir', base_dir)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request


class GetPatchMixin:
    """Mixin for resources that implement a get_patch method.

    Version Added:
        4.2
    """

    _url: str

    @request_method
    def get_patch(
        self,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Retrieve the diff file contents.

        Args:
            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ItemResource:
            A resource containing the patch. The patch data will be in the
            ``data`` attribute.
        """
        return HttpRequest(self._url, query_args=kwargs, headers={
            'Accept': 'text/x-patch',
        })
