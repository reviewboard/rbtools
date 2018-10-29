"""Utilities for managing string types and encoding."""

import six


def force_unicode(string, encoding='utf-8'):
    """Force a given string to be a unicode type.

    Args:
        string (bytes or unicode):
            The string to enforce.

    Returns:
        unicode:
        The string as a unicode type.

    Raises:
        ValueError:
            The given string was not a supported type.
    """
    if isinstance(string, six.text_type):
        return string
    elif isinstance(string, bytes):
        return string.decode(encoding)
    else:
        raise ValueError('Provided string was neither bytes nor unicode')
