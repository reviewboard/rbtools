"""Implementation of rbt setup-completion."""

import logging
import os
import platform
import sys
from typing import Optional

import importlib_resources

from rbtools.commands.base import BaseCommand, CommandError


class SetupCompletion(BaseCommand):
    """Setup auto-completion for rbt.

    This outputs a script for the given shell to enable auto-completion of
    :command:`rbt`.

    Version Changed:
        5.0:
        This no longer attempts to write files to a system directory, and
        instead outputs to the console.
    """

    name = 'setup-completion'
    author = 'The Review Board Project'
    description = 'Output RBTools auto-completion code for bash or zsh.'
    args = '<shell>'

    def main(
        self,
        shell: Optional[str] = None,
        *args,
    ) -> None:
        """Run the command.

        Args:
            shell (str):
                An optional string specifying name of shell for which
                auto-completions will be installed for.
        """
        if not shell:
            shell = os.environ.get('SHELL')

            if not shell:
                raise CommandError(
                    'Your current shell was not found. Please re-run '
                    '`rbt setup-completion` with your shell (bash or zsh) '
                    'as an argument.')

            shell = os.path.basename(shell)

        shell = shell.lower()

        try:
            script = (
                importlib_resources.files('rbtools')
                .joinpath('commands', 'conf', 'completions', shell)
                .read_text()
            )
        except FileNotFoundError:
            raise CommandError(
                f'Shell completions for {shell} are not supported.')
            return 1

        self.stdout.write(script.rstrip())
        self.json.add('script', script)
