"""Implementation of rbt logout."""

import logging

from rbtools.commands import Command


class Logout(Command):
    """Logs out of a Review Board server.

    The session cookie will be removed into from the .rbtools-cookies
    file. The next RBTools command you run will then prompt for credentials.
    """

    name = 'logout'
    author = 'The Review Board Project'

    needs_api = True

    option_list = [
        Command.server_options,
    ]

    def main(self):
        """Run the command."""
        session = self.api_root.get_session(expand='user')

        if session.authenticated:
            self.api_client.logout()

            logging.info('You are now logged out of Review Board at %s',
                         self.api_client.domain)
        else:
            logging.info('You are already logged out of Review Board at %s',
                         self.api_client.domain)
