"""Error classes for utility functions."""


class EditorError(Exception):
    """An error invoking an external text editor."""


# For backwards-compatibility, this inherits from ValueError.
class MatchReviewRequestsError(ValueError):
    """An error attempting to match review requests.

    Version Added:
        3.1

    Attributes:
        api_error (rbtools.api.errors.APIError):
            The API error that triggered this exception, if any.
    """

    def __init__(self, message, api_error=None):
        """Initialize the error.

        Args:
            message (unicode):
                The error message.

            api_error (rbtools.api.errors.APIError):
                The API error that triggered this exception, if any.
        """
        super(MatchReviewRequestsError, self).__init__(message)

        self.api_error = api_error
