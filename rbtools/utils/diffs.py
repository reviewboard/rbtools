"""Utilities for generating or parsing diffs."""

import fnmatch
import os
import sys
from typing import Iterable, Iterator, List, Optional, Pattern

from rbtools.deprecation import (RemovedInRBTools50Warning,
                                 deprecate_non_keyword_only_args)


@deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
def filename_match_any_patterns(
    filename: str,
    patterns: Iterable[str],
    *,
    base_dir: str = '',
) -> bool:
    """Check if the given filename matches any of the patterns.

    If base_dir is not supplied, it will treat the filename as relative to the
    current working directory.

    Version Changed:
        4.0:
        ``base_dir`` must now be provided as a keyword argument. This will be
        mandatory in RBTools 5.

    Args:
        filename (str):
            The filename to match against.

        patterns (list of str):
            The list of patterns to try to match.

        base_dir (str, optional):
            An optional base directory to prepend to the filename.

    Returns:
        bool:
        ``True`` if one of the patterns matched. ``False`` if no patterns
        matched.
    """
    if base_dir:
        filename = os.path.abspath(os.path.join(base_dir, filename))

    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


@deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
def filter_diff(
    diff: Iterable[bytes],
    file_index_re: Pattern[bytes],
    *,
    exclude_patterns: List[str],
    base_dir: str = '',
) -> Iterator[bytes]:
    """Filter through the lines of diff to exclude files.

    This function looks for lines that indicate the start of a new file in
    the diff and checks if the filename matches any of the given patterns.
    If it does, the diff lines corresponding to that file will not be
    yielded; if the filename does not match any patterns, the lines will be
    yielded as normal.

    Version Changed:
        4.0:
        ``exclude_patterns``, and ``base_dir`` must now be provided as keyword
        arguments. This will be mandatory in RBTools 5.

    Args:
        diff (list of bytes):
            The list of lines in a diff.

        file_index_re (re.Pattern):
            A compiled regex used to match if and only if a new file's diff is
            being started.

            This must have exactly one sub-group used to match the filename.
            For example: ``^filename: (.+)$``.

        exclude_patterns (list of str):
            The list of patterns to try to match against filenames.

            Any pattern matched will cause the file to be excluded from the
            diff.

        base_dir (str, optional):
            An optional base directory to prepend to each filename.

            If not provided, filenames should be relative to the root of the
            repository.

    Yields:
        bytes:
        A line of content from the diff.
    """
    include_file = True
    fs_encoding = sys.getfilesystemencoding()

    for line in diff:
        m = file_index_re.match(line)

        if m:
            filename = m.group(1).decode(fs_encoding)
            include_file = not filename_match_any_patterns(
                filename=filename,
                patterns=exclude_patterns,
                base_dir=base_dir)

        if include_file:
            yield line


@deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
def normalize_patterns(
    patterns: Iterable[str],
    *,
    base_dir: str,
    cwd: Optional[str] = None,
) -> List[str]:
    """Normalize a list of patterns so that they are all absolute paths.

    Paths that begin with a path separator are interpreted as being relative to
    ``base_dir``. All other paths are interpreted as being relative to the
    current working directory.

    Version Changed:
        4.0:
        ``base_dir`` and ``cwd`` must now be provided as keyword arguments.
        This will be mandatory in RBTools 5.

    Args:
        patterns (list of str):
            The list of patterns to normalize.

        base_dir (str):
            The base directory to compare pattern paths to.

        cwd (str, optional):
            The current working directory to use for normalization.

            If not provided, the current directory will be computed.

    Returns:
        list of str:
        The normalized list of patterns.
    """
    # Some SCMs (e.g., git) require us to execute git commands from the top
    # level git directory, so their respective SCMClient's diff method will
    # provide us with what the cwd was when the command was executed.
    if cwd is None:
        cwd = os.getcwd()

    sep_len = len(os.path.sep)

    def normalize(p):
        if p.startswith(os.path.sep):
            p = os.path.join(base_dir, p[sep_len:])
        else:
            p = os.path.join(cwd, p)

        return os.path.normpath(p)

    return [normalize(pattern) for pattern in patterns]


@deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
def remove_filenames_matching_patterns(
    filenames: Iterable[str],
    *,
    patterns: List[str],
    base_dir: str,
) -> Iterator[str]:
    """Return an iterable of all filenames that do not match any patterns.

    Version Changed:
        4.0:
        ``patterns`` and ``base_dir`` must now be provided as keyword
        arguments. This will be mandatory in RBTools 5.

    Args:
        filenames (list of str):
            The list of filenames to filter.

        patterns (list of str):
            The list of patterns used to match filenames to include.

        base_dir (str):
            The base director that filenames are expected to be relative to.

    Yields:
        str:
        Each filename that has been excluded.
    """
    return (
        filename
        for filename in filenames
        if not filename_match_any_patterns(filename=filename,
                                           patterns=patterns,
                                           base_dir=base_dir)
    )
