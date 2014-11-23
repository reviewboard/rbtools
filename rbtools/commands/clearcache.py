from rbtools.api.cache import clear_cache
from rbtools.commands import Command


class ClearCache(Command):
    """Delete the HTTP cache used for the API."""
    name = 'clear-cache'
    author = 'The Review Board Project'
    description = 'Delete the HTTP cache used for the API.'

    def main(self):
        """Unlink the API cache's path."""
        clear_cache()
