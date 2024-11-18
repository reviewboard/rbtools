"""Base class for review request resources.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import ItemResource, api_stub

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import (
        ResourceExtraDataField,
        ResourceLinkField,
        ResourceListField,
        TextType,
    )
    from rbtools.api.resource.base_user import UserGetParams
    from rbtools.api.resource.review_group import ReviewGroupItemResource
    from rbtools.api.resource.review_request import ReviewRequestItemResource
    from rbtools.api.resource.user import UserItemResource


class BaseReviewRequestItemResource(ItemResource):
    """Base class for review request item resources.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The branch that the code was changed on or will be committed to.
    #:
    #: This is a free-form field that can store any text.
    branch: str

    #: The list of bugs closed or referenced by this change.
    bugs_closed: ResourceListField[str]

    #: The commit that the review request represents.
    commit_id: str

    #: The list of review requests that this review request depends on.
    depends_on: ResourceListField[ReviewRequestItemResource]

    #: The review request's description.
    description: str

    #: The current or forced text type for the ``description`` field.
    description_text_type: TextType

    #: Extra data as part of the review request.
    extra_data: ResourceExtraDataField

    #: The date and time that the review request was last updated.
    last_updated: str

    #: The review request's brief summary.
    summary: str

    #: The list of review groups who were requested to review this change.
    target_groups: ResourceListField[
        ResourceLinkField[ReviewGroupItemResource]]

    #: The list of users who were requested to review this change.
    target_people: ResourceListField[ResourceLinkField[UserItemResource]]

    #: The information on the testing that was done for the change.
    testing_done: str

    #: The current or forced text type for the ``testing_done`` field.
    testing_done_text_type: TextType

    @api_stub
    def get_submitter(
        self,
        **kwargs: Unpack[UserGetParams],
    ) -> UserItemResource:
        """Get the submitter of the review request.

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
