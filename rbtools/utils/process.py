from __future__ import print_function, unicode_literals

import logging
import os
import subprocess
import sys

import six


def die(msg=None):
    """Cleanly exits the program with an error message.

    Erases all remaining temporary files.
    """
    from rbtools.utils.filesystem import cleanup_tempfiles

    cleanup_tempfiles()

    if msg:
        print(msg)

    sys.exit(1)


def execute(command,
            env=None,
            split_lines=False,
            ignore_errors=False,
            extra_ignore_errors=(),
            translate_newlines=True,
            with_errors=True,
            none_on_ignored_error=False,
            return_error_code=False,
            log_output_on_error=True,
            results_unicode=True):
    """Utility function to execute a command and return the output."""
    if isinstance(command, list):
        logging.debug(b'Running: ' + subprocess.list2cmdline(command))
    else:
        logging.debug(b'Running: ' + command)

    if env:
        env.update(os.environ)
    else:
        env = os.environ.copy()

    # TODO: This can break on systems that don't have the en_US locale
    # installed (which isn't very many). Ideally in this case, we could
    # put something in the config file, but that's not plumbed through to here.
    env['LC_ALL'] = 'en_US.UTF-8'
    env['LANGUAGE'] = 'en_US.UTF-8'

    if with_errors:
        errors_output = subprocess.STDOUT
    else:
        errors_output = subprocess.PIPE

    if sys.platform.startswith('win'):
        # Convert all environment variables to byte strings, so that subprocess
        # doesn't blow up on Windows.
        env = dict([
            (bytes(key), bytes(value))
            for key, value in six.iteritems(env)
        ])

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
    elif rc:
        if log_output_on_error:
            logging.debug('Command exited with rc %s: %s\n%s---'
                          % (rc, command, data))
        else:
            logging.debug('Command exited with rc %s: %s'
                          % (rc, command))

    if rc and none_on_ignored_error:
        data = None

    if data is not None:
        # If Popen is called with universal_newlines=True, the resulting data
        # returned from stdout will be a text stream (and therefore a unicode
        # object). Otherwise, it will be a byte stream. Translate the results
        # into the desired type.
        if split_lines and len(data) > 0:
            if results_unicode and isinstance(data[0], bytes):
                data = [line.decode('utf-8') for line in data]
            elif not results_unicode and isinstance(data[0], six.text_type):
                data = [line.encode('utf-8') for line in data]
        elif not split_lines:
            if results_unicode and isinstance(data, bytes):
                data = data.decode('utf-8')
            elif not results_unicode and isinstance(data, six.text_type):
                data = line.encode('utf-8')

    if return_error_code:
        return rc, data
    else:
        return data
