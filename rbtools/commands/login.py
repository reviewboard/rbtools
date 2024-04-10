"""Implementation of rbt login."""

import logging

from rbtools.api.errors import AuthorizationError
from rbtools.commands.base import BaseCommand, CommandError, Option
from rbtools.utils.users import get_authenticated_session


class Login(BaseCommand):
    """Logs into a Review Board server.

    The user will either be directed to log in via the Review Board web page,
    or prompted for a username and password. This depends on whether the
    ``--web`` option is enabled.

    Optionally, the user can pass an API token or username and password on
    the command line.

    A session cookie will be saved upon successful authentication.

    If the user is already logged in, this won't do anything.

    Version Changed:
        5.0:
        Added the ``--web`` option for web-based login, along with the
        ``--open`` and ``--enable-logging`` options that are specific to
        web-based login.
    """

    name = 'login'
    author = 'The Review Board Project'

    needs_api = True

    option_list = [
        Option('-w', '--web',
               dest='web',
               action='store_true',
               config_key='WEB_LOGIN',
               default=False,
               help='Use web-based login instead of prompting for '
                    'for credentials directly in the terminal.',
               added_in='5.0'),
        Option('-o', '--open',
               dest='open_browser',
               action='store_true',
               config_key='OPEN_BROWSER',
               default=False,
               help='When using web-based login, this will automatically '
                    'open a browser to the login page.',
               added_in='5.0'),
        Option('-l', '--enable-logging',
               dest='enable_logging',
               action='store_true',
               default=False,
               help='When using web-based login, this will display the '
                    'login server logs. This should only be used by '
                    'admins for debugging.',
               added_in='5.0'),
        BaseCommand.server_options,
    ]

    def main(self):
        """Run the command."""
        session = self.api_root.get_session(expand='user')
        was_authenticated = session.authenticated

        if not was_authenticated:
            try:
                session = get_authenticated_session(
                    api_client=self.api_client,
                    api_root=self.api_root,
                    auth_required=True,
                    session=session,
                    via_web=self.options.web,
                    open_browser=self.options.open_browser,
                    enable_logging=self.options.enable_logging,
                    capabilities=self.capabilities)
            except AuthorizationError:
                raise CommandError('Unable to log in to Review Board.')

        if session.authenticated:
            if (not was_authenticated or
                (self.options.username and self.options.password) or
                self.options.api_token):
                logging.info('Successfully logged in to Review Board.')
            else:
                logging.info('You are already logged in to Review Board at %s',
                             self.api_client.domain)
