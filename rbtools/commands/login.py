"""Implementation of rbt login."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from rbtools.api.errors import AuthorizationError
from rbtools.commands.base import (BaseCommand,
                                   CommandError,
                                   Option,
                                   OptionGroup)
from rbtools.utils.users import get_authenticated_session

if TYPE_CHECKING:
    import argparse

    from rbtools.config import RBToolsConfig


class Login(BaseCommand):
    """Logs into a Review Board server.

    The user will either be directed to log in via the Review Board web page,
    or prompted for a username and password. This depends on whether the
    ``--web-login`` option is enabled.

    Optionally, the user can pass an API token or username and password on
    the command line.

    A session cookie will be saved upon successful authentication.

    If the user is already logged in, this won't do anything.

    Version Changed:
        6.0:
        Deprecated the ``-l`` option in favour of ``--debug``.

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
        Option('-l', '--enable-logging',
               dest='enable_logging',
               action='store_true',
               default=False,
               help='With web-based login, display the login server logs.',
               added_in='5.0',
               deprecated_in='6.0',
               removed_in='7.0',
               replacement='--debug'),
        BaseCommand.server_options,
    ]

    def main(self) -> int:
        """Run the command.

        Returns:
            int:
            The resulting exit code.

        Raises:
            rbtools.command.CommandError:
                The login failed.
        """
        options = self.options
        api_client = self.api_client
        api_root = self.api_root
        assert api_client is not None
        assert api_root is not None

        session = api_root.get_session(expand='user')
        was_authenticated = session.authenticated

        if not was_authenticated:
            web_login_options = api_client.web_login_options
            assert web_login_options
            web_login_options.debug = (web_login_options.debug or
                                       options.enable_logging)

            try:
                session = get_authenticated_session(
                    api_client=api_client,
                    api_root=api_root,
                    auth_required=True,
                    session=session,
                    capabilities=self.capabilities)
            except AuthorizationError:
                raise CommandError('Unable to log in to Review Board.')

        if session.authenticated:
            if (not was_authenticated or
                (options.username and options.password) or
                options.api_token):
                self.log.info('Successfully logged in to Review Board.')
            else:
                self.log.info(
                    'You are already logged in to Review Board at %s',
                    api_client.domain)

        return 0

    def create_parser(
        self,
        config: RBToolsConfig,
        argv: (list[str] | None) = None,
    ) -> argparse.ArgumentParser:
        """Create and return the argument parser for this command.

        Version Added:
            6.0

        Args:
            config (dict):
                The loaded RBTools config.

            argv (list, optional):
                The argument list.

        Returns:
            argparse.ArgumentParser:
            The argument parser.
        """
        # Make copies of the option lists so that we don't modify the
        # shared options.
        global_options_orig = self._global_options
        global_options_copy = copy.deepcopy(global_options_orig)
        options_orig = self.option_list
        options_copy = copy.deepcopy(options_orig)

        for option in global_options_copy:
            if option.opts[0] == '--open-browser':
                option.opts = ('-o', '--open', '--open-browser')
                break

        for item in options_copy:
            if isinstance(item, OptionGroup):
                for option in item.option_list:
                    if option.opts[0] == '--web-login':
                        option.opts = ('-w', '--web', '--web-login')
                        break

        try:
            self._global_options = global_options_copy
            Login.option_list = options_copy
            parser = super().create_parser(config, argv)
        finally:
            self._global_options = global_options_orig
            Login.option_list = options_orig

        return parser
