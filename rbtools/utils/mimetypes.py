"""Utilities for working with MIME types.

Version Added:
    5.0
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

import puremagic
from housekeeping import deprecate_non_keyword_only_args
from typing_extensions import TypedDict

from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.utils.filesystem import is_exe_in_path


logger = logging.getLogger(__name__)


class MIMEType(TypedDict):
    """A MIME type, parsed into its component parts.

    Version Added:
        5.0
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
    #: This will include vendor information, if present.
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


def parse_mimetype(
    mime_type: str,
) -> MIMEType:
    """Parse a MIME type into its component parts.

    Version Added:
        5.0

    Args:
        mime_type (str):
            The MIME type to parse.

    Returns:
        ParsedMIMEType:
        The type, parsed into its component parts.

    Raises:
        ValueError:
            The given MIME type could not be parsed.
    """
    parts = mime_type.split(';')[0].split('/')

    if len(parts) != 2:
        raise ValueError('f"{mime_type}" is not a valid MIME type')

    main_type, sub_type = parts

    sub_type_parts = sub_type.split('+', 1)

    if len(sub_type_parts) == 1:
        vendor = ''
        format = sub_type_parts[0]
    else:
        vendor = sub_type_parts[0]
        format = sub_type_parts[1]

    return MIMEType(
        type=mime_type,
        main_type=main_type,
        sub_type=sub_type,
        vendor=vendor,
        format=format)


DEFAULT_MIMETYPE = 'application/octet-stream'
_has_file_exe = None


@deprecate_non_keyword_only_args(RemovedInRBTools70Warning)
def guess_mimetype(
    *,
    data: bytes,
    filename: Optional[str] = None,
) -> str:
    """Guess the MIME type of the given file content.

    Version Added:
        5.0

    Args:
        data (bytes):
            The file content.

    Returns:
        str:
        The guessed MIME type.
    """
    global _has_file_exe

    if _has_file_exe is None:
        _has_file_exe = is_exe_in_path('file')

    if not _has_file_exe:
        try:
            types = puremagic.magic_string(data)
        except puremagic.PureError:
            return DEFAULT_MIMETYPE

        if len(types) > 0:
            return types[0].mime_type

        return DEFAULT_MIMETYPE

    mimetype: Optional[str] = None

    try:
        p = subprocess.Popen(['file', '--mime-type', '-b', '-'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE)

        assert p.stdin is not None
        assert p.stdout is not None

        # Write the content of the file in 4k chunks until the ``file``
        # utility has enough data to make a determination.
        for i in range(0, len(data), 4096):
            try:
                p.stdin.write(data[i:i + 4096])
            except OSError:
                # ``file`` closed, so we hopefully have an answer.
                break

        try:
            p.stdin.close()
        except OSError:
            # This was closed by `file`.
            #
            # Note that we may not get this on all Python environments. A
            # closed pipe doesn't necessarily fail when calling close() again.
            pass

        ret = p.wait()

        if ret == 0:
            result = p.stdout.read().strip().decode('utf-8')

            if result:
                mimetype = result
    except Exception as e:
        logger.exception('Unexpected error when determining mimetype '
                         'using `file`: %s',
                         e)

    return mimetype or DEFAULT_MIMETYPE


def match_mimetype(
    pattern: MIMEType,
    test: MIMEType,
) -> float:
    """Return a score for how well the pattern matches the mimetype.

    This is an ordered list of precedence (``_`` indicates non-match):

    ======================= ==========
    Format                  Precedence
    ======================= ==========
    ``Type/Vendor+Subtype`` 2.0
    ``Type/Subtype``        1.9
    ``Type/*``              1.8
    ``*/Vendor+Subtype``    1.7
    ``*/_     +Subtype``    1.6
    ``*/*``                 1.5
    ``_``                   0
    ======================= ==========

    Version Added:
        5.0

    Args:
        pattern (MIMEType):
            A parsed mimetype pattern to score. This is a 3-tuple of the type,
            subtype, and parameters as returned by
            :py:func:`mimeparse.parse_mime_type`. This may include ``*``
            wildcards.

        test (MIMEType):
            A parsed mimetype to match against the pattern. This is a 3-tuple
            of the type, subtype, and parameters as returned by
            :py:func:`mimeparse.parse_mime_type`.

    Returns:
        float:
        The resulting score for the match.
    """
    EXACT_TYPE = 1.0
    ANY_TYPE = 0.7
    EXACT_SUBTYPE = 0.9
    ANY_SUBTYPE = 0.8
    VND_SUBTYPE = 0.1

    pattern_type = pattern['main_type']
    pattern_subtype = pattern['format']
    pattern_vendor = pattern['vendor']
    test_type = test['main_type']
    test_subtype = test['format']
    test_vendor = test['vendor']

    score = 0

    if pattern_type == test_type:
        score += EXACT_TYPE
    elif pattern_type == '*':
        score += ANY_TYPE
    else:
        return 0

    if pattern_subtype == test_subtype:
        score += EXACT_SUBTYPE
    elif pattern_subtype == '*':
        score += ANY_SUBTYPE
    else:
        return 0

    if pattern_vendor != '*' and pattern_vendor == test_vendor:
        score += VND_SUBTYPE

    return score
