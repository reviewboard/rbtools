import io
import logging
import os
import subprocess
from typing import Any, AnyStr, Dict, List, Optional, Tuple, Union

from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.encoding import force_unicode


logger = logging.getLogger(__name__)


class RunProcessResult:
    """The result of running a process.

    This provides information on the command that was run, the return code,
    flags indicating if an error was met or ignored, and access to the raw
    or decoded standard output and error streams.

    This should only be constructed by :py:func:`run_process` or in unit tests
    when spying.

    Version Added:
        4.0
    """

    #: A string representation of the command that was run.
    #:
    #: Type:
    #:     str
    command: str

    #: The exit code from the process.
    #:
    #: Type:
    #:     int
    exit_code: int

    #: Whether this returned an exit code that was ignored.
    #:
    #: Type:
    #:     bool
    ignored_error: bool

    #: The encoding expected for any standard output or errors.
    #:
    #: This is used for decoding the streams when accessing
    #: :py:attr:`stdout` or :py:attr:`stderr`.
    #:
    #: Type:
    #:     str
    encoding: str

    #: The raw standard output from the process.
    #:
    #: This is a standard bytes I/O stream, which can be used to read
    #: some or all of the data from the process, either as raw bytes or
    #: lines of bytes.
    #:
    #: This is pre-populated with the entire contents of the process's
    #: standard output.
    #:
    #: Type:
    #:     io.BytesIO
    stdout_bytes: io.BytesIO

    #: The raw standard error output from the process.
    #:
    #: This is a standard bytes I/O stream, which can be used to read
    #: some or all of the data from the process, either as raw bytes or
    #: lines of bytes.
    #:
    #: This is pre-populated with the entire contents of the process's
    #: standard error output.
    #:
    #: Type:
    #:     io.BytesIO
    stderr_bytes: io.BytesIO

    def __init__(
        self,
        *,
        command: str,
        exit_code: int = 0,
        ignored_error: bool = False,
        stdout: bytes = b'',
        stderr: bytes = b'',
        encoding: str = 'utf-8',
    ) -> None:
        """Initialize the process result.

        Args:
            command (str):
                The string form of the command that was run.

            exit_code (int, optional):
                The exit code of the process.

            ignored_error (bool, optional):
                Whether a non-0 exit code was ignored.

            stdout (bytes, optional):
                The standard output from the process.

            stderr (bytes, optional):
                The standard error output from the process.

            encoding (str, optional):
                The expected encoding for the output streams.
        """
        self.command = command
        self.exit_code = exit_code
        self.ignored_error = ignored_error
        self.encoding = encoding
        self.stdout_bytes = io.BytesIO(stdout)
        self.stderr_bytes = io.BytesIO(stderr)
        self._stdout: Optional[io.TextIOWrapper] = None
        self._stderr: Optional[io.TextIOWrapper] = None

    @property
    def stdout(self) -> io.TextIOWrapper:
        """The standard output as a decoded Unicode stream.

        This will construct a text I/O wrapper on first access, wrapping
        :py:attr:`stdout_bytes` and decoding it using :py:attr:`encoding`.

        Type:
            io.TextIOWrapper
        """
        if self._stdout is None:
            self._stdout = io.TextIOWrapper(self.stdout_bytes,
                                            encoding=self.encoding)

        return self._stdout

    @property
    def stderr(self) -> io.TextIOWrapper:
        """The standard error output as a decoded Unicode stream.

        This will construct a text I/O wrapper on first access, wrapping
        :py:attr:`stderr_bytes` and decoding it using :py:attr:`encoding`.

        Type:
            io.TextIOWrapper
        """
        if self._stderr is None:
            self._stderr = io.TextIOWrapper(self.stderr_bytes,
                                            encoding=self.encoding)

        return self._stderr


class RunProcessError(Exception):
    """An error running a process.

    The error code and standard output/error streams are available through
    the :py:attr:`result` attribute. This can be used to further evaluate
    the cause of the error.

    Version Added:
        4.0
    """

    #: The result of running the process.
    #:
    #: Type:
    #:     RunProcessResult
    result: RunProcessResult

    def __init__(
        self,
        result: RunProcessResult,
    ) -> None:
        """Initialize the error.

        Args:
            result (RunProcessResult):
                The result of running the process.
        """
        super().__init__('Unexpected error executing the command: %s'
                         % result.command),

        self.result = result


