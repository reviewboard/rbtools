"""Resource definitions for diffs.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from typing_extensions import Self

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    api_stub,
    request_method_returns,
    resource_mimetype,
)
from rbtools.api.resource.mixins import DiffUploaderMixin, GetPatchMixin

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.request import HttpRequest, QueryArgs
    from rbtools.api.resource.base import (
        BaseGetListParams,
        BaseGetParams,
        ResourceExtraDataField,
    )
    from rbtools.api.resource.diff_commit import DiffCommitListResource
    from rbtools.api.resource.draft_diff_commit import \
        DraftDiffCommitListResource
    from rbtools.api.resource.file_diff import FileDiffListResource
    from rbtools.api.resource.repository import RepositoryItemResource


@resource_mimetype('application/vnd.reviewboard.org.diff')
class DiffItemResource(GetPatchMixin, ItemResource):
    """Item resource for diffs.

    This corresponds to Review Board's :ref:`rb:webapi2.0-diff-resource`.

    Version Changed:
        6.0:
        Renamed from DiffResource.
    """

    ######################
    # Instance variables #
    ######################

    #: The ID/revision that this change is built upon.
    #:
    #: If using a parent diff, then this is the base for that diff. This may
    #: not be provided for all diffs or repository types, depending on how the
    #: diff was uploaded.
    base_commit_id: str

    #: The base directory that will be prepended to all paths in the diff.
    #:
    #: This is needed for some types of repositories. The directory must be
    #: between the root of the repository and the top directory referenced in
    #: the diff paths.
    basedir: str

    #: The number of commits present.
    #:
    #: This will only be set for review requests created with commit history.
    commit_count: str

    #: Extra data as part of the diff.
    extra_data: ResourceExtraDataField

    #: The numeric ID of the diff.
    id: int

    #: The name of the diff, usually the filename.
    name: str

    #: The revision of the diff.
    #:
    #: This starts at 1 for public diffs. Draft diffs may be 0.
    revision: int

    #: The date and time that the diff was uploaded, in ISO-8601 format.
    timestamp: str

    @request_method_returns[Self]()
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

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        if not isinstance(cumulative_diff, bytes):
            raise TypeError(
                f'cumulative_diff must be bytes, not {type(cumulative_diff)}')

        if parent_diff is not None and not isinstance(parent_diff, bytes):
            raise TypeError(
                f'parent_diff must be bytes, not {type(cumulative_diff)}')

        request = self._make_httprequest(url=self._links['self']['href'],
                                         method='PUT')

        request.add_field('finalize_commit_series', '1')
        request.add_file('cumulative_diff', 'cumulative_diff',
                         cumulative_diff)
        request.add_field('validation_info', validation_info)

        if parent_diff is not None:
            request.add_file('parent_diff', 'parent_diff', parent_diff)

        return request

    @api_stub
    def get_commits(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> DiffCommitListResource:
        """Get the commits for the diff.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommitListResource:
            The diff commit list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_draft_commits(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> DraftDiffCommitListResource:
        """Get the commits for the diff when the diff is a draft.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DraftDiffCommitListResource:
            The diff commit list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_draft_files(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileDiffListResource:
        """Get the files for the diff when the diff is a draft.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffListResource:
            The diff commit list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_files(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileDiffListResource:
        """Get the files for the diff.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffListResource:
            The file diff list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repository(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> RepositoryItemResource:
        """Get the repository for this diff.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryItemResource:
            The repository item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


@resource_mimetype('application/vnd.reviewboard.org.diffs')
class DiffListResource(DiffUploaderMixin, ListResource[DiffItemResource]):
    """List resource for diffs.

    This corresponds to Review Board's :ref:`rb:webapi2.0-diff-list-resource`.
    """

    @request_method_returns[DiffItemResource]()
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

    @request_method_returns[DiffItemResource]()
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
        request = self._make_httprequest(url=self._url, method='POST',
                                         query_args=kwargs)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request
