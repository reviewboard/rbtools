"""Resource definitions for review requests.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING, cast, overload
from urllib.parse import urljoin

from typing_extensions import Self

from rbtools.api.resource.base import (
    BaseGetListParams,
    BaseGetParams,
    ListResource,
    api_stub,
    request_method_returns,
    resource_mimetype,
)
from rbtools.api.resource.base_review_request import \
    BaseReviewRequestItemResource
from rbtools.api.resource.review_request_draft import \
    ReviewRequestDraftResource
from rbtools.utils.graphs import path_exists

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import ClassVar, Literal

    from typing_extensions import Unpack

    from rbtools.api.request import HttpRequest
    from rbtools.api.resource.base import (
        ResourceLinkField,
        ResourceListField,
        TextType,
    )
    from rbtools.api.resource.change import ChangeListResource
    from rbtools.api.resource.diff import DiffItemResource, DiffListResource
    from rbtools.api.resource.diff_context import (
        DiffContextGetParams,
        DiffContextResource,
    )
    from rbtools.api.resource.file_attachment import FileAttachmentListResource
    from rbtools.api.resource.last_update import LastUpdateResource
    from rbtools.api.resource.repository import RepositoryItemResource
    from rbtools.api.resource.review import ReviewListResource
    from rbtools.api.resource.screenshot import ScreenshotListResource
    from rbtools.api.resource.status_update import (
        StatusUpdateGetListParams,
        StatusUpdateListResource,
    )


@resource_mimetype('application/vnd.reviewboard.org.review-request')
class ReviewRequestItemResource(BaseReviewRequestItemResource):
    """Item resource for review requests.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-request-resource`.

    Version Changed:
        6.0:
        Renamed from ReviewRequestResource.
    """

    ######################
    # Instance variables #
    ######################

    #: The reason why the review request was not approved.
    approval_failure: str | None

    #: Whether the review request has been approved by reviewers.
    #:
    #: On a default install, a review request is approved if it has at least
    #: one Ship It! and no open issues. Extensions may change these
    #: requirements.
    approved: bool

    #: The list of review requests that this review request is blocking.
    blocks: ResourceListField[ReviewRequestItemResource]

    #: The change number that the review request represents.
    #:
    #: These are server-side repository-specific change numbers, and are not
    #: supported by all types of repositories. This is deprecated in favor of
    #: the ``commit_id`` field.
    changenum: int | None

    #: The text describing the closing of the review request.
    close_description: str

    #: The current or forced text type for the ``close_description`` field.
    close_description_text_type: TextType

    #: Whether or not the review request was created with history support.
    #:
    #: A value of ``True`` indicates that the review request will have commits
    #: attached.
    created_with_history: bool

    #: The numeric ID of the review request.
    id: int

    #: The number of dropped issues on this review request.
    issue_dropped_count: int

    #: The number of open issues on this review request.
    issue_open_count: int

    #: The number of resolved issues on this review request.
    issue_resolved_count: int

    #: The number of issues waiting for verification to resolve or drop.
    issue_verifying_count: int

    #: The most recent diff.
    latest_diff: ResourceLinkField[DiffItemResource] | None

    #: Whether or not the review request is currently visible to other users.
    public: bool

    #: The number of Ship It-s given to this review request.
    ship_it_count: int

    #: The current status of the review request.
    status: Literal['discarded', 'pending', 'submitted']

    #: The date and time that the review request was added.
    time_added: str

    @property
    def absolute_url(self) -> str:
        """The absolute URL for the Review Request.

        The value of absolute_url is returned if it's defined. Otherwise the
        absolute URL is generated and returned.

        Type:
            str
        """
        if 'absolute_url' in self._fields:
            return cast(str, self._fields['absolute_url'])
        else:
            assert self._url is not None

            base_url = self._url.split('/api/')[0]
            return urljoin(base_url, self.url)

    @property
    def url(self) -> str:
        """The relative URL to the Review Request.

        The value of 'url' is returned if it's defined. Otherwise, a relative
        URL is generated and returned.

        This provides compatibility with versions of Review Board older
        than 1.7.8, which do not have a 'url' field.

        Type:
            str
        """
        return cast(str, self._fields.get('url', f'/r/{self.id}/'))

    @request_method_returns[Self]()
    def submit(
        self,
        description: (str | None) = None,
        changenum: (str | None) = None,
    ) -> HttpRequest:
        """Submit a review request.

        Args:
            description (str, optional):
                The close description text to include.

            changenum (str, optional):
                The change number (commit ID) for the review request now that
                the code has been submitted.

        Returns:
            ReviewRequestResource:
            The updated review request.
        """
        data = {
            'status': 'submitted',
        }

        if description:
            data['description'] = description

        if changenum:
            data['changenum'] = changenum

        return self.update(data=data, internal=True)

    @request_method_returns[ReviewRequestDraftResource]()
    def get_or_create_draft(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> HttpRequest:
        """Retrieve or create a draft.

        Args:
            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewRequestDraftResource:
            The review request draft.
        """
        request = self.get_draft(internal=True)
        request.method = 'POST'

        for name, value in kwargs.items():
            if not isinstance(value, (str, bytes)):
                value = str(value)

            request.add_field(name, value)

        return request

    def build_dependency_graph(
        self,
    ) -> defaultdict[Self, set[Self]]:
        """Build the dependency graph for the review request.

        Only review requests in the same repository as this one will be in the
        graph.

        A ValueError is raised if the graph would contain cycles.
        """
        def get_url(resource: Self) -> str:
            """Get the URL of the resource."""
            if hasattr(resource, 'href'):
                return resource.href
            else:
                return resource.absolute_url

        # Even with the API cache, we don't want to be making more requests
        # than necessary. The review request resource will be cached by an
        # ETag, so there will still be a round trip if we don't cache them
        # here.
        review_requests_by_url = {}
        review_requests_by_url[self.absolute_url] = self

        def get_review_request_resource(
            resource: Self,
        ) -> Self:
            url = get_url(resource)

            if url not in review_requests_by_url:
                review_requests_by_url[url] = resource.get(expand='repository')

            return review_requests_by_url[url]

        repository = self.get_repository()

        graph = defaultdict(set)

        visited = set()

        unvisited = deque()
        unvisited.append(self)

        while unvisited:
            head = unvisited.popleft()

            if head in visited:
                continue

            visited.add(get_url(head))

            for tail in head.depends_on:
                tail = get_review_request_resource(tail)

                if path_exists(graph, tail.id, head.id):
                    raise ValueError('Circular dependencies.')

                # We don't want to include review requests for other
                # repositories, so we'll stop if we reach one. We also don't
                # want to re-land submitted review requests.
                if (repository.id == tail.repository.id and
                    tail.status != 'submitted'):
                    graph[head].add(tail)
                    unvisited.append(tail)

        graph.default_factory = None

        return graph

    @api_stub
    def get_changes(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ChangeListResource:
        """Get the change descriptions for the review request.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ChangeListResource:
            The change description list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_context(
        self,
        **kwargs: Unpack[DiffContextGetParams],
    ) -> DiffContextResource:
        """Get the diff context resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffContextResource:
            The diff context resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diffs(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> DiffListResource:
        """Get the diff list for the review request.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffListResource:
            The diff list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @overload
    def get_draft(
        self,
        internal: Literal[False] = False,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewRequestDraftResource:
        ...

    @overload
    def get_draft(
        self,
        internal: Literal[True],
        **kwargs: Unpack[BaseGetParams],
    ) -> HttpRequest:
        ...

    @api_stub
    def get_draft(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> HttpRequest | ReviewRequestDraftResource:
        """Get the review request draft.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewRequestDraftResource:
            The draft resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_attachments(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileAttachmentListResource:
        """Get the file attachment list for the review request.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentListResource:
            The file attachment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_last_update(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> LastUpdateResource:
        """Get the last update resource for a review request.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.LastUpdateResource:
            The last update resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_latest_diff(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> DiffItemResource:
        """Get the most recent diff list for the review request.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffItemResource:
            The diff item resource.

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
        """Get the repository for this review request.

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

    @api_stub
    def get_reviews(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ReviewListResource:
        """Get the reviews for this review request.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewListResource:
            The review list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_screenshots(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ScreenshotListResource:
        """Get the screenshot list for the review request.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotListResource:
            The screenshot list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_status_updates(
        self,
        **kwargs: Unpack[StatusUpdateGetListParams],
    ) -> StatusUpdateListResource:
        """Get the status updates for the review request.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.StatusUpdateListResource:
            The status update list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


class ReviewRequestGetListParams(BaseGetListParams, total=False):
    """Params for the review request list GET operation.

    Version Added:
        6.0
    """

    #: The branch field on a review request to filter by.
    branch: str

    #: The change number the review requests must have set.
    #:
    #: This will only return one review request per repository, and only works
    #: for repository types that support server-side changesets. This is
    #: deprecated in favor of the ``commit_id`` parameter.
    changenum: int

    #: The commit that review requests must have set.
    #:
    #: This will only return one review request per repository.
    commit_id: str

    #: The username that the review requests must be owned by.
    from_user: str

    #: Return results with exactly the provided number of dropped issues.
    issue_dropped_count: int

    #: Return results with more than the provided number of dropped issues.
    issue_dropped_count_gt: int

    #: Return results with at least the provided number of dropped issues.
    issue_dropped_count_gte: int

    #: Return results with less than the provided number of dropped issues.
    issue_dropped_count_lt: int

    #: Return results with at most than the provided number of dropped issues.
    issue_dropped_count_lte: int

    #: Return results with exactly the provided number of open issues.
    issue_open_count: int

    #: Return results with more than the provided number of open issues.
    issue_open_count_gt: int

    #: Return results with at least the provided number of open issues.
    issue_open_count_gte: int

    #: Return results with less than the provided number of open issues.
    issue_open_count_lt: int

    #: Return results with at most than the provided number of open issues.
    issue_open_count_lte: int

    #: Return results with exactly the provided number of resolved issues.
    issue_resolved_count: int

    #: Return results with more than the provided number of resolved issues.
    issue_resolved_count_gt: int

    #: Return results with at least the provided number of resolved issues.
    issue_resolved_count_gte: int

    #: Return results with less than the provided number of resolved issues.
    issue_resolved_count_lt: int

    #: Return results with at most than the provided number of resolved issues.
    issue_resolved_count_lte: int

    #: The earliest date-time the review requests are last updated.
    #:
    #: This is compared against the review request's ``last_updated`` field. It
    #: should be sent in ISO-8601 format.
    last_updated_from: str

    #: The latest date-time the review requests are last updated.
    #:
    #: This is compared against the review request's ``last_updated`` field. It
    #: should be sent in ISO-8601 format.
    last_updated_to: str

    #: The ID of the repository that review requests must be on.
    repository: int

    #: Return review requests with at least one Ship It!.
    #:
    #: This is deprecated in favor of the more specific ship-it count
    #: parameters.
    ship_it: bool

    #: Return results with exactly the provided number of ship-its.
    ship_it_count: int

    #: Return results with more than the provided number of ship-its.
    ship_it_count_gt: int

    #: Return results with at least the provided number of ship-its.
    ship_it_count_gte: int

    #: Return results with less than the provided number of ship-its.
    ship_it_count_lt: int

    #: Return results with at most the provided number of ship-its.
    ship_it_count_lte: int

    #: Return all unpublished review requests.
    #:
    #: If the requesting user is an admin or hase the
    #: ``reviews.can_submit_as_another_user`` permission, unpublished review
    #: requests will also be returned.
    show_all_unpublished: bool

    #: The status of review requests to filter.
    status: Literal['all', 'discarded', 'pending', 'submitted']

    #: The earliest date-time the review requests are added.
    #:
    #: This is compared against the review request's ``time_added`` field. It
    #: should be sent in ISO-8601 format.
    time_added_from: str

    #: The latest date-time the review requests are added.
    #:
    #: This is compared against the review request's ``time_added`` field. It
    #: should be sent in ISO-8601 format.
    time_added_to: str

    #: A comma-separated list of review group names to filter by.
    to_groups: str

    #: A comma-separated list of usernames who are in assigned groups.
    to_user_groups: str

    #: A comma-separated list of usernames who are assigned.
    #:
    #: These users must be in the user list either directly or as a group
    #: member.
    to_users: str

    #: A comma-separated list of usernames who are directly assigned.
    to_users_directly: str


@resource_mimetype('application/vnd.reviewboard.org.review-requests')
class ReviewRequestListResource(ListResource[ReviewRequestItemResource]):
    """List resource for review requests.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-review-request-list-resource`.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[Mapping[str, str]] = {
        'commit_id': 'commit-id',
        'from_user': 'from-user',
        'issue_dropped_count': 'issue-dropped-count',
        'issue_dropped_count_gt': 'issue-dropped-count-gt',
        'issue_dropped_count_gte': 'issue-dropped-count-gte',
        'issue_dropped_count_lt': 'issue-dropped-count-lt',
        'issue_dropped_count_lte': 'issue-dropped-count-lte',
        'issue_open_count': 'issue-open-count',
        'issue_open_count_gt': 'issue-open-count-gt',
        'issue_open_count_gte': 'issue-open-count-gte',
        'issue_open_count_lt': 'issue-open-count-lt',
        'issue_open_count_lte': 'issue-open-count-lte',
        'issue_resolved_count': 'issue-resolved-count',
        'issue_resolved_count_gt': 'issue-resolved-count-gt',
        'issue_resolved_count_gte': 'issue-resolved-count-gte',
        'issue_resolved_count_lt': 'issue-resolved-count-lt',
        'issue_resolved_count_lte': 'issue-resolved-count-lte',
        'last_updated_from': 'last-updated-from',
        'last_updated_to': 'last-updated-to',
        'ship_it': 'ship-it',
        'ship_it_count': 'ship-it-count',
        'ship_it_count_gt': 'ship-it-count-gt',
        'ship_it_count_gte': 'ship-it-count-gte',
        'ship_it_count_lt': 'ship-it-count-lt',
        'ship_it_count_lte': 'ship-it-count-lte',
        'show_all_unpublished': 'show-all-unpublished',
        'time_added_from': 'time-added-from',
        'time_added_to': 'time-added-to',
        'to_groups': 'to-groups',
        'to_user_groups': 'to-user-groups',
        'to_users': 'to-users',
        'to_users_directly': 'to-users-directly',
        **ListResource._httprequest_params_name_map,
    }
