from typing import Optional, Type
from urllib.parse import urlparse

from rbtools.api.resource import Resource
from rbtools.api.transport import Transport
from rbtools.api.transport.sync import SyncTransport


class RBClient:
    """Main client used to talk to a Review Board server's API.

    This provides methods used to authenticate with a Review Board API and
    perform API requests.

    Clients make use of a transport class for all server communication. This
    handles all HTTP-related state and communication, and can be used to mock,
    intercept, or alter the way in which clients talk to Review Board.

    Most methods wrap methods on the transport, which may change how arguments
    are provided and data is returned. With the default sync transport, no
    additional arguments are provided in any ``*args`` or ``**kwargs``, and
    results are returned directly from the methods.
    """

    ######################
    # Instance variables #
    ######################

    #: The domain name of the Review Board server.
    #:
    #: Type: str
    domain: str

    #: The URL of the Review Board server.
    #:
    #: Type: str
    url: str

    def __init__(
        self,
        url: str,
        transport_cls: Type[Transport] = SyncTransport,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the client.

        Args:
            url (str):
                The URL of the Review Board server.

            transport_cls (type, optional):
                The type of transport to use for communicating with the server.

            *args (tuple):
                Positional arguments to pass to the transport.

            **kwargs (dict):
                Keyword arguments to pass to the transport.
        """
        self.url = url
        self.domain = urlparse(url)[1]
        self._transport = transport_cls(url, *args, **kwargs)

    def get_root(
        self,
        *args,
        **kwargs,
    ) -> Optional[Resource]:
        """Return the root resource of the API.

        Args:
            *args (tuple):
                Positional arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.get_root`.

            **kwargs (dict):
                Keyword arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.get_root`.

        Returns:
            rbtools.api.resource.Resource:
            The root API resource.

        Raises:
            rbtools.api.errors.APIError:
                The API returned an error. Details are in the error object.

            rbtools.api.errors.ServerInterfaceError:
                There was a non-API error communicating with the Review Board
                server. The URL may have been invalid. The reason is in the
                exception's message.
        """
        return self._transport.get_root(*args, **kwargs)

    def get_path(
        self,
        path: str,
        *args,
        **kwargs,
    ) -> Optional[Resource]:
        """Return the API resource at the given path.

        Args:
            path (str):
                The path relative to the Review Board server URL.

            *args (tuple):
                Positional arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.get_path`.

            **kwargs (dict):
                Keyword arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.get_path`.

        Returns:
            rbtools.api.resource.Resource:
            The resource at the given path.

        Raises:
            rbtools.api.errors.APIError:
                The API returned an error. Details are in the error object.

            rbtools.api.errors.ServerInterfaceError:
                There was a non-API error communicating with the Review Board
                server. The URL may have been invalid. The reason is in the
                exception's message.
        """
        return self._transport.get_path(path, *args, **kwargs)

    def get_url(
        self,
        url: str,
        *args,
        **kwargs,
    ) -> Optional[Resource]:
        """Return the API resource at the given URL.

        Args:
            url (str):
                The URL of the resource to fetch.

            *args (tuple):
                Positional arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.get_url`.

            **kwargs (dict):
                Keyword arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.get_url`.

        Returns:
            rbtools.api.resource.Resource:
            The resource at the given path.

        Raises:
            rbtools.api.errors.APIError:
                The API returned an error. Details are in the error object.

            rbtools.api.errors.ServerInterfaceError:
                There was a non-API error communicating with the Review Board
                server. The URL may have been invalid. The reason is in the
                exception's message.
        """
        return self._transport.get_url(url, *args, **kwargs)

    def login(self, *args, **kwargs) -> None:
        """Log in to the Review Board server.

        Args:
            *args (tuple):
                Positional arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.login`.

            **kwargs (dict):
                Keyword arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.login`.

        Raises:
            rbtools.api.errors.APIError:
                The API returned an error. Details are in the error object.

            rbtools.api.errors.ServerInterfaceError:
                There was a non-API error communicating with the Review Board
                server. The URL may have been invalid. The reason is in the
                exception's message.
        """
        self._transport.login(*args, **kwargs)

    def logout(self, *args, **kwargs) -> None:
        """Log out from the Review Board server.

        Args:
            *args (tuple):
                Positional arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.logout`.

            **kwargs (dict):
                Keyword arguments to pass to the transport's
                :py:meth:`~rbtools.api.transport.Transport.logout`.

        Returns:
            object:
            The return value from
            :py:meth:`~rbtools.api.transport.Transport.logout`.

        Raises:
            rbtools.api.errors.APIError:
                The API returned an error. Details are in the error object.

            rbtools.api.errors.ServerInterfaceError:
                There was a non-API error communicating with the Review Board
                server. The URL may have been invalid. The reason is in the
                exception's message.
        """
        self._transport.logout(*args, **kwargs)
