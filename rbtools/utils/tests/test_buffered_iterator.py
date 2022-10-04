"""Unit tests for rbtools.utils.streams.BufferedIterator.

Version Added:
    4.0
"""

from rbtools.testing import TestCase
from rbtools.utils.streams import BufferedIterator


class BufferedIteratorTests(TestCase):
    """Unit tests for rbtools.utils.streams.BufferedIterator."""

    def test_is_empty_with_iter_empty(self):
        """Testing BufferedIterator.is_empty with empty iterator"""
        iterator = BufferedIterator([])
        self.assertTrue(iterator.is_empty)

    def test_is_empty_with_iter_populated(self):
        """Testing BufferedIterator.is_empty with iterator populated"""
        iterator = BufferedIterator([1])

        self.assertFalse(iterator.is_empty)

    def test_is_empty_with_iter_empty_buffer_populated(self):
        """Testing BufferedIterator.is_empty with iterator empty and buffer
        populated
        """
        iterator = BufferedIterator([1])
        iterator.peek(1)

        self.assertFalse(iterator.is_empty)

    def test_iter(self):
        """Testing BufferedIterator.__iter__"""
        iterator = BufferedIterator([1, 2, 3, 4])

        self.assertEqual(list(iterator), [1, 2, 3, 4])

    def test_iter_after_peek(self):
        """Testing BufferedIterator.__iter__ after peek"""
        iterator = BufferedIterator([1, 2, 3, 4])
        iterator.peek(2)

        self.assertEqual(list(iterator), [1, 2, 3, 4])

    def test_next(self):
        """Testing BufferedIterator.__next__"""
        iterator = BufferedIterator([1, 2, 3, 4])

        self.assertEqual(next(iterator), 1)
        self.assertEqual(next(iterator), 2)
        self.assertEqual(next(iterator), 3)
        self.assertEqual(next(iterator), 4)

        with self.assertRaises(StopIteration):
            next(iterator)

    def test_next_after_peek(self):
        """Testing BufferedIterator.__next__"""
        iterator = BufferedIterator([1, 2, 3, 4])
        iterator.peek(2)

        self.assertEqual(next(iterator), 1)
        self.assertEqual(next(iterator), 2)
        self.assertEqual(next(iterator), 3)
        self.assertEqual(next(iterator), 4)

        with self.assertRaises(StopIteration):
            next(iterator)

    def test_peek(self):
        """Testing BufferedIterator.peek"""
        iterator = BufferedIterator([1, 2, 3, 4])

        self.assertEqual(iterator.peek(2), [1, 2])

        # Doing this again should return the same buffer contents.
        self.assertEqual(iterator.peek(2), [1, 2])

    def test_peek_overflow(self):
        """Testing BufferedIterator.peek with count > iterator count"""
        iterator = BufferedIterator([1, 2, 3, 4])

        self.assertEqual(iterator.peek(6), [1, 2, 3, 4])

        # Doing this again should return the same buffer contents.
        self.assertEqual(iterator.peek(6), [1, 2, 3, 4])

    def test_peek_empty(self):
        """Testing BufferedIterator.peek with empty iterator"""
        iterator = BufferedIterator([])

        self.assertEqual(iterator.peek(2), [])

    def test_consume(self):
        """Testing BufferedIterator.consume"""
        iterator = BufferedIterator([1, 2, 3, 4])

        self.assertEqual(iterator.consume(2), [1, 2])

        # Doing this again should return the next contents.
        self.assertEqual(iterator.consume(2), [3, 4])

    def test_consume_overflow(self):
        """Testing BufferedIterator.consume with count > iterator count"""
        iterator = BufferedIterator([1, 2, 3, 4])

        self.assertEqual(iterator.consume(6), [1, 2, 3, 4])

        # Doing this again should return an empty list.
        self.assertEqual(iterator.consume(6), [])

    def test_consume_empty(self):
        """Testing BufferedIterator.consume with empty iterator"""
        iterator = BufferedIterator([])

        self.assertEqual(iterator.consume(2), [])

    def test_consume_after_peek(self):
        """Testing BufferedIterator.consume after peek"""
        iterator = BufferedIterator([1, 2, 3, 4])
        iterator.peek(2)

        self.assertEqual(iterator.consume(2), [1, 2])

        # One more time to be sure.
        iterator.peek(2)
        self.assertEqual(iterator.consume(2), [3, 4])
