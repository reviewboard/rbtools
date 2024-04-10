"""Utilities for working with user sessions."""

from __future__ import annotations

import logging
import sys
from typing import Optional, TYPE_CHECKING

from rbtools.api.errors import AuthorizationError
from rbtools.config.loader import load_config
from rbtools.utils.console import get_input, get_pass
from rbtools.utils.web_login import WebLoginManager, is_web_login_enabled

if TYPE_CHECKING:
    from rbtools.api.capabilities import Capabilities
    from rbtools.api.client import RBClient
    from rbtools.api.resource import Resource, RootResource


def get_authenticated_session(
    api_client: RBClient,
    api_root: RootResource,
    auth_required: bool = False,
    session: Optional[Resource] = None,
    num_retries: int = 3,
    via_web: Optional[bool] = None,
    open_browser: bool = False,
    enable_logging: bool = False,
    capabilities: Optional[Capabilities] = None,
) -> Optional[Resource]:
    """Return an authenticated session.

    None will be returned if the user is not authenticated, unless the
    'auth_required' parameter is ``True``, in which case the user will be
    prompted to login.

    Version Changed:
        5.0:
        Added support for authenticating through web-based login. This
        includes the new arguments: ``via_web``, ``open_browser``,
        ``enable_logging`` and ``capabilities``.

    Args:
        api_client (rbtools.api.client.RBClient):
            The API client of the command that is creating the server.

        api_root (rbtools.api.resource.RootResource):
            The root resource for the Review Board server.

        auth_required (bool, optional):
            Whether to require authenticating the user. If ``True``, the user
            will be prompted to log in if they are not currently
            authenticated.

        session (rbtools.api.resource.Resource, optional):
            The current session, if available.

        num_retries (int, optional):
            The number of times to retry authenticating if it fails.

        via_web (bool, optional):
            Whether to use web-based login.

            Version Added:
                5.0

        open_browser (bool, optional):
            Whether to automatically open a browser when using web-based login.

            Version Added:
                5.0

        enable_logging (bool, optional):
            Whether to display the logs for the web login server when using
            web-based login.

            Version Added:
                5.0

        capabilities (rbtools.api.capabilities.Capabilities, optional):
            The Review Board server capabilities.

            Version Added:
                5.0

    Returns:
        rbtools.api.resource.Resource:
        The authenticated session resource or ``None`` if the user is not
        authenticated.
    """
    # TODO: Consolidate the logic in this function with
    #       Command.credentials_prompt().
    if not session:
        session = api_root.get_session(expand='user')

    if not session.authenticated:
        if not auth_required:
            return None

        if via_web is None:
            config = load_config()
            via_web = config.get('WEB_LOGIN')

        web_login_enabled = is_web_login_enabled(
            server_info=api_root.get_info(),
            capabilities=capabilities)

        if via_web and web_login_enabled:
            web_login_manager = WebLoginManager(
                api_client=api_client,
                enable_logging=enable_logging,
                open_browser=open_browser)

            web_login_manager.start_web_login_server()
            login_successful = web_login_manager.wait_login_result()

            if login_successful:
                return api_root.get_session(expand='user')
            else:
                logging.error('Web-based login failed.')
                raise AuthorizationError()

        if via_web and not web_login_enabled:
            logging.debug('Web-based login requires at least Review Board '
                          '5.0.5 and for the ``client_web_login`` site '
                          'configuration setting to be set to ``True``. '
                          'Falling back to username and password prompt.')

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
            api_client.login(username=username, password=password)

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
