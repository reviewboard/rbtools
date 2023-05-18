"""Classes for representing patch results in SCM clients.

Version Added:
    4.0
"""


class PatchAuthor(object):
    """The author of a patch or commit.

    This wraps the full name and e-mail address of a commit or patch's
    author primarily for use in :py:meth:`BaseSCMClient.apply_patch
    <rbtools.clients.base.scmclient.BaseSCMClient.apply_patch>`.

    Version Changed:
        4.0:
        * Moved from :py:mod:`rbtools.clients`. That module still provides
          compatibility imports.

    Attributes:
        fullname (unicode):
            The full name of the author.

        email (unicode):
            The e-mail address of the author.
    """

    def __init__(self, full_name, email):
        """Initialize the author information.

        Args:
            full_name (unicode):
                The full name of the author.

            email (unicode):
                The e-mail address of the author.
        """
        self.fullname = full_name
        self.email = email


class PatchResult(object):
    """The result of a patch operation.

    This stores state on whether the patch could be applied (fully or
    partially), whether there are conflicts that can be resolved (as in
    conflict markers, not reject files), which files conflicted, and the
    patch output.

    Version Changed:
        4.0:
        * Moved from :py:mod:`rbtools.clients`. That module still provides
          compatibility imports.
    """

    def __init__(self, applied, has_conflicts=False,
                 conflicting_files=[], patch_output=None):
        """Initialize the object.

        Args:
            applied (bool):
                Whether the patch was applied.

            has_conflicts (bool, optional):
                Whether the applied patch included conflicts.

            conflicting_files (list of unicode, optional):
                A list of the filenames containing conflicts.

            patch_output (unicode, optional):
                The output of the patch command.
        """
        self.applied = applied
        self.has_conflicts = has_conflicts
        self.conflicting_files = conflicting_files
        self.patch_output = patch_output
