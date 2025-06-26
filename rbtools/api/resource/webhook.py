"""Resource definitions for WebHooks.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)

if TYPE_CHECKING:
    from rbtools.api.resource.base import (
        ResourceExtraDataField,
        ResourceLinkField,
        ResourceListField,
    )
    from rbtools.api.resource.repository import RepositoryItemResource


@resource_mimetype('application/vnd.reviewboard.org.webhook')
class WebHookItemResource(ItemResource):
    """Item resource for WebHooks.

    This corresponds to Review Board's :ref:`rb:webapi2.0-web-hook-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: What review requests the WebHook applies to.
    #:
    #: In the case of ``custom``, the repositories are specified in the
    #: repositories field.
    apply_to: Literal['all', 'none', 'custom']

    #: An optional custom payload.
    custom_content: str

    #: Whether or not the WebHook is enabled.
    enabled: bool

    #: The encoding for the payload.
    encoding: Literal[
        'application/json',
        'application/xml',
        'application/x-www-form-urlencoded',
    ]

    #: A list of events that will cause the WebHook to trigger.
    events: list[str]

    #: Extra data as part of the WebHook.
    extra_data: ResourceExtraDataField

    #: The numeric ID of the WebHook.
    id: int

    #: The list of repositories this applies to.
    repositories: ResourceListField[ResourceLinkField[RepositoryItemResource]]

    #: An optional HMAC digest for the WebHook payload.
    #:
    #: If this is specified, the payload will be signed with it.
    secret: str

    #: The URL to make HTTP requests against.
    url: str


@resource_mimetype('application/vnd.reviewboard.org.webhooks')
class WebHookListResource(ListResource[WebHookItemResource]):
    """List resource for WebHooks.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-web-hook-list-resource`.

    Version Added:
        6.0
    """
