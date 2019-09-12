from __future__ import unicode_literals

import os
import re
import sys
import unittest


class TestCase(unittest.TestCase):
    """The base class for RBTools test cases.

    Unlike the standard unittest.TestCase, this allows the test case
    description (generally the first line of the docstring) to wrap multiple
    lines.
    """

    ws_re = re.compile(r'\s+')

    default_text_editor = '%s %s' % (
        sys.executable,
        os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     'scripts', 'editor.py'))
    )

    def setUp(self):
        super(TestCase, self).setUp()

        os.environ[str('RBTOOLS_EDITOR')] = str(self.default_text_editor)

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

    def assertRaisesMessage(self, expected_exception, expected_message):
        """Assert that a call raises an exception with the given message.

        Args:
            expected_exception (type):
                The type of exception that's expected to be raised.

            expected_message (unicode):
                The expected exception message.

        Raises:
            AssertionError:
                The assertion failure, if the exception and message isn't
                raised.
        """
        return self.assertRaisesRegexp(expected_exception,
                                       re.escape(expected_message))
