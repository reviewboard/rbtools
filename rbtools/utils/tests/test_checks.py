"""Unit tests for rbtools.utils.checks."""

from __future__ import unicode_literals

import sys

from rbtools.utils import checks
from rbtools.utils.testbase import RBTestBase


class ChecksTests(RBTestBase):
    """Unit tests for rbtools.utils.checks."""

    def test_check_install(self):
        """Testing check_install"""
        self.assertTrue(checks.check_install([sys.executable, ' --version']))
        self.assertFalse(checks.check_install([self.gen_uuid()]))

    def test_is_valid_version(self):
        """Testing is_valid_version"""
        self.assertTrue(checks.is_valid_version((1, 0, 0), (1, 0, 0)))
        self.assertTrue(checks.is_valid_version((1, 1, 0), (1, 0, 0)))
        self.assertTrue(checks.is_valid_version((1, 0, 1), (1, 0, 0)))
        self.assertTrue(checks.is_valid_version((1, 1, 0), (1, 1, 0)))
        self.assertTrue(checks.is_valid_version((1, 1, 1), (1, 1, 0)))
        self.assertTrue(checks.is_valid_version((1, 1, 1), (1, 1, 1)))

        self.assertFalse(checks.is_valid_version((0, 9, 9), (1, 0, 0)))
        self.assertFalse(checks.is_valid_version((1, 0, 9), (1, 1, 0)))
        self.assertFalse(checks.is_valid_version((1, 1, 0), (1, 1, 1)))
