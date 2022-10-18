import logging
from typing import Any, Callable, Optional

from rbtools.api.decode import decode_response
from rbtools.api.factory import create_resource
from rbtools.api.request import (AuthCallback,
                                 HttpRequest,
                                 OTPCallback,
                                 ReviewBoardServer)
from rbtools.api.resource import Resource
from rbtools.api.transport import Transport


logger = logging.getLogger(__name__)


class SyncTransport(Transport):
    """A synchronous transport layer for the API client.

    The file provided in cookie_file is used to store and retrieve
    the authentication cookies for the API.

    The optional agent parameter can be used to specify a custom
    User-Agent string for the API. If not provided, the default
    RBTools User-Agent will be used.

    The optional session can be used to specify an 'rbsessionid'
    to use when authenticating with reviewboard.
    """
    def __init__(
        self,
        url: str,
        cookie_file: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_token: Optional[str] = None,
        agent: Optional[str] = None,
        session: Optional[str] = None,
        disable_proxy: bool = False,
        auth_callback: Optional[AuthCallback] = None,
        otp_token_callback: Optional[OTPCallback] = None,
        verify_ssl: bool = True,
        allow_caching: bool = True,
        cache_location: Optional[str] = None,
        in_memory_cache: bool = False,
        save_cookies: bool = True,
        ext_auth_cookies: Optional[str] = None,
        ca_certs: Optional[str] = None,
        client_key: Optional[str] = None,
        client_cert: Optional[str] = None,
        proxy_authorization: Optional[str] = None,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the transport.

        Args:
            url (str):
                The URL of the Review Board server.

            cookie_file (str, optional):
                The name of the file to store authentication cookies in.

            username (str, optional):
                The username to use for authentication.

            password (str, optional):
                The password to use for authentication.

            api_token (str, optional):
                An API token to use for authentication. If present, this is
                preferred over the username and password.

            agent (str, optional):
                A User-Agent string to use for the client. If not specified,
                the default RBTools User-Agent will be used.

            session (str, optional):
                An ``rbsessionid`` string to use for authentication.

            disable_proxy (bool):
                Whether to disable HTTP proxies.

            auth_callback (callable, optional):
                A callback method to prompt the user for a username and
                password.

            otp_token_callback (callable, optional):
                A callback method to prompt the user for their two-factor
                authentication code.

            verify_ssl (bool, optional):
                Whether to verify SSL certificates.

            allow_caching (bool, optional):
                Whether to cache the result of HTTP requests.

            cache_location (str, optional):
                The filename to store the cache in, if using a persistent
                cache.

            in_memory_cache (bool, optional):
                Whether to keep the cache data in memory rather than persisting
                to a file.

            save_cookies (bool, optional):
                Whether to save authentication cookies.

            ext_auth_cookies (str, optional):
                The name of a file to load additional cookies from. These will
                be layered on top of any cookies loaded from ``cookie_file``.

            ca_certs (str, optional):
                The name of a file to load certificates from.

            client_key (str, optional):
                The key for a client certificate to load into the chain.

            client_cert (str, optional):
                A client certificate to load into the chain.

            proxy_authorization (str, optional):
                A string to use for the ``Proxy-Authorization`` header.

            *args (tuple):
                Positional arguments to pass to the base class.

            **kwargs (dict):
                Keyword arguments to pass to the base class.
        """
        super().__init__(url, *args, **kwargs)

        self.allow_caching = allow_caching
        self.cache_location = cache_location
        self.in_memory_cache = in_memory_cache
        self.server = ReviewBoardServer(
            self.url,
            cookie_file=cookie_file,
            username=username,
            password=password,
            api_token=api_token,
            session=session,
            disable_proxy=disable_proxy,
            auth_callback=auth_callback,
            otp_token_callback=otp_token_callback,
            verify_ssl=verify_ssl,
            save_cookies=save_cookies,
            ext_auth_cookies=ext_auth_cookies,
            ca_certs=ca_certs,
            client_key=client_key,
            client_cert=client_cert,
            proxy_authorization=proxy_authorization)

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
        return self._execute_request(HttpRequest(self.server.url))

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
                Additional positional arguments.

            **kwargs (dict, unused):
                Additional keyword arguments.

        Returns:
            rbtools.api.resource.Resource:
            The resource at the given path.
        """
        if not path.endswith('/'):
            path = path + '/'

        if path.startswith('/'):
            path = path[1:]

        return self._execute_request(
            HttpRequest(self.server.url + path, query_args=kwargs))

    def get_url(
        self,
        url: str,
        *args,
        **kwargs,
    ) -> Optional[Resource]:
        """Return the API resource at the provided URL.

        Args:
            url (str):
                The URL to the API resource.

            *args (tuple, unused):
                Additional positional arguments.

            **kwargs (dict, unused):
                Additional keyword arguments.

        Returns:
            rbtools.api.resource.Resource:
            The resource at the given path.
        """
        if not url.endswith('/'):
            url = url + '/'

        return self._execute_request(HttpRequest(url, query_args=kwargs))

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
                Unused positional arguments.

            **kwargs (dict, unused):
                Unused keyword arguments.
        """
        self.server.login(username, password)

    def logout(self):
        """Log out of a session on the Review Board server."""
        self.server.logout()

    def execute_request_method(
        self,
        method: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute a method and return the resulting resource.

        Args:
            method (callable):
                The method to run.

            *s (tuple):
                Positional arguments to pass to the method.

            **kwargs (dict):
                Keyword arguments to pass to the method.

        Returns:
            rbtools.api.resource.Resource or object:
            If the method returns an HttpRequest, this will construct a
            resource from that. If it returns another value, that value will be
            returned directly.
        """
        request = method(*args, **kwargs)

        if isinstance(request, HttpRequest):
            return self._execute_request(request)

        return request

    def _execute_request(
        self,
        request: HttpRequest,
    ) -> Optional[Resource]:
        """Execute an HTTPRequest and construct a resource from the payload.

        Args:
            request (rbtools.api.request.HttpRequest):
                The HTTP request.

        Returns:
            rbtools.api.resource.Resource:
            The resource object, if available.
        """
        logger.debug('Making HTTP %s request to %s',
                     request.method, request.url)

        rsp = self.server.make_request(request)
        assert rsp is not None

        info = rsp.info()
        mime_type = info['Content-Type']
        item_content_type = info.get('Item-Content-Type', None)

        if request.method == 'DELETE':
            # DELETE calls don't return any data. Everything else should.
            return None
        else:
            payload = decode_response(rsp.read(), mime_type)

            return create_resource(self, payload, request.url,
                                   mime_type=mime_type,
                                   item_mime_type=item_content_type)

    def enable_cache(
        self,
        cache_location: Optional[str] = None,
        in_memory: bool = False,
    ) -> None:
        """Enable caching for all future HTTP requests.

        The cache will be created at the default location if none is provided.

        Args:
            cache_location (str, optional):
                The filename to store the cache in, if using a persistent
                cache.

            in_memory (bool, optional):
                Whether to keep the cache data in memory rather than persisting
                to a file.
        """
        if self.allow_caching:
            cache_location = cache_location or self.cache_location
            in_memory = in_memory or self.in_memory_cache

            self.server.enable_cache(cache_location=cache_location,
                                     in_memory=in_memory)

    def __repr__(self) -> str:
        """Return a string representation of the object.

        Returns:
            str:
            A string representation of the object.
        """
        return '<%s(url=%r, cookie_file=%r, agent=%r)>' % (
            self.__class__.__name__,
            self.url,
            self.server.cookie_file,
            self.server.agent)
