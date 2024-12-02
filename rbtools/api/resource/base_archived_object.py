"""Base resource definitions for archived object resources.

The archived/muted object resources are special because they don't support
GET at all. This means we can't use our normal fetch-then-introspect
methods in order to populate links.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import Generic, Optional, TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    LINKS_TOK,
    ListResource,
    TItemResource,
)

if TYPE_CHECKING:
    from typelets.json import JSONDict

    from rbtools.api.transport import Transport


class BaseArchivedObjectItemResource(ItemResource):
    """Base class for archived object item resources.

    Version Added:
        6.0
    """

    def __init__(
        self,
        transport: Transport,
        payload: JSONDict,
        url: str,
        token: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Initialize the resource.

        Args:
            transport (rbtools.api.transport.Transport):
                The API transport.

            payload (dict):
                The request payload.

            url (str):
                The URL for the resource.

            token (str, optional):
                The key within the request payload for the resource data.

            **kwargs (dict):
                Keyword arguments to pass through to the parent class.
        """
        payload[LINKS_TOK] = {
            'self': {
                'href': url,
                'method': 'GET',
            },
            'delete': {
                'href': url,
                'method': 'DELETE',
            },
        }

        super().__init__(
            transport=transport,
            payload=payload,
            url=url,
            token=token,
            **kwargs)


class BaseArchivedObjectListResource(Generic[TItemResource],
                                     ListResource[TItemResource]):
    """Base class for archived object list resources.

    Version Added:
        6.0
    """

    def __init__(
        self,
        transport: Transport,
        payload: JSONDict,
        url: str,
        token: Optional[str] = None,
        item_mime_type: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Initialize the resource.

        Args:
            transport (rbtools.api.transport.Transport):
                The API transport.

            payload (dict):
                The request payload.

            url (str):
                The URL for the resource.

            token (str, optional):
                The key within the request payload for the resource data.

            item_mime_type (str, optional):
                The mimetype of the items within the list.

            **kwargs (dict):
                Keyword arguments to pass through to the parent class.
        """
        payload[LINKS_TOK] = {
            'self': {
                'href': url,
                'method': 'GET',
            },
            'create': {
                'href': url,
                'method': 'POST',
            },
        }

        super().__init__(
            transport=transport,
            payload=payload,
            url=url,
            token=token,
            item_mime_type=item_mime_type,
            **kwargs)
