import json

from rbtools.api.utils import parse_mimetype


DECODER_MAP = {}


def DefaultDecoder(payload):
    """Default decoder for API payloads.

    The default decoder is used when a decoder is not found in the
    DECODER_MAP. This is a last resort which should only be used when
    something has gone wrong.
    """
    return {
        'resource': {
            'data': payload,
        },
    }

DEFAULT_DECODER = DefaultDecoder


def JsonDecoder(payload):
    return json.loads(payload)

DECODER_MAP['application/json'] = JsonDecoder


def PlainTextDecoder(payload):
    return {
        'resource': {
            'text': payload,
        },
    }

DECODER_MAP['text/plain'] = PlainTextDecoder


def PatchDecoder(payload):
    return {
        'resource': {
            'diff': payload,
        },
    }

DECODER_MAP['text/x-patch'] = PatchDecoder


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
