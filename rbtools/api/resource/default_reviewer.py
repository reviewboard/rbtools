"""Resource definitions for default reviewers.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ItemResource,
    ListResource,
    resource_mimetype,
)

if TYPE_CHECKING:
    from rbtools.api.resource.base import ResourceLinkField, ResourceListField
    from rbtools.api.resource.review_group import ReviewGroupItemResource
    from rbtools.api.resource.user import UserItemResource


@resource_mimetype('application/vnd.reviewboard.org.default-reviewer')
class DefaultReviewerItemResource(ItemResource):
    """Item resource for default reviewers.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The regular expression that is used to match files uploaded in a diff.
    file_regex: str

    #: The groups that this default reviewer will add.
    groups: ResourceListField[ResourceLinkField[ReviewGroupItemResource]]

    #: The numeric ID of the default reviewer.
    id: int

    #: A descriptive name of the default reviewer.
    name: str

    #: The repositories that this default reviewer will match against.
    # TODO
    # repositories: ResourceListField[
    #     ResourceLinkField[RepositoryItemResource]]

    #: The users that this default reviewer will add.
    users: ResourceListField[ResourceLinkField[UserItemResource]]


class DefaultReviewerGetListParams(BaseGetListParams, total=False):
    """Params for the default reviewer list GET operation.

    Version Added:
        6.0
    """

    #: A comma-separated list of group names to match.
    groups: str

    #: A comma-separated list of repository IDs to match.
    repositories: str

    #: A comma-separated list of usernames to match.
    users: str


@resource_mimetype('application/vnd.reviewboard.org.default-reviewers')
class DefaultReviewerListResource(ListResource[DefaultReviewerItemResource]):
    """List resource for default reviewers.

    Version Added:
        6.0
    """
