def get_diff(scmtool, repository_info, revision_range=None,
             svn_changelist=None, files=[]):
    """Returns a diff as a string."""
    if revision_range:
        diff, parent_diff = scmtool.diff_between_revisions(
            revision_range,
            files,
            repository_info)
    elif svn_changelist:
        diff, parent_diff = scmtool.diff_changelist(svn_changelist)
    else:
        diff, parent_diff = scmtool.diff(files)

    return diff, parent_diff
