"""Resource definitions for diff commit validation.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import ItemResource, resource_mimetype


@resource_mimetype('application/vnd.reviewboard.org.commit-validation')
class ValidateDiffCommitResource(ItemResource):
    """The commit validation resource specific base class."""

    @request_method_decorator
    def validate_commit(self, repository, diff, commit_id, parent_id,
                        parent_diff=None, base_commit_id=None,
                        validation_info=None, **kwargs):
        """Validate the diff for a commit.

        Args:
            repository (unicode):
                The name of the repository.

            diff (bytes):
                The contents of the diff to validate.

            commit_id (unicode):
                The ID of the commit being validated.

            parent_id (unicode):
                The ID of the parent commit.

            parent_diff (bytes, optional):
                The contents of the parent diff.

            base_commit_id (unicode, optional):
                The base commit ID.

            validation_info (unicode, optional):
                Validation information from a previous call to this resource.

            **kwargs (dict):
                Keyword arguments used to build the querystring.

        Returns:
            ValidateDiffCommitResource:
            The validation result.
        """
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
