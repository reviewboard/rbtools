from __future__ import unicode_literals


def parse_mimetype(mime_type):
    """Parse the mime type in to it's component parts."""
    types = mime_type.split(';')[0].split('/')

    ret_val = {
        'type': mime_type,
        'main_type': types[0],
        'sub_type': types[1]
    }

    sub_type = types[1].split('+')
    ret_val['vendor'] = ''
    if len(sub_type) == 1:
        ret_val['format'] = sub_type[0]
    else:
        ret_val['format'] = sub_type[1]
        ret_val['vendor'] = sub_type[0]

    vendor = ret_val['vendor'].split('.')
    if len(vendor) > 1:
        ret_val['resource'] = vendor[-1].replace('-', '_')
    else:
        ret_val['resource'] = ''

    return ret_val


def rem_mime_format(mime_type):
    """Strip the subtype from a mimetype, leaving vendor specific information.

    Removes the portion of the subtype after a +, or the entire
    subtype if no vendor specific type information is present.
    """
    if mime_type.rfind('+') != 0:
        return mime_type.rsplit('+', 1)[0]
    else:
        return mime_type.rsplit('/', 1)[0]
