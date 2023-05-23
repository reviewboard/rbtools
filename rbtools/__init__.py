"""RBTools version and package information.

These variables and functions can be used to identify the version of
Beanbag Tools. They're largely used for packaging purposes.
"""

#: The version of RBTools
#:
#: This is in the format of:
#:
#: (Major, Minor, Micro, Patch, alpha/beta/rc/final, Release Number, Released)
#:
VERSION = (4, 1, 0, 0, 'final', 0, True)


def get_version_string():
    """Return the version as a human-readable string.

    Returns:
        str:
        The version number as a human-readable string.
    """
    major, minor, micro, patch, tag, relnum, is_release = VERSION

    version = '%s.%s' % (major, minor)

    if micro or patch:
        version += '.%s' % micro

        if patch:
            version += '.%s' % patch

    if tag != 'final':
        if tag == 'rc':
            version += ' RC'
        else:
            version += ' %s ' % tag

        version += '%s' % relnum

    if not is_release:
        version += ' (dev)'

    return version


def get_package_version():
    """Return the version as a Python package version string.

    Returns:
        str:
        The version number as used in a Python package.
    """
    major, minor, micro, patch, tag, relnum = __version_info__

    version = '%s.%s' % (major, minor)

    if micro or patch:
        version += '.%s' % micro

        if patch:
            version += '.%s' % patch

    if tag != 'final':
        version += '%s%s' % (
            {
                'alpha': 'a',
                'beta': 'b',
            }.get(tag, tag),
            relnum)

    return version


def is_release():
    """Return whether this is a released version.

    Returns:
        bool:
        ``True`` if this is a released version of the package.
        ``False`` if it is a development version.
    """
    return VERSION[-1]


__version_info__ = VERSION[:-1]
__version__ = get_package_version()
