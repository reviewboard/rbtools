from __future__ import unicode_literals

import fnmatch
import os
import sys


def filename_match_any_patterns(filename, patterns, base_dir=''):
    """Check if the given filename matches any of the patterns.

    If base_dir is not supplied, it will treat the filename as relative to the
    current working directory.
    """
    if base_dir:
        filename = os.path.abspath(os.path.join(base_dir, filename))

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

    The base_dir parameter is the directory that the filenames will be relative
    to, which is the root of the repository in most cases.
    """
    include_file = True
    fs_encoding = sys.getfilesystemencoding()

    for line in diff:
        m = file_index_re.match(line)

        if m:
            filename = m.group(1).decode(fs_encoding)
            include_file = not filename_match_any_patterns(filename,
                                                           exclude_patterns,
                                                           base_dir)

        if include_file:
            yield line


def normalize_patterns(patterns, base_dir, cwd=None):
    """Normalize the patterns so that they are all absolute paths.

    Paths that begin with a path separator are interpreted as being relative to
    base_dir. All other paths are interpreted as being relative to the current
    working directory.
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


def remove_filenames_matching_patterns(filenames, patterns, base_dir):
    """Return an iterable of all filenames that do not match any patterns.

    The base_dir parameter is the directory that the filenames will be relative
    to.
    """
    return (
        filename
        for filename in filenames
        if not filename_match_any_patterns(filename, patterns, base_dir)
    )
