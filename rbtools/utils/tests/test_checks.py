"""Unit tests for rbtools.utils.checks."""

from __future__ import annotations

import sys

from rbtools.testing import TestCase
from rbtools.utils.checks import check_install


class ChecksTests(TestCase):
    """Unit tests for rbtools.utils.checks."""

    def test_check_install_with_found(self) -> None:
        """Testing check_install with executable found"""
        self.assertTrue(check_install([sys.executable, ' --version']))

    def test_check_install_with_not_found(self) -> None:
        """Testing check_install with executable not found"""
        self.assertFalse(check_install(['xxx-invalid-bin-xxx']))
