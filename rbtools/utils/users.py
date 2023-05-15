"""Utilities for working with user sessions."""

import logging
import sys

from rbtools.api.errors import AuthorizationError
from rbtools.utils.console import get_input, get_pass


def get_authenticated_session(api_client, api_root, auth_required=False,
                              session=None, num_retries=3):
    """Return an authenticated session.

    None will be returned if the user is not authenticated, unless the
    'auth_required' parameter is True, in which case the user will be prompted
    to login.
    """
    # TODO: Consolidate the logic in this function with
    #       Command.credentials_prompt().
    if not session:
        session = api_root.get_session(expand='user')

    if not session.authenticated:
        if not auth_required:
            return None

        # Interactive prompts don't work correctly when input doesn't come
        # from a terminal. This could seem to be a rare case not worth
        # worrying about, but this is what happens when using native
        # Python in Cygwin terminal emulator under Windows and it's very
        # puzzling to the users, especially because stderr is also _not_
        # flushed automatically in this case, so the program just appears
        # to hang.
        if not sys.stdin.isatty():
            message_parts = [
                'Authentication is required but RBTools cannot prompt for '
                'it.'
            ]

            if sys.platform == 'win32':
                message_parts.append(
                    'This can occur if you are piping input into the '
                    'command, or if you are running in a Cygwin terminal '
                    'emulator and not using Cygwin Python.'
                )
            else:
                message_parts.append(
                    'This can occur if you are piping input into the '
                    'command.'
                )

            message_parts.append(
                'You may need to explicitly provide API credentials when '
                'invoking the command, or try logging in separately.'
            )

            raise AuthorizationError(message=' '.join(message_parts))

        logging.info('Please log in to the Review Board server at %s',
                     api_client.domain)

        for i in range(num_retries + 1):
            username = get_input('Username: ', require=True)
            password = get_pass('Password: ', require=True)
            api_client.login(username, password)

            try:
                session = session.get_self()
                break
            except AuthorizationError:
                sys.stderr.write('\n')

                if i == num_retries:
                    raise

                logging.error('The username or password was incorrect. '
                              'Please try again.')

    return session


def get_user(api_client, api_root, auth_required=False):
    """Return the user resource for the current session."""
    session = get_authenticated_session(api_client, api_root, auth_required)

    if session:
        return session.user

    return None


def get_username(api_client, api_root, auth_required=False):
    """Return the username for the current session."""
    user = get_user(api_client, api_root, auth_required)

    if user:
        return user.username

    return None
