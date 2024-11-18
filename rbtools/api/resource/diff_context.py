"""Resource definitions for the diff context resource.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetParams,
    ItemResource,
    resource_mimetype,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class DiffContextGetParams(BaseGetParams, total=False):
    """Params for the diff context GET operation.

    Version Added:
        6.0
    """

    #: The ID of the base commit to use.
    #:
    #: This only applies for review requests created with commit history.
    #: Only changes from after the specified commit will be included in the
    #: diff.
    base_commit_id: int

    #: A comma-separated list of filenames or patterns to include.
    #:
    #: The entries in this list can be case-sensitive filenames or shell-style
    #: globs.
    filenames: str

    #: A tip revision for showing interdiffs.
    #:
    #: If this is provided, the ``revision`` parameter will be the base diff.
    interdiff_revision: int

    #: The page number for paginated diffs.
    page: int

    #: Which revision of the diff to show.
    revision: int

    #: The ID of the tip commit to use.
    #:
    #: This only applies for review requests created with commit history.
    #: No changes from beyond this commit will be included in the diff.
    tip_commit_id: int


@resource_mimetype('application/vnd.reviewboard.org.diff-context')
class DiffContextResource(ItemResource):
    """Diff context resource.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[Mapping[str, str]] = {
        'base_commit_id': 'base-commit-id',
        'interdiff_revision': 'interdiff-revision',
        'tip_commit_id': 'tip-commit-id',
        **ItemResource._httprequest_params_name_map,
    }
