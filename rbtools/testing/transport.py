"""Transport subclass used for unit testing.

Deprecated::
    3.1:
    Replaced with
    :py:class:`rbtools.testing.api.transport.URLMapTransport.`
"""

from rbtools.api.factory import create_resource
from rbtools.api.request import HttpRequest
from rbtools.api.tests.base import TestWithPayloads
from rbtools.api.transport import Transport


class TestTransport(Transport):
    """Mocked subclass of Transport used for unit tests.

    This is mainly used to test functionality that requires interacting with
    and reading data from a Review Board server. Unlike the original
    implementation of its parent class, custom payloads can be passed in to
    force return a specific subclass of
    :py:class:`rbtools.api.resource.Resource`.

    Deprecated::
        3.1:
        Replaced with
        :py:class:`rbtools.testing.api.transport.URLMapTransport.`
    """

    def __init__(self, url, list_payload=TestWithPayloads.list_payload,
                 root_payload=TestWithPayloads.root_payload):
        """Initialize an instance of TestTransport.

        Args:
            url (list of unicode):
                URL representing the Transport URL.

            list_payload (dict, optional):
                Dictionary of key-pair values representing the payload for a
                :py:class:`rbtools.api.resource.ItemResource` instance.
                Default value is a payload defined in
                rbtools.api.tests.base.TestWithPayloads.

            root_payload (dict, optional):
                Dictionary of key-pair values representing the payload for a
                :py:class:`rbtools.api.resource.RootResource`. Default
                value is a payload defined in
                rbtools.api.tests.base.TestWithPayloads.
        """
        self.url = url
        self.list_payload = list_payload
        self.root_payload = root_payload

    def execute_request_method(self, method, *args, **kwargs):
        """Return an instance of ItemResource.

        Instead of executing :py:meth:`execute_request_method` and carrying out
        an instance of :py:class:`rbtools.api.request.HttpRequest`, it returns
        an instance of:py:class:`rbtools.api.resource.ItemResource`. The type
        of metadata this instance contains depends on the type of
        :py:attr:`list_payload` passed in.

        Args:
            method (callable):
                A function that acts as a method to be executed and returns a
                :py:class:`rbtools.api.request.HttpRequest` instance.

            *args:
                Variable arguments used for running the passed in method.

            **kwargs:
                Keyword arguments used for running the passed in method.

        Returns:
            rbtools.api.resource.ItemResource:
            An instance of :py:class:`rbtools.api.resource.ItemResource` if the
            executed method is an instance of
            :py:class:`rbtools.api.request.HttpRequest`.
        """
        request = method(*args, **kwargs)

        if isinstance(request, HttpRequest):
            return create_resource(
                transport=self,
                payload=self.list_payload,
                url='http://localhost:8080/api/repositories/',
                mime_type='application/vnd.reviewboard.org.list+json',
                item_mime_type='application/vnd.reviewboard.org.repository'
                               '+json')

        return request

    def get_root(self):
        """Return an instance of RootResource

        Instead of calling :py:meth:`get_root` and returning an
        instance of :py:class:`rbtools.api.request.HttpRequest`, an instance of
        :py:class:`rbtools.api.resource.RootResource` is simply returned.
        The type of metadata this instance contains depends on the
        type of :py:attr:`root_payload` passed in.

        Returns:
            rbtools.api.resource.RootResource:
            An instance of :py:class:`rbtools.api.request.RootResource`.
        """
        return create_resource(
            transport=self,
            payload=self.root_payload,
            url='http://localhost:8080/api/',
            mime_type='application/vnd.reviewboard.org.root+json')
