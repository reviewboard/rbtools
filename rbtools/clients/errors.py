class OptionsCheckError(Exception):
    """
    An error that represents when command-line options were used
    inappropriately for the given SCMClient backend. The message in the
    exception is presented to the user.
    """
    pass
