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
    DiffListResource,
    DiffResource,
)
from rbtools.api.resource.diff_commit import DiffCommitItemResource
from rbtools.api.resource.diff_file_attachment import (
    DiffFileAttachmentListResource,
)
from rbtools.api.resource.draft_diff_commit import DraftDiffCommitItemResource
from rbtools.api.resource.draft_file_attachment import (
    DraftFileAttachmentListResource,
)
from rbtools.api.resource.draft_screenshot import DraftScreenshotListResource
from rbtools.api.resource.file_attachment import FileAttachmentListResource
from rbtools.api.resource.file_diff import FileDiffResource
from rbtools.api.resource.mixins import (
    DiffUploaderMixin,
    GetPatchMixin,
)
from rbtools.api.resource.review_request import ReviewRequestResource
from rbtools.api.resource.root import RootResource
from rbtools.api.resource.screenshot import ScreenshotListResource
from rbtools.api.resource.validate_diff import ValidateDiffResource
from rbtools.api.resource.validate_diff_commit import (
    ValidateDiffCommitResource,
)


# Compatibility names for renamed resource subclasses.
DraftDiffResource = DiffResource


__all__ = [
    'CountResource',
    'DiffCommitItemResource',
    'DiffFileAttachmentListResource',
    'DiffListResource',
    'DiffResource',
    'DiffUploaderMixin',
    'DraftDiffCommitItemResource',
    'DraftDiffResource',
    'DraftFileAttachmentListResource',
    'DraftScreenshotListResource',
    'FileAttachmentListResource',
    'FileDiffResource',
    'GetPatchMixin',
    'ItemResource',
    'ListResource',
    'RESOURCE_MAP',
    'Resource',
    'ResourceDictField',
    'ResourceExtraDataField',
    'ResourceLinkField',
    'ResourceListField',
    'ReviewRequestResource',
    'RootResource',
    'ScreenshotListResource',
    'ValidateDiffCommitResource',
    'ValidateDiffResource',
    'resource_mimetype',
]
