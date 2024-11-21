"""Base class for review group resources.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, Generic, Optional, TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ItemResource,
    ListResource,
    TItemResource,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rbtools.api.resource.base import ResourceExtraDataField


class BaseReviewGroupItemResource(ItemResource):
    """Base class for review group item resources.

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


class BaseReviewGroupListResource(Generic[TItemResource],
                                  ListResource[TItemResource]):
    """List resource for review groups.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[Mapping[str, str]] = {
        'invite_only': 'invite-only',
        **ListResource._httprequest_params_name_map,
    }
