import logging
import os
import subprocess
import sys

from rbtools.utils.filesystem import cleanup_tempfiles


def die(msg=None):
    """
    Cleanly exits the program with an error message. Erases all remaining
    temporary files.
    """
    cleanup_tempfiles()

    if msg:
        print msg

    sys.exit(1)


def execute(command, env=None, split_lines=False, ignore_errors=False,
            extra_ignore_errors=(), translate_newlines=True, with_errors=True):
    """
    Utility function to execute a command and return the output.
    """
    if isinstance(command, list):
        logging.debug(subprocess.list2cmdline(command))
    else:
        logging.debug(command)

    if env:
        env.update(os.environ)
    else:
        env = os.environ.copy()

    env['LC_ALL'] = 'en_US.UTF-8'
    env['LANGUAGE'] = 'en_US.UTF-8'

    if with_errors:
        errors_output = subprocess.STDOUT
    else:
        errors_output = subprocess.PIPE

    if sys.platform.startswith('win'):
        p = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=errors_output,
                             shell=False,
                             universal_newlines=translate_newlines,
                             env=env)
    else:
        p = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=errors_output,
                             shell=False,
                             close_fds=True,
                             universal_newlines=translate_newlines,
                             env=env)
    if split_lines:
        data = p.stdout.readlines()
    else:
        data = p.stdout.read()

    rc = p.wait()

    if rc and not ignore_errors and rc not in extra_ignore_errors:
        die('Failed to execute command: %s\n%s' % (command, data))

    return data
