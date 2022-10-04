"""Utilities for working with streams.

Version Added:
    4.0
"""

from collections import deque
from itertools import islice
from typing import Deque, Iterable, Iterator, List, TypeVar


T = TypeVar('T')


class BufferedIterator(Iterator[T]):
    """A buffered wrapper for an iterator that allows for peeking.

    This allows consumers to look ahead on an iterator without consuming the
    items. It's particularly useful for stream processing, reading lines
    from the output of a command or the generation of a diff.

    Version Added:
        4.0
    """

    def __init__(
        self,
        iterable: Iterable[T],
    ) -> None:
        """Initialize the iterator.

        Args:
            iterable (iterable):
                The iterable to wrap.
        """
        self._iterator: Iterator[T] = iter(iterable)
        self._buffer: Deque[T] = deque()

    @property
    def is_empty(self) -> bool:
        """Whether the iterator is empty.

        Type:
            bool
        """
        return self.peek(1) == []

    def __iter__(self) -> Iterator[T]:
        """Iterate through the iterator.

        Yields:
            object:
            Each item in the iterator.
        """
        return self

    def __next__(self) -> T:
        """Return the next item from the iterator.

        Returns:
            object:
            The next item in the iterator.

        Raises:
            StopIteration:
                There are no more items left in the iterator.
        """
        buffer = self._buffer

        if buffer:
            return buffer.popleft()
        else:
            return next(self._iterator)

    def peek(
        self,
        count: int = 1,
    ) -> List[T]:
        """Return up to a specified number of items without consuming them.

        Peeked items will remain in the iterator for consumption.

        The resulting list will contain up to the requested amount. It will
        may contain less than the count, if there aren't enough items left
        in the iterator.

        If the iterator is empty, the result will be an empty list.

        Args:
            count (int, optional):
                The number of items to peek.

        Returns:
            list:
            The list of items.
        """
        buffer = self._buffer
        buffer_len = len(buffer)

        if count > buffer_len:
            buffer.extend(islice(self._iterator, count - buffer_len))

        return list(islice(buffer, count))

    def consume(
        self,
        count: int = 1,
    ) -> List[T]:
        """Consume up to a specified number of items from the iterator.

        This will return the consumed items as a list.

        The resulting list will contain up to the requested amount. It will
        may contain less than the count, if there aren't enough items left
        in the iterator.

        If the iterator is empty, the result will be an empty list.

        Args:
            count (int, optional):
                The number of items to consume.

        Returns:
            list:
            The list of items.
        """
        return list(islice(self, count))
