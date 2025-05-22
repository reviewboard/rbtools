"""API payload decoders."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rbtools.api.utils import parse_mimetype
from rbtools.utils.encoding import force_unicode

if TYPE_CHECKING:
    from typelets.json import JSONDict


def DefaultDecoder(
    payload: bytes | str,
) -> JSONDict:
    """Decode API payloads with no supported type.

    The default decoder is used when a decoder is not found in the
    DECODER_MAP. This will stick the body of the response into the
    'data' field.

    Args:
        payload (bytes or str):
            The API payload.

    Returns:
        dict:
        The decoded API object.
    """
    return {
        'resource': {
            'data': payload,
        },
    }


def JsonDecoder(
    payload: bytes | str,
) -> JSONDict:
    """Decode an application/json-encoded API response.

    Args:
        payload (bytes or str):
            The API payload.

    Returns:
        dict:
        The decoded API object.
    """
    return json.loads(force_unicode(payload))


#: Mapping from API format to decoder method.
#:
#: Type: dict
DECODER_MAP = {
    'application/json': JsonDecoder,
}


def decode_response(
    payload: bytes | str,
    mime_type: str,
) -> JSONDict:
    """Decode a Web API response.

    The body of a Web API response will be decoded into a dictionary,
    according to the provided mime_type.
    """
    mime = parse_mimetype(mime_type)
    main_type = mime['main_type']
    mime_format = mime['format']

    api_format = f'{main_type}/{mime_format}'
    decoder = DECODER_MAP.get(api_format, DefaultDecoder)

    return decoder(payload)
