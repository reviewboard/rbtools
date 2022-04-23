"""API payload generation factory for unit tests.

Version Added:
    3.1
"""

from __future__ import unicode_literals

from copy import deepcopy


class ResourcePayloadFactory(object):
    """Factory for creating simulated API payloads for testing.

    This can be used by unit tests (first-party or third-party) or the testing
    framework to create API payloads that commands or other RBTools logic
    can test against.

    The results of these aren't directly injected into any transport. Instead,
    they're meant to be built and passed into something like a KGB spy or the
    :py:class:`rbtools.testing.api.transport.URLMapTransport`.

    There are two kinds of payload data that this factory can generate:

    1. HTTP response payloads

       The full payload that would normally be serialized and then sent to a
       browser in a HTTP response. There are list, item, and error response
       payload generators:

       * :py:meth:`make_error_response_payload`
       * :py:meth:`make_item_response_payload`
       * :py:meth:`make_list_response_payload`

    2. Object payload data

       These generate data for an object residing in part of the resource tree,
       for use within either a list or an item response payload. The results
       are dictionaries that contain:

       Keys:
            item_key (unicode):
                The name of the key that would map to the payload in an item
                resource. If ``None``, then the contents of the payload will
                be merged into the root of the response payload.

            mimetype (unicode):
                The mimetype representing the object.

            payload (dict):
                The object payload data, for embedding into item or list
                response payloads.

            url (unicode):
                The URL to where the item resource for this object would live.

            headers (dict, optional):
                Any optional headers that may correspond to the result when
                in an item response payload.

       These generators include:

       * :py:meth:`make_api_info_object_data`
       * :py:meth:`make_repository_object_data`
       * :py:meth:`make_repository_info_object_data`
       * :py:meth:`make_root_object_data`

    Whenever unit tests need to generate a type of payload not provided in
    this factory, they should add a suitable function to the factory rather
    than create it themselves. This will help provide consistency across all
    unit tests.

    Version Added:
        3.1
    """

    #: The default capabilities that go into the root resource.
    DEFAULT_CAPABILITIES = {
        'diffs': {
            'base_commit_ids': True,
            'moved_files': True,
            'validation': {
                'base_commit_ids': True,
            },
        },
        'extra_data': {
            'json_patching': True,
        },
        'review_requests': {
            'commit_ids': True,
            'supports_history': True,
            'trivial_publish': True,
        },
        'scmtools': {
            'git': {
                'empty_files': True,
                'symlinks': True,
            },
            'mercurial': {
                'empty_files': True,
            },
            'perforce': {
                'empty_files': True,
                'moved_files': True,
            },
            'svn': {
                'empty_files': True,
            },
        },
        'text': {
            'can_include_raw_values': True,
            'markdown': True,
            'per_field_text_types': True,
        },
    }

    _ITEM_LINK_NAME_MAP = {
        'DELETE': 'delete',
        'GET': 'self',
        'PUT': 'update',
    }

    _LIST_LINK_NAME_MAP = {
        'GET': 'self',
        'POST': 'create',
    }

    def __init__(self, server_url):
        """Initialize the factory.

        Args:
            server_url (unicode):
                The URL to the simulated server. This must ends with ``/``.
        """
        assert server_url.endswith('/')

        self.server_url = server_url
        self.root_api_url = '%sapi/' % server_url

    def make_mimetype(self, name, payload_format='json'):
        """Return a mimetype for a resource.

        Args:
            name (unicode):
                The name of the mimetype, following
                ``application/vnd.reviewboard.org.``

            payload_format (unicode, optional):
                The payload format indicator, following the ``+``.

        Returns:
            unicode:
            The mimetype for the resource.
        """
        return 'application/vnd.reviewboard.org.%s+%s' % (name, payload_format)

    def make_item_response_payload(self, object_payload, item_key=None):
        """Return a new item response payload.

        This will generate a success payload with the provided object payload,
        either nested within ``item_key`` or merged into the root of the
        payload.

        This is used for items and singletons.

        Args:
            object_payload (dict):
                The object payload to include within the response payload.

            item_key (unicode, optional):
                A key to place the object payload within. If ``None``, the
                object payload will instead be merged into the root of the
                response payload.

        Returns:
            dict:
            The item response payload.
        """
        payload = {
            'stat': 'ok',
        }

        if item_key:
            payload[item_key] = object_payload
        else:
            payload.update(object_payload)

        return payload

    def make_list_response_payload(self, url, list_key, items):
        """Return a new list response payload.

        This will generate a success payload with the given list of items,
        total result count, and list of links.

        Note that this does not handle pagination at this time. All provided
        items will be included.

        Args:
            url (unicode):
                The absolute or relative URL where this list resource would
                live.

            list_key (unicode):
                The key within the payload that maps to the list of items.

            items (list of dict):
                The list of item payloads to include.

        Returns:
            dict:
            The list response payload.
        """
        return {
            list_key: items,
            'links': self._make_list_links(url),
            'stat': 'ok',
            'total_results': len(items),
        }

    def make_error_response_payload(self, error_code, error_message,
                                    payload_extra={}):
        """Return a new error response payload.

        This will generate an error payload with the given code, message, and
        any extra payload state to merge into the root of the response payload.

        Args:
            error_code (int):
                The API error code.

            error_message (unicode):
                The error message to show.

            payload_extra (dict, optional):
                Optional extra payload state to merge into the root of the
                response payload.

        Returns:
            dict:
            The error response payload.
        """
        return dict({
            'err': {
                'code': error_code,
                'msg': error_message,
            },
            'stat': 'fail',
        }, **(payload_extra or {}))

    def make_root_object_data(self, package_version='5.0.0', version='5.0',
                              capabilities=None):
        """Return new root resource data.

        Args:
            package_version (unicode):
                The Review Board package version to include in the API results.
                Callers should expect that this value may change over time,
                and should provide any values they may need for the test.

            version (unicode):
                The Review Board display version to include in the API results.
                Callers should expect that this value may change over time,
                and should provide any values they may need for the test.

            capabilities (dict, optional):
                Optional explicit capabilities to include. If not provided,
                this will use a copy of :py:attr:`DEFAULT_CAPABILITIES`.

        Returns:
            dict:
            The resource payload and metadata. See the class documentation
            for details.
        """
        server_url = self.server_url
        url = self._make_api_url('')

        links = self._make_item_links(
            url=url,
            methods=['GET'],
            child_resource_names=[
                'default-reviewers',
                'extensions',
                'groups',
                'hosting-service-accounts',
                'hosting-services',
                'info',
                'oauth-apps',
                'oauth-tokens',
                'repositories',
                'review-requests',
                'search',
                'session',
                'users',
                'validation',
                'webhooks',
            ])

        return {
            'item_key': None,
            'mimetype': self.make_mimetype('root'),
            'payload': {
                'capabilities': (capabilities or
                                 deepcopy(self.DEFAULT_CAPABILITIES)),
                'links': links,
                'product': {
                    'is_release': True,
                    'name': 'Review Board',
                    'package_version': package_version,
                    'version': version,
                },
                'site': {
                    'administrators': [{
                        'email': 'admin@example.com',
                        'name': 'Admin User',
                    }],
                    'time_zone': 'US/Pacific',
                    'url': server_url,
                },
                'stat': 'ok',
                'uri_templates': {
                    'info': '%sinfo/' % url,
                    'repositories': '%srepositories/' % url,
                    'review_requests': '%sreview-requests/' % url,
                },
            },
            'url': url,
        }

    def make_api_info_object_data(self, root_payload):
        """Return new API info resource data.

        Args:
            root_payload (dict):
                An existing payload for the root resource. The relevant data
                from that resource will be copied into here.

        Returns:
            dict:
            The resource payload and metadata. See the class documentation
            for details.
        """
        return {
            'item_key': 'info',
            'mimetype': self.make_mimetype('info'),
            'payload': {
                _key: root_payload[_key]
                for _key in ('capabilities', 'product', 'site')
            },
            'url': self._make_api_url('info/'),
        }

    def make_repository_object_data(self,
                                    repository_id=1,
                                    name='Test Repository',
                                    tool='Git',
                                    path='/path/to/repo.git',
                                    mirror_path='',
                                    bug_tracker='',
                                    visible=True,
                                    extra_data={}):
        """Return new repository resource data.

        Args:
            repository_id (int, optional):
                The value of the ``id`` field. The URL will also include this
                value.

            name (unicode, optional):
                The value of the ``name`` field.

            tool (unicode, optional):
                The value of the ``tool`` field.

            path (unicode, optional):
                The value of the ``path`` field.

            mirror_path (unicode, optional):
                The value of the ``mirror_path`` field.

            bug_tracker (unicode, optional):
                The value of the ``bug_tracker`` field.

            visible (bool, optional):
                The value of the ``visible`` field.

            extra_data (dict, optional):
                The value of the ``extra_data`` field.

        Returns:
            dict:
            The resource payload and metadata. See the class documentation
            for details.
        """
        url = self._make_api_url('repositories/%s/' % repository_id)

        links = self._make_item_links(
            url=url,
            child_resource_names=[
                'branches',
                'commits',
                'diff-file-attachments',
                'info',
            ])

        return {
            'item_key': 'repository',
            'mimetype': self.make_mimetype('repository'),
            'payload': {
                'bug_tracker': bug_tracker,
                'extra_data': extra_data,
                'id': repository_id,
                'links': links,
                'mirror_path': mirror_path,
                'name': name,
                'path': path,
                'tool': tool,
                'visible': visible,
            },
            'url': url,
        }

    def make_repository_info_object_data(self, repository_id, info_payload):
        """Return new repository info resource data.

        Args:
            repository_id (int, optional):
                The value of the ``id`` field. The URL will also include this
                value.

            info_payload (dict, optional):
                The repository-specific payload to include within the
                ``info`` key.

        Returns:
            dict:
            The resource payload and metadata. See the class documentation
            for details.
        """
        url = self._make_api_url('repositories/%s/info/' % repository_id)

        return {
            'url': url,
            'mimetype': self.make_mimetype('repository-info'),
            'payload': info_payload,
        }

    def _make_item_links(self, url, methods=['GET', 'PUT', 'DELETE'],
                         child_resource_names=[]):
        """Return links for use in item payloads.

        Args:
            url (unicode):
                The path to the item resource's location in the API tree.

            methods (list of unicode):
                The list of HTTP methods that this resource would support.

            child_resource_names (list of unicode):
                A list of child resource names to generate links for.

        Returns:
            dict:
            The dictionary of links.
        """
        links = {
            self._ITEM_LINK_NAME_MAP[_method]: {
                'href': url,
                'method': _method,
            }
            for _method in methods
        }

        if child_resource_names:
            links.update({
                _name: {
                    'href': '%s%s/' % (url, _name.replace('_', '-')),
                    'method': 'GET',
                }
                for _name in child_resource_names
            })

        return links

    def _make_list_links(self, url, methods=['POST', 'GET']):
        """Return links for use in list payloads.

        Args:
            url (unicode):
                The path to the list resource's location in the API tree.

            methods (list of unicode):
                The list of HTTP methods that this resource would support.

        Returns:
            dict:
            The dictionary of links.
        """
        return {
            self._LIST_LINK_NAME_MAP[_method]: {
                'href': url,
                'method': _method,
            }
            for _method in methods
        }

    def _make_child_resource_links(self, url, names):
        """Return links to child resources.

        Args:
            url (unicode):
                THe path to the resource's location in the API tree.

            names (list of unicode):
                A list of child resource names to generate links for.

        Returns:
            dict:
            The dictionary of links.
        """
        return {
            _name: {
                'href': '%s%s/' % (url, _name.replace('_', '-')),
                'method': 'GET',
            }
            for _name in names
        }

    def _make_api_url(self, path):
        """Return an absolute URL for an API path.

        The path must be relative to ``http://<domain>/api/``, must end with
        a ``/`` (or must be blank, in the case of the root resource).

        Args:
            path (unicode):
                The relative path to an API resource.

        Returns:
            unicode:
            The resulting absolute API URL.
        """
        assert not path.startswith((self.server_url,
                                    self.root_api_url,
                                    '/api/'))
        assert path.endswith('/') or not path, (
            'The URL "%s" must be built to end with a trailing "/"' % path
        )

        return '%sapi/%s' % (self.server_url, path)
