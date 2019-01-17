from __future__ import unicode_literals

import json

from rbtools.api.utils import parse_mimetype
from rbtools.utils.encoding import force_unicode


DECODER_MAP = {}


def DefaultDecoder(payload):
    """Default decoder for API payloads.

    The default decoder is used when a decoder is not found in the
    DECODER_MAP. This will stick the body of the response into the
    'data' field.
    """
    return {
        'resource': {
            'data': payload,
        },
    }


DEFAULT_DECODER = DefaultDecoder


def JsonDecoder(payload):
    # In Python 3, the payload can be bytes, not str, and json.loads explicitly
    # requires decoded strings.
    return json.loads(force_unicode(payload))


DECODER_MAP['application/json'] = JsonDecoder


def decode_response(payload, mime_type):
    """Decode a Web API response.

    The body of a Web API response will be decoded into a dictionary,
    according to the provided mime_type.
    """
    mime = parse_mimetype(mime_type)

    format = '%s/%s' % (mime['main_type'], mime['format'])

    if format in DECODER_MAP:
        decoder = DECODER_MAP[format]
    else:
        decoder = DEFAULT_DECODER

    return decoder(payload)
