from __future__ import unicode_literals

import fnmatch
import os


def filename_match_any_patterns(filename, patterns, base_dir=''):
    """Check if the given filename matches any of the patterns.

    If base_dir is not supplied, it will treat the filename as relative to the
    current working directory."""
    if base_dir:
        filename = os.path.join(base_dir, filename)

    filename = os.path.abspath(filename)

    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


def filter_diff(diff, file_index_re, exclude_patterns, base_dir=''):
    """Filter through the lines of diff to exclude files.

    This function looks for lines that indicate the start of a new file in
    the diff and checks if the filename matches any of the given patterns.
    If it does, the diff lines corresponding to that file will not be
    yielded; if the filename does not match any patterns, the lines will be
    yielded as normal.

    The file_index_re parameter is a *compiled* regular expression that
    matches if and only if a new file's diff is being started. It *must*
    have one sub-group to match the filename.

    The base_dir parameter indicates the directory of files that are being
    diffed. If it is omitted, it is interpreted as the current working
    directory.
    """
    include_file = True

    for line in diff:
        m = file_index_re.match(line)

        if m:
            filename = m.group(1).decode('utf-8')
            include_file = not filename_match_any_patterns(
                filename, exclude_patterns, base_dir)

        if include_file:
            yield line


def normalize_patterns(patterns):
    """Normalize the patterns so that they are all absolute paths.

    All relative paths be interpreted as being relative to the current working
    directory and will be transformed into absolute paths"""
    return [os.path.abspath(pattern) for pattern in patterns]


def remove_filenames_matching_patterns(filenames, patterns, base_dir=''):
    """Return an iterable of all filenames that do not match any patterns."""
    return (
        filename
        for filename in filenames
        if not filename_match_any_patterns(filename, patterns, base_dir)
    )
