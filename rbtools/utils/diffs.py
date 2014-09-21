import fnmatch


def filename_match_any_patterns(filename, patterns):
    """Check if the given filename matches any of the patterns."""
    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


def remove_filenames_matching_patterns(filenames, patterns):
    """Return an iterable of all filenames that do not match any patterns."""
    return (
        filename
        for filename in filenames
        if not filename_match_any_patterns(filename, patterns)
    )
