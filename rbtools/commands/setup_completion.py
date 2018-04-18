from __future__ import print_function, unicode_literals

import logging
import os
import platform
import sys

from pkg_resources import resource_string

from rbtools.commands import Command


class SetupCompletion(Command):
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
        script = resource_string('rbtools', self.SHELLS[shell][system]['src'])
        dest = os.path.join(self.SHELLS[shell][system]['dest'],
                            self.SHELLS[shell][system]['filename'])

        try:
            with open(dest, 'w') as f:
                f.write(script)
        except IOError as e:
            logging.error('I/O Error (%s): %s', e.errno, e.strerror)
            sys.exit()

        print('Successfully installed %s auto-completions.' % shell)
        print('Restart the terminal for completions to work.')

    def main(self, shell=None):
        """Run the command.

        Args:
            shell (str):
                An optional string specifying name of shell for which
                auto-completions will be installed for.
        """
        if not shell:
            shell = os.environ.get(b'SHELL')

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
