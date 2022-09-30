from typing import Any, Callable, Optional

from rbtools.api.resource import Resource


class Transport:
    """Base class for API Transport layers.

    An API Transport layer acts as an intermediary between the API
    user and the Resource objects. All access to a resource's data,
    and all communication with the Review Board server are handled by
    the Transport. This allows for Transport implementations with
    unique interfaces which operate on the same underlying resource
    classes. Specifically, this allows for both a synchronous, and an
    asynchronous implementation of the transport.
    """

    def __init__(
        self,
        url: str,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the transport.

        Args:
            url (str):
                The URL of the Review Board server

            *args (tuple, unused):
                Positional arguments, reserved for future expansion.

            **kwargs (tuple, unused):
                Keyword arguments, reserved for future expansion.
        """
        self.url = url

    def get_root(
        self,
        *args,
        **kwargs,
    ) -> Optional[Resource]:
        """Return the root API resource.

        Args:
            *args (tuple, unused):
                Positional arguments (may be used by the transport
                implementation).

            **kwargs (dict, unused):
                Keyword arguments (may be used by the transport
                implementation).

        Returns:
            rbtools.api.resource.Resource:
            The root API resource.
        """
        raise NotImplementedError

    def get_path(
        self,
        path: str,
        *args,
        **kwargs,
    ) -> Optional[Resource]:
        """Return the API resource at the provided path.

        Args:
            path (str):
                The path to the API resource.

            *args (tuple, unused):
                Positional arguments (may be used by the transport
                implementation).

            **kwargs (dict, unused):
                Keyword arguments (may be used by the transport
                implementation).

        Returns:
            rbtools.api.resource.Resource:
            The resource at the given path.
        """
        raise NotImplementedError

    def get_url(
        self,
        url: str,
        *args,
        **kwargs,
    ) -> Optional[Resource]:
        """Return the API resource at the provided URL.

        The URL is not guaranteed to be part of the configured Review
        Board domain.

        Args:
            url (str):
                The URL to the API resource.

            *args (tuple, unused):
                Positional arguments (may be used by the transport
                implementation).

            **kwargs (dict, unused):
                Keyword arguments (may be used by the transport
                implementation).

        Returns:
            rbtools.api.resource.Resource:
            The resource at the given path.
        """
        raise NotImplementedError

    def login(
        self,
        username: str,
        password: str,
        *args,
        **kwargs,
    ) -> None:
        """Log in to the Review Board server.

        Args:
            username (str):
                The username to log in with.

            password (str):
                The password to log in with.

            *args (tuple, unused):
                Positional arguments (may be used by the transport
                implementation).

            **kwargs (dict, unused):
                Keyword arguments (may be used by the transport
                implementation).
        """
        raise NotImplementedError

    def logout(self) -> None:
        """Log out of a session on the Review Board server."""
        raise NotImplementedError

    def execute_request_method(
        self,
        method: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute a method and carry out the returned HttpRequest.

        Args:
            method (callable):
                The method to run.

            *args (tuple):
                Positional arguments to pass to the method.

            **kwargs (dict):
                Keyword arguments to pass to the method.

        Returns:
            rbtools.api.resource.Resource or object:
            If the method returns an HttpRequest, this will construct a
            resource from that. If it returns another value, that value will be
            returned directly.
        """
        return method(*args, **kwargs)

    def enable_cache(
        self,
        cache_location: Optional[str] = None,
        in_memory: bool = False,
    ) -> None:
        """Enable caching for all future HTTP requests.

        The cache will be created at the default location if none is provided.

        If the in_memory parameter is True, the cache will be created in memory
        instead of on disk. This overrides the cache_location parameter.

        Args:
            cache_location (str, optional):
                The filename to store the cache in, if using a persistent
                cache.

            in_memory (bool, optional):
                Whether to keep the cache data in memory rather than persisting
                to a file.
        """
        raise NotImplementedError
