"""Resource definitions for diff validation.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from rbtools.api.decorators import request_method_decorator
from rbtools.api.resource.base import ItemResource, resource_mimetype
from rbtools.api.resource.mixins import DiffUploaderMixin


@resource_mimetype('application/vnd.reviewboard.org.diff-validation')
class ValidateDiffResource(DiffUploaderMixin, ItemResource):
    """The Validate Diff resource specific base class.

    Provides additional functionality to assist in the validation of diffs.
    """

    @request_method_decorator
    def validate_diff(self, repository, diff, parent_diff=None, base_dir=None,
                      base_commit_id=None, **kwargs):
        """Validate a diff."""
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
