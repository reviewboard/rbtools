"""Implementation of rbt clear-cache."""

from rbtools.api.cache import APICache, clear_cache
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
        cache_location = (self.options.cache_location or
                          APICache.DEFAULT_CACHE_PATH)

        if clear_cache(cache_location):
            self.stdout.write('Cleared cache in "%s"' % cache_location)
