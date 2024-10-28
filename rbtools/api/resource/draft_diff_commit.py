"""Resource definitions for draft diff commits.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)
from rbtools.api.resource.mixins import GetPatchMixin

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs


logger = logging.getLogger(__name__)


@resource_mimetype('application/vnd.reviewboard.org.draft-commit')
class DraftDiffCommitItemResource(GetPatchMixin, ItemResource):
    """Item resource for draft diff commits.

    Version Added:
        4.2
    """


@resource_mimetype('application/vnd.reviewboard.org.draft-commits')
class DraftDiffCommitListResource(ListResource):
    """List resource for draft diff commits."""

    @request_method_decorator
    def upload_commit(
        self,
        validation_info: str,
        diff: bytes,
        commit_id: str,
        parent_id: str,
        author_name: str,
        author_email: str,
        author_date: str,
        commit_message: str,
        committer_name: Optional[str] = None,
        committer_email: Optional[str] = None,
        committer_date: Optional[str] = None,
        parent_diff: Optional[bytes] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Upload a commit.

        Args:
            validation_info (str):
                The validation info, or ``None`` if this is the first commit in
                a series.

            diff (bytes):
                The diff contents.

            commit_id (str):
                The ID of the commit being uploaded.

            parent_id (str):
                The ID of the parent commit.

            author_name (str):
                The name of the author.

            author_email (str):
                The e-mail address of the author.

            author_date (str):
                The date and time the commit was authored in ISO 8601 format.

            commit_message (str):
                The commit message.

            committer_name (str, optional):
                The name of the committer (if applicable).

            committer_email (str, optional):
                The e-mail address of the committer (if applicable).

            committer_date (str, optional):
                The date and time the commit was committed in ISO 8601 format
                (if applicable).

            parent_diff (bytes, optional):
                The contents of the parent diff.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            DraftDiffCommitItemResource:
            The created resource.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred while uploading the commit.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)

        request.add_file('diff', 'diff', diff)
        request.add_field('commit_id', commit_id)
        request.add_field('parent_id', parent_id)
        request.add_field('commit_message', commit_message)
        request.add_field('author_name', author_name)
        request.add_field('author_email', author_email)
        request.add_field('author_date', author_date)

        if validation_info:
            request.add_field('validation_info', validation_info)

        if committer_name and committer_email and committer_date:
            request.add_field('committer_name', committer_name)
            request.add_field('committer_email', committer_email)
            request.add_field('committer_date', committer_date)
        elif committer_name or committer_email or committer_name:
            logger.warning(
                'Either all or none of committer_name, committer_email, and '
                'committer_date must be provided to upload_commit. None of '
                'these fields will be submitted.'
            )

        if parent_diff:
            request.add_file('parent_diff', 'parent_diff', parent_diff)

        return request
