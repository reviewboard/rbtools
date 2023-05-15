"""Utilities for checking for dependencies."""

import os
import subprocess

from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.process import execute


GNU_DIFF_WIN32_URL = 'http://gnuwin32.sourceforge.net/packages/diffutils.htm'


def check_install(command):
    """Check if the given command is installed.

    Try executing an external command and return a boolean indicating whether
    that command is installed or not.  The 'command' argument should be
    something that executes quickly, without hitting the network (for
    instance, 'svn help' or 'git --version').
    """
    try:
        p = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)

        stdout, stderr = p.communicate()

        # When pyenv is in use, and the needed executable is only available in
        # a different Python version, pyenv intercepts the call and prints an
        # error/returns 127. This prevents us from getting any of the expected
        # exceptions.
        if b'command not found' in stderr:
            return False
        else:
            return (p.returncode != 127)
    except (OSError, ValueError):
        # We catch ValueError exceptions here to work around bug in the
        # version of Python that ships with OS X 10.11. I don't know if the
        # logic is 100% reliable but if we get a ValueError here, it typically
        # means the command we are trying to run doesn't exist. See
        # http://bugs.python.org/issue26083
        return False


def check_gnu_diff():
    """Check if GNU diff is installed, and informs the user if it's not.

    Deprecated:
        4.0:
        Clients should use Diff Tools (see :py:mod:`rbtools.diffs.tools`)
        instead.

        This will be removed in 5.0.

    Raises:
        Exception:
            GNU diff is not installed.
    """
    RemovedInRBTools50Warning.warn(
        'check_gnu_diff() is deprecated and will be removed in RBTools 5.0. '
        'Use Diff Tools (rbtools.diffs.tools) instead.')

    has_gnu_diff = False

    try:
        if hasattr(os, 'uname') and os.uname()[0] == 'SunOS':
            diff_cmd = 'gdiff'
        else:
            diff_cmd = 'diff'

        result = execute([diff_cmd, '--version'], ignore_errors=True)
        has_gnu_diff = 'GNU diffutils' in result
    except OSError:
        pass

    if not has_gnu_diff:
        error = ('GNU diff is required in order to generate diffs. '
                 'Make sure it is installed and in the path.\n')

        if os.name == 'nt':
            error += ('On Windows, you can install this from %s\n'
                      % GNU_DIFF_WIN32_URL)

        raise Exception(error)


def is_valid_version(actual, expected):
    """Return whether one tuple is greater than or equal to another.

    Tuples should be in the form of::

        (major_version, minor_version, micro_version)

    With each version an integer.

    Deprecated:
        4.0:
        Consumers should just compare tuples directly. This will be removed
        in RBTools 5.0.

    Args:
        actual (tuple of int):
            The actual version to compare.

        expected (tuple of int):
            The expected version to compare against.

    Returns:
        bool:
        ``True`` if ``actual`` is greater than or equal to the expected
        version. ``False`` otherwise.
    """
    RemovedInRBTools50Warning.warn(
        'is_valid_version() is deprecated and will be removed in RBTools 5.0. '
        'Please compare tuples directly.')

    return ((actual[0] > expected[0]) or
            (actual[0] == expected[0] and actual[1] > expected[1]) or
            (actual[0] == expected[0] and actual[1] == expected[1] and
             actual[2] >= expected[2]))
