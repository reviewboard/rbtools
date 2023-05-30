"""Unit tests for rbtools.utils.encoding.

Version Added:
    5.0
"""

from __future__ import annotations

from rbtools.testing import TestCase
from rbtools.utils.encoding import force_bytes, force_unicode


class MyBytesObject:
    def __bytes__(self) -> bytes:
        return b'a\x1b\x2c\x99'


class MyStrObject:
    def __str__(self) -> str:
        return 'abc 🙃 def'


class ForceBytesTests(TestCase):
    """Unit tests for force_bytes.

    Version Added:
        5.0
    """

    def test_with_bytes(self) -> None:
        """Testing force_bytes with bytes"""
        self.assertEqual(force_bytes(b'a\x1b\x2c\x99'),
                         b'a\x1b\x2c\x99')

    def test_with_str(self) -> None:
        """Testing force_bytes with Unicode string"""
        self.assertEqual(force_bytes('abc 🙃 def'),
                         b'abc \xf0\x9f\x99\x83 def')

    def test_with_cast_to_bytes(self) -> None:
        """Testing force_bytes with object with __bytes__ method and default
        behavior
        """
        obj = MyBytesObject()

        message = (
            'The provided value could not be cast to a byte string: %r'
            % obj
        )

        with self.assertRaisesMessage(ValueError, message):
            force_bytes(obj)  # type: ignore

    def test_with_cast_to_bytes_and_strings_only_false(self) -> None:
        """Testing force_bytes with object with __bytes__ method and
        strings_only=False
        """
        self.assertEqual(force_bytes(MyBytesObject(), strings_only=False),
                         b'a\x1b\x2c\x99')

    def test_with_cast_to_str(self) -> None:
        """Testing force_bytes with object with __str__ method and default
        behavior
        """
        obj = MyStrObject()

        message = (
            'The provided value could not be cast to a byte string: %r'
            % obj
        )

        with self.assertRaisesMessage(ValueError, message):
            force_bytes(obj)  # type: ignore

    def test_with_cast_to_str_and_strings_only_false(self) -> None:
        """Testing force_bytes with object with __str__ method and
        strings_only=False
        """
        self.assertEqual(force_bytes(MyStrObject(), strings_only=False),
                         b'abc \xf0\x9f\x99\x83 def')


class ForceUnicodeTests(TestCase):
    """Unit tests for force_unicode.

    Version Added:
        5.0
    """

    def test_with_str(self) -> None:
        """Testing force_unicode with Unicode string"""
        self.assertEqual(force_unicode('abc 🙃 def'),
                         'abc 🙃 def')

    def test_with_bytes(self) -> None:
        """Testing force_unicode with bytes"""
        self.assertEqual(force_unicode(b'abc \xf0\x9f\x99\x83 def'),
                         'abc 🙃 def')

    def test_with_cast_to_str(self) -> None:
        """Testing force_unicode with object with __str__ method and default
        behavior
        """
        obj = MyStrObject()

        message = (
            'The provided value could not be cast to a Unicode string: %r'
            % obj
        )

        with self.assertRaisesMessage(ValueError, message):
            force_unicode(obj)  # type: ignore

    def test_with_cast_to_str_and_strings_only_false(self) -> None:
        """Testing force_unicode with object with __str__ method and
        strings_only=False
        """
        self.assertEqual(force_unicode(MyStrObject(), strings_only=False),
                         'abc 🙃 def')
