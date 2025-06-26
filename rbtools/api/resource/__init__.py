"""Resource definitions for the RBTools Python API."""

from __future__ import annotations

from rbtools.api.resource.api_token import (
    APITokenItemResource,
    APITokenListResource,
)
from rbtools.api.resource.archived_review_request import (
    ArchivedReviewRequestItemResource,
    ArchivedReviewRequestListResource,
)
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
from rbtools.api.resource.hosting_service import (
    HostingServiceItemResource,
    HostingServiceListResource,
)
from rbtools.api.resource.hosting_service_account import (
    HostingServiceAccountItemResource,
    HostingServiceAccountListResource,
)
from rbtools.api.resource.last_update import LastUpdateResource
from rbtools.api.resource.mixins import (
    DiffUploaderMixin,
    GetPatchMixin,
)
from rbtools.api.resource.muted_review_request import (
    MutedReviewRequestItemResource,
    MutedReviewRequestListResource,
)
from rbtools.api.resource.oauth_application import (
    OAuthApplicationItemResource,
    OAuthApplicationListResource,
)
from rbtools.api.resource.oauth_token import (
    OAuthTokenItemResource,
    OAuthTokenListResource,
)
from rbtools.api.resource.plain_text import PlainTextResource
from rbtools.api.resource.remote_repository import (
    RemoteRepositoryItemResource,
    RemoteRepositoryListResource,
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
from rbtools.api.resource.search import SearchResource
from rbtools.api.resource.server_info import ServerInfoResource
from rbtools.api.resource.session import SessionResource
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
from rbtools.api.resource.watched import WatchedResource
from .watched_review_group import (
    WatchedReviewGroupItemResource,
    WatchedReviewGroupListResource,
)
from rbtools.api.resource.watched_review_request import (
    WatchedReviewRequestItemResource,
    WatchedReviewRequestListResource,
)
from rbtools.api.resource.webhook import (
    WebHookItemResource,
    WebHookListResource,
)


# Compatibility names for renamed resource subclasses.
DiffResource = DiffItemResource
DraftDiffResource = DiffItemResource
FileDiffResource = FileDiffItemResource
ReviewRequestResource = ReviewRequestItemResource


__all__ = [
    'APITokenItemResource',
    'APITokenListResource',
    'ArchivedReviewRequestItemResource',
    'ArchivedReviewRequestListResource',
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
    'HostingServiceAccountItemResource',
    'HostingServiceAccountListResource',
    'HostingServiceItemResource',
    'HostingServiceListResource',
    'ItemResource',
    'LastUpdateResource',
    'ListResource',
    'MutedReviewRequestItemResource',
    'MutedReviewRequestListResource',
    'OAuthApplicationItemResource',
    'OAuthApplicationListResource',
    'OAuthTokenItemResource',
    'OAuthTokenListResource',
    'PlainTextResource',
    'RESOURCE_MAP',
    'RemoteRepositoryItemResource',
    'RemoteRepositoryListResource',
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
    'SearchResource',
    'ServerInfoResource',
    'SessionResource',
    'StatusUpdateItemResource',
    'StatusUpdateListResource',
    'UserFileAttachmentItemResource',
    'UserFileAttachmentListResource',
    'UserItemResource',
    'UserListResource',
    'ValidateDiffCommitResource',
    'ValidateDiffResource',
    'ValidationResource',
    'WatchedResource',
    'WatchedReviewGroupItemResource',
    'WatchedReviewGroupListResource',
    'WatchedReviewRequestItemResource',
    'WatchedReviewRequestListResource',
    'WebHookItemResource',
    'WebHookListResource',
    'resource_mimetype',
]


__autodoc_excludes__ = __all__
