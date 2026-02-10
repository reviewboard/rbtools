"""RBTools version and package information.

These variables and functions can be used to identify the version of
Beanbag Tools. They're largely used for packaging purposes.
"""

from __future__ import annotations


#: The version of RBTools
#:
#: This is in the format of:
#:
#: (Major, Minor, Micro, Patch, alpha/beta/rc/final, Release Number, Released)
#:
VERSION: tuple[int, int, int, int, str, int, bool] = \
    (6, 0, 1, 0, 'alpha', 0, False)


def get_version_string() -> str:
    """Return the version as a human-readable string.

    Returns:
        str:
        The version number as a human-readable string.
    """
    major, minor, micro, patch, tag, release_num, is_release = VERSION

    version = f'{major}.{minor}'

    if micro or patch:
        version += '.{micro}'

        if patch:
            version += '.{patch}'

    if tag != 'final':
        if tag == 'rc':
            version += f' RC {release_num}'
        else:
            version += f' {tag} {release_num}'

    if not is_release:
        version += ' (dev)'

    return version


def get_package_version() -> str:
    """Return the version as a Python package version string.

    Returns:
        str:
        The version number as used in a Python package.
    """
    major, minor, micro, patch, tag, release_num = VERSION[:-1]

    version = f'{major}.{minor}'

    if micro or patch:
        version += f'.{micro}'

        if patch:
            version += f'.{patch}'

    if tag != 'final':
        if tag == 'alpha':
            tag = 'a'
        elif tag == 'beta':
            tag = 'b'

        version += f'{tag}{release_num}'

    return version


def is_release() -> bool:
    """Return whether this is a released version.

    Returns:
        bool:
        ``True`` if this is a released version of the package.
        ``False`` if it is a development version.
    """
    return VERSION[-1]


__version_info__ = VERSION[:-1]
__version__ = get_package_version()
