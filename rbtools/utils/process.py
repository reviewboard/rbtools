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
            results_unicode=True,
            return_errors=False):
    """Utility function to execute a command and return the output.

    :param command:
        The command to execute as either a string or a list of strings.
    :param env:
        The environment variables to pass to the called executable.
        These variables will be added to the current set of environment
        variables.
    :param split_lines:
        Determines if the program's output will be split into multiple lines.
    :param ignore_errors:
        If ``False``, RBTools will exit if a command returns a non-zero status.
    :param extra_ignore_errors:
        The set of return status codes that should be treated as if the program
        exited with status 0.
    :param translate_newlines:
        If ``True``, all line endings will be translated to ``\n``.
    :param with_errors:
        If ``True``, the command's standard output and standard error streams
        will be combined. This parameter is mutually exclusive with the
        ``return_errors`` parameter.
    :param none_on_ignored_error:
        If ``True``, this function will return ``None`` if either
        ``ignore_errors`` is ``True` and the program returns a non-zero exit
        status or the program exits with a status code in
        ``extra_ignored_errors``.
    :param return_error_code:
        Determines if the exit status of the executed command will also be
        returned.
    :param log_output_on_error:
        Determines if the output of the executed command will be logged if it
        returns a non-zero status code.
    :param results_unicode:
        Determines if the output will be interpreted as UTF-8. If ``True``,
        the process's output will be returned as a ``six.text_type``.
        Otherwise, it will return a ``six.binary_type``.
    :param return_errors:
        Determines if the standard error stream will be returned. This
        parameter is mutually exclusive with the ``with_errors`` parameter.

    :returns:
        This function returns either a single value or a 2- or 3-tuple.

        If ``return_error_code`` is True, the error code of the process will be
        returned as the first element of the tuple.

        If ``return_errors`` is True, the process' standard error stream will
        be returned as the last element of the tuple.

        If both of ``return_error_code`` and ``return_errors`` are ``False``,
        then the process' output will be returned. If either or both of them
        are ``True``, then this is the other element of the returned tuple.
    """
    def post_process_output(output):
        """Post process the given output to convert it to the desired type."""
        # If Popen is called with universal_newlines=True, the resulting data
        # returned from stdout will be a text stream (and therefore a unicode
        # object). Otherwise, it will be a byte stream. Translate the results
        # into the desired type.
        encoding = sys.getfilesystemencoding()

        if split_lines and len(output) > 0:
            if results_unicode and isinstance(output[0], six.binary_type):
                return [line.decode(encoding) for line in output]
            elif not results_unicode and isinstance(output[0], six.text_type):
                return [line.encode('utf-8') for line in output]
        elif not split_lines:
            if results_unicode and isinstance(output, six.binary_type):
                return output.decode(encoding)
            elif not results_unicode and isinstance(output, six.text_type):
                return output.encode('utf-8')

        return output

    assert not (with_errors and return_errors)

    if isinstance(command, list):
        logging.debug(b'Running: ' + subprocess.list2cmdline(command))
    else:
        logging.debug(b'Running: ' + command)

    new_env = os.environ.copy()

    if env:
        new_env.update(env)

    # TODO: This can break on systems that don't have the en_US locale
    # installed (which isn't very many). Ideally in this case, we could
    # put something in the config file, but that's not plumbed through to here.
    new_env['LC_ALL'] = 'en_US.UTF-8'
    new_env['LANGUAGE'] = 'en_US.UTF-8'

    if with_errors:
        errors_output = subprocess.STDOUT
    else:
        errors_output = subprocess.PIPE

    if sys.platform.startswith('win'):
        # Convert all environment variables to byte strings, so that subprocess
        # doesn't blow up on Windows.
        new_env = dict(
            (six.binary_type(key), six.binary_type(value))
            for key, value in six.iteritems(new_env)
        )

        p = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=errors_output,
                             shell=False,
                             universal_newlines=translate_newlines,
                             env=new_env)
    else:
        p = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=errors_output,
                             shell=False,
                             close_fds=True,
                             universal_newlines=translate_newlines,
                             env=new_env)

    errors = None

    if split_lines:
        data = p.stdout.readlines()

        if return_errors:
            errors = p.stderr.readlines()
    else:
        data = p.stdout.read()

        if return_errors:
            errors = p.stderr.read()

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
        data = post_process_output(data)

    if return_errors:
        errors = post_process_output(errors)

    if return_error_code or return_errors:
        if return_error_code and return_errors:
            return rc, data, errors
        elif return_error_code:
            return rc, data
        else:
            return data, errors
    else:
        return data
