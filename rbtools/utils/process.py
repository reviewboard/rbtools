from __future__ import print_function, unicode_literals

import logging
import os
import subprocess
import sys

import six

from rbtools.utils.encoding import force_unicode


def log_command_line(fmt, command):
    """Log a command line.

    Args:
        fmt (unicode):
            A format string to use for the log message.

        command (list):
            A command line in list form.
    """
    # While most of the subprocess library can deal with bytes objects in
    # command lines, list2cmdline can't. Decode each part if necessary.
    logging.debug(fmt, subprocess.list2cmdline([
        force_unicode(part) for part in command
    ]))


def execute(command,
            env=None,
            cwd=None,
            split_lines=False,
            ignore_errors=False,
            extra_ignore_errors=(),
            with_errors=True,
            none_on_ignored_error=False,
            return_error_code=False,
            log_output_on_error=True,
            results_unicode=True,
            return_errors=False):
    """Execute a command and return the output.

    Args:
        command (unicode or list of unicode):
            The command to execute.

        env (dict, optional):
            Environment variables to pass to the called executable. These will
            be added to the current environment.

        cwd (unicode, optional):
            An optional working directory to change to before executing the
            process.

        split_lines (bool, optional):
            Whether to return the output as a list of lines or a single string.

        ignore_errors (bool, optional):
            Whether to ignore errors. If ``False``, this will raise an
            exception.

        extra_ignore_errors (tuple, optional):
            A set of errors to ignore even when ``ignore_errors`` is False.
            This is used because some commands (such as diff) use non-zero
            return codes even when the command was successful.

        with_errors (bool, optional):
            Whether to combine the output and error streams of the command
            together into a single return value. This argument is mutually
            exclusive with the ``return_errors`` argument.

        none_on_ignored_error (bool, optional):
            Whether to return ``None`` in the case that an error was ignored
            (instead of the output of the command).

        return_error_code (bool, optional):
            Whether to include the exit status of the executed command in
            addition to the output

        log_output_on_error (bool, optional):
            If ``True``, the output from the command will be logged in the case
            that the command returned a non-zero exit code.

        results_unicode (bool, optional):
            If ``True``, the output will be treated as text and returned as
            unicode strings instead of bytes.

        return_errors (bool, optional):
            Whether to return the content of the stderr stream. This argument
            is mutually exclusive with the ``with_errors`` argument.

    Returns:
        This returns a single value, 2-tuple, or 3-tuple depending on the
        arguments.

        If ``return_error_code`` is True, the error code of the process will be
        returned as the first element of the tuple.

        If ``return_errors`` is True, the process' standard error stream will
        be returned as the last element of the tuple.

        If both of ``return_error_code`` and ``return_errors`` are ``False``,
        then the process' output will be returned. If either or both of them
        are ``True``, then this is the other element of the returned tuple.
    """
    assert not (with_errors and return_errors)

    if isinstance(command, list):
        log_command_line('Running: %s', command)
    else:
        logging.debug('Running: %s', command)

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

    popen_encoding_args = {}

    if results_unicode:
        # Popen before Python 3.6 doesn't support the ``encoding`` parameter,
        # so we have to use ``universal_newlines`` and then decode later.
        if six.PY3 and sys.version_info.minor >= 6:
            popen_encoding_args['encoding'] = 'utf-8'
        else:
            popen_encoding_args['universal_newlines'] = True

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
                             env=new_env,
                             cwd=cwd,
                             **popen_encoding_args)
    else:
        p = subprocess.Popen(command,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=errors_output,
                             shell=False,
                             close_fds=True,
                             env=new_env,
                             cwd=cwd,
                             **popen_encoding_args)

    data, errors = p.communicate()

    # We did not specify `encoding` to Popen earlier, so we must decode now.
    if results_unicode and 'encoding' not in popen_encoding_args:
        data = force_unicode(data)

    if split_lines:
        data = data.splitlines(True)

    if return_errors:
        if split_lines:
            errors = errors.splitlines(True)
    else:
        errors = None

    rc = p.wait()

    if rc and not ignore_errors and rc not in extra_ignore_errors:
        if log_output_on_error:
            logging.debug('Command exited with rc %s: %s\n%s---',
                          rc, command, data)

        raise Exception('Failed to execute command: %s' % command)
    elif rc:
        if log_output_on_error:
            logging.debug('Command exited with rc %s: %s\n%s---',
                          rc, command, data)
        else:
            logging.debug('Command exited with rc %s: %s',
                          rc, command)

    if rc and none_on_ignored_error:
        data = None

    if return_error_code and return_errors:
        return rc, data, errors
    elif return_error_code:
        return rc, data
    elif return_errors:
        return data, errors
    else:
        return data
