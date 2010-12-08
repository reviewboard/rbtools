class ResourceError(Exception):
    def __init__(self, msg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.msg = msg

    def __str__(self):
        return self.msg


class ServerInterfaceError(Exception):
    def __init__(self, msg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.msg = msg

    def __str__(self):
        return self.msg


class ChildResourceUncreatableError(ResourceError):
    pass


class InvalidChildResourceUrlError(ResourceError):
    pass


class InvalidResourceTypeError(ResourceError):
    pass


class InvalidKeyError(ResourceError):
    pass


class LoginRequiredError(ResourceError):
    pass


class RequestFailedError(ResourceError):
    pass


class UnloadedResourceError(ResourceError):
    pass


class UnknownResourceTypeError(ResourceError):
    pass 


class InvalidRequestMethodError(ServerInterfaceError):
    pass
