class Capabilities(object):
    """Stores and retrieves Review Board server capabilities."""
    def __init__(self, capabilities):
        self.capabilities = capabilities

    def has_capability(self, category, name):
        try:
            return self.capabilities[category][name]
        except (TypeError, KeyError):
            # The server either doesn't support the capability,
            # or returned no capabilities at all.
            return False
