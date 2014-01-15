def get_diff(scmtool, repository_info, revision_spec=None, files=[]):
    """Returns diff data.

    This returns a dictionary with the diff content, parent diff content
    (if any), and the base commit ID/revision the diff applies to (if
    supported by the SCMClient).
    """
    revision_spec = revision_spec or []
    files = files or []

    return scmtool.diff(revision_spec, files)
