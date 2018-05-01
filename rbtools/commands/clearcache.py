from __future__ import unicode_literals

from rbtools.api.cache import clear_cache
from rbtools.commands import Command, Option


class ClearCache(Command):
    """Delete the HTTP cache used for the API."""

    name = 'clear-cache'
    author = 'The Review Board Project'
    description = 'Delete the HTTP cache used for the API.'

    option_list = [
        Option('--cache-location',
               dest='cache_location',
               metavar='FILE',
               config_key='CACHE_LOCATION',
               default=None,
               help='The file to use for the API cache database.',
               added_in='0.7.3'),
    ]

    def main(self):
        """Unlink the API cache's path."""
        if self.options.cache_location:
            clear_cache(self.options.cache_location)
        else:
            clear_cache()
