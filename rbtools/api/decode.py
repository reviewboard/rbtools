"""API payload decoders."""

import json
from typing import Dict, Union

from rbtools.api.utils import parse_mimetype
from rbtools.utils.encoding import force_unicode


def DefaultDecoder(
    payload: Union[bytes, str],
) -> Dict:
    """Default decoder for API payloads.

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
    payload: Union[bytes, str],
) -> Dict:
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
    payload: Union[bytes, str],
    mime_type: str,
) -> Dict:
    """Decode a Web API response.

    The body of a Web API response will be decoded into a dictionary,
    according to the provided mime_type.
    """
    mime = parse_mimetype(mime_type)

    format = '%s/%s' % (mime['main_type'], mime['format'])
    decoder = DECODER_MAP.get(format, DefaultDecoder)

    return decoder(payload)
