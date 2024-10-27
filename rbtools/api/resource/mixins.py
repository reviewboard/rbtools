"""Mixins for API resources.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest


class DiffUploaderMixin:
    """A mixin for uploading diffs to a resource."""

    def prepare_upload_diff_request(self, diff, parent_diff=None,
                                    base_dir=None, base_commit_id=None,
                                    **kwargs):
        """Create a request that can be used to upload a diff.

        The diff and parent_diff arguments should be strings containing the
        diff output.
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

    @request_method_decorator
    def get_patch(self, **kwargs):
        """Retrieve the diff file contents.

        Args:
            **kwargs (dict):
                Query args to pass to
                :py:meth:`~rbtools.api.request.HttpRequest.__init__`.

        Returns:
            ItemResource:
            A resource payload whose :py:attr:`~ItemResource.data` attribute is
            the requested patch.
        """
        return HttpRequest(self._url, query_args=kwargs, headers={
            'Accept': 'text/x-patch',
        })
