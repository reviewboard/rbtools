"""Implementation of rbt logout."""

from __future__ import annotations

from urllib.parse import urlparse

from rbtools.commands.base import BaseCommand


class Logout(BaseCommand):
    """Logs out of a Review Board server.

    The session cookie will be removed into from the .rbtools-cookies
    file. The next RBTools command you run will then prompt for credentials.
    """

    name = 'logout'
    author = 'The Review Board Project'

    option_list = [
        BaseCommand.server_options,
    ]

    def main(self) -> int:
        """Run the command."""
        # Initialize the client and root resource ourselves instead of setting
        # needs_api=True, so that we have more control over the auth flow.
        #
        # Some servers have a fully private API, so fetching the root resource
        # may prompt for authentication. We check if we have session cookie,
        # if not then we know that the user is logged out without having to
        # hit the API and possibly trigger an authentication.
        server_url = self._init_server_url()
        self.server_url = server_url

        if not urlparse(server_url).scheme:
            server_url = f'http://{server_url}'

        api_client = self._make_api_client(server_url)
        self.api_client = api_client

        if not api_client.has_session_cookie():
            self.log.info('You are already logged out of Review Board at %s',
                          api_client.domain)
            return 0

        api_root = api_client.get_root()
        self.api_root = api_root

        session = api_root.get_session(expand='user')

        if session.authenticated:
            api_client.logout()

            self.log.info('You are now logged out of Review Board at %s',
                          api_client.domain)
        else:
            self.log.info('You are already logged out of Review Board at %s',
                          api_client.domain)

        return 0
