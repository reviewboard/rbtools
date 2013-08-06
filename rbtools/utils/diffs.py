def get_diff(scmtool, repository_info, revision_range=None,
             svn_changelist=None, files=[]):
    """Returns diff data.

    This returns a dictionary with the diff content, parent diff content
    (if any), and the base commit ID/revision the diff applies to (if
    supported by the SCMClient).
    """
    if revision_range:
        diff_info = scmtool.diff_between_revisions(
            revision_range,
            files,
            repository_info)
    elif svn_changelist:
        diff_info = scmtool.diff_changelist(svn_changelist)
    else:
        diff_info = scmtool.diff(files)

    # Support compatibility with diff functions that haven't been updated
    # to return a dictionary.
    if isinstance(diff_info, tuple):
        diff_info = {
            'diff': diff_info[0],
            'parent_diff': diff_info[1],
            'base_commit_id': None,
        }

    return diff_info
