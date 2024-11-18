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

from rbtools.api.cache import MINIMUM_VERSION
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

if TYPE_CHECKING:
    from typing_extensions import Self, Unpack

    from rbtools.api.request import HttpRequest, QueryArgs
    from rbtools.api.resource.base import (
        BaseGetListParams,
        BaseGetParams,
    )
    from rbtools.api.resource.base_user import (
        UserGetListParams,
        UserGetParams,
    )
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
    from rbtools.api.resource.file_diff import (
        FileDiffItemResource,
        FileDiffListResource,
    )
    from rbtools.api.resource.last_update import LastUpdateResource
    from rbtools.api.resource.review_group import (
        ReviewGroupGetListParams,
        ReviewGroupItemResource,
        ReviewGroupListResource,
    )
    from rbtools.api.resource.review_group_user import (
        ReviewGroupUserItemResource,
        ReviewGroupUserListResource,
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

    @request_method
    def _get_template_request(
        self,
        url_template: str,
        values: Optional[dict[str, str]] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Generate an HttpRequest from a uri-template.

        This will replace each '{variable}' in the template with the
        value from kwargs['variable'], or if it does not exist, the
        value from values['variable']. The resulting url is used to
        create an HttpRequest.

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

        url = self._TEMPLATE_PARAM_RE.sub(get_template_value, url_template)

        return self._make_httprequest(url=url, query_args=kwargs)

    @api_stub
    def get_change(
        self,
        *,
        review_request_id: int,
        change_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> ChangeItemResource:
        """Get a change description item resource.

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_review_request_change` should be used instead.

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

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_review_request_changes` should be used instead.

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

        This method exists for compatibility with older versions of Review
        Board. :py:meth:`get_diff_commit` should be used instead.

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

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_review_request_draft` should be used instead.

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

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_file_diff` should be used instead.

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

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_file_diffs` should be used instead.

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

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_review_request_file_attachment` should be used instead.

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

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_review_request_file_attachments` should be used instead.

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
    def get_last_update(
        self,
        *,
        review_request_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> LastUpdateResource:
        """Get the last update resource for a review request.

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_review_request_last_update` should be used instead.

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
    def get_status_update(
        self,
        *,
        review_request_id: int,
        status_update_id: int,
        **kwargs: Unpack[BaseGetParams],
    ) -> StatusUpdateItemResource:
        """Get a status update item resource.

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_review_request_status_update` should be used instead.

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

        This method is for compatibility with older versions of Review Board.
        :py:meth:`get_review_request_status_updates` should be used instead.

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