def run_process(
    command: Union[AnyStr, List[AnyStr]],
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    encoding: str = 'utf-8',
    needs_stdout: bool = True,
    needs_stderr: bool = True,
    redirect_stderr: bool = False,
    ignore_errors: Union[bool, Tuple[int, ...]] = False,
    log_debug_output_on_error: bool = True,
) -> RunProcessResult:
    """Run a command and return the results.

    This will run the provided command and its arguments, optionally with
    the provided environment and working directory, returning a result that
    can be processed by the caller.

    Callers have access to the raw byte streams of the process's standard
    output and error streams, and can use those to decode or further process
    any results.

    This is the successor to :py:func:`execute`, which will be removed in a
    future release.

    Note that unit tests should not spy on this function. Instead, spy on
    :py:func:`run_process_exec`.

    Version Added:
        4.0

    Args:
        command (list of str):
            The command to execute.

            This should always be passed as a list of strings. It does accept
            passing a single string, or passing bytes instead of Unicode
            strings, but this is not recommended and is mainly for
            backwards-compatibility with :py:func:`execute`.

        cwd (str, optional):
            An optional working directory in which to run the command.

        env (dict, optional):
            Environment variables to pass to the called executable.

            These will be combined with the current environment and used for
            the process.

            :envvar:`LC_ALL` and :envvar:`LANGUAGE` will added to the final
            environment, set to ``en_US.UTF-8``.

        encoding (str, optional):
            The encoding used to convert any output to Unicode strings.
            This can usually be left as the default of ``utf-8``.

        needs_stdout (bool, optional):
            Whether the caller needs standard output captured.

            If ``True`` (the default), :py:attr:`RunProcessResult.stdout_bytes`
            and :py:attr:`RunProcessResult.stdout` will contain any standard
            output from the process.

            If ``False``, standard output will be not be captured, and those
            will contain empty strings.

        needs_stderr (bool, optional):
            Whether the caller needs standard error output captured.

            If ``True`` (the default), :py:attr:`RunProcessResult.stderr_bytes`
            and :py:attr:`RunProcessResult.stderr` will contain any standard
            error output from the process.

            If ``False``, standard error output will be not be captured, and
            those will contain empty strings.

            Note that ``redirect_stderr`` takes precedence over this.

        redirect_stderr (bool, optional):
            Whether to redirect stderr output to stdout, combining the results
            into one.

            If set, :py:attr:`RunProcessResult.stderr_bytes` and
            :py:attr:`RunProcessResult.stderr` will be empty. Instead, any
            standard error output (if any) will be set in
            :py:attr:`RunProcessResult.stdout` (note that this also requires
            ``needs_stdout=True`` to stay set, which is the default).

        ignore_errors (bool or tuple, optional):
            Whether to ignore errors, or specific exit codes to ignore.

            If ``False`` (the default), non-0 exit codes will raise a
            :py:class:`RunProcessError`.

            If ``True``, exit codes will never cause the exception to be
            raised.

            If set to a tuple of exit codes, then those codes (including 0)
            will be ignored, and any other non-0 code will raise the
            exception.

            This is a convenience over catching :py:class:`RunProcessError`
            and accessing :py:attr:`RunProcessError.result`.

        log_debug_output_on_error (bool, optional):
            Whether to log the full output and errors of a command if it
            returns a non-0 exit code.

            Non-0 error codes will always log a debug message about the
            result. However, if this is ``True``, the output and errors
            will also be logged.

            The default is ``True``.

    Returns:
        RunProcessResult:
        The result of running the process, if no errors in execution were
        encountered.

    Raises:
        Exception:
            Any unexpected exceptions from running the command.

        FileNotFoundError:
            The provided program could not be found.

        PermissionError:
            The user didn't have permissions to run the provided program,
            or the program wasn't executable.

        RunProcessError:
            The command returned a non-0 exit code, and that code wasn't
            ignored. Details of the command and its results will be available
            as part of the exception.

        TypeError:
            The value for ``command`` was not a string, bytes, or list of
            either.
    """
    assert isinstance(ignore_errors, (bool, tuple))

    if isinstance(command, list):
        command_str = subprocess.list2cmdline(
            force_unicode(_part)
            for _part in command
        )
    elif isinstance(command, bytes):
        command_str = force_unicode(command)
    elif isinstance(command, str):
        command_str = command
    else:
        raise TypeError('Unsupported type for command: %s' % type(command))

    logger.debug('Running: %s', command_str)

    # Build a new environment for the process, containing any caller-provided
    # arguments and some default locales.
    new_env = os.environ.copy()

    if env:
        new_env.update(env)

    # NOTE: This can break on systems that don't have the en_US locale
    #       installed (which isn't very many). Ideally in this case, we could
    #       put something in the config file, but that's not plumbed through to
    #       here.
    new_env['LC_ALL'] = 'en_US.UTF-8'
    new_env['LANGUAGE'] = 'en_US.UTF-8'

    # Run the process.
    try:
        exit_code, stdout, stderr = run_process_exec(
            command,
            cwd=cwd,
            env=new_env,
            needs_stdout=needs_stdout,
            needs_stderr=needs_stderr,
            redirect_stderr=redirect_stderr)
    except FileNotFoundError:
        logger.debug('Command not found (%s)',
                     command_str)
        raise
    except PermissionError as e:
        logger.debug('Permission denied running command (%s): %s',
                     command_str, e)
        raise
    except Exception as e:
        logger.debug('Unexpected error running command (%s): %s',
                     command_str, e)
        raise

    # Process results. We'll build a response, and then determine if we need
    # to raise an exception.
    assert isinstance(exit_code, int)
    assert stdout is None or isinstance(stdout, bytes)
    assert stderr is None or isinstance(stderr, bytes)
    assert needs_stderr or not redirect_stderr or stderr in (b'', None)
    assert needs_stdout or stdout in (b'', None)

    has_error = (exit_code != 0)

    ignored_error = (
        has_error and
        ignore_errors is True or
        (isinstance(ignore_errors, tuple) and
         exit_code in ignore_errors))

    # Convert that into a result for the caller or the exception.
    run_result = RunProcessResult(
        command=command_str,
        encoding=encoding,
        exit_code=exit_code,
        ignored_error=ignored_error,
        stdout=stdout or b'',
        stderr=stderr or b'')

    if has_error:
        # Log some useful information on the result, and possibly raise an
        # exception.
        if ignored_error:
            logger.debug('Command exited with rc=%s (errors ignored): %s',
                         exit_code, run_result.command)
        else:
            logger.debug('Command errored with rc=%s: %s',
                         exit_code, run_result.command)

        if log_debug_output_on_error:
            logger.debug('Command stdout=%r', stdout)
            logger.debug('Command stderr=%r', stderr)

        if not ignored_error:
            raise RunProcessError(run_result)

    return run_result


