"""Resource definitions for change descriptions.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TypedDict, TYPE_CHECKING

from typing_extensions import NotRequired

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    TextType,
    resource_mimetype,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from typelets.json import JSONValue


class ChangedField(TypedDict):
    """Definition for a changed field.

    Version Added:
        6.0
    """

    #: Items that were added to the field.
    #:
    #: The particular value of this is dependent on the type of the field. See
    #: the :ref:`change resource documentation <webapi2.0-change-resource>` for
    #: the Review Board Web API for details.
    added: NotRequired[JSONValue]

    #: The old value of the field.
    #:
    #: The particular value of this is dependent on the type of the field. See
    #: the :ref:`change resource documentation <webapi2.0-change-resource>` for
    #: the Review Board Web API for details.
    old: NotRequired[JSONValue]

    #: The new value of the field.
    #:
    #: The particular value of this is dependent on the type of the field. See
    #: the :ref:`change resource documentation <webapi2.0-change-resource>` for
    #: the Review Board Web API for details.
    new: NotRequired[JSONValue]

    #: Items that were removed from the field.
    #:
    #: The particular value of this is dependent on the type of the field. See
    #: the :ref:`change resource documentation <webapi2.0-change-resource>` for
    #: the Review Board Web API for details.
    removed: NotRequired[JSONValue]


@resource_mimetype('application/vnd.reviewboard.org.review-request-change')
class ChangeItemResource(ItemResource):
    """Item resource for review request changes.

    This corresponds to Review Board's :ref:`rb:webapi2.0-change-resource`.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The fields that were changed.
    fields_changed: Mapping[str, ChangedField]

    #: The numeric ID of the change description.
    id: int

    #: The description of the text written by the submitter.
    text: str

    #: The text type for the text attribute.
    text_type: TextType

    #: The date and time that the change was made, in ISO-8601 format.
    timestamp: str


@resource_mimetype('application/vnd.reviewboard.org.review-request-changes')
class ChangeListResource(ListResource[ChangeItemResource]):
    """List resource for review request changes.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-change-list-resource`.

    Version Added:
        6.0
    """
