"""Classes for representing patch results in SCM clients.

Deprecated:
    5.1:
    This module has moved to :py:mod:`rbtools.diffs.patches`. This module
    will be removed in RBTools 7.

Version Added:
    4.0
"""

from __future__ import annotations

from housekeeping import module_moved

from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.diffs.patches import PatchAuthor, PatchResult


module_moved(RemovedInRBTools70Warning,
             old_module_name=__name__,
             new_module_name='rbtools.diffs.patches')


__all__ = [
    'PatchAuthor',
    'PatchResult',
]

__autodoc_excludes__ = __all__