def run_process_exec(
    command: Union[AnyStr, List[AnyStr]],
    cwd: Optional[str],
    env: Dict[str, str],
    needs_stdout: bool,
    needs_stderr: bool,
    redirect_stderr: bool,
) -> Tuple[int, Optional[bytes], Optional[bytes]]:
    """Executes a command for run_process, returning results.

    This normally wraps :py:func:`subprocess.run`, returning results for use
    in :py:func:`run_process`.

    Unit tests should override this method to return results, rather than
    spying on :py:func:`run_process` itself. This will ensure the most
    accurate test results. :py:func:`run_process` will sanity-check the
    results to ensure they match the input parameters.

    Version Added:
        4.0

    Args:
        command (str):
            The command to run.

        cwd (str, optional):
            An optional working directory in which to run the command.

        env (dict, optional):
            Environment variables to pass to the called executable.

        needs_stdout (bool, optional):
            Whether the caller needs standard output captured.

        needs_stderr (bool, optional):
            Whether the caller needs standard error output captured.

        redirect_stderr (bool, optional):
            Whether to redirect stderr output to stdout, combining the results
            into one.

    Returns:
        tuple:
        A 3-tuple containing:

        Tuple:
            0 (int):
                The exit code.

            1 (bytes):
                The standard output, or ``None``.

            2 (bytes):
                The standard error output, or ``None``.

    Raises:
        Exception:
            All exceptions will be bubbled up to :py:func:`run_process`.
    """
    # Determine what we want to set for stdout and stderr.
    if needs_stdout:
        stdout = subprocess.PIPE
    else:
        stdout = subprocess.DEVNULL

    if redirect_stderr:
        stderr = subprocess.STDOUT
    elif needs_stderr:
        stderr = subprocess.PIPE
    else:
        stderr = subprocess.DEVNULL

    # Run the process.
    result = subprocess.run(
        command,
        stdin=subprocess.PIPE,
        stdout=stdout,
        stderr=stderr,
        env=env,
        cwd=cwd)

    return result.returncode, result.stdout, result.stderr


