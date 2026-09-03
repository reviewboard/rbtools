"""Utilities for working with commit messages.

Version Added:
    7.0
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, TypedDict

from typing_extensions import NotRequired

if TYPE_CHECKING:
    from typing import TypeAlias

    from rbtools.api.resource.review_request import ReviewRequestItemResource


class ParsedCommitMessage(TypedDict):
    """The result of parsing a commit message.

    The ``summary`` key is always present. Every other key is optional, and
    is only present if the parser found a value for it.

    The default parser only sets ``summary``, ``description``,
    ``testing_done``, and ``bugs_closed``. The remaining keys are here for
    custom parsers to set.

    Custom parsers may set additional keys. If these match known field names in
    the review request, they will be set when guessing fields is enabled.

    Version Added:
        7.0
    """

    #: The summary of the commit message.
    #:
    #: This is the first line of the commit message.
    #:
    #: Type:
    #:     str
    summary: str

    #: The description of the commit message.
    #:
    #: This is the body text between the summary and any recognized field
    #: headers.
    #:
    #: Type:
    #:     str
    description: NotRequired[str]

    #: The testing done information from the commit message.
    #:
    #: This is the text following a ``Testing Done:`` header.
    #:
    #: Type:
    #:     str
    testing_done: NotRequired[str]

    #: The bugs closed by the commit.
    #:
    #: This is the comma-separated list of bug IDs following a
    #: ``Bugs closed:`` header.
    #:
    #: Type:
    #:     str
    bugs_closed: NotRequired[str]


#: A callable that parses a raw commit message into structured fields.
#:
#: Version Added:
#:     7.0
CommitMessageParser: TypeAlias = Callable[[str], ParsedCommitMessage | None]


#: The format string used to specify a URL to a review request in commits.
#:
#: Commands that prepare a commit message for pushing, such as rbt stamp,
#: rbt patch, and rbt land, must use this format to indicate the URL to the
#: matching review request. Review Board will parse the commit messages when
#: executing any post-receive hooks, looking for this string and a valid URL.
#:
#: Version Changed:
#:     7.0:
#:     Moved from :py:mod:`rbtools.utils.commands`
STAMP_STRING_FORMAT = 'Reviewed at %s'


#: Pattern matching a "Testing Done:" header.
#:
#: Version Added:
#:     7.0
_TESTING_DONE_RE = re.compile(
    r'^Testing [Dd]one:\n',
    re.MULTILINE,
)

#: Pattern matching a "Bugs closed:" header.
#:
#: This also matches "Bugs fixed:", and allows either capitalization of the
#: second word.
#:
#: Version Added:
#:     7.0
_BUGS_CLOSED_RE = re.compile(
    r'^Bugs (?:[Cc]losed|[Ff]ixed):\s*(.+)$',
    re.MULTILINE,
)


#: Pattern matching a "Reviewed at <url>" line.
#:
#: Version Added:
#:     7.0
_REVIEWED_AT_RE = re.compile(
    r'^Reviewed at https?://\S+$',
    re.MULTILINE,
)


def parse_commit_message(
    message: str,
    custom_parser: (CommitMessageParser | None) = None,
) -> ParsedCommitMessage | None:
    """Parse a commit message into structured fields.

    This is the inverse of :py:func:`format_commit_message`. It extracts
    ``summary``, ``description``, ``testing_done``, and ``bugs_closed``
    from a raw commit message string.

    The ``Testing Done:`` and ``Bugs closed:`` fields, as well as any
    ``Reviewed at <url>`` lines, are stripped from the description so
    that it does not contain duplicated content.

    Version Added:
        7.0

    Args:
        message (str):
            The raw commit message to parse.

        custom_parser (callable, optional):
            A callable that replaces the default parsing logic. It must
            accept a single string argument and return a
            :py:class:`ParsedCommitMessage`.

    Returns:
        ParsedCommitMessage:
        A dictionary containing the parsed fields.
    """
    if custom_parser is not None:
        return custom_parser(message)

    message = message.strip()

    if not message:
        return None

    lines = message.split('\n')

    result: ParsedCommitMessage = {
        'summary': lines[0].strip(),
    }

    # If we have a summary line, then a blank line, everything after is the
    # description. Otherwise just use the same text as summary.
    if len(lines) >= 3 and not lines[1].strip():
        body = '\n'.join(lines[2:])
    else:
        body = message

    # Extract "Bugs closed:" field.
    bugs_match = _BUGS_CLOSED_RE.search(body)

    if bugs_match:
        result['bugs_closed'] = bugs_match.group(1).strip()
        body = body[:bugs_match.start()] + body[bugs_match.end():]

    # Extract "Testing Done:" field.
    testing_match = _TESTING_DONE_RE.search(body)

    if testing_match:
        # Everything from the header to the next known section or end.
        rest = body[testing_match.end():]

        # Find the end of the Testing Done content: either the next
        # known field header, a "Reviewed at" line, or end of string.
        end_pattern = re.compile(
            r'^(?:Bugs (?:[Cc]losed|[Ff]ixed):|Reviewed at https?://\S+$)',
            re.MULTILINE,
        )
        end_match = end_pattern.search(rest)

        if end_match:
            testing_done_text = rest[:end_match.start()].strip()
        else:
            testing_done_text = rest.strip()

        if testing_done_text:
            result['testing_done'] = testing_done_text

        body = body[:testing_match.start()] + (
            rest[end_match.start():] if end_match else ''
        )

    # Strip "Reviewed at <url>" lines.
    body = _REVIEWED_AT_RE.sub('', body)

    # Clean up the description.
    description = body.strip()

    if description:
        result['description'] = description

    return result


def format_commit_message(
    review_request: ReviewRequestItemResource,
) -> str:
    """Return a commit message based on the review request.

    The commit message returned contains the Summary, Description, Bugs,
    and Testing Done fields from the review request, if available.

    Version Changed:
        7.0:
        Moved from :py:mod:`rbtools.utils.commands`.

    Args:
        review_request (rbtools.api.resource.ReviewRequestItemResource):
            The review request.

    Returns:
        str:
        A commit message assembled from the review request fields.
    """
    info = []

    summary = review_request.summary
    description = review_request.description
    testing_done = review_request.testing_done

    if not description.startswith(summary):
        info.append(summary)

    info.append(description)

    if testing_done:
        info.append(f'Testing Done:\n{testing_done}')

    if review_request.bugs_closed:
        bugs = ', '.join(review_request.bugs_closed)

        info.append(f'Bugs closed: {bugs}')

    info.append(STAMP_STRING_FORMAT % review_request.absolute_url)

    return '\n\n'.join(info)
