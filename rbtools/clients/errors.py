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


class TooManyRevisionsError(InvalidRevisionSpecError):
    """An error for when too many revisions were specified."""
    def __init__(self):
        super(TooManyRevisionsError, self).__init__(
            'Too many revisions specified')
