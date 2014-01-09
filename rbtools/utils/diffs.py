def get_diff(scmtool, repository_info, revision_spec=None,
             revision_range=None, old_files_list=[], files=[]):
    """Returns diff data.

    This returns a dictionary with the diff content, parent diff content
    (if any), and the base commit ID/revision the diff applies to (if
    supported by the SCMClient).
    """
    if scmtool.supports_new_diff_api:
        revision_spec = revision_spec or []
        files = files or []
        diff_info = scmtool.diff(revision_spec, files)
    else:
        if revision_range:
            diff_info = scmtool.diff_between_revisions(
                revision_range,
                old_files_list,
                repository_info)
        else:
            diff_info = scmtool.diff(old_files_list)

    # Support compatibility with diff functions that haven't been updated
    # to return a dictionary.
    if isinstance(diff_info, tuple):
        diff_info = {
            'diff': diff_info[0],
            'parent_diff': diff_info[1],
            'base_commit_id': None,
        }

    return diff_info
