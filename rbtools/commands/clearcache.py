from rbtools.api.cache import clear_cache
from rbtools.commands import Command, Option


class ClearCache(Command):
    """Delete the HTTP cache used for the API."""
    name = 'clear-cache'
    author = 'The Review Board Project'
    description = 'Delete the HTTP cache used for the API.'

    option_list = [
        Option('--disable-cache',
               dest='disable_cache',
               config_key='DISABLE_CACHE',
               action='store_true',
               default=False,
               help='Disable the HTTP cache.',
               added_in='0.7.3'),
    ]

    def main(self):
        """Unlink the API cache's path."""
        clear_cache(self.options.cache_path)
