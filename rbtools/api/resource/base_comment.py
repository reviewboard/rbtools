"""Base class for comment resources.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import Literal, Optional, TYPE_CHECKING

from rbtools.api.resource.base import ItemResource, TextType, api_stub

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import ResourceExtraDataField
    from rbtools.api.resource.base_user import UserGetParams
    from rbtools.api.resource.user import UserItemResource


class BaseCommentItemResource(ItemResource):
    """Base class for comment item resources.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: Extra data as part of the comment.
    extra_data: ResourceExtraDataField

    #: The numeric ID of the comment
    id: int

    #: Whether or not the comment opens an issue.
    issue_opened: bool

    #: The status of the issue.
    issue_status: Optional[Literal[
        'dropped',
        'open',
        'resolved',
        'verifying-dropped',
        'verifying-resolved',
    ]]

    #: Whether or not the comment is part of a public review.
    public: bool

    #: The comment text.
    text: str

    #: The text type for the comment text.
    text_type: TextType

    #: The date and time that the comment was made, in ISO-8601 format.
    timestamp: str

    @api_stub
    def get_user(
        self,
        **kwargs: Unpack[UserGetParams],
    ) -> UserItemResource:
        """Get the user who made the comment.

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
