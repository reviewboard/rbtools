from __future__ import unicode_literals

from six.moves.urllib.parse import urlparse

from rbtools.api.transport.sync import SyncTransport


class RBClient(object):
    """Entry point for accessing RB resources through the web API.

    By default the synchronous transport will be used. To use a
    different transport, provide the transport class in the
    'transport_cls' parameter.
    """
    def __init__(self, url, transport_cls=SyncTransport, *args, **kwargs):
        self.url = url
        self.domain = urlparse(url)[1]
        self._transport = transport_cls(url, *args, **kwargs)

    def get_root(self, *args, **kwargs):
        return self._transport.get_root(*args, **kwargs)

    def get_path(self, path, *args, **kwargs):
        return self._transport.get_path(path, *args, **kwargs)

    def get_url(self, url, *args, **kwargs):
        return self._transport.get_url(url, *args, **kwargs)

    def login(self, *args, **kwargs):
        return self._transport.login(*args, **kwargs)

    def logout(self, *args, **kwargs):
        return self._transport.logout(*args, **kwargs)
