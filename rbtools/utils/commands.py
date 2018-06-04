from __future__ import unicode_literals

import six


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


#: The format string used to specify a URL to a review request in commits.
#:
#: Commands that prepare a commit message for pushing, such as rbt stamp,
#: rbt patch, and rbt land, must use this format to indicate the URL to the
#: matching review request. Review Board will parse the commit messages when
#: executing any post-receive hooks, looking for this string and a valid URL.
STAMP_STRING_FORMAT = 'Reviewed at %s'


class AlreadyStampedError(Exception):
    """An error indicating the change has already been stamped."""


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

    info.append(STAMP_STRING_FORMAT % review_request.absolute_url)

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


def stamp_commit_with_review_url(revisions, review_request_url, tool):
    """Amend the tip revision message to include review_request_url."""
    commit_message = tool.get_raw_commit_message(revisions)
    stamp_string = STAMP_STRING_FORMAT % review_request_url

    if stamp_string in commit_message:
        raise AlreadyStampedError('This change is already stamped.')

    new_message = (commit_message.rstrip() + '\n\n' + stamp_string)
    tool.amend_commit_description(new_message, revisions)
