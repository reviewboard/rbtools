"""Implementation of rbt list-repo-types."""

import textwrap

from rbtools.clients import load_scmclients
from rbtools.commands import Command


class ListRepoTypes(Command):
    """List available repository types."""

    name = 'list-repo-types'
    author = 'The Review Board Project'
    description = 'Print a list of supported repository types.'

    def main(self, *args):
        """Ruen the command.

        Args:
            *args (tuple):
                Capture for any additional arguments passed in.
        """
        self.stdout.write(textwrap.fill(
            'The following repository types are supported by this '
            'installation of RBTools. Each "<type>" may be used as a value '
            'for the "--repository-type=<type>" command line argument. '
            'Repository types which are detected in the current directory '
            'are marked with a "*".',
            width=79))
        self.stdout.new_line()

        load_scmclients(self.config, self.options)
        from rbtools.clients import SCMCLIENTS

        self.json.add('repository_types', [])

        for name, tool in SCMCLIENTS.items():
            has_repository_info = tool.get_repository_info() is not None

            self.json.append('repository_types', {
                'name': name,
                'tool': tool.name,
                'detected': has_repository_info
            })

            if has_repository_info:
                self.stdout.write(' * "%s": %s' % (name, tool.name))
            else:
                self.stdout.write('   "%s": %s' % (name, tool.name))
