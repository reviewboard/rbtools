"""Resource definition for the session resource.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import ItemResource, api_stub, resource_mimetype

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base_user import UserGetParams
    from rbtools.api.resource.user import UserItemResource


@resource_mimetype('application/vnd.reviewboard.org.session')
class SessionResource(ItemResource):
    """Resource for the session.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: Whether the session is logged in.
    authenticated: bool

    @api_stub
    def get_user(
        self,
        **kwargs: Unpack[UserGetParams],
    ) -> UserItemResource:
        """Get the logged-in user for the session.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.UserItemResource:
            The user item resource for the logged-in user.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError
