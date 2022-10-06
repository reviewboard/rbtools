"""Unit tests for rbtools.utils.checks."""

import re
import sys

from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.testing import TestCase
from rbtools.utils.checks import check_install, is_valid_version


class ChecksTests(TestCase):
    """Unit tests for rbtools.utils.checks."""

    def test_check_install_with_found(self):
        """Testing check_install with executable found"""
        self.assertTrue(check_install([sys.executable, ' --version']))

    def test_check_install_with_not_found(self):
        """Testing check_install with executable not found"""
        self.assertFalse(check_install(['xxx-invalid-bin-xxx']))

    def test_is_valid_version(self):
        """Testing is_valid_version"""
        def _is_valid_version(actual, expected):
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                return is_valid_version(actual, expected)

        message = re.escape(
            'is_valid_version() is deprecated and will be removed in '
            'RBTools 5.0. Please compare tuples directly.'
        )

        self.assertTrue(_is_valid_version((1, 0, 0), (1, 0, 0)))
        self.assertTrue(_is_valid_version((1, 1, 0), (1, 0, 0)))
        self.assertTrue(_is_valid_version((1, 0, 1), (1, 0, 0)))
        self.assertTrue(_is_valid_version((1, 1, 0), (1, 1, 0)))
        self.assertTrue(_is_valid_version((1, 1, 1), (1, 1, 0)))
        self.assertTrue(_is_valid_version((1, 1, 1), (1, 1, 1)))

        self.assertFalse(_is_valid_version((0, 9, 9), (1, 0, 0)))
        self.assertFalse(_is_valid_version((1, 0, 9), (1, 1, 0)))
        self.assertFalse(_is_valid_version((1, 1, 0), (1, 1, 1)))
