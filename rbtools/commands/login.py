from __future__ import unicode_literals

import logging

from rbtools.api.errors import AuthorizationError
from rbtools.commands import Command, CommandError
from rbtools.utils.users import get_authenticated_session


class Login(Command):
    """Logs into a Review Board server.

    The user will be prompted for a username and password, unless otherwise
    passed on the command line, allowing the user to log in and save a
    session cookie without needing to be in a repository or posting to
    the server.

    If the user is already logged in, this won't do anything.
    """

    name = 'login'
    author = 'The Review Board Project'

    needs_api = True

    option_list = [
        Command.server_options,
    ]

    def main(self):
        """Run the command."""
        session = self.api_root.get_session(expand='user')
        was_authenticated = session.authenticated

        if not was_authenticated:
            try:
                session = get_authenticated_session(api_client=self.api_client,
                                                    api_root=self.api_root,
                                                    auth_required=True,
                                                    session=session)
            except AuthorizationError:
                raise CommandError('Unable to log in to Review Board.')

        if session.authenticated:
            if not was_authenticated or (self.options.username and
                                         self.options.password):
                logging.info('Successfully logged in to Review Board.')
            else:
                logging.info('You are already logged in to Review Board at %s',
                             self.api_client.domain)
