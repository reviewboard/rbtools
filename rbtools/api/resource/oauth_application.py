"""Resource definitions for OAuth2 applications.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

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
    from rbtools.api.resource.base_user import UserGetParams
    from rbtools.api.resource.user import UserItemResource


@resource_mimetype('application/vnd.reviewboard.org.oauth-app')
class OAuthApplicationItemResource(ItemResource):
    """Item resource for OAuth2 applications.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-oauth-application-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: How the authorization is granted to the application.
    authorization_grant_type: Literal['authorization-code',
                                      'client-credentials',
                                      'implicit',
                                      'password']

    #: The client ID.
    #:
    #: This will be used by your application to identify itself to Review
    #: Board.
    client_id: str

    #: The client secret.
    #:
    #: This should only be known to Review Board and the application.
    client_secret: str

    #: The type of client.
    #:
    #: Public clients may include the :py:attr:`client_secret` in published
    #: information (for example, JavaScript code served to a browser).
    #: Confidential clients must be able to keep the secret private.
    client_type: Literal['confidential', 'public']

    #: Whether or not this application is enabled.
    #:
    #: If disabled, authentication and API access will not be available for
    #: clients using this application.
    enabled: bool

    #: Extra information associated with the application.
    extra_data: ResourceExtraDataField

    #: The application ID.
    #:
    #: This uniquely identifies the application when communicating with the
    #: Web API.
    id: int

    #: The application name.
    name: str

    #: The list of allowed URIs to redirect to.
    redirect_uris: list[str]

    #: Whether or not users will be prompted for authentication.
    #:
    #: This field is only editable by administrators.
    skip_authorization: bool

    @api_stub
    def get_user(
        self,
        **kwargs: Unpack[UserGetParams],
    ) -> UserItemResource:
        """Get the user who created the application.

        Args:
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


class OAuthApplicationGetListParams(BaseGetListParams, total=False):
    """Params for the OAuth2 application list GET operation.

    Version Added:
        6.0
    """

    #: A user to filter for.
    #:
    #: If present, the results will be filtered to applications owned by the
    #: specified user.
    username: str


@resource_mimetype('application/vnd.reviewboard.org.oauth-apps')
class OAuthApplicationListResource(ListResource[OAuthApplicationItemResource]):
    """List resource for OAuth2 applications.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-oauth-application-list-resource`.

    Version Added:
        6.0
    """
