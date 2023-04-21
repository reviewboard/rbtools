"""A diff tool interfacing with GNU Diff.

Version Added:
    4.0
"""

import io
import os
import platform
import re
from typing import Iterator, List, Set

from rbtools.diffs.tools.base import BaseDiffTool, DiffFileResult
from rbtools.utils.filesystem import iter_exes_in_path
from rbtools.utils.process import RunProcessError, run_process


class GNUDiffTool(BaseDiffTool):
    """A diff tool interfacing with GNU Diff.

    Version Added:
        4.0
    """

    diff_tool_id = 'gnu'
    name = 'GNU Diff'

    _BEANBAG_DIFFUTILS_URL = \
        'http://downloads.reviewboard.org/ports/gnu-diffutils/'

    _GIT_WINDOWS_URL = 'https://git-scm.com/download/win'

    _BINARY_FILES_DIFFER_RE = re.compile(
        br'^(Binary files|Files) .*? and .*? differ$')

    @classmethod
    def get_install_instructions(cls) -> str:
        """Return instructions for installing this tool.

        This will provide different instructions for Windows and Linux,
        helping users install GNU Diff.

        macOS will always ship GNU Diff or Apple Diff, so we don't bother
        providing instructions here.

        Returns:
            str:
            The installation instructions, or an empty string, depending on
            the platform.
        """
        system = platform.system()

        # Only return instructions for Windows and Linux. For macOS,
        # /usr/bin/diff will be set to either GNU Diff (macOS 12 and older)
        # or Apple Diff (macOS 13 and newer) automatically.
        if system == 'Windows':
            return (
                "On Windows, if you're not using our RBTools for Windows "
                "installer, you can manually download our version of diff.exe "
                "(%(beanbag_diffutils_url)s) and place the bin/ directory in "
                "your system path. Alternatively, install Git for Windows "
                "(%(git_windows_url)s) and place it in your system path, as "
                "this version will also be compatible."
                % {
                    'beanbag_diffutils_url': cls._BEANBAG_DIFFUTILS_URL,
                    'git_windows_url': cls._GIT_WINDOWS_URL,
                }
            )
        elif system == 'Linux':
            return (
                'On Linux, GNU Diff can be installed using your system '
                'package manager.'
            )
        else:
            return ''

    def check_available(self) -> bool:
        """Check whether GNU Diff is available for use.

        This will check if GNU Diff is present in the system path.

        If available, this will set :py:attr:`exe_path` and
        :py:attr:`version_info`.

        Returns:
            bool:
            ``True`` if GNU Diff is available. ``False`` if it's not.
        """
        tried: Set[str] = set()

        for diff_path in self._iter_diff_paths():
            if diff_path in tried:
                continue

            tried.add(diff_path)

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

            if result and 'GNU diffutils' in result[0]:
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

        This will call GNU Diff with the appropriate parameters, returning
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
            # We may get either value from GNU Diff for binary files,
            # despite documentation claiming we'd receive an exit code of 2.
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
                    diff=process_result.stdout_bytes)

        # Something else went wrong. Raise this.
        raise RunProcessError(process_result)

    def _iter_diff_paths(self) -> Iterator[str]:
        """Iterate through possible paths for GNU diff.

        The results are not necessarily locations where GNU diff (or even
        a diff tool) reside, but rather are locations that should be checked.

        Version Added:
            4.0.1

        Yields:
            str:
            Each possible path for GNU diff.
        """
        if platform.system() == 'Windows':
            # On Windows, we want to prioritize some known locations first,
            # in order to avoid issues with other tools named diff.exe.
            #
            # First, try the version that comes with RBTools's Windows
            # installer.
            yield from (
                os.path.abspath(os.path.join(_rbt_path, '..', 'diff.exe'))
                for _rbt_path in iter_exes_in_path('rbt')
            )

            # Git supplies a copy of GNU Diff, but it's not in the PATH. If
            # Git is installed, attempt to include these paths.
            yield from (
                os.path.abspath(os.path.join(
                    git_path, '..', '..', 'usr', 'bin', 'diff.exe'))
                for git_path in iter_exes_in_path('git')
            )

            # Unity ships GNU diff (or it does at the time of this writing).
            # Try it.
            #
            # We'll hard-code the most likely path. This won't consider other
            # drives. If it's elsewhere, and a legacy install, people should
            # have it in their system path.
            yield r'C:\Program Files\Unity\Editor\Data\Tools\diff.exe'

            # Try the old GnuWin32 locations. These are old versions of GNU
            # diff, but may exist.
            #
            # We'll hard-code the most likely path. This won't consider other
            # drives. If it's elsewhere, and a legacy install, people should
            # have it in their system path.
            yield r'C:\Program Files (x86)\GnuWin32\bin\diff.exe'

        # Try everything named "gdiff", followed by "diff". On some systems,
        # GNU Diff (which is preferred) will be named "gdiff".
        yield from iter_exes_in_path('gdiff')
        yield from iter_exes_in_path('diff')
