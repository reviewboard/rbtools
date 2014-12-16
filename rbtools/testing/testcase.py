from __future__ import unicode_literals

import re
import unittest


class TestCase(unittest.TestCase):
    """The base class for RBTools test cases.

    Unlike the standard unittest.TestCase, this allows the test case
    description (generally the first line of the docstring) to wrap multiple
    lines.
    """
    ws_re = re.compile(r'\s+')

    def shortDescription(self):
        """Returns the description of the current test.

        This changes the default behavior to replace all newlines with spaces,
        allowing a test description to span lines. It should still be kept
        short, though.
        """
        doc = self._testMethodDoc

        if doc is not None:
            doc = doc.split('\n\n', 1)[0]
            doc = self.ws_re.sub(' ', doc).strip()

        return doc
