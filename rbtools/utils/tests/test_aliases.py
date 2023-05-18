"""Unit tests for rbtools.utils.aliases."""

from rbtools.testing import TestCase
from rbtools.utils.aliases import replace_arguments


class AliasTests(TestCase):
    """Tests for rbtools.utils.aliases."""

    def test_replace_arguments_basic(self):
        """Testing replace_arguments with variables and arguments"""
        self.assertEqual(replace_arguments('$1', ['HEAD'], posix=True),
                         ['HEAD'])

    def test_replace_arguments_multiple(self):
        """Testing replace_arguments with multiple variables and arguments"""
        self.assertEqual(replace_arguments('$1..$2', ['a', 'b'], posix=True),
                         ['a..b'])

    def test_replace_arguments_blank(self):
        """Testing replace_arguments with variables and a missing argument"""
        self.assertEqual(replace_arguments('rbt post $1', [], posix=True),
                         ['rbt', 'post'])

    def test_replace_arguments_append(self):
        """Testing replace_arguments with no variables or arguments."""
        self.assertEqual(
            replace_arguments('echo', ['a', 'b', 'c'], posix=True),
            ['echo', 'a', 'b', 'c'])

    def test_replace_arguments_unrecognized_variables(self):
        """Testing replace_arguments with an unrecognized variable name"""
        self.assertEqual(replace_arguments('$1 $test', ['f'], posix=True),
                         ['f', '$test'])

    def test_replace_arguments_star(self):
        """Testing replace_arguments with the special $* variable"""
        self.assertEqual(replace_arguments('$*', ['a', 'b', 'c'], posix=True),
                         ['a', 'b', 'c'])

    def test_replace_arguments_star_whitespace(self):
        """Testing replace_arguments with the special $* variable with
        whitespace-containing arguments
        """
        self.assertEqual(
            replace_arguments('$*', ['a', 'b', 'c d e'], posix=True),
            ['a', 'b', 'c d e'])

    def test_replace_arguments_unescaped_non_posix(self):
        """Testing replace_arguments in non-POSIX mode does not evaluate escape
        sequences
        """
        self.assertEqual(replace_arguments(r'"$1 \\"', ['a'], posix=False),
                         [r'"a \\"'])

    def test_replace_arguments_invalid_quote(self):
        """Testing replace_arguments with invalid quotes in POSIX and non-POSIX
        mode raises an error
        """
        self.assertRaises(
            ValueError,
            lambda: replace_arguments('"foo', [], posix=True))

        self.assertRaises(
            ValueError,
            lambda: replace_arguments('"foo', [], posix=False))

    def test_replace_arguments_invalid_quote_posix(self):
        """Testing replace_arguments with escaped ending quote in non-POSIX
        mode does not escape the quote
        """
        self.assertEqual(replace_arguments('"\\"', [], posix=False),
                         ['"\\"'])

    def test_replace_arguments_invalid_quote_non_posix(self):
        """Testing replace_arguments with escaped ending quote in POSIX mode
        raises an error
        """
        self.assertRaises(
            ValueError,
            lambda: replace_arguments('"\\"', [], posix=True))

    def test_replace_arguments_quoted_non_posix(self):
        """Testing replace_arguments in non-POSIX mode with a quoted sequence
        in the command
        """
        self.assertEqual(
            replace_arguments("find . -iname '*.pyc' -delete", [],
                              posix=False),
            ['find', '.', '-iname', "'*.pyc'", '-delete'])

    def test_replace_arguments_escaped_posix(self):
        """Testing replace_arguments in POSIX mode evaluates escape sequences
        """
        self.assertEqual(
            replace_arguments(r'$1 \\ "\\" "\""', ['a'], posix=True),
            ['a', '\\', '\\', '"'])
