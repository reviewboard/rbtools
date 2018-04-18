from __future__ import unicode_literals

import os
import subprocess

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
        subprocess.Popen(command,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
        return True
    except (OSError, ValueError):
        # We catch ValueError exceptions here to work around bug in the
        # version of Python that ships with OS X 10.11. I don't know if the
        # logic is 100% reliable but if we get a ValueError here, it typically
        # means the command we are trying to run doesn't exist. See
        # http://bugs.python.org/issue26083
        return False


def check_gnu_diff():
    """Checks if GNU diff is installed, and informs the user if it's not."""
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
    """
    Takes two tuples, both in the form:
        (major_version, minor_version, micro_version)
    Returns true if the actual version is greater than or equal to
    the expected version, and false otherwise.
    """
    return ((actual[0] > expected[0]) or
            (actual[0] == expected[0] and actual[1] > expected[1]) or
            (actual[0] == expected[0] and actual[1] == expected[1] and
             actual[2] >= expected[2]))
