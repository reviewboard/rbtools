"""Utilities for checking for dependencies."""

from __future__ import annotations

import subprocess


GNU_DIFF_WIN32_URL = 'http://gnuwin32.sourceforge.net/packages/diffutils.htm'


def check_install(
    command: list[str],
) -> bool:
    """Check if the given command is installed.

    Try executing an external command and return a boolean indicating whether
    that command is installed or not. The 'command' argument should be
    something that executes quickly, without hitting the network (for
    instance, 'svn help' or 'git --version').

    Args:
        command (list of str):
            The command to run.

    Returns:
        bool:
        Whether the given command can be run.
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
