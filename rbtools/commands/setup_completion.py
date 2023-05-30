"""Implementation of rbt setup-completion."""

import logging
import os
import platform
import sys

import importlib_resources

from rbtools.commands.base import BaseCommand


class SetupCompletion(BaseCommand):
    """Setup auto-completion for rbt.

    By default, the command installs an auto-completion file for the user's
    login shell. The user can optionally specify a shell for which the command
    will install the auto-completion file for.
    """

    name = 'setup-completion'
    author = 'The Review Board Project'
    description = 'Setup auto-completion for bash or zsh.'
    args = '<shell>'

    #: A dictionary of supported shells.
    #:
    #: Each shell contains paths to its completion file and the directory
    #: where the file will be installed.
    SHELLS = {
        'bash': {
            'Linux': {
                'src': 'commands/conf/rbt-bash-completion',
                'dest': '/etc/bash_completion.d',
                'filename': 'rbt',
            },
            'Darwin': {
                'src': 'commands/conf/rbt-bash-completion',
                'dest': '/usr/local/etc/bash_completion.d',
                'filename': 'rbt',
            },
        },
        'zsh': {
            'Linux': {
                'src': 'commands/conf/_rbt-zsh-completion',
                'dest': '/usr/share/zsh/functions/Completion',
                'filename': '_rbt',
            },
            'Darwin': {
                'src': 'commands/conf/_rbt-zsh-completion',
                'dest': '/usr/share/zsh/site-functions',
                'filename': '_rbt',
            },
        }
    }

    def setup(self, shell):
        """Install auto-completions for the appropriate shell.

        Args:
            shell (str):
                String specifying name of shell for which auto-completions
                will be installed for.
        """
        system = platform.system()
        shell_info = self.SHELLS[shell][system]

        script = (
            importlib_resources.files('rbtools')
            .joinpath(shell_info['src'])
            .read_bytes()
        )

        dest = os.path.join(shell_info['dest'], shell_info['filename'])

        try:
            with open(dest, 'wb') as fp:
                fp.write(script)
        except IOError as e:
            logging.error('I/O Error (%s): %s', e.errno, e.strerror)
            sys.exit()

        self.stdout.write('Successfully installed %s auto-completions.'
                          % shell)
        self.stdout.write('Restart the terminal for completions to work.')

    def main(self, shell=None):
        """Run the command.

        Args:
            shell (str):
                An optional string specifying name of shell for which
                auto-completions will be installed for.
        """
        if not shell:
            shell = os.environ.get('SHELL')

            if shell:
                shell = os.path.basename(shell)
            else:
                logging.error('No login shell found. Re-run the command with '
                              'a shell as an argument or refer to manual '
                              'installation in documentation')
                sys.exit()

        if shell in self.SHELLS:
            system = platform.system()

            if system in self.SHELLS[shell]:
                if os.path.exists(self.SHELLS[shell][system]['dest']):
                    self.setup(shell)
                else:
                    logging.error('Could not locate %s completion directory. '
                                  'Refer to manual installation in '
                                  'documentation',
                                  shell)
            else:
                logging.error('The %s operating system is currently '
                              'unsupported',
                              system)
        else:
            logging.error('The shell "%s" is currently unsupported',
                          shell)
