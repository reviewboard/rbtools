"""Resource creation method(s)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from rbtools.api.resource import (CountResource,
                                  ItemResource,
                                  ListResource,
                                  Resource,
                                  RESOURCE_MAP)
from rbtools.api.utils import rem_mime_format

if TYPE_CHECKING:
    from typelets.json import JSONDict

    from rbtools.api.transport import Transport


SPECIAL_KEYS = {
    'links',
    'total_results',
    'stat',
    'count',
}


def create_resource(
    transport: Transport,
    payload: JSONDict,
    url: str,
    mime_type: Optional[str] = None,
    item_mime_type: Optional[str] = None,
    guess_token: bool = True,
    force_resource_type: Optional[type[Resource]] = None,
) -> Resource:
    """Construct and return a resource object.

    Version Changed:
        6.0:
        * Added the ``force_resource_type`` argument.

    Args:
        transport (rbtools.api.transport.Transport):
            The API transport.

        payload (dict):
            The payload returned from the API endpoint.

        url (str):
            The URL of the API endpoint.

        mime_type (str, optional):
            The MIME type of the API response. This is used to find a resource
            specific class. If no resource specific class exists, one of the
            generic base classes (:py:class:`~rbtools.api.resource.Resource`
            or :py:class:`~rbtools.api.resource.ResourceList`) will be used.

        item_mime_type (str, optional):
            The MIME type to use when constructing individual items within a
            list resource.

        guess_token (bool, optional):
            Whether to guess the key for the API response body. If ``False``,
            we assume that the resource body is the body of the payload itself.
            This is important for constructing item resources from a resource
            list.

        force_resource_type (type, optional):
            The resource class to instantiate.

            Version Added:
                6.0

    Returns:
        rbtools.api.resource.Resource:
        The resource instance.
    """
    # Determine the key for the resources data.
    token = None

    if guess_token:
        other_keys = set(payload.keys()).difference(SPECIAL_KEYS)

        if len(other_keys) == 1:
            token = other_keys.pop()

    resource_class: type[Resource]

    # Select the base class for the resource.
    if force_resource_type is not None:
        resource_class = force_resource_type
    elif 'count' in payload:
        resource_class = CountResource
    elif mime_type and rem_mime_format(mime_type) in RESOURCE_MAP:
        resource_class = RESOURCE_MAP[rem_mime_format(mime_type)]
    elif token and isinstance(payload[token], list):
        resource_class = ListResource
    else:
        resource_class = ItemResource

    if issubclass(resource_class, ListResource):
        assert token is not None

    return resource_class(transport, payload, url, token=token,
                          item_mime_type=item_mime_type)
