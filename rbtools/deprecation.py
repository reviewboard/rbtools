"""Internal support for handling deprecations in RBTools.

The version-specific objects in this module are not considered stable between
releases, and may be removed at any point. The base objects are considered
stable.
"""

from __future__ import unicode_literals

import warnings


class BaseRemovedInRBToolsVersionWarning(DeprecationWarning):
    """Base class for a RBTools deprecation warning.

    All version-specific deprecation warnings inherit from this, allowing
    callers to check for Review Board deprecations without being tied to a
    specific version.
    """

    @classmethod
    def warn(cls, message, stacklevel=2):
        """Emit the deprecation warning.

        This is a convenience function that emits a deprecation warning using
        this class, with a suitable default stack level. Callers can provide
        a useful message and a custom stack level.

        Args:
            message (unicode):
                The message to show in the deprecation warning.

            stacklevel (int, optional):
                The stack level for the warning.
        """
        warnings.warn(message, cls, stacklevel=stacklevel + 1)


class RemovedInRBTools40Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 4.0.

    Note that this class will itself be removed in RBTools 4.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """


RemovedInNextRBToolsVersionWarning = RemovedInRBTools40Warning
