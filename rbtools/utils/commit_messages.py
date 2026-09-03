"""Utilities for working with commit messages.

Version Added:
    7.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rbtools.api.resource.review_request import ReviewRequestItemResource


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
