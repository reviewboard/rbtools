"""Base test helpers.

This is old and deprecated. It will be removed in RBTools 5.0.
"""

from rbtools.deprecation import RemovedInRBTools50Warning


class OptionsStub(object):
    def __init__(self):
        RemovedInRBTools50Warning.warn(
            'OptionsStub is deprecated and will be removed in RBTools 5.0.')

        self.debug = True
        self.guess_summary = False
        self.guess_description = False
        self.tracking = None
        self.username = None
        self.password = None
        self.repository_url = None
        self.disable_proxy = False
        self.summary = None
        self.description = None
