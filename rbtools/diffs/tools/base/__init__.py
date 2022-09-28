"""Base support for creating diff tools.

This contains the classes used to construct a diff tool implementation and
to provide diff results.

This particular module contains forwarding imports for:

.. autosummary::
   :nosignatures:

   ~rbtools.diffs.tools.base.diff_file_result.DiffFileResult
   ~rbtools.diffs.tools.base.diff_tool.BaseDiffTool

Version Added:
    4.0
"""

from rbtools.diffs.tools.base.diff_file_result import DiffFileResult
from rbtools.diffs.tools.base.diff_tool import BaseDiffTool


__all__ = [
    'BaseDiffTool',
    'DiffFileResult',
]

__autodoc_excludes__ = __all__
