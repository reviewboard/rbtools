"""Error definitions for SCMClient implementations."""

from __future__ import unicode_literals


class SCMError(Exception):
    """A generic error from an SCM."""


class AuthenticationError(Exception):
    """An error for when authentication fails."""


class MergeError(Exception):
    """An error for when merging two branches fails."""


class PushError(Exception):
    """An error for when pushing a branch to upstream fails."""


class AmendError(Exception):
    """An error for when amending a commit fails."""


class OptionsCheckError(Exception):
    """An error for when command line options are used incorrectly."""


class InvalidRevisionSpecError(Exception):
    """An error for when the specified revisions are invalid."""


class MinimumVersionError(Exception):
    """An error for when software doesn't meet version requirements."""


class TooManyRevisionsError(InvalidRevisionSpecError):
    """An error for when too many revisions were specified."""

    def __init__(self):
        """Initialize the error."""
        super(TooManyRevisionsError, self).__init__(
            'Too many revisions specified')


class EmptyChangeError(Exception):
    """An error for when there are no changed files."""

    def __init__(self):
        """Initialize the error."""
        super(EmptyChangeError, self).__init__(
            "Couldn't find any affected files for this change.")