def log_command_line(
    fmt: str,
    command: List[AnyStr],
) -> None:
    """Log a command line.

    Deprecated:
        4.0:
        Callers should just pass the command line to
        :py:func:`subprocess.list2cmdline` and log the results instead.

    Args:
        fmt (unicode):
            A format string to use for the log message.

        command (list):
            A command line in list form.
    """
    RemovedInRBTools50Warning.warn(
        'log_command_line is deprecated and will be removed in RBTools 5.0. '
        'Please manually log the results of subprocess.list2cmdline instead.')

    # While most of the subprocess library can deal with bytes objects in
    # command lines, list2cmdline can't. Decode each part if necessary.
    logging.debug(fmt, subprocess.list2cmdline([
        force_unicode(part) for part in command
    ]))


def execute(
    command: Union[AnyStr, List[AnyStr]],
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    split_lines: bool = False,
    ignore_errors: bool = False,
    extra_ignore_errors: Tuple[int, ...] = (),
    with_errors: bool = True,
    none_on_ignored_error: bool = False,
    return_error_code: bool = False,
    log_output_on_error: bool = True,
    results_unicode: bool = True,
    return_errors: bool = False,
) -> Any:
    """Execute a command and return the output.

    Deprecated:
        4.0:
        This has been replaced with :py:func:`run_process`, which is more
        future-proof and has better type safety.

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
    data: Optional[Union[str, bytes, List[str], List[bytes]]]
    errors: Optional[Union[str, bytes, List[str], List[bytes]]]
    stdout: io.IOBase
    stderr: io.IOBase

    # We eventually want to unconditionally warn, but this has side effects
    # right now for tests checking other deprecation warnings for code that
    # eventually calls execute(). Short-term, we'll lock this behind an
    # environment variable to help with our development and debugging, and
    # make it mandatory later.
    if os.environ.get('RBTOOLS_WARN_EXECUTE_DEPRECATED') == '1':
        RemovedInRBTools50Warning.warn(
            'execute() is deprecated and will be removed in RBTools 5.0. '
            'Callers should use rbtools.utils.process.run_process() instead, '
            'which is future-proof and has better type safety.')

    assert not (with_errors and return_errors)

    result = run_process(
        command,
        cwd=cwd,
        env=env,
        redirect_stderr=with_errors,
        needs_stderr=return_errors,
        ignore_errors=ignore_errors or extra_ignore_errors or False,
        log_debug_output_on_error=log_output_on_error)

    rc: int = result.exit_code

    if results_unicode:
        stdout = result.stdout
        stderr = result.stderr
    else:
        stdout = result.stdout_bytes
        stderr = result.stderr_bytes

    if result.ignored_error and none_on_ignored_error:
        data = None
    elif split_lines:
        data = stdout.readlines()
    else:
        data = stdout.read()

    if not return_errors:
        errors = None
    elif split_lines:
        errors = stderr.readlines()
    else:
        errors = stderr.read()

    if return_error_code and return_errors:
        return rc, data, errors
    elif return_error_code:
        return rc, data
    elif return_errors:
        return data, errors
    else:
        return data
