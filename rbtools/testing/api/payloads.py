"""API payload generation factory for unit tests.

Version Added:
    3.1
"""

from copy import deepcopy


class LinkExpansionType(object):
    """A type of link expansion.

    This helps to indicate if a link should expand as an item or a list.

    Version Added:
        3.1
    """

    #: Always expand links as lists.
    LIST = 1

    #: Expand links as individual items (if contents are not a list).
    ITEM = 2


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
       * :py:meth:`make_review_request_draft_object_data`
       * :py:meth:`make_review_request_object_data`
       * :py:meth:`make_root_object_data`
       * :py:meth:`make_session_object_data`
       * :py:meth:`make_user_object_data`

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

    def expand_link(self, payload, link_key, expanded_payload,
                    expand_key=None, expansion_type=None):
        """Expand a link in the payload.

        This will remove the link from ``links`` and add the provided expanded
        payload to the object payload.

        Args:
            payload (dict):
                The payload where the epanded resource will be provided, and
                where ``links`` resides.

            link_key (unicode):
                The name of the link key.

            expanded_payload (dict or list of dict):
                The payload or list of payloads to put in the object payload
                under the key.

            expand_key (unicode, optional):
                The key to use for the expanded payloads. If not provided,
                this defaults to the value of ``link_key``.
        """
        assert 'links' in payload
        assert link_key in payload['links']

        if expansion_type == LinkExpansionType.LIST:
            if expanded_payload is None:
                expanded_payload = []
            elif not isinstance(expanded_payload, list):
                expanded_payload = [expanded_payload]

        del payload['links'][link_key]
        payload[expand_key or link_key] = expanded_payload

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
                    'draft': ('%sreview-requests/{review_request_id}/draft/'
                              % url),
                    'info': '%sinfo/' % url,
                    'repositories': '%srepositories/' % url,
                    'repository': '%srepositories/{repository_id}/' % url,
                    'review_request': ('%sreview-requests/{review_request_id}/'
                                       % url),
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

    def make_review_request_object_data(
            self,
            review_request_id,
            approval_failure=None,
            approved=False,
            blocks_ids=[],
            branch='test-branch',
            bugs_closed=[],
            changenum=None,
            close_description='',
            close_description_text_type='plain',
            commit_id=None,
            created_with_history=True,
            depends_on_ids=[],
            description='Test Description',
            description_text_type='plain',
            extra_data={},
            issue_dropped_count=0,
            issue_open_count=0,
            issue_resolved_count=0,
            issue_verifying_count=0,
            last_updated='2022-04-21T15:44:00Z',
            public=True,
            repository_id=None,
            ship_it_count=0,
            status='pending',
            submitter_username='test-user',
            summary='Test Summary',
            target_group_names=[],
            target_people_usernames=[],
            testing_done='Test Testing Done',
            testing_done_text_type='plain',
            text_type=None,
            time_added='2022-04-21T12:30:00Z',
            latest_diff_id=1):
        """Return new review request resource data.

        Args:
            review_request_id (int):
                The ID of the review request.

            approval_failure (unicode, optional):
                The value of the ``approval_failure`` field.

            approved (bool, optional):
                The value of the ``approved`` field.

            blocks_ids (list of int, optional):
                A list of review request IDs that this blocks, for use in
                the ``blocks`` field.

            branch (unicode, optional):
                The value of the ``branch`` field.

            bugs_closed (list of unicode, optional):
                The value of the ``bugs_closed`` field.

            changenum (int, optional):
                The value of the ``changenum`` field.

            close_description (unicode, optional):
                The value of the ``close_description`` field.

            close_description _text_type (unicode, optional):
                The value of the ``close_description_text_type`` field.

            commit_id (unicode, optional):
                The value of the ``commit_id`` field.

            created_with_history (bool, optional):
                The value of the ``created_with_history`` field.

            depends_on_ids (list of int, optional):
                A list of review request IDs that this depends on, for use
                in the ``depends_on`` field.

            description (unicode, optional):
                The value of the ``description`` field.

            description_text_type (unicode, optional):
                The value of the ``description_text_type`` field.

            extra_data (dict, optional):
                The value of the ``extra_data`` field.

            issue_dropped_count (int, optional):
                The value of the ``issue_dropped_count`` field.

            issue_open_count (int, optional):
                The value of the ``issue_open_count`` field.

            issue_resolved_count (int, optional):
                The value of the ``issue_resolved_count`` field.

            issue_verifying_count (int, optional):
                The value of the ``issue_verifying_count`` field.

            last_updated (unicode, optional):
                The value of the ``last_updated`` field.

            public (bool, optional):
                The value of the ``public`` field.

            repository_id (int, optional):
                The ID of the repository, for the ``repository`` link.

            ship_it_count (int, optional):
                The value of the ``ship_it_count`` field.

            status (unicode, optional):
                The value of the ``status`` field.

            submitter_username (unicode, optional):
                The username of the submitter, for the ``submitter`` link.

            summary (unicode, optional):
                The value of the ``summary`` field.

            target_group_names (unicode, optional):
                A list of group names, for use in the ``target_groups`` field.

            target_people_usernames (unicode, optional):
                A list of usernames, for use in the ``target_people`` field.

            testing_done (unicode, optional):
                The value of the ``testing_done`` field.

            testing_done_text_type (unicode, optional):
                The value of the ``testing_done_text_type`` field.

            text_type (unicode, optional):
                The value of the ``text_type`` field.

            time_added (unicode, optional):
                The value of the ``time_added`` field.

            latest_diff_id (int, optional):
                The ID of the last diff on the review request, for use in
                the ``latest_diff`` link.

        Returns:
            dict:
            The resource payload and metadata. See the class documentation
            for details.
        """
        url = self._make_api_url('review-requests/%s/' % review_request_id)

        links = self._make_item_links(
            url=url,
            child_resource_names=[
                'changes',
                'diff_context',
                'diffs',
                'draft',
                'file_attachments',
                'last_update',
                'reviews',
                'screenshots',
                'status_updates',
            ])
        links['submitter'] = {
            'href': self._make_api_url('users/%s/' % submitter_username),
            'method': 'GET',
            'title': submitter_username,
        }

        if repository_id is not None:
            links.update({
                'latest_diff': {
                    'href': '%sdiffs/%s/' % (url, latest_diff_id),
                    'method': 'GET',
                },
                'repository': {
                    'href': self._make_api_url('repositories/%s/'
                                               % repository_id),
                    'method': 'GET',
                    'title': 'Test Repository',
                },
            })

        return {
            'item_key': 'review_request',
            'mimetype': self.make_mimetype('review-request'),
            'payload': {
                'absolute_url': '%sr/%s/' % (self.server_url,
                                             review_request_id),
                'approval_failure': approval_failure,
                'approved': approved,
                'blocks': [
                    {
                        'href': self._make_api_url('review-requests/%s/'
                                                   % _id),
                        'method': 'GET',
                        'title': 'Review request %s' % _id,
                    }
                    for _id in blocks_ids
                ],
                'branch': branch,
                'bugs_closed': bugs_closed,
                'changenum': changenum,
                'close_description': close_description,
                'close_description_text_type': close_description_text_type,
                'commit_id': commit_id,
                'created_with_history': created_with_history,
                'depends_on': [
                    {
                        'href': self._make_api_url('review-requests/%s/'
                                                   % _id),
                        'method': 'GET',
                        'title': 'Review request %s' % _id,
                    }
                    for _id in depends_on_ids
                ],
                'description': description,
                'description_text_type': description_text_type,
                'extra_data': extra_data,
                'id': review_request_id,
                'issue_dropped_count': issue_dropped_count,
                'issue_open_count': issue_open_count,
                'issue_resolved_count': issue_resolved_count,
                'issue_verifying_count': issue_verifying_count,
                'last_updated': last_updated,
                'links': links,
                'public': public,
                'ship_it_count': ship_it_count,
                'status': status,
                'summary': summary,
                'target_groups': [
                    {
                        'href': self._make_api_url('groups/%s/' % _name),
                        'method': 'GET',
                        'title': _name,
                    }
                    for _name in target_group_names
                ],
                'target_people': [
                    {
                        'href': self._make_api_url('users/%s/' % _username),
                        'method': 'GET',
                        'title': _username,
                    }
                    for _username in target_people_usernames
                ],
                'testing_done': testing_done,
                'testing_done_text_type': testing_done_text_type,
                'text_type': text_type,
                'time_added': time_added,
                'url': '/r/%s/' % review_request_id,
            },
            'url': url,
        }

    def make_review_request_draft_object_data(
            self,
            draft_id,
            review_request_id,
            branch='test-branch',
            bugs_closed=[],
            close_description='',
            close_description_text_type='plain',
            commit_id=None,
            depends_on_ids=[],
            description='Test Description',
            description_text_type='plain',
            extra_data={},
            last_updated='2022-04-21T15:44:00Z',
            public=True,
            submitter_username='test-user',
            summary='Test Summary',
            target_group_names=[],
            target_people_usernames=[],
            testing_done='Test Testing Done',
            testing_done_text_type='plain',
            text_type=None):
        """Return new review request draft resource data.

        Args:
            draft_id (int):
                The ID of the review request draft.

            review_request_id (int):
                The ID of the review request.

            branch (unicode, optional):
                The value of the ``branch`` field.

            bugs_closed (list of unicode, optional):
                The value of the ``bugs_closed`` field.

            close_description (unicode, optional):
                The value of the ``close_description`` field.

            close_description _text_type (unicode, optional):
                The value of the ``close_description_text_type`` field.

            commit_id (unicode, optional):
                The value of the ``commit_id`` field.

            depends_on_ids (list of int, optional):
                A list of review request IDs that this depends on, for use
                in the ``depends_on`` field.

            description (unicode, optional):
                The value of the ``description`` field.

            description_text_type (unicode, optional):
                The value of the ``description_text_type`` field.

            extra_data (dict, optional):
                The value of the ``extra_data`` field.

            last_updated (unicode, optional):
                The value of the ``last_updated`` field.

            public (bool, optional):
                The value of the ``public`` field.

            submitter_username (unicode, optional):
                The username of the submitter, for the ``submitter`` link.

            summary (unicode, optional):
                The value of the ``summary`` field.

            target_group_names (unicode, optional):
                A list of group names, for use in the ``target_groups`` field.

            target_people_usernames (unicode, optional):
                A list of usernames, for use in the ``target_people`` field.

            testing_done (unicode, optional):
                The value of the ``testing_done`` field.

            testing_done_text_type (unicode, optional):
                The value of the ``testing_done_text_type`` field.

            text_type (unicode, optional):
                The value of the ``text_type`` field.

        Returns:
            dict:
            The resource payload and metadata. See the class documentation
            for details.
        """
        url = self._make_api_url('review-requests/%s/draft/'
                                 % review_request_id)

        links = self._make_item_links(
            url=url,
            child_resource_names=[
                'draft_diffs',
                'draft_file_attachments',
                'draft_screenshots',
            ])
        links.update({
            'review_request': {
                'href': self._make_api_url('review-requests/%s/'
                                           % review_request_id),
                'method': 'GET',
                'title': 'Review request #%s' % review_request_id,
            },
            'submitter': {
                'href': self._make_api_url('users/%s/' % submitter_username),
                'method': 'GET',
                'title': submitter_username,
            },
        })

        return {
            'item_key': 'draft',
            'mimetype': self.make_mimetype('review-request-draft'),
            'payload': {
                'branch': branch,
                'bugs_closed': bugs_closed,
                'close_description': close_description,
                'close_description_text_type': close_description_text_type,
                'commit_id': commit_id,
                'depends_on': [
                    {
                        'href': self._make_api_url('review-requests/%s/'
                                                   % _id),
                        'method': 'GET',
                        'title': 'Review Request %s' % _id,
                    }
                    for _id in depends_on_ids
                ],
                'description': description,
                'description_text_type': description_text_type,
                'extra_data': extra_data,
                'id': draft_id,
                'last_updated': last_updated,
                'links': links,
                'public': public,
                'summary': summary,
                'target_groups': [
                    {
                        'href': self._make_api_url('groups/%s/' % _name),
                        'method': 'GET',
                        'title': _name,
                    }
                    for _name in target_group_names
                ],
                'target_people': [
                    {
                        'href': self._make_api_url('users/%s/' % _username),
                        'method': 'GET',
                        'title': _username,
                    }
                    for _username in target_people_usernames
                ],
                'testing_done': testing_done,
                'testing_done_text_type': testing_done_text_type,
                'text_type': text_type,
            },
            'url': url,
        }

    def make_session_object_data(self, authenticated=True,
                                 username='test-user'):
        """Return new session resource data.

        Args:
            authenticated (bool, optional):
                Whether this should be an authenticated session.

            username (unicode, optional):
                The current username, if authenticated.

        Returns:
            dict:
            The resource payload and metadata. See the class documentation
            for details.
        """
        url = self._make_api_url('session/')

        links = self._make_item_links(url=url)

        if authenticated:
            assert username

            links['user'] = {
                'href': self._make_api_url('users/%s/' % username),
                'method': 'GET',
                'title': username,
            }

        return {
            'item_key': 'session',
            'mimetype': self.make_mimetype('session'),
            'payload': {
                'authenticated': authenticated,
                'links': links,
            },
            'url': url,
        }

    def make_user_object_data(self,
                              user_id=1,
                              username='test-user',
                              email='test-user@example.com',
                              first_name='Test',
                              last_name='User',
                              is_active=True,
                              avatar_html=None,
                              avatar_urls={}):
        """Return new user resource data.

        Args:
            user_id (int, optional):
                The ID of the user.

            username (unicode, optional):
                The value of the ``username`` field.

            email (unicode, optional):
                The value of the ``email`` field.

            first_name (unicode, optional):
                The value of the ``first_name`` field.

                This also affects the ``fullname`` field.

            last_name (unicode, optional):
                The value of the ``last_name`` field.

                This also affects the ``fullname`` field.

            is_active (bool, optional):
                The value of the ``is_active`` field.

            avatar_html (unicode, optional):
                The value of the ``avatar_html`` field.

            avatar_urls (dict, optional):
                The value of the ``avatar_urls`` field.

                If set, and if it contains a ``1x`` key, this will also
                affect the ``avatar_url`` field.

        Returns:
            dict:
            The resource payload and metadata. See the class documentation
            for details.
        """
        url = self._make_api_url('users/%s/' % username)

        links = self._make_item_links(
            url=url,
            child_resource_names=[
                'api_tokens',
                'archived_review_requests',
                'muted_review_requests',
                'user_file_attachments',
                'watched',
            ])

        return {
            'item_key': 'user',
            'mimetype': self.make_mimetype('user'),
            'payload': {
                'avatar_html': avatar_html,
                'avatar_url': avatar_urls.get('1x'),
                'avatar_urls': avatar_urls,
                'email': email,
                'first_name': first_name,
                'fullname': '%s %s' % (first_name, last_name),
                'id': user_id,
                'is_active': is_active,
                'last_name': last_name,
                'links': links,
                'url': '/users/%s/' % username,
                'username': username,
            },
            'url': url,
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
