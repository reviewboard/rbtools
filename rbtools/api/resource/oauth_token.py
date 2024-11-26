"""Resource definitions for OAuth2 tokens.

Version Added:
    6.0
"""

from __future__ import annotations

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)


@resource_mimetype('application/vnd.reviewboard.org.oauth-token')
class OAuthTokenItemResource(ItemResource):
    """Item resource for OAuth2 tokens.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The name of the application this token is for.
    application: str

    #: When this token is set to expire.
    #:
    #: This is a date/time in ISO-8601 format.
    expires: str

    #: The scopes this token has access to.
    scope: list[str]

    #: The access token.
    token: str


@resource_mimetype('application/vnd.reviewboard.org.oauth-tokens')
class OAuthTokenListResource(ListResource[OAuthTokenItemResource]):
    """List resource for OAuth2 tokens.

    Version Added:
        6.0
    """
