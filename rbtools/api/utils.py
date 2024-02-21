"""API-specific MIME type utilities."""

from __future__ import annotations

from typing import cast

from rbtools.utils import mimetypes


class ParsedMIMEType(mimetypes.MIMEType):
    """A parsed MIME type for resources.

    Version Added:
        4.0
    """

    #: The particular API resource name, if available.
    #:
    #: For example, "test" in "application/vnd.reviewboard.org.test+json".
    #:
    #: Type:
    #:     str
    resource: str


def parse_mimetype(
    mime_type: str,
) -> ParsedMIMEType:
    """Parse a MIME type into its component parts.

    Args:
        mime_type (str):
            The MIME type to parse.

    Returns:
        ParsedMIMEType:
        The type, parsed into its component parts.
    """
    parsed = cast(ParsedMIMEType, mimetypes.parse_mimetype(mime_type))

    vendor_parts = parsed['vendor'].split('.')

    if len(vendor_parts) > 1:
        resource = vendor_parts[-1].replace('-', '_')
    else:
        resource = ''

    parsed['resource'] = resource

    return parsed


def rem_mime_format(
    mime_type: str,
) -> str:
    """Strip the subtype from a mimetype, leaving vendor specific information.

    Removes the portion of the subtype after a +, or the entire
    subtype if no vendor specific type information is present.

    Args:
        mime_type (str):
            The MIME type string to modify.

    Returns:
        str:
        The MIME type less any subtypes.
    """
    if mime_type.rfind('+') != 0:
        return mime_type.rsplit('+', 1)[0]
    else:
        return mime_type.rsplit('/', 1)[0]
