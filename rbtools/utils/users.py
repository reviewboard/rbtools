"""Utilities for working with user sessions."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from rbtools.api.client import RBClientWebLoginOptions
from rbtools.api.errors import AuthorizationError
from rbtools.utils.console import get_input, get_pass
from rbtools.utils.web_login import WebLoginNotAllowed, attempt_web_login

if TYPE_CHECKING:
    from rbtools.api.capabilities import Capabilities
    from rbtools.api.client import RBClient
    from rbtools.api.resource import Resource, RootResource


def get_authenticated_session(
    api_client: RBClient,
    api_root: RootResource,
    auth_required: bool = False,
    session: (Resource | None) = None,
    num_retries: int = 3,
    via_web: (bool | None) = None,
    open_browser: (bool | None) = None,
    enable_logging: (bool | None) = None,
    capabilities: (Capabilities | None) = None,
) -> Resource | None:
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

            If this is set, it will take precedence over what's set in
            :py:attr:`rbtools.api.client.RBClient.web_login_options`.

            Version Added:
                5.0

        open_browser (bool, optional):
            Whether to automatically open a browser when using web-based login.

            If this is set, it will take precedence over what's set in
            :py:attr:`rbtools.api.client.RBClient.web_login_options`.

            Version Added:
                5.0

        enable_logging (bool, optional):
            Whether to display the logs for the web login server when using
            web-based login.

            If this is set, it will take precedence over what's set in
            :py:attr:`rbtools.api.client.RBClient.web_login_options`.

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
    if not session:
        session = api_root.get_session(expand='user')

    if not session.authenticated:
        if not auth_required:
            return None

        web_login_options = (
            api_client.web_login_options or
            RBClientWebLoginOptions(
                allow=False,
                debug=False,
                open_browser=False)
        )

        if via_web is not None:
            web_login_options.allow = via_web

        if open_browser is not None:
            web_login_options.open_browser = open_browser

        if enable_logging is not None:
            web_login_options.debug = enable_logging

        api_client.web_login_options = web_login_options

        try:
            login_successful = attempt_web_login(
                api_client=api_client,
                api_root=api_root,
                capabilities=capabilities)

            if login_successful:
                return api_root.get_session(expand='user')
            else:
                logging.error('Web-based login failed.')
                raise AuthorizationError()
        except WebLoginNotAllowed:
            pass

        for i in range(num_retries + 1):
            username, password = credentials_prompt(
                server_url=api_client.domain,
                is_retry=(i != 0))
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


def credentials_prompt(
    server_url: str,
    username: (str | None) = None,
    password: (str | None) = None,
    is_retry: bool = False,
) -> tuple[str, str]:
    """Prompt for a username and/or password using the command line.

    Version Added:
        5.4

    Args:
        server_url (str):
            The Review Board server URL.

        username (str, optional):
            The username for authentication, if one has already been provided.

        password (str, optional):
            The password for authentication, if one has already been provided.

        is_retry (bool, optional):
            Whether credentials have already been prompted for before.

    Returns:
        tuple:
        A 2-tuple of:

        Tuple:
            username (str):
                The user-provided username.

            password (str):
                The user-provided password.

    Raises:
        rbtools.api.errors.AuthorizationError:
            RBTools is unable to prompt for the credentials.
    """
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

    if not is_retry:
        logging.info('Please log in to the Review Board server at %s',
                     server_url)

    if username is None:
        username = get_input('Username: ', require=True)

    if password is None:
        password = get_pass('Password: ', require=True)

    return username, password
