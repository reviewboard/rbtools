"""Resource definitions for review groups.

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
    from typing_extensions import Unpack

    from rbtools.api.resource.base import ResourceExtraDataField
    from rbtools.api.resource.base_user import UserGetListParams
    from rbtools.api.resource.review_group_user import \
        ReviewGroupUserListResource


@resource_mimetype('application/vnd.reviewboard.org.review-group')
class ReviewGroupItemResource(ItemResource):
    """Item resource for review groups.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The absolute URL to the group's page on the site.
    absolute_url: str

    #: The human-readable name of the group.
    display_name: str

    #: Extra data as part of the review group.
    extra_data: Optional[ResourceExtraDataField]

    #: The numeric ID of the review group.
    id: int

    #: Whether or not the group is invite-only.
    #:
    #: An invite-only group is only accessible by members of the group.
    invite_only: bool

    #: The e-mail address of a mailing list for the group.
    mailing_list: str

    #: The short name of the group, used in the reviewer list and dashboard.
    name: str

    #: The URL to the group's page on the site.
    #:
    #: This is deprecated in favor of the ``absolute_url`` attribute.
    url: str

    #: Whether or not the group is visible to users who are not members.
    visible: bool

    @api_stub
    def get_review_group_users(
        self,
        **kwargs: Unpack[UserGetListParams],
    ) -> ReviewGroupUserListResource:
        """Get the users for the review group.

        Args:
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


class ReviewGroupGetListParams(BaseGetListParams, total=False):
    """Params for the review group list GET operation.

    Version Added:
        6.0
    """

    #: Specifies whether ``q`` should also match the display name.
    displayname: bool

    #: Whether to limit results to accessible invite-only groups.
    invite_only: bool

    #: The string that the group name (or display name) must start with.
    #:
    #: The display name will be included if the ``displayname`` parameter is
    #: ``True``. This query is case-insensitive.
    q: str

    #: Whether to include accessible invisible review groups in the results.
    show_invisible: bool


@resource_mimetype('application/vnd.reviewboard.org.review-groups')
class ReviewGroupListResource(ListResource[ReviewGroupItemResource]):
    """List resource for review groups.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[dict[str, str]] = {
        'invite_only': 'invite-only',
        **ListResource._httprequest_params_name_map,
    }
