from __future__ import unicode_literals


class Capabilities(object):
    """Stores and retrieves Review Board server capabilities."""
    def __init__(self, capabilities):
        self.capabilities = capabilities

    def has_capability(self, *args):
        caps = self.capabilities

        try:
            for arg in args:
                caps = caps[arg]

            # If only part of a capability path is specified, we don't want
            # to evaluate to True just because it has contents. We want to
            # only say we have a capability if it is indeed 'True'.
            return caps is True
        except (TypeError, KeyError):
            # The server either doesn't support the capability,
            # or returned no capabilities at all.
            return False
