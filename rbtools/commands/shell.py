from __future__ import print_function, unicode_literals

import code
import logging
import readline

from rbtools.commands import Command, CommandError, Option
from rlcompleter import Completer


class Shell(Command):
    """Start a pre-configured Python shell.

    This will inject predefined variables from your .reviewboardrc into the
    scope of a new interactive Python shell.
    """

    name = 'shell'
    author = 'The Review Board Project'
    description = 'Opens pre-configured python shell environment.'
    option_list = [
        Option('-i', '--ipython',
               dest='shell',
               action='store_const',
               config_key='SHELL',
               const='ipython',
               help='Returns an ipython shell if it is available.'),
        Option('-b', '--bpython',
               dest='shell',
               action='store_const',
               config_key='SHELL',
               const='bpython',
               help='Returns an bpython shell if it is available.'),
        Option('-q', '--quiet',
               dest='quiet',
               action='store_true',
               config_key='QUIET',
               default=False,
               help='Surpress output regarding variable imports.'),
        Command.server_options,
    ]

    def log_import(self, message):
        """Log variable import made to shell."""
        if not self.options.quiet:
            print(message)

    def ipython(self):
        """Import IPython shell."""
        from IPython.terminal.embed import InteractiveShellEmbed

        ipshell = InteractiveShellEmbed()
        return ipshell

    def bpython(self):
        """Import bpython shell."""
        import bpython as bpython_shell

        return bpython_shell

    def main(self, *args):
        """Start interactive shell with user."""
        # Define namespace for shell interaction and update namespace based on
        # configuration files and options.
        namespace = {
            'config': self.config,
            'options': vars(self.options),
        }
        self.log_import('Namespace from configuration files have been '
                        'imported as "config"')
        self.log_import('Command options have been imported as "options"')

        if self.options.server is not None:
            try:
                api_client, api_root = self.get_api(self.options.server)
            except CommandError as e:
                logging.exception(e)
            else:
                namespace['api_client'] = api_client
                namespace['api_root'] = api_root
                self.log_import('The api client has been imported as '
                                '"api_client"')
                self.log_import('The api root has been imported as "api_root"')

        # Set up tab completion for the namespace.
        readline.set_completer(Completer(namespace).complete)
        readline.parse_and_bind('tab:complete')

        try:
            if self.options.shell == 'ipython':
                ipython_shell = self.ipython()
                ipython_shell(local_ns=namespace)
                return
            elif self.options.shell == 'bpython':
                bpython_shell = self.bpython()
                bpython_shell.embed(namespace)
                return
            elif self.options.shell:
                logging.error('Unknown shell "%s"', self.options.shell)
        except ImportError as e:
            logging.error('Could not import desired shell: %s', e)

        code.interact(local=namespace)
