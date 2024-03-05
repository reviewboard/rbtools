"""Internal support for handling deprecations in RBTools.

The version-specific objects in this module are not considered stable between
releases, and may be removed at any point. The base objects are considered
stable.
"""

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


class RemovedInRBTools50Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 5.0.

    Note that this class will itself be removed in RBTools 5.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """

    version = '5.0'


class RemovedInRBTools60Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 6.0.

    Note that this class will itself be removed in RBTools 6.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """

    version = '6.0'


class RemovedInRBTools70Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 7.0.

    Note that this class will itself be removed in RBTools 7.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """

    version = '7.0'


RemovedInNextRBToolsVersionWarning = RemovedInRBTools60Warning
