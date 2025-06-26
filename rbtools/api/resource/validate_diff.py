"""Resource definitions for diff validation.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    request_method,
    resource_mimetype,
)
from rbtools.api.resource.mixins import DiffUploaderMixin

if TYPE_CHECKING:
    from rbtools.api.request import HttpRequest, QueryArgs


@resource_mimetype('application/vnd.reviewboard.org.diff-validation')
class ValidateDiffResource(DiffUploaderMixin, ItemResource):
    """Singleton resource for diff validation.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-validate-diff-resource`.
    """

    @request_method
    def validate_diff(
        self,
        repository: str,
        diff: bytes,
        parent_diff: Optional[bytes] = None,
        base_dir: Optional[str] = None,
        base_commit_id: Optional[str] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Validate a diff.

        Args:
            repository (str):
                The repository name.

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
            ValidateDiffResource:
            The validation response.
        """
        request = self.prepare_upload_diff_request(
            diff,
            parent_diff=parent_diff,
            base_dir=base_dir,
            base_commit_id=base_commit_id,
            **kwargs)

        request.add_field('repository', repository)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request
