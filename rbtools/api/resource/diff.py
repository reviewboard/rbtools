"""Resource definitions for diffs.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    request_method,
    resource_mimetype,
)
from rbtools.api.resource.mixins import DiffUploaderMixin, GetPatchMixin

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs


@resource_mimetype('application/vnd.reviewboard.org.diff')
class DiffResource(GetPatchMixin, ItemResource):
    """Item resource for diffs."""

    @request_method
    def finalize_commit_series(
        self,
        cumulative_diff: bytes,
        validation_info: str,
        parent_diff: Optional[bytes] = None,
    ) -> HttpRequest:
        """Finalize a commit series.

        Args:
            cumulative_diff (bytes):
                The cumulative diff of the entire commit series.

            validation_info (str):
                The validation information returned by validating the last
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
            raise TypeError(
                f'cumulative_diff must be bytes, not {type(cumulative_diff)}')

        if parent_diff is not None and not isinstance(parent_diff, bytes):
            raise TypeError(
                f'parent_diff must be bytes, not {type(cumulative_diff)}')

        request = HttpRequest(self._links['self']['href'],
                              method='PUT')

        request.add_field('finalize_commit_series', '1')
        request.add_file('cumulative_diff', 'cumulative_diff',
                         cumulative_diff)
        request.add_field('validation_info', validation_info)

        if parent_diff is not None:
            request.add_file('parent_diff', 'parent_diff', parent_diff)

        return request


@resource_mimetype('application/vnd.reviewboard.org.diffs')
class DiffListResource(DiffUploaderMixin, ListResource):
    """List resource for diffs."""

    @request_method
    def upload_diff(
        self,
        diff: bytes,
        parent_diff: Optional[bytes] = None,
        base_dir: Optional[str] = None,
        base_commit_id: Optional[str] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Upload a diff to the resource.

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
            DiffItemResource:
            The newly-created diff.
        """
        return self.prepare_upload_diff_request(
            diff,
            parent_diff=parent_diff,
            base_dir=base_dir,
            base_commit_id=base_commit_id,
            **kwargs)

    @request_method
    def create_empty(
        self,
        base_commit_id: Optional[str] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Create an empty DiffSet that commits can be added to.

        Args:
            base_commit_id (str, optional):
                The base commit ID of the diff.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            DiffItemResource:
            The newly-created diff.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request
