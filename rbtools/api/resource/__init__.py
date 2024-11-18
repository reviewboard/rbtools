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
from rbtools.api.resource.change import ChangeItemResource, ChangeListResource
from rbtools.api.resource.default_reviewer import (
    DefaultReviewerItemResource,
    DefaultReviewerListResource,
)
from rbtools.api.resource.diff import (
    DiffItemResource,
    DiffListResource,
)
from rbtools.api.resource.diff_context import DiffContextResource
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
from rbtools.api.resource.extension import (
    ExtensionItemResource,
    ExtensionListResource,
)
from rbtools.api.resource.file_attachment import (
    FileAttachmentItemResource,
    FileAttachmentListResource,
)
from rbtools.api.resource.file_diff import (
    FileDiffItemResource,
    FileDiffListResource,
)
from rbtools.api.resource.last_update import LastUpdateResource
from rbtools.api.resource.mixins import (
    DiffUploaderMixin,
    GetPatchMixin,
)
from rbtools.api.resource.review_group import (
    ReviewGroupItemResource,
    ReviewGroupListResource,
)
from rbtools.api.resource.review_group_user import (
    ReviewGroupUserItemResource,
    ReviewGroupUserListResource,
)
from rbtools.api.resource.review_request import (
    ReviewRequestItemResource,
    ReviewRequestListResource,
)
from rbtools.api.resource.review_request_draft import (
    ReviewRequestDraftResource,
)
from rbtools.api.resource.root import RootResource
from rbtools.api.resource.screenshot import (
    ScreenshotItemResource,
    ScreenshotListResource,
)
from rbtools.api.resource.status_update import (
    StatusUpdateItemResource,
    StatusUpdateListResource,
)
from rbtools.api.resource.user import UserItemResource, UserListResource
from rbtools.api.resource.user_file_attachment import (
    UserFileAttachmentItemResource,
    UserFileAttachmentListResource,
)
from rbtools.api.resource.validate_diff import ValidateDiffResource
from rbtools.api.resource.validate_diff_commit import (
    ValidateDiffCommitResource,
)
from rbtools.api.resource.validation import ValidationResource


# Compatibility names for renamed resource subclasses.
DiffResource = DiffItemResource
DraftDiffResource = DiffItemResource
FileDiffResource = FileDiffItemResource
ReviewRequestResource = ReviewRequestItemResource


__all__ = [
    'ChangeItemResource',
    'ChangeListResource',
    'CountResource',
    'DefaultReviewerItemResource',
    'DefaultReviewerListResource',
    'DiffCommitItemResource',
    'DiffCommitListResource',
    'DiffContextResource',
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
    'ExtensionItemResource',
    'ExtensionListResource',
    'FileAttachmentItemResource',
    'FileAttachmentListResource',
    'FileDiffItemResource',
    'FileDiffResource',
    'FileDiffListResource',
    'GetPatchMixin',
    'ItemResource',
    'LastUpdateResource',
    'ListResource',
    'RESOURCE_MAP',
    'Resource',
    'ResourceDictField',
    'ResourceExtraDataField',
    'ResourceLinkField',
    'ResourceListField',
    'ReviewGroupItemResource',
    'ReviewGroupListResource',
    'ReviewGroupUserItemResource',
    'ReviewGroupUserListResource',
    'ReviewRequestItemResource',
    'ReviewRequestResource',
    'ReviewRequestDraftResource',
    'ReviewRequestListResource',
    'RootResource',
    'ScreenshotItemResource',
    'ScreenshotListResource',
    'StatusUpdateItemResource',
    'StatusUpdateListResource',
    'UserFileAttachmentItemResource',
    'UserFileAttachmentListResource',
    'UserItemResource',
    'UserListResource',
    'ValidateDiffCommitResource',
    'ValidateDiffResource',
    'ValidationResource',
    'resource_mimetype',
]
