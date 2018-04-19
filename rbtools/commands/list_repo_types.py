from __future__ import unicode_literals

from rbtools.clients import print_clients
from rbtools.commands import Command


class ListRepoTypes(Command):
    """List available repository types."""

    name = 'list-repo-types'
    author = 'The Review Board Project'
    description = 'Print a list of supported repository types.'

    def main(self, *args):
        print_clients(self.config, self.options)
