"""API transports for unit tests.

Version Added:
    3.1
"""

from __future__ import unicode_literals

import json
import logging
from collections import defaultdict

from six.moves.urllib.parse import urljoin, urlparse

from rbtools.api.errors import create_api_error
from rbtools.api.factory import create_resource
from rbtools.api.request import HttpRequest
from rbtools.api.transport import Transport
from rbtools.testing.api.payloads import ResourcePayloadFactory


logger = logging.getLogger(__name__)


class URLMapTransport(Transport):
    """API transport for defining and querying URL maps of responses.

    This transport allows unit tests to define the URLs they want to test
    against, mapping URLS and HTTP methods to groups of payloads and headers,
    and HTTP status codes.

    By default, this provides a handful of pre-built URLs:

    * ``/api/``
    * ``/api/info/``
    * ``/api/repositories/``

    Unit tests can define any additional resources they need through the
    following functions:

    * :py:meth:`add_item_url`
    * :py:meth:`add_list_url`

    Any defined URLs can be modified by changing entries anywhere in the
    :py:data:`urls` dictionary. These changes will not persist to other unit
    tests.

    API capabilities can also be changed be modifying :py:attr:`capabilities`.

    If unit tests need URLs that are not already defined on this transport,
    it may be worth contributing helper functions to this class, in order to
    ensure consistency (see the implementation of :py:meth:`add_repository_url`
    for details).

    Version Added:
        3.1

    Attributes:
        api_calls (list of dict):
            A list of API calls that have been made. Each is a dictionary
            containing:

            Keys:
                method (unicode):
                    The HTTP method.

                path (unicode):
                    The API path, relative to the root of the server.

        cache_location (unicode):
            The cache location configured when constructing the transport
            or when calling :py:meth:`enable_cache`.

        cache_in_memory (bool):
            The cache-in-memory flag configured when constructing the transport
            or when calling :py:meth:`enable_cache`.

        capabilities (dict):
            The dictionary of capabilities to simulate being returned from
            the API. This can be modified as needed by unit tests.

        list_item_payloads (dict):
            A mapping of relative list URLs to lists of item payloads that
            should be returned when accessing that list resource.

            Note that list resources must be registered through
            :py:meth:`add_list_url`.

        logged_in (bool):
            Whether the user is logged in.

            This will be set to ``True`` if a username and password are
            provided during construction, or if :py:meth:`login` is called.

        login_credentials (dict):
            A dictionary of login credentials.

            This will be set to a dictionary with ``username`` and ``password``
            keys if a username and password are provided during construction,
            or if :py:meth:`login` is called. Otherwise it will be ``None``.

        payload_factory (rbtools.testing.api.payloads.PayloadFactory):
            The payload factory used to construct resource object and response
            payloads. This can be used when calling :py:meth:`add_item_url`
            or :py:meth:`add_list_url`.

        transport_kwargs (dict):
            Additional keyword arguments passed during construction.

        urls (dict):
            The mapping of URLs to response information. This is in the
            following form:

            .. code-block:: python

               urls = {
                   '/api/.../[?...]': {
                       '<HTTP method>': {
                           'headers': {
                               'Content-Type': '...',
                               ...,
                           },
                           'http_status': ...,
                           'payload': {
                               'stat': '...',
                               ...,
                           },
                       },
                       ...
                   },
                   ...
               }

            Anything in this tree can be freely modified by unit tests. Changes
            will not persist across tests.
    """

    def __init__(self, url, username=None, password=None,
                 cache_location=None, in_memory_cache=False,
                 **kwargs):
        """Initialize the transport.

        Args:
            url (unicode):
                The URL to the root of the server. This must end with ``/``.

            username (unicode, optional):
                An optional username to simulate logging in with. If set,
                ``password`` is required.

            password (unicode, optional):
                An optional password to simulate logging in with. This is
                ignored if ``username`` is not set.

            cache_location (unicode, optional):
                An optional cache location to set. This only affects
                :py:attr:`cache_location` and will otherwise be ignored.

            in_memory_cache (bool, optional):
                Whether to use an in-memory cache. This only affects
                :py:attr:`cache_in_memory` and will otherwise be ignored.

            **kwargs (dict):
                Additional keyword arguments passed to the transport. These
                will be stored in :py:attr:`transport_kwargs`.
        """
        # Enforce consistency in tests and reduce the string manipulation
        # needed.
        assert url.endswith('/')

        super(URLMapTransport, self).__init__(url=url, **kwargs)

        self.logged_in = False
        self.login_credentials = None
        self.cache_location = cache_location
        self.cache_in_memory = in_memory_cache
        self.api_calls = []
        self.urls = {}
        self.transport_kwargs = kwargs
        self.list_item_payloads = defaultdict(list)

        payload_factory = ResourcePayloadFactory(self.url)
        self.payload_factory = payload_factory

        # Set up the default resource URLs for this instance.
        root_info = self.add_item_url(
            **payload_factory.make_root_object_data())
        root_payload = root_info['node']['payload']

        self.add_item_url(
            url='/api/info/',
            method='GET',
            mimetype='application/vnd.reviewboard.org.info+json',
            item_key='info',
            payload=lambda: (
                # This is dynamic, so that it will always reflect changes
                # made to the root resource.
                payload_factory.make_api_info_object_data(
                    root_payload=root_payload)
            ))

        self.add_list_url(
            url='/api/repositories/',
            list_key='repositories',
            mimetype=payload_factory.make_mimetype('repositories'),
            item_mimetype=payload_factory.make_mimetype('repository'))

        # Pull out the capabilities for clients to easily set in tests.
        self.capabilities = root_payload['capabilities']

        if username:
            assert password
            self.login(username, password)

    def add_url(self, url, mimetype, method='GET', http_status=200,
                headers={}, payload={}):
        """Add a URL mapping to a payload.

        Args:
            url (unicode):
                The URL for the resource. This can include or omit a query
                string, as needed (exact query strings have higher precedence
                than not having a query string).

            mimetype (unicode):
                The mimetype for the response.

            method (unicode, optional):
                The HTTP method that the payload will map to.

            http_status (int, optional):
                The HTTP status code of the response.

            headers (dict, optional):
                Any custom headers to provide in the response.

            payload (dict or bytes):
                The payload data. This can be a dictionary of deserialized
                API results, or it can be a byte string of content.

        Responses:
            dict:
            The results of the add operation, for further tracking or
            processing.

            Keys:
                method (unicode):
                    The registered HTTP method.

                url (unicode):
                    The normalized registered URL used to store the mapping.

                node (dict):
                    The registered dictionary that the URL and method maps to,
                    for modification.
        """
        url = self._normalize_api_url(url)
        node = {
            'http_status': http_status,
            'headers': dict({
                'Content-Type': mimetype,
            }, **headers),
            'payload': payload,
        }

        self.urls.setdefault(url, {})[method] = node

        return {
            'method': method,
            'url': url,
            'node': node,
        }

    def add_item_url(self, url, payload, item_key=None, in_list_urls=[],
                     **kwargs):
        """Add a URL for an item or singleton resource.

        Args:
            url (unicode):
                The URL for the resource. This can include or omit a query
                string, as needed (exact query strings have higher precedence
                than not having a query string).

            payload (dict):
                The object payload to provide in the response payload.

            item_key (unicode, optional):
                The item key used to map to the object's payload in the
                response payload. If ``None``, the object payload will be
                merged into the response payload.

            in_list_urls (list of unicode):
                Any URLs for list resources that should contain this item
                in list responses.

            **kwargs (dict):
                Additional keyword arguments for the registration. See
                :py:meth:`add_url` for details.

        Responses:
            dict:
            The results of the add operation, for further tracking or
            processing. See the return type for :py:meth:`add_url` for
            details.
        """
        response_payload = self.payload_factory.make_item_response_payload(
            item_key=item_key,
            object_payload=payload)

        url_info = self.add_url(url=url,
                                payload=response_payload,
                                **kwargs)

        for list_url in in_list_urls:
            self.list_item_payloads[list_url].append(payload)

        return url_info

    def add_list_url(self, url, list_key, item_mimetype, headers={}, **kwargs):
        """Add a URL for a list resource.

        The payload will be computed dynamically as needed, listing items
        registered in :py:attr:`list_item_payloads`.

        Args:
            url (unicode):
                The URL for the resource. This can include or omit a query
                string, as needed (exact query strings have higher precedence
                than not having a query string).

            list_key (unicode):
                The key used to map to the list of item payloads in the
                response payload.

            item_mimetype (unicode):
                The mimetype for items in the list.

            headers (dict, optional):
                Any custom headers to provide in the response.

            **kwargs (dict):
                Additional keyword arguments for the registration. See
                :py:meth:`add_url` for details.

        Responses:
            dict:
            The results of the add operation, for further tracking or
            processing. See the return type for :py:meth:`add_url` for
            details.
        """
        return self.add_url(
            url=url,
            payload=lambda: self.payload_factory.make_list_response_payload(
                url=url,
                list_key=list_key,
                items=self.list_item_payloads.get(url, [])),
            headers=dict({
                'Item-Content-Type': item_mimetype,
            }, **headers),
            **kwargs)

    def add_error_url(self, url, error_code, error_message, payload_extra=None,
                      http_status=400, **kwargs):
        """Add a URL for an error response.

        Args:
            url (unicode):
                The URL that triggers the error. This can include or omit a
                query string, as needed (exact query strings have higher
                precedence than not having a query string).

            error_code (int):
                The API error code.

            error_message (unicode):
                The API error message.

            payload_extra (dict, optional):
                Additional data to provide in the root of the error payload.

            http_status (int, optional):
                The HTTP status code for the error.

            **kwargs (dict):
                Additional keyword arguments for the registration. See
                :py:meth:`add_url` for details.

        Responses:
            dict:
            The results of the add operation, for further tracking or
            processing. See the return type for :py:meth:`add_url` for
            details.
        """
        return self.add_url(
            url=url,
            http_status=http_status,
            payload=self.payload_factory.make_error_response_payload(
                error_code=error_code,
                error_message=error_message,
                payload_extra=payload_extra),
            mimetype='application/vnd.reviewboard.org.error+json',
            **kwargs)

    def add_repository_urls(self, repository_id=1, info_payload=None,
                            **kwargs):
        """Add URLs for a repository.

        This will add a URL for a repository item resource and register it in
        the corresponding list resource.

        A repository info URL is also registered, returning either a specified
        repository-specific info payload or a suitable error.

        Args:
            repository_id (int, optional):
                The ID of the repository being added to the API.

            info_payload (dict, optional):
                Any payload data for the ``info/`` URL. If ``None``, then
                an error payload will be registered instead.

            **kwargs (dict):
                Additional keyword arguments for the repository payload. See
                :py:meth:`rbtools.testing.api.payloads.PayloadFactory.
                make_repository_object_data` for details.

        Returns:
            dict:
            A dictionary of :py:meth:`add_url` results for the two URLs.

            Keys:
                repositories_info_url_info (dict):
                    The result of the repository info URL registration.

                repositories_url_info (dict):
                    The result of the repository URL registration.
        """
        payload_factory = self.payload_factory

        obj_data = payload_factory.make_repository_object_data(
            repository_id=repository_id,
            **kwargs)

        repos_url_info = self.add_item_url(
            in_list_urls=['/api/repositories/'],
            **obj_data)

        if info_payload:
            repo_info_url_info = self.add_item_url(
                **payload_factory.make_repository_info_object_data(
                    repository_id=repository_id,
                    info_payload=info_payload))
        else:
            repo_info_url_info = self.add_error_url(
                url='%sinfo/' % obj_data['url'],
                http_status=501,
                error_code=209,
                error_message=('The specified repository is not able to '
                               'perform this action.'))

        return {
            'repositories_info_url_info': repo_info_url_info,
            'repositories_url_info': repos_url_info,
        }

    def get_root(self):
        """Perform a simulated HTTP GET on the root API.

        Returns:
            rbtools.api.resource.RootResource:
            The resulting root resource.
        """
        return self.get_path('/api/')

    def get_path(self, path, *args, **kwargs):
        """Perform a simulated HTTP GET on the given relative path.

        Args:
            path (unicode):
                The path relative to the root of the server.

            *args (tuple, unused):
                Unused positional arguments.

            **kwargs (dict):
                Additional query arguments used to build a query string.

        Returns:
            rbtools.api.resource.Resource or rbtools.api.errors.APIError:
            The resulting resource or error.
        """
        assert not path.startswith(self.url)

        return self.get_url(urljoin(self.url, path), *args, **kwargs)

    def get_url(self, url, *args, **kwargs):
        """Perform a simulated HTTP GET on the given absolute URL.

        Args:
            url (unicode):
                The absolute URL.

            *args (tuple, unused):
                Unused positional arguments.

            **kwargs (dict):
                Additional query arguments used to build a query string.

        Returns:
            rbtools.api.resource.Resource or rbtools.api.errors.APIError:
            The resulting resource or error.
        """
        assert url.endswith('/'), (
            'The URL "%s" must be built to end with a trailing "/"' % url
        )

        # We use this rather than a direct call to handle_api_path() since
        # we want to take advantage of HttpRequest normalizing query_args
        # and adding it to the URL.
        return self.execute_request_method(
            lambda: HttpRequest(url, query_args=kwargs))

    def login(self, username, password, *args, **kwargs):
        """Log in to the server.

        This will simply set the :py:attr:`logged_in` and
        :py:attr:`login_credentials` login state.

        Args:
            username (unicode):
                The username used for authentication.

            password (unicode):
                The password used for authentication.

            *args (tuple, unused):
                Unused positional arguments.

            **kwargs (dict, unused):
                Unused keyword arguments.
        """
        self.logged_in = True
        self.login_credentials = {
            'username': username,
            'password': password,
        }

    def logout(self):
        """Log out of the server.

        This will simply clear the :py:attr:`logged_in` and
        :py:attr:`login_credentials` login state.
        """
        self.logged_in = False
        self.login_credentials = None

    def execute_request_method(self, method, *args, **kwargs):
        """Execute a method and process the resulting HttpRequest.

        Args:
            method (callable):
                The method to call to generate the HTTP request.

            *args (tuple):
                Positional arguments to pass to the method.

            **kwargs (dict):
                Keyword arguments to pass to the method.

        Returns:
            rbtools.api.resource.Resource or rbtools.api.errors.APIError:
            The resulting resource or error.
        """
        request = method(*args, **kwargs)

        if isinstance(request, HttpRequest):
            return self.handle_api_path(path=request.url,
                                        method=request.method)

        return request

    def enable_cache(self, cache_location=None, in_memory=False):
        """Enable the HTTP cache.

        This will simply set the :py:attr:`cache_location` and
        :py:attr:`cache_in_memory` attributes.

        Args:
            cache_location (unicode, optional):
                The cache location to set.

            in_memory (bool, optional):
                The cache-in-memory flag to set.
        """
        self.cache_location = cache_location
        self.cache_in_memory = in_memory

    def handle_api_path(self, path, method):
        """Handle a request to an API path.

        This will log the request attempt for debugging purposes, look up
        the appropriate response, and return it if found.

        Any missing URL or method mappings will result in an assertion error.

        Args:
            path (unicode):
                The path or URL the API request was made to.

            method (unicode):
                The HTTP method being performed.

        Returns:
            rbtools.api.resource.Resource or rbtools.api.errors.APIError:
            The resulting resource or error.

            This may also return ``None`` for DELETE requests.
        """
        logger.debug('Client API: HTTP %s %s', method, path)

        path = self._normalize_api_url(path)

        api_call = {
            'path': path,
            'method': method,
        }
        self.api_calls.append(api_call)

        try:
            url_info = self.urls[path]
        except KeyError:
            try:
                url_info = self.urls[urlparse(path).path]
            except KeyError:
                raise AssertionError(
                    'URL "%s" was not defined in the transport!'
                    % path)

        try:
            method_info = url_info[method]
        except KeyError:
            raise AssertionError(
                'HTTP method "%s" for URL "%s" was not defined in the '
                'transport!'
                % (method, path))

        http_status = method_info.get('http_status', 200)
        payload = method_info.get('payload')

        headers = method_info.get('headers', {})
        item_mimetype = headers.get('Item-Content-Type')

        if callable(payload):
            payload = payload()

        api_call['response'] = payload

        try:
            mimetype = headers['Content-Type']
        except KeyError:
            raise AssertionError('HTTP method "%s" for URL "%s" is missing a '
                                 'mimetype!'
                                 % (method, path))

        if 200 <= http_status < 300:
            if method == 'DELETE':
                return None

            return create_resource(transport=self,
                                   payload=payload,
                                   url=urljoin(self.url, path),
                                   mime_type=mimetype,
                                   item_mime_type=item_mimetype)
        elif 300 <= http_status < 400:
            assert 'Location' in headers

            return self.handle_api_path(path=headers['Location'],
                                        method=method)
        else:
            try:
                if isinstance(payload, dict):
                    rsp = payload
                else:
                    rsp = json.loads(payload)

                error_code = rsp['err']['code']
                message = rsp['err']['msg']
            except (KeyError, ValueError):
                rsp = None
                error_code = None
                message = payload

            raise create_api_error(http_status, error_code, rsp, message)

    def _normalize_api_url(self, url):
        """Return a normalized version of the given URL.

        This will strip off the base server URL, if found, and ensure that
        the result ends with a ``/``.

        Args:
            url (unicode):
                The URL to normalize.

        Returns:
            unicode:
            The normalized URL.
        """
        if url.startswith(self.url):
            # Strip off the server URL, but keep the trailing "/".
            url = url[len(self.url) - 1:]

        assert urlparse(url).path.endswith('/'), (
            'The URL "%s" must be built to end with a trailing "/"' % url
        )

        return url
