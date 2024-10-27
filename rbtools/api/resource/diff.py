"""Resource definitions for diffs.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)
from rbtools.api.resource.mixins import DiffUploaderMixin, GetPatchMixin


@resource_mimetype('application/vnd.reviewboard.org.diff')
class DiffResource(GetPatchMixin, ItemResource):
    """The Diff resource specific base class.

    Provides the 'get_patch' method for retrieving the content of the
    actual diff file itself.
    """

    @request_method_decorator
    def finalize_commit_series(self, cumulative_diff, validation_info,
                               parent_diff=None):
        """Finalize a commit series.

        Args:
            cumulative_diff (bytes):
                The cumulative diff of the entire commit series.

            validation_info (unicode):
                The validation information returned by validatin the last
                commit in the series with the
                :py:class:`ValidateDiffCommitResource`.

            parent_diff (bytes, optional):
                An optional parent diff.

                This will be the same parent diff uploaded with each commit.

        Returns:
            DiffItemResource:
            The finalized diff resource.
        """
        if not isinstance(cumulative_diff, bytes):
            raise TypeError('cumulative_diff must be byte string, not %s'
                            % type(cumulative_diff))

        if parent_diff is not None and not isinstance(parent_diff, bytes):
            raise TypeError('parent_diff must be byte string, not %s'
                            % type(cumulative_diff))

        request = HttpRequest(self.links['self']['href'],
                              method='PUT')

        request.add_field('finalize_commit_series', True)
        request.add_file('cumulative_diff', 'cumulative_diff',
                         cumulative_diff)
        request.add_field('validation_info', validation_info)

        if parent_diff is not None:
            request.add_file('parent_diff', 'parent_diff', parent_diff)

        return request


@resource_mimetype('application/vnd.reviewboard.org.diffs')
class DiffListResource(DiffUploaderMixin, ListResource):
    """The Diff List resource specific base class.

    This resource provides functionality to assist in the uploading of new
    diffs.
    """

    @request_method_decorator
    def upload_diff(self, diff, parent_diff=None, base_dir=None,
                    base_commit_id=None, **kwargs):
        """Upload a diff to the resource.

        The diff and parent_diff arguments should be strings containing the
        diff output.
        """
        return self.prepare_upload_diff_request(
            diff,
            parent_diff=parent_diff,
            base_dir=base_dir,
            base_commit_id=base_commit_id,
            **kwargs)

    @request_method_decorator
    def create_empty(self, base_commit_id=None, **kwargs):
        """Create an empty DiffSet that commits can be added to.

        Args:
            base_commit_id (unicode, optional):
                The base commit ID of the diff.

            **kwargs (dict):
                Keyword arguments to encode into the querystring of the request
                URL.
        Returns:
            DiffItemResource:
            The created resource.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request
