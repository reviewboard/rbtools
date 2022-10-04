"""Unit tests for rbtools.utils.process."""

import os
import re
import sys
from typing import Any, List

import rbtools.testing
from rbtools.testing import TestCase
from rbtools.utils.process import (RunProcessError,
                                   RunProcessResult,
                                   execute,
                                   run_process)


class RunProcessTests(TestCase):
    """Unit tests for run_process."""

    def test_with_command_list_str(self):
        """Testing run_process with command as list of strings"""
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process([
                sys.executable,
                '-c',
                'print("⭐️")',
            ])

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=r'%s -c print(\"⭐️\")' % sys.executable,
            expected_stdout_bytes=b'\xe2\xad\x90\xef\xb8\x8f\n',
            expected_stdout_str='⭐️\n')

    def test_with_command_list_bytes(self):
        """Testing run_process with command as list of bytes"""
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process([
                sys.executable.encode('utf-8'),
                b'-c',
                b'print("\xe2\xad\x90\xef\xb8\x8f")',
            ])

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=r'%s -c print(\"⭐️\")' % sys.executable,
            expected_stdout_bytes=b'\xe2\xad\x90\xef\xb8\x8f\n',
            expected_stdout_str='⭐️\n')

    def test_with_command_str(self):
        """Testing run_process with command as string"""
        cwd = os.getcwd()

        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process('pwd')

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command='pwd',
            expected_stdout_bytes=b'%s\n' % cwd.encode('utf-8'),
            expected_stdout_str='%s\n' % cwd)

    def test_with_command_bytes(self):
        """Testing run_process with command as bytes"""
        cwd = os.getcwd()

        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process(b'pwd')

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command='pwd',
            expected_stdout_bytes=b'%s\n' % cwd.encode('utf-8'),
            expected_stdout_str='%s\n' % cwd)

    def test_with_stdout(self):
        """Testing run_process with stdout"""
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process([
                sys.executable,
                '-c',
                'print("test 🦕")',
            ])

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=r'%s -c "print(\"test 🦕\")"' % sys.executable,
            expected_stdout_bytes=b'test \xf0\x9f\xa6\x95\n',
            expected_stdout_str='test 🦕\n')

    def test_with_stderr(self):
        """Testing run_process with stderr"""
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process([
                sys.executable,
                '-c',
                'import sys; sys.stdout.write("test"); sys.stderr.write("🦕")',
            ])

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                r'%s -c "import sys; sys.stdout.write(\"test\");'
                r' sys.stderr.write(\"🦕\")"'
                % sys.executable
            ),
            expected_stdout_bytes=b'test',
            expected_stderr_bytes=b'\xf0\x9f\xa6\x95',
            expected_stdout_str='test',
            expected_stderr_str='🦕')

    def test_with_redirect_stderr(self):
        """Testing run_process with redirect_stderr="""
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process(
                [
                    sys.executable,
                    '-c',
                    'import sys; sys.stdout.write("test");'
                    ' sys.stderr.write("🦕")',
                ],
                redirect_stderr=True)

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                r'%s -c "import sys; sys.stdout.write(\"test\");'
                r' sys.stderr.write(\"🦕\")"'
                % sys.executable
            ),
            expected_stdout_bytes=b'test\xf0\x9f\xa6\x95',
            expected_stdout_str='test🦕')

    def test_with_exit_code_non_0(self):
        """Testing run_process with exit_code != 0"""
        command = '%s -c "import sys; sys.exit(1)"' % sys.executable
        message = 'Unexpected error executing the command: %s' % command

        with self.assertLogs(level='DEBUG') as log_ctx:
            with self.assertRaisesMessage(RunProcessError, message) as e_ctx:
                run_process([
                    sys.executable,
                    '-c',
                    'import sys; sys.exit(1)',
                ])

        result = e_ctx.exception.result

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                '%s -c "import sys; sys.exit(1)"'
                % sys.executable
            ),
            expected_exit_code=1,
            expected_extra_log_lines=[
                "DEBUG:rbtools.utils.process:Command errored with rc=1: %s"
                % result.command,

                "DEBUG:rbtools.utils.process:Command stdout=b''",

                "DEBUG:rbtools.utils.process:Command stderr=b''",
            ])

    def test_with_exit_code_non_0_and_log_debug_output_on_error_false(self):
        """Testing run_process with exit_code != 0 and
        log_debug_output_on_error=False
        """
        command = '%s -c "import sys; sys.exit(1)"' % sys.executable
        message = 'Unexpected error executing the command: %s' % command

        with self.assertLogs(level='DEBUG') as log_ctx:
            with self.assertRaisesMessage(RunProcessError, message) as e_ctx:
                run_process(
                    [
                        sys.executable,
                        '-c',
                        'import sys; sys.exit(1)',
                    ],
                    log_debug_output_on_error=False)

        result = e_ctx.exception.result

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                '%s -c "import sys; sys.exit(1)"'
                % sys.executable
            ),
            expected_exit_code=1,
            expected_extra_log_lines=[
                "DEBUG:rbtools.utils.process:Command errored with rc=1: %s"
                % result.command,
            ])

    def test_with_cwd(self):
        """Testing run_process with cwd="""
        path = os.path.abspath(os.path.join(rbtools.testing.__file__, '..'))

        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process(
                [
                    sys.executable,
                    '-c',
                    'import os; print(os.getcwd())',
                ],
                cwd=path)

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                '%s -c "import os; print(os.getcwd())"'
                % sys.executable
            ),
            expected_stdout_bytes=b'%s\n' % path.encode('utf-8'),
            expected_stdout_str='%s\n' % path)

    def test_with_env(self):
        """Testing run_process with env="""
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process(
                [
                    sys.executable,
                    '-c',
                    'import os; print(os.environ.get("RBTOOLS_TEST"))',
                ],
                env={
                    'RBTOOLS_TEST': 'hi!',
                })

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                r'%s -c "import os; print(os.environ.get(\"RBTOOLS_TEST\"))"'
                % sys.executable
            ),
            expected_stdout_bytes=b'hi!\n',
            expected_stdout_str='hi!\n')

    def test_with_encoding(self):
        """Testing run_process with encoding="""
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process(
                [
                    sys.executable,
                    '-c',
                    r'import sys;'
                    r' sys.stdout.buffer.write("🦕\n".encode("utf-16"))',
                ],
                encoding='utf-16')

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                r'%s -c "import sys;'
                r' sys.stdout.buffer.write(\"🦕\n\".encode(\"utf-16\"))"'
                % sys.executable
            ),
            expected_encoding='utf-16',
            expected_stdout_bytes=b'\xff\xfe>\xd8\x95\xdd\n\x00',
            expected_stdout_str='🦕\n')

    def test_with_ignore_errors_true(self):
        """Testing run_process with ignore_errors=True"""
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process(
                [
                    sys.executable,
                    '-c',
                    'import sys; print("test"); sys.exit(1)'
                ],
                ignore_errors=True)

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                r'%s -c "import sys; print(\"test\"); sys.exit(1)"'
                % sys.executable
            ),
            expected_exit_code=1,
            expected_ignored_error=True,
            expected_stdout_bytes=b'test\n',
            expected_stdout_str='test\n',
            expected_extra_log_lines=[
                "DEBUG:rbtools.utils.process:Command exited with rc=1"
                " (errors ignored): %s"
                % result.command,

                "DEBUG:rbtools.utils.process:Command stdout=b'test\\n'",

                "DEBUG:rbtools.utils.process:Command stderr=b''",
            ])

    def test_with_ignore_errors_tuple_and_code_found(self):
        """Testing run_process with ignore_errors=(...) with exit code found
        """
        with self.assertLogs(level='DEBUG') as log_ctx:
            result = run_process(
                [
                    sys.executable,
                    '-c',
                    'import sys; print("test"); sys.exit(10)'
                ],
                ignore_errors=(1, 2, 10))

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                r'%s -c "import sys; print(\"test\"); sys.exit(10)"'
                % sys.executable
            ),
            expected_exit_code=10,
            expected_ignored_error=True,
            expected_stdout_bytes=b'test\n',
            expected_stdout_str='test\n',
            expected_extra_log_lines=[
                "DEBUG:rbtools.utils.process:Command exited with rc=10"
                " (errors ignored): %s"
                % result.command,

                "DEBUG:rbtools.utils.process:Command stdout=b'test\\n'",

                "DEBUG:rbtools.utils.process:Command stderr=b''",
            ])

    def test_with_ignore_errors_tuple_and_code_not_found(self):
        """Testing run_process with ignore_errors=(...) with exit code not
        found
        """
        message = (
            r'Unexpected error executing the command: '
            r'%s -c "import sys; print(\"test\"); sys.exit(3)"'
            % sys.executable
        )

        with self.assertLogs(level='DEBUG') as log_ctx:
            with self.assertRaisesMessage(RunProcessError, message) as ctx:
                run_process(
                    [
                        sys.executable,
                        '-c',
                        'import sys; print("test"); sys.exit(3)'
                    ],
                    ignore_errors=(1, 2, 10))

        result = ctx.exception.result

        self._check_result(
            result=result,
            log_ctx=log_ctx,
            expected_command=(
                r'%s -c "import sys; print(\"test\"); sys.exit(3)"'
                % sys.executable
            ),
            expected_exit_code=3,
            expected_stdout_bytes=b'test\n',
            expected_stdout_str='test\n',
            expected_extra_log_lines=[
                "DEBUG:rbtools.utils.process:Command errored with rc=3: %s"
                % result.command,

                "DEBUG:rbtools.utils.process:Command stdout=b'test\\n'",

                "DEBUG:rbtools.utils.process:Command stderr=b''",
            ])

    def test_with_file_not_found(self):
        """Testing run_process with executable file not found"""
        with self.assertLogs(level='DEBUG') as log_ctx:
            with self.assertRaises(FileNotFoundError):
                run_process('/xxx-invalid-command')

        self.assertEqual(
            log_ctx.output,
            [
                'DEBUG:rbtools.utils.process:Running: /xxx-invalid-command',

                'DEBUG:rbtools.utils.process:Command not found'
                ' (/xxx-invalid-command)',
            ])

    def test_with_permission_error(self):
        """Testing run_process with permission error"""
        with self.assertLogs(level='DEBUG') as log_ctx:
            with self.assertRaises(PermissionError):
                run_process(__file__)

        self.assertEqual(
            log_ctx.output,
            [
                "DEBUG:rbtools.utils.process:Running: %s" % __file__,

                "DEBUG:rbtools.utils.process:Permission denied running"
                " command (%s): [Errno 13] Permission denied: '%s'"
                % (__file__, __file__),
            ])

    def _check_result(
        self,
        result: RunProcessResult,
        log_ctx: Any,
        *,
        expected_command: str,
        expected_exit_code: int = 0,
        expected_ignored_error: bool = False,
        expected_encoding: str = 'utf-8',
        expected_stdout_bytes: bytes = b'',
        expected_stderr_bytes: bytes = b'',
        expected_stdout_str: str = '',
        expected_stderr_str: str = '',
        expected_extra_log_lines: List[str] = [],
    ) -> None:
        """Check the results of a call to run_process().

        This will check the result object and the log records for the
        expected values.

        Args:
            result (rbtools.utils.process.RunProcessResult):
                The result object from
                :py:func:`~rbtools.utils.process.run_process`.

            log_ctx (object):
                The log context.

            expected_command (str, optional):
                The expected command string.

            expected_exit_code (int, optional):
                The expected value for ``exit_code``.

            expected_ignored_error (bool, optional):
                The expected value for ``ignored_error``.

            expected_encoding (str, optional):
                The expected value for ``encoding``.

            expected_stdout_bytes (bytes, optional):
                The expected value for ``stdout_bytes.read()``.

            expected_stderr_bytes (bytes, optional):
                The expected value for ``stderr_bytes.read()``.

            expected_stdout_str (str, optional):
                The expected value for ``stdout.read()``.

            expected_stderr_str (str, optional):
                The expected value for ``stderr.read()``.

            expected_extra_log_lines (list of str, optional):
                The expected list of log lines after the initial
                "Running" log line.

        Raises:
            AssertionError:
                An expectation failed.
        """
        self.assertEqual(result.command, expected_command)
        self.assertEqual(result.exit_code, expected_exit_code)
        self.assertEqual(result.ignored_error, expected_ignored_error)
        self.assertEqual(result.encoding, expected_encoding)
        self.assertEqual(result.stdout_bytes.read(), expected_stdout_bytes)
        self.assertEqual(result.stderr_bytes.read(), expected_stderr_bytes)

        result.stdout_bytes.seek(0)
        result.stderr_bytes.seek(0)
        self.assertEqual(result.stdout.read(), expected_stdout_str)
        self.assertEqual(result.stderr.read(), expected_stderr_str)

        self.assertEqual(
            log_ctx.output,
            ['DEBUG:rbtools.utils.process:Running: %s' % expected_command] +
            expected_extra_log_lines)


class ExecuteTests(TestCase):
    """Unit tests for execute."""

    def test_execute(self):
        """Testing execute"""
        self.assertTrue(
            re.match('.*?%d.%d.%d' % sys.version_info[:3],
                     execute([sys.executable, '-V'])))
