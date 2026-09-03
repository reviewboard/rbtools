"""Utilities for commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from housekeeping import func_moved

from rbtools.deprecation import RemovedInRBTools90Warning
from rbtools.utils.commit_messages import (
    STAMP_STRING_FORMAT,
    format_commit_message,
)

if TYPE_CHECKING:
    from rbtools.api.resource.review_request import ReviewRequestItemResource


DEFAULT_OPTIONS_MAP = {
    'debug': '--debug',
    'server': '--server',
    'enable_proxy': '--disable-proxy',
    'disable_ssl_verification': '--disable-ssl-verification',
    'username': '--username',
    'password': '--password',
    'api_token': '--api-token',
    'repository_name': '--repository',
    'repository_url': '--repository-url',
    'repository_type': '--repository-type',
}


class AlreadyStampedError(Exception):
    """An error indicating the change has already been stamped."""


@func_moved(RemovedInRBTools90Warning,
            new_func=format_commit_message)
def extract_commit_message(
    review_request: ReviewRequestItemResource,
) -> str:
    """Return a commit message based on the review request.

    The commit message returned contains the Summary, Description, Bugs,
    and Testing Done fields from the review request, if available.

    Deprecated:
        7.0:
        Moved to :py:mod:`rbtools.utils.commit_messages`.

    Args:
        review_request (rbtools.api.resource.ReviewRequestItemResource):
            The review request.

    Returns:
        str:
        A commit message assembled from the review request fields.
    """
    return format_commit_message(review_request)


def build_rbtools_cmd_argv(options, options_map=DEFAULT_OPTIONS_MAP):
    """Generates a list of command line arguments from parsed command options.

    Used for building command line arguments from existing options, when
    calling another RBTools command. ``options_map`` specifies the options
    and their corresponding argument names that need to be included.
    """
    argv = []

    for option_key, arg_name in options_map.items():
        option_value = getattr(options, option_key, None)

        if option_value is True and option_key != 'enable_proxy':
            argv.append(arg_name)
        elif option_value not in (True, False, None):
            argv.extend([arg_name, option_value])

    # This is a special case where --disable-proxy is stored in
    # enable_proxy with its value inverted.
    if 'enable_proxy' in options_map and not options.enable_proxy:
        argv.append(options_map['enable_proxy'])

    return argv


def stamp_commit_with_review_url(revisions, review_request_url, tool):
    """Amend the tip revision message to include review_request_url."""
    commit_message = tool.get_raw_commit_message(revisions)
    stamp_string = STAMP_STRING_FORMAT % review_request_url

    if stamp_string in commit_message:
        raise AlreadyStampedError('This change is already stamped.')

    new_message = (commit_message.rstrip() + '\n\n' + stamp_string)
    tool.amend_commit_description(new_message, revisions)
