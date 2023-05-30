"""Utilities for managing string types and encoding."""

from __future__ import annotations

from typing import Any, Union, overload

from typing_extensions import Literal


@overload
def force_bytes(
    string: Union[bytes, str],
    encoding: str = ...,
    *,
    strings_only: Literal[True] = ...,
) -> bytes:
    ...


@overload
def force_bytes(
    string: Any,
    encoding: str = ...,
    *,
    strings_only: Literal[False],
) -> bytes:
    ...


def force_bytes(
    string: Any,
    encoding: str = 'utf-8',
    *,
    strings_only: bool = True,
) -> bytes:
    """Force a given string to be a byte string type.

    Version Changed:
        5.0:
        Added the ``strings_only`` parameter.

    Args:
        string (bytes or str or object):
            The string to enforce, or an object that can cast to a string
            type.

        encoding (str, optional):
            The optional encoding, if encoding Unicode strings.

        strings_only (bool, optional):
            Whether to only transform byte/Unicode strings.

            If ``True`` (the default), any other type will result in an error.

            If ``False``, the object will be cast to a string using
            the object's :py:meth:`~object.__bytes__` or
            :py:meth:`~object.__str__` method.

            Version Added:
                5.0

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
    elif not strings_only:
        if hasattr(string, '__bytes__'):
            return bytes(string)
        else:
            return str(string).encode(encoding)

    raise ValueError(
        'The provided value could not be cast to a byte string: %r'
        % (string,))


@overload
def force_unicode(
    string: Union[bytes, str],
    encoding: str = ...,
    *,
    strings_only: Literal[True] = ...,
) -> str:
    ...


@overload
def force_unicode(
    string: Any,
    encoding: str = ...,
    *,
    strings_only: Literal[False],
) -> str:
    ...


def force_unicode(
    string: Any,
    encoding: str = 'utf-8',
    *,
    strings_only: bool = True,
) -> str:
    """Force a given string to be a Unicode string type.

    Version Changed:
        5.0:
        Added the ``strings_only`` parameter.

    Args:
        string (bytes or str or object):
            The string to enforce, or an object that can cast to a string
            type.

        encoding (str, optional):
            The optional encoding, if decoding byte strings.

        strings_only (bool, optional):
            Whether to only transform byte/Unicode strings.

            If ``True`` (the default), any other type will result in an error.

            If ``False``, the object will be cast to a string using
            the object's :py:meth:`~object.__str__` method.

            Version Added:
                5.0

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
    elif not strings_only and hasattr(string, '__str__'):
        return str(string)
    else:
        raise ValueError(
            'The provided value could not be cast to a Unicode string: %r'
            % (string,))
