"""Unit tests for rbtools.utils.process."""

from __future__ import unicode_literals

import re
import sys

from rbtools.utils.process import execute
from rbtools.utils.testbase import RBTestBase


class ProcessTests(RBTestBase):
    """Unit tests for rbtools.utils.process."""

    def test_execute(self):
        """Testing execute"""
        self.assertTrue(re.match('.*?%d.%d.%d' % sys.version_info[:3],
                        execute([sys.executable, '-V'])))
