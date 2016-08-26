from __future__ import print_function, unicode_literals

import logging
import subprocess

from rbtools.api.client import RBClient
from rbtools.api.errors import APIError, ServerInterfaceError


SUBMITTED = 'submitted'


class HookError(Exception):
    pass


def get_api(server_url, **kwargs):
    """Returns an RBClient instance and the associated root resource.

    Hooks should use this method to gain access to the API, instead of
    instantiating their own client.

    Args:
        server_url (unicode):
            The server URL to retrieve.

        **kwargs (dict):
            Additional keyword arguments to pass to the
            :py:class:`~rbtools.api.client.RBClient` constructor. See
            :py:meth:`SyncTransport.__init__()
            <rbtools.api.transport.sync.SyncTransport.__init__>` for arguments
            that are accepted.

    Returns:
        tuple:
        This returns a 2-tuple of the :py:class:`~rbtools.api.client.RBClient`
        and :py:class:`<root resource> rbtools.api.resource.Resource`.
    """
    api_client = RBClient(server_url, **kwargs)

    try:
        api_root = api_client.get_root()
    except ServerInterfaceError as e:
        raise HookError('Could not reach the Review Board server at %s: %s'
                        % (server_url, e))
    except APIError as e:
        raise HookError('Unexpected API Error: %s' % e)

    return api_client, api_root


def execute(command):
    """Executes the specified command and returns the stdout output."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    output = process.communicate()[0].strip()

    if process.returncode:
        logging.warning('Failed to execute command: %s', command)
        return None

    return output


def initialize_logging():
    """Sets up a log handler to format log messages.

    Warning, error, and critical messages will show the level name as a prefix,
    followed by the message.
    """
    root = logging.getLogger()

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    handler.setLevel(logging.WARNING)
    root.addHandler(handler)


def get_review_request_id(regex, commit_message):
    """Returns the review request ID referenced in the commit message.

    We assume there is at most one review request associated with each commit.
    If a matching review request cannot be found, we return 0.
    """
    match = regex.search(commit_message)
    return (match and int(match.group('id'))) or 0


def get_review_request(review_request_id, api_root):
    """Returns the review request resource for the given ID."""
    try:
        review_request = api_root.get_review_request(
            review_request_id=review_request_id)
    except APIError as e:
        raise HookError('Error getting review request: %s' % e)

    return review_request


def close_review_request(server_url, username, password, review_request_id,
                         description):
    """Closes the specified review request as submitted."""
    api_client, api_root = get_api(server_url, username, password)
    review_request = get_review_request(review_request_id, api_root)

    if review_request.status == SUBMITTED:
        logging.warning('Review request #%s is already %s.',
                        review_request_id, SUBMITTED)
        return

    if description:
        review_request = review_request.update(status=SUBMITTED,
                                               description=description)
    else:
        review_request = review_request.update(status=SUBMITTED)

    print('Review request #%s is set to %s.' %
          (review_request_id, review_request.status))


def get_review_request_approval(server_url, username, password,
                                review_request_id):
    """Returns the approval information for the given review request."""
    api_client, api_root = get_api(server_url, username, password)
    review_request = get_review_request(review_request_id, api_root)

    return review_request.approved, review_request.approval_failure
