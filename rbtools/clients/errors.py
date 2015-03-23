class MergeError(Exception):
    """An error for when merging two branches fails."""
    pass


class PushError(Exception):
    """An error for when pushing a branch to upstream fails."""
    pass


class OptionsCheckError(Exception):
    """
    An error that represents when command-line options were used
    inappropriately for the given SCMClient backend. The message in the
    exception is presented to the user.
    """
    pass


class InvalidRevisionSpecError(Exception):
    """An error for when the specified revisions are invalid."""
    pass


class MinimumVersionError(Exception):
    """An error for when software doesn't meet version requirements."""
    pass


class TooManyRevisionsError(InvalidRevisionSpecError):
    """An error for when too many revisions were specified."""
    def __init__(self):
        super(TooManyRevisionsError, self).__init__(
            'Too many revisions specified')


class EmptyChangeError(Exception):
    def __init__(self):
        super(EmptyChangeError, self).__init(
            "Couldn't find any affected files for this change.")
