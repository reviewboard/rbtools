from __future__ import unicode_literals


def request_method_decorator(f):
    """Wraps methods returned from a resource to capture HttpRequests.

    When a method which returns HttpRequests is called, it will
    pass the method and arguments off to the transport to be executed.

    This wrapping allows the transport to skim arguments off the top
    of the method call, and modify any return values (such as executing
    a returned HttpRequest).

    However, if called with the ``internal`` argument set to True,
    the method itself will be executed and the value returned as-is.
    Thus, any method calls embedded inside the code for another method
    should use the ``internal`` argument to access the expected value.
    """
    def request_method(self, *args, **kwargs):
        if kwargs.pop('internal', False):
            return f(self, *args, **kwargs)
        else:
            def method_wrapper(*args, **kwargs):
                return f(self, *args, **kwargs)

            return self._transport.execute_request_method(method_wrapper,
                                                          *args, **kwargs)

    request_method.__name__ = f.__name__
    request_method.__doc__ = f.__doc__
    request_method.__dict__.update(f.__dict__)
    return request_method
