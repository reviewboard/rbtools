from __future__ import unicode_literals

from rbtools.api.resource import (CountResource, ItemResource,
                                  ListResource, RESOURCE_MAP)
from rbtools.api.utils import rem_mime_format


SPECIAL_KEYS = set(('links', 'total_results', 'stat', 'count'))


def create_resource(transport, payload, url, mime_type=None,
                    item_mime_type=None, guess_token=True):
    """Construct and return a resource object.

    The mime type will be used to find a resource specific base class.
    Alternatively, if no resource specific base class exists, one of
    the generic base classes, Resource or ResourceList, will be used.

    If an item mime type is provided, it will be used by list
    resources to construct item resources from the list.

    If 'guess_token' is True, we will try and guess what key the
    resources body lives under. If False, we assume that the resource
    body is the body of the payload itself. This is important for
    constructing Item resources from a resource list.
    """

    # Determine the key for the resources data.
    token = None

    if guess_token:
        other_keys = set(payload.keys()).difference(SPECIAL_KEYS)
        if len(other_keys) == 1:
            token = other_keys.pop()

    # Select the base class for the resource.
    if 'count' in payload:
        resource_class = CountResource
    elif mime_type and rem_mime_format(mime_type) in RESOURCE_MAP:
        resource_class = RESOURCE_MAP[rem_mime_format(mime_type)]
    elif token and isinstance(payload[token], list):
        resource_class = ListResource
    else:
        resource_class = ItemResource

    return resource_class(transport, payload, url, token=token,
                          item_mime_type=item_mime_type)
