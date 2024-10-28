"""Resource definitions for review requests.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Optional, TYPE_CHECKING
from urllib.parse import urljoin

from typing_extensions import Self

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    request_method,
    resource_mimetype,
)
from rbtools.utils.graphs import path_exists

if TYPE_CHECKING:
    from rbtools.api.request import HttpRequest, QueryArgs


@resource_mimetype('application/vnd.reviewboard.org.review-request')
class ReviewRequestResource(ItemResource):
    """Item resource for review requests."""

    @property
    def absolute_url(self) -> str:
        """The absolute URL for the Review Request.

        The value of absolute_url is returned if it's defined. Otherwise the
        absolute URL is generated and returned.

        Type:
            str
        """
        if 'absolute_url' in self._fields:
            return self._fields['absolute_url']
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
        return self._fields.get('url', f'/r/{self.id}/')

    @request_method
    def submit(
        self,
        description: Optional[str] = None,
        changenum: Optional[str] = None,
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

    @request_method
    def get_or_create_draft(
        self,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Retrieve or create a draft.

        Args:
            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ItemResource:
            The review request draft.
        """
        request = self.get_draft(internal=True)
        request.method = 'POST'

        for name, value in kwargs.items():
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


@resource_mimetype('application/vnd.reviewboard.org.review-requests')
class ReviewRequestListResource(ListResource):
    """List resource for review requests.

    Version Added:
        6.0
    """
