"""Resource definitions for the RBTools Python API."""

from __future__ import annotations

from rbtools.api.resource.base import (
    CountResource,
    ItemResource,
    ListResource,
    RESOURCE_MAP,
    Resource,
    ResourceDictField,
    ResourceExtraDataField,
    ResourceLinkField,
    ResourceListField,
    resource_mimetype,
)
from rbtools.api.resource.diff import (
    DiffItemResource,
    DiffListResource,
)
from rbtools.api.resource.diff_commit import (
    DiffCommitItemResource,
    DiffCommitListResource,
)
from rbtools.api.resource.diff_file_attachment import (
    DiffFileAttachmentItemResource,
    DiffFileAttachmentListResource,
)
from rbtools.api.resource.draft_diff_commit import (
    DraftDiffCommitItemResource,
    DraftDiffCommitListResource,
)
from rbtools.api.resource.draft_file_attachment import (
    DraftFileAttachmentItemResource,
    DraftFileAttachmentListResource,
)
from rbtools.api.resource.draft_screenshot import (
    DraftScreenshotItemResource,
    DraftScreenshotListResource,
)
from rbtools.api.resource.file_attachment import (
    FileAttachmentItemResource,
    FileAttachmentListResource,
)
from rbtools.api.resource.file_diff import (
    FileDiffItemResource,
    FileDiffListResource,
)
from rbtools.api.resource.mixins import (
    DiffUploaderMixin,
    GetPatchMixin,
)
from rbtools.api.resource.review_request import (
    ReviewRequestItemResource,
    ReviewRequestListResource,
)
from rbtools.api.resource.root import RootResource
from rbtools.api.resource.screenshot import (
    ScreenshotItemResource,
    ScreenshotListResource,
)
from rbtools.api.resource.validate_diff import ValidateDiffResource
from rbtools.api.resource.validate_diff_commit import (
    ValidateDiffCommitResource,
)


# Compatibility names for renamed resource subclasses.
DiffResource = DiffItemResource
DraftDiffResource = DiffItemResource
FileDiffResource = FileDiffItemResource
ReviewRequestResource = ReviewRequestItemResource


__all__ = [
    'CountResource',
    'DiffCommitItemResource',
    'DiffCommitListResource',
    'DiffFileAttachmentListResource',
    'DiffItemResource',
    'DiffListResource',
    'DiffResource',
    'DiffUploaderMixin',
    'DraftDiffCommitItemResource',
    'DraftDiffCommitListResource',
    'DraftDiffResource',
    'DiffFileAttachmentItemResource',
    'DraftFileAttachmentItemResource',
    'DraftFileAttachmentListResource',
    'DraftScreenshotItemResource',
    'DraftScreenshotListResource',
    'FileAttachmentItemResource',
    'FileAttachmentListResource',
    'FileDiffItemResource',
    'FileDiffResource',
    'FileDiffListResource',
    'GetPatchMixin',
    'ItemResource',
    'ListResource',
    'RESOURCE_MAP',
    'Resource',
    'ResourceDictField',
    'ResourceExtraDataField',
    'ResourceLinkField',
    'ResourceListField',
    'ReviewRequestItemResource',
    'ReviewRequestResource',
    'ReviewRequestListResource',
    'RootResource',
    'ScreenshotItemResource',
    'ScreenshotListResource',
    'ValidateDiffCommitResource',
    'ValidateDiffResource',
    'resource_mimetype',
]
