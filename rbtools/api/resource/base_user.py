"""Base class for user resources.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, Generic, Optional

from rbtools.api.resource.base import (
    BaseGetListParams,
    BaseGetParams,
    ItemResource,
    ListResource,
    TItemResource,
)


class UserGetParams(BaseGetParams, total=False):
    """Params for the user item GET operation.

    Version Added:
        6.0
    """

    #: A comma-separated list of avatar pixel sizes to render.
    #:
    #: Each of the requested sizes will be available in the ``avatar_html``
    #: field of the returned resource.
    render_avatars_at: str


class BaseUserItemResource(ItemResource):
    """Base class for user item resources.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[dict[str, str]] = {
        'render_avatars_at': 'render-avatars-at',
        **ItemResource._httprequest_params_name_map,
    }

    ######################
    # Instance variables #
    ######################

    #: HTML for rendering the avatar at specified sizes.
    #:
    #: This is only present if the resource was fetched with
    #: ``?render-avatars-at=`` (for GET requests) or
    #: ``render-avatars-at=`` (for POST requests).
    avatar_html: Optional[str]

    #: The URL for an avatar representing the user, if available.
    avatar_url: Optional[str]

    #: The URLs for an avatar representing the user.
    #:
    #: The keys of this will be screen pixel density (for example, ``1x`` or
    #: ``2x``). The values are URLs to avatar images to render for that screen
    #: type.
    avatar_urls: dict[str, str]

    #: The user's e-mail address.
    email: Optional[str]

    #: The user's first name.
    first_name: Optional[str]

    #: The user's full name (first and last).
    fullname: Optional[str]

    #: The numeric ID of the user.
    id: int

    #: Whether or not the user is active.
    #:
    #: Inactive users are not able to log in or make changes to Review Board.
    is_active: bool

    #: The user's last name.
    last_name: Optional[str]

    #: The URL to the user's page on the site.
    url: str

    #: The user's username.
    username: str


class UserGetListParams(BaseGetListParams, total=False):
    """Params for the user list GET operation.

    Version Added:
        6.0
    """

    #: Specifies whether the ``q`` parameter should also match the full name.
    #:
    #: If set, queries will also match the beginning of the first name or last
    #: name. Ignored if ``q`` is not set.
    fullname: bool

    #: Whether to include users who have been marked as inactive.
    include_inactive: bool

    #: The string to match.
    #:
    #: By default, this will match the start of the username field. If
    #: ``fullname`` is set, this will also match first and last names. This is
    #: case-sensitive.
    q: str

    #: A comma-separated list of avatar pixel sizes to render.
    #:
    #: Each of the requested sizes will be available in the ``avatar_html``
    #: field of the returned resource.
    render_avatars_at: str


class BaseUserListResource(Generic[TItemResource],
                           ListResource[TItemResource]):
    """Base class for user list resources.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[dict[str, str]] = {
        'render_avatars_at': 'render-avatars-at',
        **ListResource._httprequest_params_name_map,
    }
