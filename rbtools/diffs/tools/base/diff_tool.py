"""Base class for building diff tools.

Version Added:
    4.0
"""

from typing import List, Optional

from typing_extensions import final

from rbtools.diffs.tools.base.diff_file_result import DiffFileResult


class BaseDiffTool:
    """Base class for diff tools.

    This provides a standard interface for working with arbitrary diff tools.

    Version Added:
        4.0
    """

    #: The unique ID of this diff tool.
    #:
    #: Type:
    #:     str
    diff_tool_id: str = ''

    #: The publicly-displayable name of this diff tool.
    #:
    #: Type:
    #:     str
    name: str = ''

    ######################
    # Instance variables #
    ######################

    #: Whether the diff tool is available for use.
    #:
    #: This is set after calling :py:meth:`setup`. If ``None``, this hasn't
    #: been set yet.
    #:
    #: Type:
    #:     bool
    available: Optional[bool]

    #: The path to the executable used to run this tool.
    #:
    #: If the diff tool is backed by an executable, this will be set after
    #: calling :py:meth:`setup`.
    #:
    #: Type:
    #:     str
    exe_path: Optional[str]

    #: The diff tool version information found when checking availability.
    #:
    #: If the diff tool provides this information, then this will be set
    #: after calling :py:meth:`setup`.
    #:
    #: Type:
    #:     str
    version_info: Optional[str]

    @classmethod
    def get_install_instructions(cls) -> str:
        """Return instructions for installing this tool.

        This can be provided by subclasses to help users install any missing
        dependencies.

        Returns:
            str:
            The installation instructions, or an empty string (default) to
            avoid showing instructions.
        """
        return ''

    def __init__(self) -> None:
        """Initialize the tool."""
        self.available = None
        self.exe_path = None
        self.version_info = None

    @final
    def setup(self) -> None:
        """Set up the diff tool.

        This will check for the tool's availability, allowing it to be used.

        This must be called before calling :py:meth:`run_diff_file`.
        """
        self.available = self.check_available()

    def check_available(self) -> bool:
        """Check whether the tool is available for use.

        This must be implemented by subclasses. If appropriate, they should
        set :py:attr:`exe_path` and :py:attr:`version_info`.

        Returns:
            bool:
            ``True`` if the tool is available. ``False`` if it's not.
        """
        raise NotImplementedError

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
        raise NotImplementedError

    def run_diff_file(
        self,
        *,
        orig_path: str,
        modified_path: str,
        show_hunk_context: bool = False,
        treat_missing_as_empty: bool = True,
    ) -> DiffFileResult:
        """Return the result of a diff between two files.

        Subclasses are responsible for generating a Unified Diff, and ensuring
        that the contents are in line with what's expected for typical GNU
        Diff contents.

        That is, text content must be in the following format:

        .. code-block:: diff

           --- <orig_filename>\\t<extra info>
           +++ <modified_filename>\\t<extra info>
           <unified diff hunks>

        Binary file content must be in the following format:

        .. code-block:: diff

            Binary files <orig_filename> and <modified_filenames> differ

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
            rbtools.diffs.tools.base.diff_file_result.DiffFileResult:
            The result of the diff operation.

        Raises:
            rbtools.utils.process.RunProcessError:
                There was an error invoking the diff tool. Details are in the
                exception.
        """
        raise NotImplementedError
