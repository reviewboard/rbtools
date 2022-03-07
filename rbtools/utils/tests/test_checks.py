"""Unit tests for rbtools.utils.checks."""

from __future__ import unicode_literals

import sys

from rbtools.testing import TestCase
from rbtools.utils import checks


class ChecksTests(TestCase):
    """Unit tests for rbtools.utils.checks."""

    def test_check_install_with_found(self):
        """Testing check_install with executable found"""
        self.assertTrue(checks.check_install([sys.executable, ' --version']))

    def test_check_install_with_not_found(self):
        """Testing check_install with executable not found"""
        self.assertFalse(checks.check_install(['xxx-invalid-bin-xxx']))

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
