"""Resource definitions for repositories.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, Optional, TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ItemResource,
    ListResource,
    api_stub,
    resource_mimetype,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from typing_extensions import Unpack

    from rbtools.api.resource.base import (
        BaseGetParams,
        ResourceExtraDataField,
    )
    from rbtools.api.resource.base_review_group import ReviewGroupGetListParams
    from rbtools.api.resource.base_user import UserGetListParams
    from rbtools.api.resource.diff_file_attachment import (
        DiffFileAttachmentGetListParams,
        DiffFileAttachmentListResource,
    )
    from rbtools.api.resource.repository_branch import \
        RepositoryBranchListResource
    from rbtools.api.resource.repository_commit import (
        RepositoryCommitGetListParams,
        RepositoryCommitListResource,
    )
    from rbtools.api.resource.repository_group import \
        RepositoryGroupListResource
    from rbtools.api.resource.repository_info import RepositoryInfoResource
    from rbtools.api.resource.repository_user import RepositoryUserListResource


@resource_mimetype('application/vnd.reviewboard.org.repository')
class RepositoryItemResource(ItemResource):
    """Item resource for repositories.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The URL to the bug tracker for this repository.
    #:
    #: This is a format string, where ``%s`` is in place of the bug ID.
    bug_tracker: str

    #: Extra data as part of the repository.
    #:
    #: Some of this will be dependent on the type of repository or hosting
    #: service being used, and those entries should not be modified.
    extra_data: ResourceExtraDataField

    #: The numeric ID of the repository.
    id: int

    #: An alternate path to the repository, for lookup purposes.
    mirror_path: str

    #: The name of the repository.
    name: str

    #: The main path to the repository.
    #:
    #: This is used for communicating with the repository and accessing files.
    path: str

    #: Whether the repository requires a patch base directory.
    requires_basedir: bool

    #: Whether the repository requires a change number for new review requests.
    requires_change_number: bool

    #: Whether the repository supports post-commit review.
    #:
    #: This indicates whether this repository can be used to create review
    #: requests for committed changes on the "New Review Request" page.
    supports_post_commit: bool

    #: The name of the internal repository communication class.
    tool: str

    #: Whether or not this repository is visible.
    #:
    #: This will only be present when interacting with the API as an admin
    #: user.
    visible: Optional[bool]

    @api_stub
    def get_branches(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> RepositoryBranchListResource:
        """Get the repository branches resource.

        Args:
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
    def get_commits(
        self,
        **kwargs: Unpack[RepositoryCommitGetListParams],
    ) -> RepositoryCommitListResource:
        """Get the repository commits resource.

        Args:
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
    def get_diff_file_attachments(
        self,
        **kwargs: Unpack[DiffFileAttachmentGetListParams],
    ) -> DiffFileAttachmentListResource:
        """Get the diff file attachments list resource for this repository.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffFileAttachmentListResource:
            The diff file attachment list.

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
    ) -> RepositoryInfoResource:
        """Get the repository info resource.

        Args:
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
    def get_repository_groups(
        self,
        **kwargs: Unpack[ReviewGroupGetListParams],
    ) -> RepositoryGroupListResource:
        """Get the repository group list resource.

        Args:
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
    def get_repository_users(
        self,
        **kwargs: Unpack[UserGetListParams],
    ) -> RepositoryUserListResource:
        """Get the repository users resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.RepositoryUserListResource:
            The repository commits.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError


class RepositoryGetListParams(BaseGetListParams, total=False):
    """Params for the repository list GET operation.

    Version Added:
        6.0
    """

    #: A comma-separated list of hosting service IDs to filter by.
    hosting_service: str

    #: A comma-separated list of repository names to filter by.
    name: str

    #: A comma-separated list of names, paths, or mirror paths to filter by.
    name_or_path: str

    #: A comma-separated list of paths or mirror paths to filter by.
    path: str

    #: A search query to filter by.
    #:
    #: This will match the start of repository names.
    q: str

    #: Whether to show all repositories, including ones marked as not visible.
    show_invisible: bool

    #: A comma-separated list of tool names to filter by.
    tool: str

    #: A comma-separated list of usernames to filter by.
    #:
    #: These are matched against the repository (or hosting service account)
    #: username.
    username: str


@resource_mimetype('application/vnd.reviewboard.org.repositories')
class RepositoryListResource(ListResource[RepositoryItemResource]):
    """List resource for repositories.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[Mapping[str, str]] = {
        'hosting_service': 'hosting-service',
        'name_or_path': 'name-or-path',
        'show_invisible': 'show-invisible',
        **ListResource._httprequest_params_name_map,
    }
