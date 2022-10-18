"""Review Board server capability management."""

from typing import Dict


class Capabilities:
    """Provides information on Review Board server capabilities."""

    #: The dictionary of capabilities from the Review Board API.
    #:
    #: Type:
    #:     dict
    capabilities: Dict

    def __init__(
        self,
        capabilities: Dict,
    ) -> None:
        """Initialize the capabilities information.

        Args:
            capabilities (dict):
                The capabilities dictionary from the server.
        """
        self.capabilities = capabilities

    def has_capability(self, *cap_path) -> bool:
        """Return whether the server provides a given capability.

        Args:
            *cap_path (tuple of str):
                The keys forming a path to the capability.

        Returns:
            bool:
            ``True`` if the capability is explicitly set to ``True``. ``False``
            if the capability is set to ``False`` or is not present in the API
            capabilities.
        """
        caps = self.capabilities

        try:
            for key in cap_path:
                caps = caps[key]

            # If only part of a capability path is specified, we don't want to
            # evaluate to True just because it has contents. We want to only
            # say we have a capability if it is indeed 'True'.
            return caps is True
        except (TypeError, KeyError):
            # The server either doesn't support the capability, or returned no
            # capabilities at all.
            return False
