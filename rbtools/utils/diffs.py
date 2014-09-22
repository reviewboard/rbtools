import fnmatch


def filename_match_any_patterns(filename, patterns):
    """Check if the given filename matches any of the patterns."""
    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


def filter_diff(diff, file_index_re, exclude_patterns):
        """Filter through the lines of diff to exclude files.

        This function looks for lines that indicate the start of a new file in
        the diff and checks if the filename matches any of the given patterns.
        If it does, the diff lines corresponding to that file will not be
        yielded; if the filename does not match any patterns, the lines will be
        yielded as normal.

        The file_index_re parameter is a *compiled* regular expression that
        matches if and only if a new file's diff is being started. It *must*
        have one sub-group to match the filename.
        """
        include_file = True

        for line in diff:
            m = file_index_re.match(line)

            if m:
                include_file = True
                filename = m.group(1)

                for pattern in exclude_patterns:
                    if fnmatch.fnmatch(filename, pattern):
                        include_file = False
                        break

            if include_file:
                yield line


def remove_filenames_matching_patterns(filenames, patterns):
    """Return an iterable of all filenames that do not match any patterns."""
    return (
        filename
        for filename in filenames
        if not filename_match_any_patterns(filename, patterns)
    )
