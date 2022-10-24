"""Utilities used by the API interfaces."""

from typing_extensions import TypedDict


class ParsedMIMEType(TypedDict):
    """A MIME type, parsed into its component parts.

    Version Added:
        4.0
    """

    #: The full MIME type.
    #:
    #: Type:
    #:     str
    type: str

    #: Main type (For example, "application" for "application/octet-stream")
    #:
    #: Type:
    #:     str
    main_type: str

    #: Sub-type (for example, "plain" for "text/plain").
    #:
    #: Type:
    #:     str
    sub_type: str

    #: The vendor tag, if available.
    #:
    #: For example, "vnd.reviewboard.org.test" in
    #: "application/vnd.reviewboard.org.test+json".
    #:
    #: Type:
    #:     str
    vendor: str

    #: The sub-type format, if available.
    #:
    #: For example, "json" in "application/vnd.reviewboard.org.test+json".
    #:
    #: Type:
    #:     str
    format: str

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
    """Parse a mime type into its component parts.

    Args:
        mime_type (str):
            The MIME type to parse.

    Returns:
        ParsedMIMEType:
        The type, parsed into its component parts.
    """
    types = mime_type.split(';')[0].split('/')

    sub_type = types[1].split('+')

    if len(sub_type) == 1:
        vendor = ''
        format = sub_type[0]
    else:
        vendor = sub_type[0]
        format = sub_type[1]

    vendor_parts = vendor.split('.')

    if len(vendor_parts) > 1:
        resource = vendor_parts[-1].replace('-', '_')
    else:
        resource = ''

    return ParsedMIMEType(
        type=mime_type,
        main_type=types[0],
        sub_type=types[0],
        vendor=vendor,
        format=format,
        resource=resource)


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
