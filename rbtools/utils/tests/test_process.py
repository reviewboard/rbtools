"""Unit tests for rbtools.utils.process."""

from __future__ import unicode_literals

import re
import sys

from rbtools.testing import TestCase
from rbtools.utils.process import execute


class ProcessTests(TestCase):
    """Unit tests for rbtools.utils.process."""

    def test_execute(self):
        """Testing execute"""
        self.assertTrue(
            re.match('.*?%d.%d.%d' % sys.version_info[:3],
                     execute([sys.executable, '-V'])))
