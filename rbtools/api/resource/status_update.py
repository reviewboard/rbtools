"""Resource definitions for status updates.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import ClassVar, Literal, TYPE_CHECKING

from rbtools.api.resource.base import (
    BaseGetListParams,
    ItemResource,
    ListResource,
    api_stub,
    resource_mimetype,
)

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import (
        BaseGetParams,
        ResourceExtraDataField,
    )
    from rbtools.api.resource.change import ChangeItemResource


@resource_mimetype('application/vnd.reviewboard.org.status-update')
class StatusUpdateItemResource(ItemResource):
    """Item resource for status updates.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: A user-visible description of the status update.
    description: str

    #: Extra data as part of the status update.
    extra_data: ResourceExtraDataField

    #: The ID of the status update.
    id: int

    #: A unique identifier for the service providing the status update.
    service_id: str

    #: The current state of the status update.
    state: Literal['pending', 'done-success', 'done-failure', 'error',
                   'timed-out']

    #: A user-visible short summary of the status update.
    summary: str

    #: An optional timeout for pending status updates, measured in seconds.
    timeout: int

    #: An optional URL to link to for more details about the status update.
    url: str

    #: The text to use for the link.
    url_text: str

    @api_stub
    def get_change(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ChangeItemResource:
        """Get the change description for this status update.

        If a status update is connected to a review request update, this will
        return the change description.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ChangeItemResource:
            The change description item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    # TODO get_review stub


class StatusUpdateGetListParams(BaseGetListParams, total=False):
    """Params for the status update list GET operation.

    Version Added:
        6.0
    """

    #: The ID of the change description to get status updates for.
    change: int

    #: The service ID to query for.
    service_id: str

    #: The state to query for.
    state: Literal['pending', 'done-success', 'done-failure', 'error']


@resource_mimetype('application/vnd.reviewboard.org.status-updates')
class StatusUpdateListResource(ListResource[StatusUpdateItemResource]):
    """List resource for status updates.

    Version Added:
        6.0
    """

    _httprequest_params_name_map: ClassVar[dict[str, str]] = {
        'service_id': 'service-id',
        **ListResource._httprequest_params_name_map,
    }
