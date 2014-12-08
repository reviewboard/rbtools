import getpass
import logging
import sys

from six.moves import input

from rbtools.api.errors import AuthorizationError
from rbtools.commands import CommandError


def get_authenticated_session(api_client, api_root, auth_required=False):
    """Return an authenticated session.

    None will be returned if the user is not authenticated, unless the
    'auth_required' parameter is True, in which case the user will be prompted
    to login.
    """
    session = api_root.get_session()

    if not session.authenticated:
        if not auth_required:
            return None

        logging.warning('You are not authenticated with the Review Board '
                        'server at %s, please login.' % api_client.url)
        sys.stderr.write('Username: ')
        username = input()
        password = getpass.getpass('Password: ')
        api_client.login(username, password)

        try:
            session = session.get_self()
        except AuthorizationError:
            raise CommandError('You are not authenticated.')

    return session


def get_user(api_client, api_root, auth_required=False):
    """Return the user resource for the current session."""
    session = get_authenticated_session(api_client, api_root, auth_required)

    if session:
        return session.get_user()


def get_username(api_client, api_root, auth_required=False):
    """Return the username for the current session."""
    session = get_authenticated_session(api_client, api_root, auth_required)

    if session:
        return session.links.user.title
