"""Resource definitions for the API root.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar, Optional, TYPE_CHECKING, cast

from packaging.version import parse as parse_version
from typelets.json import JSONDict
from typing_extensions import Unpack

from rbtools.api.cache import MINIMUM_VERSION
from rbtools.api.resource.archived_review_request import (
    ArchivedReviewRequestItemResource,
    ArchivedReviewRequestListResource,
)
from rbtools.api.resource.base import (
    ItemResource,
    RequestMethodResult,
    ResourceDictField,
    api_stub,
    is_api_stub,
    replace_api_stub,
    request_method,
    resource_mimetype,
)
from rbtools.api.resource.muted_review_request import (
    MutedReviewRequestItemResource,
    MutedReviewRequestListResource,
)

if TYPE_CHECKING:
    from typing_extensions import Self, Unpack

    from rbtools.api.request import HttpRequest, QueryArgs
    from rbtools.api.resource.api_token import (
        APITokenItemResource,
        APITokenListResource,
    )
    from rbtools.api.resource.base import (
        BaseGetListParams,
        BaseGetParams,
    )
    from rbtools.api.resource.base_user import (
        UserGetListParams,
        UserGetParams,
    )
    from rbtools.api.resource.base_review_group import ReviewGroupGetListParams
    from rbtools.api.resource.default_reviewer import (
        DefaultReviewerGetListParams,
        DefaultReviewerItemResource,
        DefaultReviewerListResource,
    )
    from rbtools.api.resource.change import (
        ChangeItemResource,
        ChangeListResource,
    )
    from rbtools.api.resource.diff import (
        DiffItemResource,
        DiffListResource,
    )
    from rbtools.api.resource.diff_comment import (
        DiffCommentGetListParams,
        DiffCommentItemResource,
        DiffCommentListResource,
    )
    from rbtools.api.resource.diff_commit import (
        DiffCommitItemResource,
        DiffCommitListResource,
    )
    from rbtools.api.resource.diff_context import (
        DiffContextGetParams,
        DiffContextResource,
    )
    from rbtools.api.resource.diff_file_attachment import (
        DiffFileAttachmentGetListParams,
        DiffFileAttachmentItemResource,
        DiffFileAttachmentListResource,
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
        HostingServiceAccountGetListParams,
        HostingServiceAccountItemResource,
        HostingServiceAccountListResource,
    )
    from rbtools.api.resource.last_update import LastUpdateResource
    from rbtools.api.resource.oauth_application import (
        OAuthApplicationGetListParams,
        OAuthApplicationItemResource,
        OAuthApplicationListResource,
    )
    from rbtools.api.resource.oauth_token import (
        OAuthTokenItemResource,
        OAuthTokenListResource,
    )
    from rbtools.api.resource.plain_text import PlainTextResource
    from rbtools.api.resource.remote_repository import (
        RemoteRepositoryGetListParams,
        RemoteRepositoryItemResource,
        RemoteRepositoryListResource,
    )
    from rbtools.api.resource.repository import (
        RepositoryGetListParams,
        RepositoryItemResource,
        RepositoryListResource,
    )
    from rbtools.api.resource.repository_branch import (
        RepositoryBranchListResource,
    )
    from rbtools.api.resource.repository_commit import (
        RepositoryCommitGetListParams,
        RepositoryCommitListResource,
    )
    from rbtools.api.resource.repository_group import (
        RepositoryGroupItemResource,
        RepositoryGroupListResource,
    )
    from rbtools.api.resource.repository_info import RepositoryInfoResource
    from rbtools.api.resource.repository_user import (
        RepositoryUserItemResource,
        RepositoryUserListResource,
    )
    from rbtools.api.resource.review import (
        ReviewItemResource,
        ReviewListResource,
    )
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
        ReviewRequestGetListParams,
        ReviewRequestItemResource,
        ReviewRequestListResource,
    )
    from rbtools.api.resource.review_request_draft import (
        ReviewRequestDraftResource,
    )
    from rbtools.api.resource.screenshot import (
        ScreenshotItemResource,
        ScreenshotListResource,
    )
    from rbtools.api.resource.screenshot_comment import (
        ScreenshotCommentItemResource,
        ScreenshotCommentListResource,
    )
    from rbtools.api.resource.search import SearchGetParams, SearchResource
    from rbtools.api.resource.server_info import ServerInfoResource
    from rbtools.api.resource.session import SessionResource
    from rbtools.api.resource.status_update import (
        StatusUpdateGetListParams,
        StatusUpdateItemResource,
        StatusUpdateListResource,
    )
    from rbtools.api.resource.user import (
        UserItemResource,
        UserListResource,
    )
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
    from rbtools.api.resource.watched_review_group import (
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
    from rbtools.api.transport import Transport


logger = logging.getLogger(__name__)


@resource_mimetype('application/vnd.reviewboard.org.root')
class RootResource(ItemResource):
    """The Root resource specific base class.

    Provides additional methods for fetching any resource directly
    using the uri templates. A method of the form "get_<uri-template-name>"
    is called to retrieve the HttpRequest corresponding to the
    resource. Template replacement values should be passed in as a
    dictionary to the values parameter.
    """

    #: Capabilities for the Review Board server.
    capabilities: ResourceDictField

    #: Attributes which should be excluded when processing the payload.
    _excluded_attrs: ClassVar[set[str]] = {'uri_templates'}

    #: The regex to pull parameter names out of URI templates.
    _TEMPLATE_PARAM_RE: ClassVar[re.Pattern[str]] = \
        re.compile(r'\{(?P<key>[A-Za-z_0-9]*)\}')

    def __init__(
        self,
        transport: Transport,
        payload: JSONDict,
        url: str,
        **kwargs,
    ) -> None:
        """Initialize the resource.

        Args:
            transport (rbtools.api.transport.Transport):
                The API transport.

            payload (dict):
                The resource payload.

            url (str):
                The resource URL.

            **kwargs (dict, unused):
                Unused keyword arguments.
        """
        super().__init__(transport, payload, url, token=None)

        uri_templates = cast(dict[str, str], payload['uri_templates'])

        # Generate methods for accessing resources directly using
        # the uri-templates.
        for name, uri in uri_templates.items():
            attr_name = f'get_{name}'

            def get_method(
                resource: Self = self,
                url: str = uri,
                **kwargs,
            ) -> RequestMethodResult:
                return resource._get_template_request(url, **kwargs)

            if not hasattr(self, attr_name):
                # This log message is useful for adding new stubs. It will be
                # removed once this work for resources is done.
                params = self._TEMPLATE_PARAM_RE.findall(uri)
                logger.debug('RootResource is missing API stub for %s (%s)',
                             attr_name, ', '.join(params))

                setattr(self, attr_name, get_method)
            elif is_api_stub(stub := getattr(self, attr_name)):
                replace_api_stub(self, attr_name, stub, get_method)

        product = cast(JSONDict, payload.get('product', {}))
        server_version = cast(Optional[str], product.get('package_version'))

        if (server_version is None or
            parse_version(server_version) < parse_version(MINIMUM_VERSION)):
            # This version is too old to safely support caching (there were
            # bugs before this version). Disable caching.
            transport.disable_cache()

    def _make_url_from_template(
        self,
        url_template: str,
        values: Optional[dict[str, str]] = None,
        **kwargs: QueryArgs,
    ) -> str:
        """Create a URL from a template.

        Version Added:
            6.0

        Args:
            url_template (str):
                The URL template.

            values (dict, optional):
                The values to use for replacing template variables.

            **kwargs (rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            str:
            The URL with the values filled in.
        """
        if values is None:
            values = {}

        def get_template_value(
            m: re.Match[str],
        ) -> str:
            key = m.group('key')

            try:
                return str(kwargs.pop(key, None) or values[key])
            except KeyError:
                raise ValueError(
                    f'Template was not provided a value for "{key}"')

        return self._TEMPLATE_PARAM_RE.sub(get_template_value, url_template)

    @request_method
    def _get_template_request(
        self,
        url_template: str,
        values: Optional[dict[str, str]] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Generate an HttpRequest from a URI template.

        This will replace each ``{variable}`` in the template with the
        value from ``kwargs['variable']``, or if it does not exist, the
        value from ``values['variable']``. The resulting URL is used to
        create an ``HttpRequest``.

        Args:
            url_template (str):
                The URL template.

            values (dict, optional):
                The values to use for replacing template variables.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.Resource:
            The resource at the given URL.
        """
        url = self._make_url_from_template(url_template, values, **kwargs)

        return self._make_httprequest(url=url, query_args=kwargs)

    def get_archived_review_request(
        self,
        *,
        username: str,
        review_request_id: int,
        **kwargs: QueryArgs,
    ) -> ArchivedReviewRequestItemResource:
        """Get an archived review request item resource.

        Args:
            username (str):
                The name of the user to get the archived review request item
                for.

            review_request_id (int):
                The review request

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ArchivedReviewRequestItemResource:
            The archived review request item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        uri_templates = cast(dict[str, str], self._payload['uri_templates'])

        url = self._make_url_from_template(
            uri_templates['archived_review_request'],
            values={
                'review_request_id': f'{review_request_id}',
                'username': username,
            })

        return ArchivedReviewRequestItemResource(
            transport=self._transport,
            payload={
                'archived_review_request': {},
            },
            url=url,
            token='archived_review_request',
        )

    def get_archived_review_requests(
        self,
        *,
        username: str,
        **kwargs: QueryArgs,
    ) -> ArchivedReviewRequestListResource:
        """Get an archived review requests list resource.

        Args:
            username (str):
                The name of the user to get the archived review requests list
                for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ArchivedReviewRequestListResource:
            The archived review request list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        uri_templates = cast(dict[str, str], self._payload['uri_templates'])

        url = self._make_url_from_template(
            uri_templates['archived_review_requests'],
            values={
                'username': username,
            })

        return ArchivedReviewRequestListResource(
            transport=self._transport,
            payload={
                'archived_review_requests': [],
            },
            url=url,
            token='archived_review_requests',
        )

    def get_muted_review_request(
        self,
        *,
        username: str,
        review_request_id: int,
        **kwargs: QueryArgs,
    ) -> MutedReviewRequestItemResource:
        """Get a muted review request item resource.

        Args:
            username (str):
                The name of the user to get the muted review request item
                for.

            review_request_id (int):
                The review request.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.MutedReviewRequestItemResource:
            The muted review request item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        uri_templates = cast(dict[str, str], self._payload['uri_templates'])

        url = self._make_url_from_template(
            uri_templates['muted_review_request'],
            values={
                'review_request_id': f'{review_request_id}',
                'username': username,
            })

        return MutedReviewRequestItemResource(
            transport=self._transport,
            payload={
                'muted_review_request': {},
            },
            url=url,
            token='muted_review_request',
        )

    def get_muted_review_requests(
        self,
        *,
        username: str,
        **kwargs: QueryArgs,
    ) -> MutedReviewRequestListResource:
        """Get a muted review requests list resource.

        Args:
            username (str):
                The name of the user to get the muted review requests list
                for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.MutedReviewRequestListResource:
            The muted review request list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        uri_templates = cast(dict[str, str], self._payload['uri_templates'])

        url = self._make_url_from_template(
            uri_templates['muted_review_requests'],
            values={
                'username': username,
            })

        return MutedReviewRequestListResource(
            transport=self._transport,
            payload={
                'muted_review_requests': [],
            },
            url=url,
            token='muted_review_requests',
        )

    @api_stub
    def get_api_token(
        self,
        *,
        username: str,
        api_token_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> APITokenItemResource:
        """Get an API token item resource.

        Args:
            username (str):
                The name of the user to get the API token for.

            api_token_id (int):
                The ID of the API token to get.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.APITokenItemResource:
            The API token item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_api_tokens(
        self,
        *,
        username: str,
        **kwargs: Unpack[BaseGetListParams],
    ) -> APITokenListResource:
        """Get an API token list resource.

        Args:
            username (str):
                The name of the user to get the API token list for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.APITokenListResource:
            The API token list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_branches(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> RepositoryBranchListResource:
        """Get the repository branches resource.

        This method exists for compatibility with versions of Review Board
        prior to 5.0.2. :py:meth:`get_repository_branches` should be used
        instead.

        Args:
            repository_id (int):
                The ID of the repository to fetch commits for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryBranchListResource:
            The repository branches.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_change(
        self,
        *,
        review_request_id: int,
        change_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ChangeItemResource:
        """Get a change description item resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_request_change` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            change_id (int):
                The change description ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ChangeItemResource:
            The change description item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_changes(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ChangeListResource:
        """Get a change description list resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_request_changes` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ChangeListResource:
            The change description list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_commit(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        commit_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> DiffCommitItemResource:
        """Get a diff commit item resource.

        This method exists for compatibility with versions of Review Board
        prior to 5.0.2. :py:meth:`get_diff_commit` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The revision of the diff.

            commit_id (int):
                The ID of the commit to fetch.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffItemResource:
            The diff commit item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_commits(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[RepositoryCommitGetListParams],
    ) -> RepositoryCommitListResource:
        """Get the repository commits resource.

        This method exists for compatibility with versions of Review Board
        prior to 5.0.2. :py:meth:`get_repository_commits` should be used
        instead.

        Args:
            repository_id (int):
                The ID of the repository to fetch commits for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryCommitListResource:
            The repository commits.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_commit_validation(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ValidateDiffCommitResource:
        """Get the diff commit validation resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ValidateDiffCommitResource:
            The diff commit validation resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_default_reviewer(
        self,
        *,
        default_reviewer_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> DefaultReviewerItemResource:
        """Get a default reviewer item resource.

        Args:
            default_reviewer_id (int):
                The ID of the default reviewer to get.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DefaultReviewerItemResource:
            The default reviewer item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_default_reviewers(
        self,
        **kwargs: Unpack[DefaultReviewerGetListParams],
    ) -> DefaultReviewerListResource:
        """Get the default reviewer list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DefaultReviewerListResource:
            The default reviewer list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> DiffItemResource:
        """Get a diff item resource.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The revision of the diff to fetch.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffItemResource:
            The diff item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> DiffCommentItemResource:
        """Get a reply diff comment item resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_reply_diff_comment` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentItemResource:
            The diff comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[DiffCommentGetListParams],
    ) -> DiffCommentListResource:
        """Get a reply diff comment list resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_reply_diff_comments` should be used
        instead.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentListResource:
            The diff comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_context(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[DiffContextGetParams],
    ) -> DiffContextResource:
        """Get the diff context resource.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffContextResource:
            The diff context resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_validation(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ValidateDiffResource:
        """Get the diff validation resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ValidateDiffResource:
            The diff validation resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diffs(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> DiffListResource:
        """Get a diff list resource.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffListResource:
            The diff list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_commit(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        commit_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> DiffCommitItemResource:
        """Get a diff commit item resource.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The revision of the diff.

            commit_id (int):
                The ID of the commit to fetch.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffItemResource:
            The diff commit item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_commits(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> DiffCommitListResource:
        """Get the diff commits list.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The revision of the diff.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffListResource:
            The diff commits list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_file_attachment(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> DiffFileAttachmentItemResource:
        """Get a diff file attachment item resource.

        Args:
            repository_id (int):
                The repository for the diff file attachments.

            file_attachment_id (int):
                The ID of the file attachment.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffFileAttachmentItemResource:
            The diff file attachment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_file_attachments(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[DiffFileAttachmentGetListParams],
    ) -> DiffFileAttachmentListResource:
        """Get a diff file attachments list resource.

        Args:
            repository_id (int):
                The repository for the diff file attachments.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffFileAttachmentListResource:
            The extensions list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_draft(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewRequestDraftResource:
        """Get a review request draft.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_request_draft` should be used instead.

        Args:
            review_request_id (int):
                The ID of the review request.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewRequestDraftResource:
            The draft resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_extension(
        self,
        *,
        extension_name: str,
        **kwargs: Unpack[BaseGetParams],
    ) -> ExtensionItemResource:
        """Get an extension item resource.

        Args:
            extension_name (str):
                The class path of the extension class (for example,
                ``rbintegrations.extension.RBIntegrationsExtension``).

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ExtensionItemResource:
            The extension item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_extensions(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ExtensionListResource:
        """Get the extensions list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ExtensionListResource:
            The diff file attachments list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        filediff_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileDiffItemResource:
        """Get a file diff item resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_file_diff` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            filediff_id (int):
                The file diff ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffItemResource:
            The file diff item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_files(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileDiffListResource:
        """Get the file diffs for a diff revision.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_file_diffs` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffListResource:
            The file diff list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_attachment(
        self,
        *,
        review_request_id: int,
        file_attachment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileAttachmentItemResource:
        """Get a file attachment item resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_request_file_attachment` should be used
        instead.

        Args:
            review_request_id (int):
                The review request ID.

            file_attachment_id (int):
                The file attachment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentItemResource:
            The file attachment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_attachments(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileAttachmentListResource:
        """Get a file attachment list resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_request_file_attachments` should be used
        instead.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentListResource:
            The file attachments list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_attachment_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileAttachmentCommentItemResource:
        """Get a file attachment comment item resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentCommentItemResource:
            The file attachment comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_attachment_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileAttachmentCommentListResource:
        """Get a file attachment comment list resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentCommentListResource:
            The file attachment comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_diff(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        filediff_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileDiffItemResource:
        """Get a file diff item resource.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            filediff_id (int):
                The file diff ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffItemResource:
            The file diff item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_diffs(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileDiffListResource:
        """Get the file diffs for a diff revision.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffListResource:
            The file diff list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_diff_comments(
        self,
        review_request_id: int,
        diff_revision: int,
        filediff_id: int,
        **kwargs: Unpack[DiffCommentGetListParams],
    ) -> DiffCommentListResource:
        """Get the comments for a file diff.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            filediff_id (int):
                The ID of the file diff to fetch comments for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentListResource:
            The comments on this file diff.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_diff_original_file(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        filediff_id: int,
        **kwargs: QueryArgs,
    ) -> PlainTextResource:
        """Get the original version of a file from a diff.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            filediff_id (int):
                The file diff ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.PlainTextResource:
            The original file.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_diff_patched_file(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        filediff_id: int,
        **kwargs: QueryArgs,
    ) -> PlainTextResource:
        """Get the patched version of a file from a diff.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            filediff_id (int):
                The file diff ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.PlainTextResource:
            The patched file.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_general_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> GeneralCommentItemResource:
        """Get a general comment item resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_general_comment` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.GeneralCommentItemResource:
            The general comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_general_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> GeneralCommentListResource:
        """Get a general comment list resource.

        This method is for compatibility with versions of Review Board prior
        to 5.0.2. :py:meth:`get_review_general_comments` should be used
        instead.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.GeneralCommentListResource:
            The general comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_group(
        self,
        *,
        group_name: str,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewGroupItemResource:
        """Get a review group item resource.

        Args:
            group_name (str):
                The review group name.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewGroupItemResource:
            The review group item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_groups(
        self,
        **kwargs: Unpack[ReviewGroupGetListParams],
    ) -> ReviewGroupListResource:
        """Get the review group list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewGroupListResource:
            The review group list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_hosting_service(
        self,
        *,
        hosting_service_id: str,
        **kwargs: Unpack[BaseGetParams],
    ) -> HostingServiceItemResource:
        """Get a hosting service item resource.

        Args:
            hosting_service_id (str):
                The ID of the hosting service.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.HostingServiceItemResource:
            The hosting service item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_hosting_services(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> HostingServiceListResource:
        """Get the hosting service list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.HostingServiceListResource:
            The hosting service list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_hosting_service_account(
        self,
        *,
        account_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> HostingServiceAccountItemResource:
        """Get a hosting service account item resource.

        Args:
            account_id (int):
                The ID of the hosting service account.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.HostingServiceAccountItemResource:
            The hosting service account item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_hosting_service_accounts(
        self,
        **kwargs: Unpack[HostingServiceAccountGetListParams],
    ) -> HostingServiceAccountListResource:
        """Get the hosting service account list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.HostingServiceAccountListResource:
            The hosting service account list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_info(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ServerInfoResource:
        """Get the server info resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ServerInfoResource:
            The server info resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_last_update(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> LastUpdateResource:
        """Get the last update resource for a review request.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_request_last_update` should be used
        instead.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.LastUpdateResource:
            The last update resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_oauth_app(
        self,
        *,
        app_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> OAuthApplicationItemResource:
        """Get an OAuth2 application item resource.

        Args:
            app_id (int):
                The application ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.OAuthApplicationItemResource:
            The application item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_oauth_apps(
        self,
        **kwargs: Unpack[OAuthApplicationGetListParams],
    ) -> OAuthApplicationListResource:
        """Get the OAuth2 application list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.OAuthApplicationListResource:
            The application list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_oauth_token(
        self,
        *,
        oauth_token_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> OAuthTokenItemResource:
        """Get an OAuth2 token item resource.

        Args:
            oauth_token_id (int):
                The ID of the OAuth token.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.OAuthTokenItemResource:
            The token item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_original_file(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        filediff_id: int,
        **kwargs: QueryArgs,
    ) -> PlainTextResource:
        """Get the original version of a file.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_file_diff_original_file` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            filediff_id (int):
                The file diff ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.PlainTextResource:
            The original file.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_patched_file(
        self,
        *,
        review_request_id: int,
        diff_revision: int,
        filediff_id: int,
        **kwargs: QueryArgs,
    ) -> PlainTextResource:
        """Get the patched version of a file.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_file_diff_patched_file` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            diff_revision (int):
                The diff revision.

            filediff_id (int):
                The file diff ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.PlainTextResource:
            The patched file.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_remote_repository(
        self,
        *,
        account_id: int,
        repository_id: str,
        **kwargs: Unpack[BaseGetParams],
    ) -> RemoteRepositoryItemResource:
        """Get a remote repository item resource.

        Args:
            account_id (int):
                The ID of the hosting service account.

            repository_id (str):
                The ID of the remote repository.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RemoteRepositoryItemResource:
            The remote repository item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_remote_repositories(
        self,
        *,
        account_id: int,
        **kwargs: Unpack[RemoteRepositoryGetListParams],
    ) -> RemoteRepositoryListResource:
        """Get a remote repository list resource.

        Args:
            account_id (int):
                The ID of the hosting service account.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RemoteRepositoryListResource:
            The remote repository list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_oauth_tokens(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> OAuthTokenListResource:
        """Get the OAuth2 token list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.OAuthTokenListResource:
            The token list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_reply(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewReplyItemResource:
        """Get a review reply item resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_reply` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The ID of the review being replied to.

            reply_id (int):
                The ID of the reply.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyItemResource:
            The review reply item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_replies(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ReviewReplyListResource:
        """Get a review reply list resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_replies` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The ID of the review being replied to.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyListResource:
            The review reply list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_reply_draft(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewReplyItemResource:
        """Get a review reply draft item resource, if present.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_reply_draft` should be used instead.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The ID of the review being replied to.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyItemResource:
            The review reply draft item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repository(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> RepositoryItemResource:
        """Get a repository item resource.

        Args:
            repository_id (int):
                The ID of the repository.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryItemResource:
            The repository item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repositories(
        self,
        **kwargs: Unpack[RepositoryGetListParams],
    ) -> RepositoryListResource:
        """Get a repository list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryListResource:
            The repository list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repository_branches(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> RepositoryBranchListResource:
        """Get the repository branches resource.

        Args:
            repository_id (int):
                The ID of the repository to fetch commits for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryBranchListResource:
            The repository branches.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repository_commits(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[RepositoryCommitGetListParams],
    ) -> RepositoryCommitListResource:
        """Get the repository commits resource.

        Args:
            repository_id (int):
                The ID of the repository to fetch commits for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryCommitListResource:
            The repository commits.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repository_group(
        self,
        *,
        repository_id: int,
        group_name: str,
        **kwargs: Unpack[BaseGetParams],
    ) -> RepositoryGroupItemResource:
        """Get a repository group item resource.

        Args:
            repository_id (int):
                The ID of the repository to fetch groups for.

            group_name (str):
                The name of the group to fetch.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryGroupItemResource:
            The repository group item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repository_groups(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[ReviewGroupGetListParams],
    ) -> RepositoryGroupListResource:
        """Get a repository group list resource.

        Args:
            repository_id (int):
                The ID of the repository to fetch groups for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryGroupListResource:
            The repository group list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repository_info(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> RepositoryInfoResource:
        """Get the repository info resource.

        Args:
            repository_id (int):
                The ID of the repository to fetch commits for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryInfoResource:
            The repository commits.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_repository_user(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[UserGetParams],
    ) -> RepositoryUserItemResource:
        """Get a repository user item resource.

        Args:
            repository_id (int):
                The ID of the repository to fetch users for.

            username (str):
                The username to fetch.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryUserItemResource:
            The repo

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    def get_repository_users(
        self,
        *,
        repository_id: int,
        **kwargs: Unpack[UserGetListParams],
    ) -> RepositoryUserListResource:
        """Get a repository user list resource.

        Args:
            repository_id (int):
                The ID of the repository to fetch users for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryUserListResource:
            The repository user list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewItemResource:
        """Get a review item resource.

        Args:
            review_request_id (int):
                The ID of the review request.

            review_id (int):
                The ID of the review.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewItemResource:
            The review item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_reviews(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ReviewListResource:
        """Get a review list resource.

        Args:
            review_request_id (int):
                The ID of the review request.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewListResource:
            The review list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_draft(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewItemResource:
        """Get a review draft item resource.

        Args:
            review_request_id (int):
                The ID of the review request.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewItemResource:
            The review item resource for the user's draft, if any.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_diff_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> DiffCommentItemResource:
        """Get a diff comment item resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentItemResource:
            The diff comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_diff_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[DiffCommentGetListParams],
    ) -> DiffCommentListResource:
        """Get a diff comment list resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentListResource:
            The diff comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_general_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> GeneralCommentItemResource:
        """Get a general comment item resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.GeneralCommentItemResource:
            The general comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_general_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> GeneralCommentListResource:
        """Get a general comment list resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.GeneralCommentListResource:
            The general comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_group_user(
        self,
        *,
        group_name: str,
        username: str,
        **kwargs: Unpack[UserGetParams],
    ) -> ReviewGroupUserItemResource:
        """Get a review group user item resource.

        Args:
            group_name (str):
                The name of the review group.

            username (str):
                The username of the user.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewGroupUserItemResource:
            The review group user item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_group_users(
        self,
        *,
        group_name: str,
        **kwargs: Unpack[UserGetParams],
    ) -> ReviewGroupUserListResource:
        """Get a review group user list resource.

        Args:
            group_name (str):
                The name of the review group.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewGroupUserListResource:
            The review group user list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewReplyItemResource:
        """Get a review reply item resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The ID of the review being replied to.

            reply_id (int):
                The ID of the reply.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyItemResource:
            The review reply item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_replies(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ReviewReplyListResource:
        """Get a review reply list resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The ID of the review being replied to.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyListResource:
            The review reply list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_draft(
        self,
        *,
        review_request_id: int,
        review_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewReplyItemResource:
        """Get a review reply draft item resource, if present.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The ID of the review being replied to.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewReplyItemResource:
            The review reply draft item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_diff_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> DiffCommentItemResource:
        """Get a reply diff comment item resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            reply_id (int):
                The reply ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentItemResource:
            The diff comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_diff_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        **kwargs: Unpack[DiffCommentGetListParams],
    ) -> DiffCommentListResource:
        """Get a reply diff comment list resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            reply_id (int):
                The reply ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentListResource:
            The diff comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_file_attachment_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileAttachmentCommentItemResource:
        """Get a reply file attachment comment item resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            reply_id (int):
                The review reply ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentCommentItemResource:
            The file attachment comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_file_attachment_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileAttachmentCommentListResource:
        """Get a reply file attachment comment list resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            reply_id (int):
                The review reply ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentCommentListResource:
            The file attachment comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_general_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> GeneralCommentItemResource:
        """Get a reply general comment item resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            reply_id (int):
                The reply ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.GeneralCommentItemResource:
            The general comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_general_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> GeneralCommentListResource:
        """Get a reply general comment list resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            reply_id (int):
                The reply ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.GeneralCommentListResource:
            The general comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_screenshot_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ScreenshotCommentItemResource:
        """Get a reply screenshot comment item resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            reply_id (int):
                The reply ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotCommentItemResource:
            The screenshot comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_reply_screenshot_comments(
        self,
        *,
        review_request_id: int,
        review_id: int,
        reply_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ScreenshotCommentListResource:
        """Get a reply screenshot comment list resource.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            reply_id (int):
                The reply ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotCommentListResource:
            The screenshot comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewRequestItemResource:
        """Get a review request item resource.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewRequestItemResource:
            The review request item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_requests(
        self,
        **kwargs: Unpack[ReviewRequestGetListParams],
    ) -> ReviewRequestListResource:
        """Get the review request list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewRequestListResource:
            The review request list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_change(
        self,
        *,
        review_request_id: int,
        change_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ChangeItemResource:
        """Get a change description item resource.

        Args:
            review_request_id (int):
                The review request ID.

            change_id (int):
                The change description ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ChangeItemResource:
            The change description item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_changes(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ChangeListResource:
        """Get a change description list resource.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ChangeListResource:
            The change description list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_file_attachment(
        self,
        *,
        review_request_id: int,
        file_attachment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> FileAttachmentItemResource:
        """Get a file attachment item resource.

        Args:
            review_request_id (int):
                The review request ID.

            file_attachment_id (int):
                The file attachment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentItemResource:
            The file attachment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_file_attachments(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileAttachmentListResource:
        """Get a file attachment list resource.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentListResource:
            The file attachments list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_draft(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewRequestDraftResource:
        """Get a review request draft.

        Args:
            review_request_id (int):
                The ID of the review request.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewRequestDraftResource:
            The draft resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_file_attachment_comments(
        self,
        *,
        review_request_id: int,
        file_attachment_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileAttachmentCommentListResource:
        """Get the comments on a specific file attachment.

        Args:
            review_request_id (int):
                The ID of the review request.

            file_attachment_id (int):
                The ID of the file attachment.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentCommentListResource:
            The file attachment comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_last_update(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> LastUpdateResource:
        """Get the last update resource for a review request.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.LastUpdateResource:
            The last update resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_status_update(
        self,
        *,
        review_request_id: int,
        status_update_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> StatusUpdateItemResource:
        """Get a status update item resource.

        Args:
            review_request_id (int):
                The review request ID.

            status_update_id (int):
                The status update ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.StatusUpdateItemResource:
            The status update item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request_status_updates(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[StatusUpdateGetListParams],
    ) -> StatusUpdateListResource:
        """Get a status update list resource.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.StatusUpdateListResource:
            The status update list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_root(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> RootResource:
        """Get the root resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            RootResource:
            The root resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_screenshot(
        self,
        *,
        review_request_id: int,
        screenshot_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ScreenshotItemResource:
        """Get a screenshot list resource.

        Args:
            review_request_id (int):
                The review request ID.

            screenshot_id (int):
                The ID of the screenshot.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotItemResource:
            The screenshot item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_screenshots(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ScreenshotListResource:
        """Get a screenshot list resource.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotListResource:
            The screenshot list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_screenshot_comment(
        self,
        *,
        review_request_id: int,
        review_id: int,
        comment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ScreenshotCommentItemResource:
        """Get the screenshot comments in a review.

        Args:
            review_request_id (int):
                The review request ID.

            review_id (int):
                The review ID.

            comment_id (int):
                The comment ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotCommentItemResource:
            The screenshot comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_screenshot_comments(
        self,
        *,
        review_request_id: int,
        screenshot_id: int,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ScreenshotCommentListResource:
        """Get the comments on a screenshot.

        This is not a list analog to :py:meth:`get_screenshot_comment`
        due to a bug in Review Board's URI templates. If for some reason you
        really need to get the screenshot comments on a review, fetch the
        review first and then get the screenshot comments from that.

        Args:
            review_request_id (int):
                The review request ID.

            screenshot_id (int):
                The screenshot ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotCommentListResource:
            The screenshot comment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_search(
        self,
        **kwargs: Unpack[SearchGetParams],
    ) -> SearchResource:
        """Get the search resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.SearchResource:
            The search results.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_session(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> SessionResource:
        """Get the session resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.SessionResource:
            The session resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_status_update(
        self,
        *,
        review_request_id: int,
        status_update_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> StatusUpdateItemResource:
        """Get a status update item resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_request_status_update` should be used
        instead.

        Args:
            review_request_id (int):
                The review request ID.

            status_update_id (int):
                The status update ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.StatusUpdateItemResource:
            The status update item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_status_updates(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[StatusUpdateGetListParams],
    ) -> StatusUpdateListResource:
        """Get a status update list resource.

        This method is for compatibility with versions of Review Board prior to
        5.0.2. :py:meth:`get_review_request_status_updates` should be used
        instead.

        Args:
            review_request_id (int):
                The review request ID.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.StatusUpdateListResource:
            The status update list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_user(
        self,
        *,
        username: str,
        **kwargs: Unpack[UserGetParams],
    ) -> UserItemResource:
        """Get a user item resource.

        Args:
            username (str):
                The username of the user.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.UserItemResource:
            The user item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_users(
        self,
        **kwargs: Unpack[UserGetListParams],
    ) -> UserListResource:
        """Get the user list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.UserListResource:
            The user list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_user_file_attachment(
        self,
        *,
        username: str,
        file_attachment_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> UserFileAttachmentItemResource:
        """Get a user file attachment item resource.

        Args:
            username (str):
                The username of the user.

            file_attachment_id (int):
                The ID of the file attachment.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.UserFileAttachmentItemResource:
            The user file attachment item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_user_file_attachments(
        self,
        *,
        username: str,
        **kwargs: Unpack[BaseGetListParams],
    ) -> UserFileAttachmentListResource:
        """Get a user file attachment list resource.

        Args:
            username (str):
                The username of the user.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.UserFileAttachmentListResource:
            The user file attachment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_validation(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ValidationResource:
        """Get the validation list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ValidationResource:
            The validation list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_watched(
        self,
        *,
        username: str,
        **kwargs: Unpack[BaseGetParams],
    ) -> WatchedResource:
        """Get the watched resource.

        Args:
            username (str):
                The name of the user to get the watched resource for.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WatchedResource:
            The watched resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_watched_review_group(
        self,
        *,
        username: str,
        watched_obj_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> WatchedReviewGroupItemResource:
        """Get a watched review group item resource.

        Args:
            username (str):
                The username for the user.

            watched_obj_id (int):
                The ID of the watched review group.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WatchedReviewGroupItemResource:
            The watched review group item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_watched_review_groups(
        self,
        *,
        username: str,
        **kwargs: Unpack[BaseGetListParams],
    ) -> WatchedReviewGroupListResource:
        """Get a watched review group list resource.

        Args:
            username (str):
                The username for the user.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WatchedReviewGroupListResource:
            The watched review group list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_watched_review_request(
        self,
        *,
        username: str,
        watched_obj_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> WatchedReviewRequestItemResource:
        """Get a watched review request item resource.

        Args:
            username (str):
                The username for the user.

            watched_obj_id (int):
                The ID of the watched review request.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WatchedReviewRequestItemResource:
            The watched review request item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_watched_review_requests(
        self,
        *,
        username: str,
        **kwargs: Unpack[BaseGetListParams],
    ) -> WatchedReviewRequestListResource:
        """Get a watched review request list resource.

        Args:
            username (str):
                The username for the user.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WatchedReviewRequestListResource:
            The watched review request list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_webhook(
        self,
        *,
        webhook_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> WebHookItemResource:
        """Get a WebHook item resource.

        Args:
            webhook_id (int):
                The ID of the WebHook.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WebHookItemResource:
            The WebHook item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_webhooks(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> WebHookListResource:
        """Get the WebHook list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.WebHookListResource:
            The WebHook list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError
