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
from rbtools.api.resource.diff_comment import (
    DiffCommentItemResource,
    DiffCommentListResource,
)
from rbtools.api.resource.diff_commit import (
    DiffCommitItemResource,
    DiffCommitListResource,
)
from rbtools.api.resource.diff_context import DiffContextResource
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
from rbtools.api.resource.file_attachment_comment import (
    FileAttachmentCommentItemResource,
    FileAttachmentCommentListResource,
)
from rbtools.api.resource.file_diff import (
    FileDiffItemResource,
    FileDiffListResource,
)
from rbtools.api.resource.general_comment import (
    GeneralCommentItemResource,
    GeneralCommentListResource,
)
from rbtools.api.resource.last_update import LastUpdateResource
from rbtools.api.resource.mixins import (
    DiffUploaderMixin,
    GetPatchMixin,
)
from rbtools.api.resource.repository import (
    RepositoryItemResource,
    RepositoryListResource,
)
from rbtools.api.resource.repository_branch import (
    RepositoryBranchListResource,
)
from rbtools.api.resource.repository_commit import (
    RepositoryCommitListResource,
)
from rbtools.api.resource.repository_info import RepositoryInfoResource
from rbtools.api.resource.repository_group import (
    RepositoryGroupItemResource,
    RepositoryGroupListResource,
)
from .repository_user import (
    RepositoryUserItemResource,
    RepositoryUserListResource,
)
from rbtools.api.resource.review import ReviewItemResource, ReviewListResource
from rbtools.api.resource.review_group import (
    ReviewGroupItemResource,
    ReviewGroupListResource,
)
from rbtools.api.resource.review_group_user import (
    ReviewGroupUserItemResource,
    ReviewGroupUserListResource,
)
from rbtools.api.resource.review_reply import (
    ReviewReplyItemResource,
    ReviewReplyListResource,
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
from rbtools.api.resource.screenshot_comment import (
    ScreenshotCommentItemResource,
    ScreenshotCommentListResource,
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
    'DiffCommentItemResource',
    'DiffCommentListResource',
    'DiffContextResource',
    'DiffFileAttachmentItemResource',
    'DiffFileAttachmentListResource',
    'DiffItemResource',
    'DiffListResource',
    'DiffResource',
    'DiffUploaderMixin',
    'DraftDiffCommitItemResource',
    'DraftDiffCommitListResource',
    'DraftDiffResource',
    'DraftFileAttachmentItemResource',
    'DraftFileAttachmentListResource',
    'DraftScreenshotItemResource',
    'DraftScreenshotListResource',
    'ExtensionItemResource',
    'ExtensionListResource',
    'FileAttachmentCommentItemResource',
    'FileAttachmentCommentListResource',
    'FileAttachmentItemResource',
    'FileAttachmentListResource',
    'FileDiffItemResource',
    'FileDiffListResource',
    'FileDiffResource',
    'GeneralCommentItemResource',
    'GeneralCommentListResource',
    'GetPatchMixin',
    'ItemResource',
    'LastUpdateResource',
    'ListResource',
    'RESOURCE_MAP',
    'RepositoryBranchListResource',
    'RepositoryCommitListResource',
    'RepositoryGroupItemResource',
    'RepositoryGroupListResource',
    'RepositoryInfoResource',
    'RepositoryItemResource',
    'RepositoryListResource',
    'RepositoryUserItemResource',
    'RepositoryUserListResource',
    'Resource',
    'ResourceDictField',
    'ResourceExtraDataField',
    'ResourceLinkField',
    'ResourceListField',
    'ReviewItemResource',
    'ReviewListResource',
    'ReviewGroupItemResource',
    'ReviewGroupListResource',
    'ReviewGroupUserItemResource',
    'ReviewGroupUserListResource',
    'ReviewReplyItemResource',
    'ReviewReplyListResource',
    'ReviewRequestDraftResource',
    'ReviewRequestItemResource',
    'ReviewRequestListResource',
    'ReviewRequestResource',
    'RootResource',
    'ScreenshotCommentItemResource',
    'ScreenshotCommentListResource',
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
