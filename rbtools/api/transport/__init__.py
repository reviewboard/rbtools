class Transport(object):
    """Base class for API Transport layers.

    An API Transport layer acts as an intermediary between the API
    user and the Resource objects. All access to a resource's data,
    and all communication with the Review Board server are handled by
    the Transport. This allows for Transport implementations with
    unique interfaces which operate on the same underlying resource
    classes. Specifically, this allows for both a synchronous, and an
    asynchronous implementation of the transport.

    TODO: Actually make this class useful by pulling out
    common functionality.
    """
    def __init__(self, url, *args, **kwargs):
        self.url = url

    def get_root(self, *args, **kwargs):
        raise NotImplementedError

    def get_path(self, *args, **kwargs):
        raise NotImplementedError

    def login(self, username, password, *args, **kwargs):
        """Reset login information to be populated on next request.

        The transport should override this method and provide a way
        to reset the username and password which will be populated
        in the next request.
        """
        raise NotImplementedError
