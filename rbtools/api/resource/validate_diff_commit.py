"""Resource definitions for diff commit validation.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import (
    ItemResource,
    request_method,
    resource_mimetype,
)

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs


@resource_mimetype('application/vnd.reviewboard.org.commit-validation')
class ValidateDiffCommitResource(ItemResource):
    """Singleton resource for commit validation."""

    @request_method
    def validate_commit(
        self,
        repository: str,
        diff: bytes,
        commit_id: str,
        parent_id: str,
        parent_diff: Optional[bytes] = None,
        base_commit_id: Optional[str] = None,
        validation_info: Optional[str] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Validate the diff for a commit.

        Args:
            repository (str):
                The name of the repository.

            diff (bytes):
                The contents of the diff to validate.

            commit_id (str):
                The ID of the commit being validated.

            parent_id (str):
                The ID of the parent commit.

            parent_diff (bytes, optional):
                The contents of the parent diff.

            base_commit_id (str, optional):
                The base commit ID.

            validation_info (str, optional):
                Validation information from a previous call to this resource.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            ValidateDiffCommitResource:
            The validation result.
        """
        assert self._url is not None

        request = HttpRequest(self._url, method='POST', query_args=kwargs)
        request.add_file('diff', 'diff', diff)
        request.add_field('repository', repository)
        request.add_field('commit_id', commit_id)
        request.add_field('parent_id', parent_id)

        if parent_diff:
            request.add_file('parent_diff', 'parent_diff', parent_diff)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        if validation_info:
            request.add_field('validation_info', validation_info)

        return request
