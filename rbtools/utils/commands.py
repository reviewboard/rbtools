from __future__ import unicode_literals

import six

from rbtools.api.errors import APIError
from rbtools.commands import CommandError


DEFAULT_OPTIONS_MAP = {
    'debug': '--debug',
    'server': '--server',
    'enable_proxy': '--disable-proxy',
    'username': '--username',
    'password': '--password',
    'api_token': '--api-token',
    'repository_name': '--repository',
    'repository_url': '--repository-url',
    'repository_type': '--repository-type',
}


def get_review_request(review_request_id, api_root):
    """Returns the review request resource for the given ID."""
    try:
        review_request = api_root.get_review_request(
            review_request_id=review_request_id)
    except APIError as e:
        raise CommandError('Error getting review request %s: %s'
                           % (review_request_id, e))

    return review_request


def extract_commit_message(review_request):
    """Returns a commit message based on the review request.

    The commit message returned contains the Summary, Description, Bugs,
    and Testing Done fields from the review request, if available.
    """
    info = []

    summary = review_request.summary
    description = review_request.description
    testing_done = review_request.testing_done

    if not description.startswith(summary):
        info.append(summary)

    info.append(description)

    if testing_done:
        info.append('Testing Done:\n%s' % testing_done)

    if review_request.bugs_closed:
        info.append('Bugs closed: %s'
                    % ', '.join(review_request.bugs_closed))

    info.append('Reviewed at %s' % review_request.absolute_url)

    return '\n\n'.join(info)


def build_rbtools_cmd_argv(options, options_map=DEFAULT_OPTIONS_MAP):
    """Generates a list of command line arguments from parsed command options.

    Used for building command line arguments from existing options, when
    calling another RBTools command. ``options_map`` specifies the options
    and their corresponding argument names that need to be included.
    """
    argv = []

    for option_key, arg_name in six.iteritems(options_map):
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
