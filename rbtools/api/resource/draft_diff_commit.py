"""Resource definitions for draft diff commits.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

import logging

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)
from rbtools.api.resource.mixins import GetPatchMixin


logger = logging.getLogger(__name__)


@resource_mimetype('application/vnd.reviewboard.org.draft-commit')
class DraftDiffCommitItemResource(GetPatchMixin, ItemResource):
    """The draft commit resource-specific class.

    Version Added:
        4.2
    """


@resource_mimetype('application/vnd.reviewboard.org.draft-commits')
class DraftDiffCommitListResource(ListResource):
    """The draft commit list resource-specific class.

    Provides additional functionality in the uploading of new commits.
    """

    @request_method_decorator
    def upload_commit(self, validation_info, diff, commit_id, parent_id,
                      author_name, author_email, author_date, commit_message,
                      committer_name=None, committer_email=None,
                      committer_date=None, parent_diff=None, **kwargs):
        """Upload a commit.

        Args:
            validation_info (unicode):
                The validation info, or ``None`` if this is the first commit in
                a series.

            diff (bytes):
                The diff contents.

            commit_id (unicode):
                The ID of the commit being uploaded.

            parent_id (unicode):
                The ID of the parent commit.

            author_name (unicode):
                The name of the author.

            author_email (unicode):
                The e-mail address of the author.

            author_date (unicode):
                The date and time the commit was authored in ISO 8601 format.

            committer_name (unicode, optional):
                The name of the committer (if applicable).

            committer_email (unicode, optional):
                The e-mail address of the committer (if applicable).

            committer_date (unicode, optional):
                The date and time the commit was committed in ISO 8601 format
                (if applicable).

            parent_diff (bytes, optional):
                The contents of the parent diff.

            **kwargs (dict):
                Keyword argument used to build the querystring for the request
                URL.

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
