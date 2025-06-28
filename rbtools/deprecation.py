"""Internal support for handling deprecations in RBTools.

The version-specific objects in this module are not considered stable between
releases, and may be removed at any point. The base objects are considered
stable.
"""

from __future__ import annotations

from housekeeping import (BasePendingRemovalWarning,
                          BaseRemovedInWarning)


class PendingRemovalInRBToolsWarning(BasePendingRemovalWarning):
    """Pending deprecation for code in RBTools.

    Version Added:
        5.0
    """

    product = 'RBTools'


class BaseRemovedInRBToolsVersionWarning(BaseRemovedInWarning):
    """Base class for a RBTools deprecation warning.

    All version-specific deprecation warnings inherit from this, allowing
    callers to check for Review Board deprecations without being tied to a
    specific version.
    """

    product = 'RBTools'


class RemovedInRBTools70Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 7.0.

    Note that this class will itself be removed in RBTools 7.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """

    version = '7.0'


class RemovedInRBTools80Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 8.0.

    Note that this class will itself be removed in RBTools 8.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """

    version = '8.0'


RemovedInNextRBToolsVersionWarning = RemovedInRBTools70Warning
