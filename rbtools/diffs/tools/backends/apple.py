"""A diff tool interfacing with Apple Diff.

Version Added:
    4.0
"""

import io
import re
from datetime import datetime
from typing import List

from rbtools.diffs.tools.base import BaseDiffTool, DiffFileResult
from rbtools.utils.filesystem import iter_exes_in_path
from rbtools.utils.process import RunProcessError, run_process


class AppleDiffTool(BaseDiffTool):
    """A diff tool interfacing with Apple Diff.

    Apple Diff is introduced with macOS Ventura, replacing GNU Diff.

    Version Added:
        4.0
    """

    diff_tool_id = 'apple'
    name = 'Apple Diff'

    _BINARY_FILES_DIFFER_RE = re.compile(
        br'^Binary files .*? and .*? differ$')

    _DIFF_HEADER_RE = re.compile(
        br'^(?P<line>(?:---|\+\+\+) .*?\t\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
        br'(?P<newline>[\r\n]+)$')

    def check_available(self) -> bool:
        """Check whether Apple Diff is available for use.

        This will check if Apple Diff is present in the system path.

        If available, this will set :py:attr:`exe_path` and
        :py:attr:`version_info`.

        Returns:
            bool:
            ``True`` if Apple Diff is available. ``False`` if it's not.
        """
        for diff_path in iter_exes_in_path('diff'):
            try:
                result = (
                    run_process([diff_path, '--version'],
                                ignore_errors=True)
                    .stdout
                    .readlines()
                )
            except Exception:
                # Skip this and try the next one.
                continue

            if result and result[0].startswith('Apple diff'):
                self.exe_path = diff_path
                self.version_info = result[0].strip()
                return True

        return False

    def make_run_diff_file_cmdline(
        self,
        *,
        orig_path: str,
        modified_path: str,
        show_hunk_context: bool = False,
        treat_missing_as_empty: bool = True,
    ) -> List[str]:
        """Return the command line for running the diff tool.

        This should generally be used by :py:meth:`run_diff_file`, and
        can be useful to unit tests that need to check for the process being
        run.

        Args:
            orig_path (str):
                The path to the original file.

            modified_path (str):
                The path to the modified file.

            show_hunk_context (bool, optional):
                Whether to show context on hunk lines, if supported by the
                diff tool.

            treat_missing_as_empty (bool, optional):
                Whether to treat a missing ``orig_path`` or ``modified_path``
                as an empty file, instead of failing to diff.

                This must be supported by subclasses.

        Returns:
            list of str:
            The command line to run for the given flags.
        """
        assert self.exe_path

        flags: List[str] = ['u']

        if treat_missing_as_empty:
            flags.append('N')

        if show_hunk_context:
            flags.append('p')

        return [
            self.exe_path,
            '-%s' % ''.join(flags),
            orig_path,
            modified_path,
        ]

    def run_diff_file(
        self,
        *,
        orig_path: str,
        modified_path: str,
        show_hunk_context: bool = False,
        treat_missing_as_empty: bool = True,
    ) -> DiffFileResult:
        """Return the result of a diff between two files.

        This will call Apple Diff with the appropriate parameters, returning
        a Unified Diff of the results.

        Args:
            orig_path (str):
                The path to the original file.

            modified_path (str):
                The path to the modified file.

            show_hunk_context (bool, optional):
                Whether to show context on hunk lines, if supported by the
                diff tool.

            treat_missing_as_empty (bool, optional):
                Whether to treat a missing ``orig_path`` or ``modified_path``
                as an empty file, instead of failing to diff.

        Returns:
            rbtools.diffs.tools.base.diff_file_result.DiffFileResult:
            The result of the diff operation.

        Raises:
            rbtools.utils.process.RunProcessError:
                There was an error invoking the diff tool. Details are in the
                exception.
        """
        assert self.available

        cmdline = self.make_run_diff_file_cmdline(
            orig_path=orig_path,
            modified_path=modified_path,
            show_hunk_context=show_hunk_context,
            treat_missing_as_empty=treat_missing_as_empty)

        process_result = run_process(cmdline,
                                     ignore_errors=(1, 2),
                                     log_debug_output_on_error=False)

        if process_result.exit_code == 0:
            # There were no differences.
            return DiffFileResult(orig_path=orig_path,
                                  modified_path=modified_path,
                                  diff=io.BytesIO(),
                                  has_text_differences=False)
        else:
            # Differences were found, or trouble occurred.
            #
            # We may get either value from Apple Diff for binary files,
            # despite documentation claiming we'd receive an exit code of 1.
            lines = process_result.stdout_bytes.readlines()

            if (len(lines) == 1 and
                self._BINARY_FILES_DIFFER_RE.match(lines[0])):
                # This appears to be a binary file. Return a normalized
                # version of this.
                return DiffFileResult(
                    orig_path=orig_path,
                    modified_path=modified_path,
                    diff=io.BytesIO(b'Binary files %s and %s differ\n'
                                    % (orig_path.encode('utf-8'),
                                       modified_path.encode('utf-8'))),
                    is_binary=True,
                    has_text_differences=False)
            elif process_result.exit_code == 1:
                process_result.stdout_bytes.seek(0)

                return DiffFileResult(
                    orig_path=orig_path,
                    modified_path=modified_path,
                    diff=self._normalize_diff(process_result.stdout_bytes))

        # Something else went wrong. Raise this.
        raise RunProcessError(process_result)

    def _normalize_diff(
        self,
        stream: io.BytesIO,
    ) -> io.BytesIO:
        """Normalize an Apple Diff result.

        Apple Diff and GNU Diff mostly have the same Unified Diff output,
        but they do differ when it comes to timestamps.

        GNU Diff timestamps include millisecond precision and a timezone
        offset. For some reason, Apple Diff only does this if running in
        "legacy" mode" (running with a ``COMMAND_MODE=legacy`` environment),
        with a documentation warning that these may not be patchable.

        We still need consistency, though, and GNU Diff's output is the
        target. Rather than rely on that environment, which may conceivably
        change in the future, this method processes the diff and adds the
        millisecond precision (of 0) and timezone offset to the timestamp.

        If Apple Diff ever changes, this function will effectively be a no-op.

        Args:
            stream (io.BytesIO):
                The stream from running Apple Diff.

        Returns:
            io.BytesIO:
            The resulting stream with a processed diff.
        """
        DIFF_HEADER_RE = self._DIFF_HEADER_RE

        diff = io.BytesIO()
        timezone = datetime.now().astimezone().strftime('%z').encode('utf-8')
        normalized = False

        for i in range(2):
            line = stream.readline()

            m = DIFF_HEADER_RE.match(line)

            if m:
                diff.write(b'%s.000000000 %s%s'
                           % (m.group('line'),
                              timezone,
                              m.group('newline')))
                normalized = True
            else:
                diff.write(line)

        if normalized:
            diff.write(stream.read())
        else:
            diff = stream

        diff.seek(0)

        return diff
