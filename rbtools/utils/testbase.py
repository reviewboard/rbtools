"""Legacy testing support for RBTools.

Deprecated:
    3.0:
    This will be removed in RBTools 4.0.
"""

from rbtools.deprecation import RemovedInRBTools40Warning
from rbtools.testing import TestCase


class RBTestBase(TestCase):
    """Legacy base class for RBTools unit tests.

    This has been replaced by :py:class:`rbtools.testing.testcase.TestCase`.
    Subclasses should switch to that, and set
    :py:attr:`rbtools.testing.testcase.TestCase.needs_home` to ``True`` if
    the tests all need to run in their own home directory.

    Deprecated:
        3.0:
        This will be removed in RBTools 4.0.
    """

    @classmethod
    def setUpClass(cls):
        RemovedInRBTools40Warning.warn(
            '%r should use rbtools.testing.TestCase as a base class instead '
            'of rbtools.utils.testbase.RBTestBase. The latter will be '
            'removed in RBTools 4.0.'
            % cls)

        super(RBTestBase, cls).setUpClass()

    needs_temp_home = True
