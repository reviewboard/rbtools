"""Utilities for managing string types and encoding."""

from typing import Union


def force_bytes(
    string: Union[bytes, str],
    encoding: str = 'utf-8',
) -> bytes:
    """Force a given string to be a bytes type.

    Args:
        string (bytes or str):
            The string to enforce.

    Returns:
        bytes:
        The string as a byte string.

    Raises:
        ValueError:
            The given string was not a supported type.
    """
    if isinstance(string, bytes):
        return string
    elif isinstance(string, str):
        return string.encode(encoding)
    else:
        raise ValueError('Provided string was neither bytes nor unicode')


def force_unicode(
    string: Union[bytes, str],
    encoding: str = 'utf-8',
) -> str:
    """Force a given string to be a Unicode string type.

    Args:
        string (bytes or str):
            The string to enforce.

    Returns:
        str:
        The string as a unicode type.

    Raises:
        ValueError:
            The given string was not a supported type.
    """
    if isinstance(string, str):
        return string
    elif isinstance(string, bytes):
        return string.decode(encoding)
    else:
        raise ValueError('Provided string was neither bytes nor unicode')
