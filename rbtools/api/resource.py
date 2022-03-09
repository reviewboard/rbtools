from __future__ import unicode_literals

import logging
import re
from collections import defaultdict, deque

import six
from pkg_resources import parse_version
from six.moves import range
from six.moves.urllib.parse import urljoin

from rbtools.api.cache import MINIMUM_VERSION
from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.utils import rem_mime_format
from rbtools.utils.graphs import path_exists


RESOURCE_MAP = {}
LINKS_TOK = 'links'
EXPANDED_TOKEN = '_expanded'
LINK_KEYS = set(['href', 'method', 'title', 'mimetype'])
_EXCLUDE_ATTRS = [LINKS_TOK, EXPANDED_TOKEN, 'stat']
_EXTRA_DATA_PREFIX = 'extra_data__'


def resource_mimetype(mimetype):
    """Set the mimetype for the decorated class in the resource map."""
    def wrapper(cls):
        RESOURCE_MAP[mimetype] = cls
        return cls

    return wrapper


def _preprocess_fields(fields):
    """Pre-process request fields.

    This function rewrites fields of the form ``extra_data__field_name`` to
    fields of the form ``extra_data.field_name`` so that Review Board can
    understand them.

    Args:
        fields (dict):
            A mapping of field names to field values.
    """
    for name, value in six.iteritems(fields):
        if name.startswith(_EXTRA_DATA_PREFIX):
            name = 'extra_data.%s' % name[len(_EXTRA_DATA_PREFIX):]

        yield name, value


def _create_resource_for_field(parent_resource, field_payload,
                               mimetype, item_mimetype=None, url=None):
    """Create a resource instance based on field data.

    This will construct a resource instance for the payload of a field,
    using the given mimetype to identify it. This is intended for use with
    expanded resources or items in lists.

    Args:
        parent_resource (Resource):
            The resource containing the field payload.

        field_payload (dict):
            The field payload to use as the new resource's payload.

        mimetype (unicode):
            The mimetype of the resource.

        item_mimetype (unicode, optional):
            The mimetype of any items in the resource, if this resource
            represents a list.

        url (unicode, optional):
            The URL of the resource, if one is available.
    """
    # We need to import this here to avoid circular imports.
    from rbtools.api.factory import create_resource

    return create_resource(transport=parent_resource._transport,
                           payload=field_payload,
                           url=url,
                           mime_type=mimetype,
                           item_mime_type=item_mimetype,
                           guess_token=False)


@request_method_decorator
def _create(resource, data=None, query_args={}, *args, **kwargs):
    """Generate a POST request on a resource.

    Unlike other methods, any additional query args must be passed in
    using the 'query_args' parameter, since kwargs is used for the
    fields which will be sent.

    Review Board expects ``extra_data`` fields to be sent as
    ``extra_data.field_name``, which cannot be passed as a raw literal in
    Python. Fields like this would have to be added to a dict and splatted.
    However, this function also accepts keyword arguments of the form
    ``extra_data__field_name``, which will be rewritten to fields of the form
    ``extra_data.field_name``.
    """
    request = HttpRequest(resource._links['create']['href'], method='POST',
                          query_args=query_args)

    if data is None:
        data = {}

    kwargs.update(data)

    for name, value in _preprocess_fields(kwargs):
        request.add_field(name, value)

    return request


@request_method_decorator
def _delete(resource, *args, **kwargs):
    """Generate a DELETE request on a resource."""
    return HttpRequest(resource._links['delete']['href'], method='DELETE',
                       query_args=kwargs)


@request_method_decorator
def _get_self(resource, *args, **kwargs):
    """Generate a request for a resource's 'self' link."""
    return HttpRequest(resource._links['self']['href'], query_args=kwargs)


@request_method_decorator
def _update(resource, data=None, query_args={}, *args, **kwargs):
    """Generate a PUT request on a resource.

    Unlike other methods, any additional query args must be passed in
    using the 'query_args' parameter, since kwargs is used for the
    fields which will be sent.

    Review Board expects ``extra_data`` fields to be sent as
    ``extra_data.field_name``, which cannot be passed as a raw literal in
    Python. Fields like this would have to be added to a dict and splatted.
    However, this function also accepts keyword arguments of the form
    ``extra_data__field_name``, which will be rewritten to fields of the form
    ``extra_data.field_name``.
    """
    request = HttpRequest(resource._links['update']['href'], method='PUT',
                          query_args=query_args)

    if data is None:
        data = {}

    kwargs.update(data)

    for name, value in _preprocess_fields(kwargs):
        request.add_field(name, value)

    return request


# This dictionary is a mapping of special keys in a resources links,
# to a name and method used for generating a request for that link.
# This is used to special case the REST operation links. Any link
# included in this dictionary will be generated separately, and links
# with a None for the method will be ignored.
SPECIAL_LINKS = {
    'create': ['create', _create],
    'delete': ['delete', _delete],
    'next': ['get_next', None],
    'prev': ['get_prev', None],
    'self': ['get_self', _get_self],
    'update': ['update', _update],
}


class Resource(object):
    """Defines common functionality for Item and List Resources.

    Resources are able to make requests to the Web API by returning an
    HttpRequest object. When an HttpRequest is returned from a method
    call, the transport layer will execute this request and return the
    result to the user.

    Methods for constructing requests to perform each of the supported
    REST operations will be generated automatically. These methods
    will have names corresponding to the operation (e.g. 'update()').
    An additional method for re-requesting the resource using the
    'self' link will be generated with the name 'get_self'. Each
    additional link will have a method generated which constructs a
    request for retrieving the linked resource.
    """
    _excluded_attrs = []

    def __init__(self, transport, payload, url, token=None, **kwargs):
        self._url = url
        self._transport = transport
        self._token = token
        self._payload = payload
        self._excluded_attrs = set(self._excluded_attrs + _EXCLUDE_ATTRS)

        # Determine where the links live in the payload. This
        # can either be at the root, or inside the resources
        # token.
        if LINKS_TOK in self._payload:
            self._links = self._payload[LINKS_TOK]
        elif (token and isinstance(self._payload[token], dict) and
              LINKS_TOK in self._payload[token]):
            self._links = self._payload[token][LINKS_TOK]
        else:
            self._payload[LINKS_TOK] = {}
            self._links = {}

        # If we've expanded any fields, we'll try to convert the expanded
        # payloads into resources. We can only do this if talking to
        # Review Board 4.0+.
        if EXPANDED_TOKEN in self._payload:
            self._expanded_info = self._payload[EXPANDED_TOKEN]
        elif (token and isinstance(self._payload[token], dict) and
              EXPANDED_TOKEN in self._payload[token]):
            self._expanded_info = self._payload[token][EXPANDED_TOKEN]
        else:
            self._expanded_info = {}

        # Add a method for each supported REST operation, and
        # for retrieving 'self'.
        for link, method in six.iteritems(SPECIAL_LINKS):
            if link in self._links and method[1]:
                setattr(self,
                        method[0],
                        lambda resource=self, meth=method[1], **kwargs: (
                            meth(resource, **kwargs)))

        # Generate request methods for any additional links
        # the resource has.
        for link, body in six.iteritems(self._links):
            if link not in SPECIAL_LINKS:
                setattr(self,
                        'get_%s' % link,
                        lambda resource=self, url=body['href'], **kwargs: (
                            self._get_url(url, **kwargs)))

    def _wrap_field(self, field_payload, field_url=None, field_mimetype=None,
                    list_item_mimetype=None, force_resource=False):
        """Wrap the value of a field in a resource or field object.

        This determines a suitable wrapper for a field, turning it into
        a resource or a wrapper with utility methods that can be used to
        interact with the field or perform additional queries.

        Args:
            field_payload (object):
                The payload of the field. The type of value determines the
                way in which this is wrapped.

            field_url (unicode, optional):
                The URL representing the payload in the field, if one is
                available. If not provided, one may be computed, depending
                on the type and contents of the field.

            field_mimetype (unicode, optional):
                The mimetype used to represent the field. If provided, this
                may result in the wrapper being a :py:class:`Resource`
                subclass.

            list_item_mimetype (unicode, optional):
                The mimetype used or any items within the field, if the
                field is a list.

            force_resource (bool, optional):
                Force the return of a resource, even a generic one, instead
                of a field wrapper.

        Returns:
            object:
            A wrapper, or the field payload. This may be one of:

            1. A subclass of :py:class:`Resource`.
            2. A field wrapper (:py:class:`ResourceDictField`,
               :py:class:`ResourceLinkField`, or
               :py:class:`ResourceListField`).
            3. The field payload itself, if no wrapper is needed.
        """
        if isinstance(field_payload, dict):
            if (force_resource or
                (field_mimetype and
                 rem_mime_format(field_mimetype) in RESOURCE_MAP)):
                # We have a resource backing this mimetype. Try to create
                # an instance of the resource for this payload.
                if not field_url:
                    try:
                        field_url = field_payload['links']['self']['href']
                    except KeyError:
                        field_url = ''

                return _create_resource_for_field(parent_resource=self,
                                                  field_payload=field_payload,
                                                  mimetype=field_mimetype,
                                                  url=field_url)
            else:
                # If the payload consists solely of link-supported keys,
                # then we'll return a special ResourceLinkField. Anything
                # else is treated as a standard dictionary.
                if ('href' in field_payload and
                    not set(field_payload.keys()) - LINK_KEYS):
                    return ResourceLinkField(self, field_payload)
                else:
                    return ResourceDictField(self, field_payload)
        elif isinstance(field_payload, list):
            return ResourceListField(self, field_payload,
                                     item_mimetype=list_item_mimetype)
        else:
            return field_payload

    @property
    def links(self):
        """Get the resource's links.

        This is a special property which allows direct access to the links
        dictionary for a resource. Unlike other properties which come from the
        resource fields, this one is only accessible as a property, and not
        using array syntax."""
        return ResourceDictField(self, self._links)

    @request_method_decorator
    def _get_url(self, url, **kwargs):
        return HttpRequest(url, query_args=kwargs)

    @property
    def rsp(self):
        """Return the response payload used to create the resource."""
        return self._payload


class ResourceDictField(object):
    """Wrapper for dictionaries returned from a resource.

    Any dictionary returned from a resource will be wrapped using this
    class. Attribute access will correspond to accessing the
    dictionary key with the name of the attribute.
    """
    def __init__(self, resource, fields):
        self._resource = resource
        self._fields = fields

    def __getattr__(self, name):
        if name in self._fields:
            return self._resource._wrap_field(self._fields[name])
        else:
            raise AttributeError('This dictionary resource for %s does not '
                                 'have an attribute "%s".'
                                 % (self._resource.__class__.__name__, name))

    def __getitem__(self, key):
        try:
            return self.__getattr__(key)
        except AttributeError:
            raise KeyError

    def __contains__(self, key):
        return key in self._fields

    def iterfields(self):
        for field in self._fields:
            yield field

    def iteritems(self):
        for key, value in six.iteritems(self._fields):
            yield key, self._resource._wrap_field(value)

    def __repr__(self):
        return '%s(resource=%r, fields=%r)' % (
            self.__class__.__name__,
            self._resource,
            self._fields)


class ResourceLinkField(ResourceDictField):
    """Wrapper for link dictionaries returned from a resource.

    In order to support operations on links found outside of a
    resource's links dictionary, detected links are wrapped with this
    class.

    A links fields (href, method, and title) are accessed as
    attributes, and link operations are supported through method
    calls. Currently the only supported method is "GET", which can be
    invoked using the 'get' method.
    """
    def __init__(self, resource, fields):
        super(ResourceLinkField, self).__init__(resource, fields)
        self._transport = resource._transport

    @request_method_decorator
    def get(self, **query_args):
        return HttpRequest(self._fields['href'], query_args=query_args)


class ResourceListField(list):
    """Wrapper for lists returned from a resource.

    Acts as a normal list, but wraps any returned items.
    """
    def __init__(self, resource, list_field, item_mimetype=None):
        super(ResourceListField, self).__init__(list_field)

        self._resource = resource
        self._item_mimetype = item_mimetype

    def __getitem__(self, key):
        item = super(ResourceListField, self).__getitem__(key)
        return self._resource._wrap_field(item,
                                          field_mimetype=self._item_mimetype)

    def __iter__(self):
        for item in super(ResourceListField, self).__iter__():
            yield self._resource._wrap_field(
                item,
                field_mimetype=self._item_mimetype)

    def __repr__(self):
        return '%s(resource=%r, item_mimetype=%s, list_field=%s)' % (
            self.__class__.__name__,
            self._item_mimetype,
            self._resource,
            super(ResourceListField, self).__repr__())


class ItemResource(Resource):
    """The base class for Item Resources.

    Any resource specific base classes for Item Resources should
    inherit from this class. If a resource specific base class does
    not exist for an Item Resource payload, this class will be used to
    create the resource.

    The body of the resource is copied into the fields dictionary. The
    Transport is responsible for providing access to this data,
    preferably as attributes for the wrapping class.
    """
    _excluded_attrs = []

    def __init__(self, transport, payload, url, token=None, **kwargs):
        super(ItemResource, self).__init__(transport, payload, url,
                                           token=token, **kwargs)
        self._fields = {}

        # Determine the body of the resource's data.
        if token is not None:
            data = self._payload[token]
        else:
            data = self._payload

        for name, value in six.iteritems(data):
            if name not in self._excluded_attrs:
                self._fields[name] = value

    def __getattr__(self, name):
        """Return the value for an attribute on the resource.

        If the attribute represents an expanded resource, and there's
        information available on the expansion (available in Review Board
        4.0+), then a resource instance will be returned.

        If the attribute otherwise represents a dictionary, list, or a link,
        a wrapper may be returned.

        Args:
            name (str):
                The name of the attribute.

        Returns:
            object:
            The attribute value, or a wrapper or resource representing that
            value.

        Raises:
            AttributeError:
                A field with the given attribute name was not found.
        """
        try:
            field_payload = self._fields[name]
        except KeyError:
            raise AttributeError('This %s does not have an attribute "%s".'
                                 % (self.__class__.__name__, name))

        expand_info = self._expanded_info.get(name, {})

        if isinstance(field_payload, dict):
            value = self._wrap_field(
                field_payload=field_payload,
                field_mimetype=expand_info.get('item_mimetype'))
        elif isinstance(field_payload, list):
            value = self._wrap_field(
                field_payload=field_payload,
                field_url=expand_info.get('list_url'),
                field_mimetype=expand_info.get('list_mimetype'),
                list_item_mimetype=expand_info.get('item_mimetype'))
        else:
            value = self._wrap_field(field_payload)

        return value

    def __getitem__(self, key):
        try:
            return self.__getattr__(key)
        except AttributeError:
            raise KeyError

    def __contains__(self, key):
        return key in self._fields

    def iterfields(self):
        for key in self._fields:
            yield key

    def iteritems(self):
        """Iterate through all field/value pairs in the resource.

        Yields:
            tuple:
            A tuple in ``(field_name, value)`` form.
        """
        for key in self.iterfields():
            yield key, self.__getattr__(key)

    def __repr__(self):
        return '%s(transport=%r, payload=%r, url=%r, token=%r)' % (
            self.__class__.__name__,
            self._transport,
            self._payload,
            self._url,
            self._token)


class CountResource(ItemResource):
    """Resource returned by a query with 'counts-only' true.

    When a resource is requested using 'counts-only', the payload will
    not contain the regular fields for the resource. In order to
    special case all payloads of this form, this class is used for
    resource construction.
    """
    def __init__(self, transport, payload, url, **kwargs):
        super(CountResource, self).__init__(transport, payload, url,
                                            token=None)

    @request_method_decorator
    def get_self(self, **kwargs):
        """Generate an GET request for the resource list.

        This will return an HttpRequest to retrieve the list resource
        which this resource is a count for. Any query arguments used
        in the request for the count will still be present, only the
        'counts-only' argument will be removed
        """
        # TODO: Fix this. It is generating a new request
        # for a URL with 'counts-only' set to False, but
        # RB treats the  argument being set to any value
        # as true.
        kwargs.update({'counts_only': False})
        return HttpRequest(self._url, query_args=kwargs)


class ListResource(Resource):
    """The base class for List Resources.

    Any resource specific base classes for List Resources should
    inherit from this class. If a resource specific base class does
    not exist for a List Resource payload, this class will be used to
    create the resource.

    Instances of this class will act as a sequence, providing access
    to the payload for each Item resource in the list. Iteration is
    over the page of item resources returned by a single request, and
    not the entire list of resources. To iterate over all item
    resources 'get_next()' or 'get_prev()' should be used to grab
    additional pages of items.
    """
    def __init__(self, transport, payload, url, token=None,
                 item_mime_type=None, **kwargs):
        super(ListResource, self).__init__(transport, payload, url,
                                           token=token, **kwargs)
        self._item_mime_type = item_mime_type

        if token:
            self._item_list = payload[self._token]
        else:
            self._item_list = payload

        self.num_items = len(self._item_list)
        self.total_results = payload['total_results']

    def __len__(self):
        return self.num_items

    def __nonzero__(self):
        return self.__bool__()

    def __bool__(self):
        return True

    def __getitem__(self, index):
        """Return the item at the specified index.

        Args:
            index (int):
                The index of the item to retrieve.

        Returns:
            object:
            The item at the specified index.

        Raises:
            IndexError:
                The index is out of range.
        """
        return self._wrap_field(self._item_list[index],
                                field_mimetype=self._item_mime_type,
                                force_resource=True)

    def __iter__(self):
        for i in range(self.num_items):
            yield self[i]

    @request_method_decorator
    def get_next(self, **kwargs):
        if 'next' not in self._links:
            raise StopIteration()

        return HttpRequest(self._links['next']['href'], query_args=kwargs)

    @request_method_decorator
    def get_prev(self, **kwargs):
        if 'prev' not in self._links:
            raise StopIteration()

        return HttpRequest(self._links['prev']['href'], query_args=kwargs)

    @request_method_decorator
    def get_item(self, pk, **kwargs):
        """Retrieve the item resource with the corresponding primary key."""
        return HttpRequest(urljoin(self._url, '%s/' % pk),
                           query_args=kwargs)

    @property
    def all_pages(self):
        """Yield all pages of item resources.

        Each page of resources is itself an instance of the same
        ``ListResource`` class.
        """
        page = self

        while True:
            yield page

            try:
                page = page.get_next()
            except StopIteration:
                break

    @property
    def all_items(self):
        """Yield all item resources in all pages of this resource."""
        for page in self.all_pages:
            for item in page:
                yield item

    def __repr__(self):
        return ('%s(transport=%r, payload=%r, url=%r, token=%r, '
                'item_mime_type=%r)' % (self.__class__.__name__,
                                        self._transport,
                                        self._payload,
                                        self._url,
                                        self._token,
                                        self._item_mime_type))


@resource_mimetype('application/vnd.reviewboard.org.root')
class RootResource(ItemResource):
    """The Root resource specific base class.

    Provides additional methods for fetching any resource directly
    using the uri templates. A method of the form "get_<uri-template-name>"
    is called to retrieve the HttpRequest corresponding to the
    resource. Template replacement values should be passed in as a
    dictionary to the values parameter.
    """
    _excluded_attrs = ['uri_templates']
    _TEMPLATE_PARAM_RE = re.compile(r'\{(?P<key>[A-Za-z_0-9]*)\}')

    def __init__(self, transport, payload, url, **kwargs):
        super(RootResource, self).__init__(transport, payload, url, token=None)
        # Generate methods for accessing resources directly using
        # the uri-templates.
        for name, url in six.iteritems(payload['uri_templates']):
            attr_name = 'get_%s' % name

            if not hasattr(self, attr_name):
                setattr(self,
                        attr_name,
                        lambda resource=self, url=url, **kwargs: (
                            self._get_template_request(url, **kwargs)))

        server_version = payload.get('product', {}).get('package_version')

        if (server_version is not None and
            parse_version(server_version) >= parse_version(MINIMUM_VERSION)):
            transport.enable_cache()

    @request_method_decorator
    def _get_template_request(self, url_template, values={}, **kwargs):
        """Generate an HttpRequest from a uri-template.

        This will replace each '{variable}' in the template with the
        value from kwargs['variable'], or if it does not exist, the
        value from values['variable']. The resulting url is used to
        create an HttpRequest.
        """
        def get_template_value(m):
            try:
                return str(kwargs.pop(m.group('key'), None) or
                           values[m.group('key')])
            except KeyError:
                raise ValueError('Template was not provided a value for "%s"' %
                                 m.group('key'))

        url = self._TEMPLATE_PARAM_RE.sub(get_template_value, url_template)
        return HttpRequest(url, query_args=kwargs)


@resource_mimetype('application/vnd.reviewboard.org.commit')
class DiffCommitItemResource(ItemResource):
    """The commit resource-specific class."""

    @request_method_decorator
    def get_patch(self, **kwargs):
        """Retrieve the actual diff file contents.

        Args:
            **kwargs (dict):
                Query args to pass to
                :py:meth:`~rbtools.api.request.HttpRequest.__init__`.

        Returns:
            ItemResource:
            A resource payload whose :py:attr:`~ItemResource.data` attribute is
            the requested patch.
        """
        return HttpRequest(self._url, query_args=kwargs, headers={
            'Accept': 'text/x-patch',
        })


@resource_mimetype('application/vnd.reviewboard.org.draft-commit')
class DraftDiffCommitItemResource(ItemResource):
    """The draft commit resource-specific class."""
    pass


@resource_mimetype('application/vnd.reviewboard.org.draft-commits')
class DraftDiffCommitListResource(ListResource):
    """The draft commit list resource-specific class.

    Provides additional functionality in the uploading of new commits.
    """

    @request_method_decorator
    def upload_commit(self, validation_info, diff, commit_id, parent_id,
                      author_name, author_email, author_date, commit_message,
                      committer_name=None, committer_email=None,
                      committer_date=None, parent_diff=None, **kwargs):
        """Upload a commit.

        Args:
            validation_info (unicode):
                The validation info, or ``None`` if this is the first commit in
                a series.

            diff (bytes):
                The diff contents.

            commit_id (unicode):
                The ID of the commit being uploaded.

            parent_id (unicode):
                The ID of the parent commit.

            author_name (unicode):
                The name of the author.

            author_email (unicode):
                The e-mail address of the author.

            author_date (unicode):
                The date and time the commit was authored in ISO 8601 format.

            committer_name (unicode, optional):
                The name of the committer (if applicable).

            committer_email (unicode, optional):
                The e-mail address of the committer (if applicable).

            committer_date (unicode, optional):
                The date and time the commit was committed in ISO 8601 format
                (if applicable).

            parent_diff (bytes, optional):
                The contents of the parent diff.

            **kwargs (dict):
                Keyword argument used to build the querystring for the request
                URL.

        Returns:
            DraftDiffCommitItemResource:
            The created resource.

        Raises:
            rbtools.api.errors.APIError:
                An error occurred while uploading the commit.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)

        request.add_file('diff', 'diff', diff)
        request.add_field('commit_id', commit_id)
        request.add_field('parent_id', parent_id)
        request.add_field('commit_message', commit_message)
        request.add_field('author_name', author_name)
        request.add_field('author_email', author_email)
        request.add_field('author_date', author_date)

        if validation_info:
            request.add_field('validation_info', validation_info)

        if committer_name and committer_email and committer_date:
            request.add_field('committer_name', committer_name)
            request.add_field('committer_email', committer_email)
            request.add_field('committer_date', committer_date)
        elif committer_name or committer_email or committer_name:
            logging.warning(
                'Either all or none of committer_name, committer_email, and '
                'committer_date must be provided to upload_commit. None of '
                'these fields will be submitted.'
            )

        if parent_diff:
            request.add_file('parent_diff', 'parent_diff', parent_diff)

        return request


class DiffUploaderMixin(object):
    """A mixin for uploading diffs to a resource."""

    def prepare_upload_diff_request(self, diff, parent_diff=None,
                                    base_dir=None, base_commit_id=None,
                                    **kwargs):
        """Create a request that can be used to upload a diff.

        The diff and parent_diff arguments should be strings containing the
        diff output.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)
        request.add_file('path', 'diff', diff)

        if parent_diff:
            request.add_file('parent_diff_path', 'parent_diff', parent_diff)

        if base_dir:
            request.add_field('basedir', base_dir)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request


@resource_mimetype('application/vnd.reviewboard.org.diffs')
class DiffListResource(DiffUploaderMixin, ListResource):
    """The Diff List resource specific base class.

    This resource provides functionality to assist in the uploading of new
    diffs.
    """

    @request_method_decorator
    def upload_diff(self, diff, parent_diff=None, base_dir=None,
                    base_commit_id=None, **kwargs):
        """Upload a diff to the resource.

        The diff and parent_diff arguments should be strings containing the
        diff output.
        """
        return self.prepare_upload_diff_request(
            diff,
            parent_diff=parent_diff,
            base_dir=base_dir,
            base_commit_id=base_commit_id,
            **kwargs)

    @request_method_decorator
    def create_empty(self, base_commit_id=None, **kwargs):
        """Create an empty DiffSet that commits can be added to.

        Args:
            base_commit_id (unicode, optional):
                The base commit ID of the diff.

            **kwargs (dict):
                Keyword arguments to encode into the querystring of the request
                URL.
        Returns:
            DiffItemResource:
            The created resource.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request


@resource_mimetype('application/vnd.reviewboard.org.diff')
class DiffResource(ItemResource):
    """The Diff resource specific base class.

    Provides the 'get_patch' method for retrieving the content of the
    actual diff file itself.
    """
    @request_method_decorator
    def get_patch(self, **kwargs):
        """Retrieves the actual diff file contents."""
        return HttpRequest(self._url, query_args=kwargs, headers={
            'Accept': 'text/x-patch',
        })

    @request_method_decorator
    def finalize_commit_series(self, cumulative_diff, validation_info,
                               parent_diff=None):
        """Finalize a commit series.

        Args:
            cumulative_diff (bytes):
                The cumulative diff of the entire commit series.

            validation_info (unicode):
                The validation information returned by validatin the last
                commit in the series with the
                :py:class:`ValidateDiffCommitResource`.

            parent_diff (bytes, optional):
                An optional parent diff.

                This will be the same parent diff uploaded with each commit.

        Returns:
            DiffItemResource:
            The finalized diff resource.
        """
        if not isinstance(cumulative_diff, bytes):
            raise TypeError('cumulative_diff must be byte string, not %s'
                            % type(cumulative_diff))

        if parent_diff is not None and not isinstance(parent_diff, bytes):
            raise TypeError('parent_diff must be byte string, not %s'
                            % type(cumulative_diff))

        request = HttpRequest(self.links['self']['href'],
                              method='PUT')

        request.add_field('finalize_commit_series', True)
        request.add_file('cumulative_diff', 'cumulative_diff',
                         cumulative_diff)
        request.add_field('validation_info', validation_info)

        if parent_diff is not None:
            request.add_file('parent_diff', 'parent_diff', parent_diff)

        return request


@resource_mimetype('application/vnd.reviewboard.org.file')
class FileDiffResource(ItemResource):
    """The File Diff resource specific base class."""
    @request_method_decorator
    def get_patch(self, **kwargs):
        """Retrieves the actual diff file contents."""
        return HttpRequest(self._url, query_args=kwargs, headers={
            'Accept': 'text/x-patch',
        })

    @request_method_decorator
    def get_diff_data(self, **kwargs):
        """Retrieves the actual raw diff data for the file."""
        return HttpRequest(self._url, query_args=kwargs, headers={
            'Accept': 'application/vnd.reviewboard.org.diff.data+json',
        })


@resource_mimetype('application/vnd.reviewboard.org.file-attachments')
@resource_mimetype('application/vnd.reviewboard.org.user-file-attachments')
class FileAttachmentListResource(ListResource):
    """The File Attachment List resource specific base class."""
    @request_method_decorator
    def upload_attachment(self, filename, content, caption=None,
                          attachment_history=None, **kwargs):
        """Uploads a new attachment.

        The content argument should contain the body of the file to be
        uploaded, in string format.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)
        request.add_file('path', filename, content)

        if caption:
            request.add_field('caption', caption)

        if attachment_history:
            request.add_field('attachment_history', attachment_history)

        return request


@resource_mimetype('application/vnd.reviewboard.org.draft-file-attachments')
class DraftFileAttachmentListResource(FileAttachmentListResource):
    """The Draft File Attachment List resource specific base class."""
    pass


@resource_mimetype('application/vnd.reviewboard.org.screenshots')
class ScreenshotListResource(ListResource):
    """The Screenshot List resource specific base class."""
    @request_method_decorator
    def upload_screenshot(self, filename, content, caption=None, **kwargs):
        """Uploads a new screenshot.

        The content argument should contain the body of the screenshot
        to be uploaded, in string format.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)
        request.add_file('path', filename, content)

        if caption:
            request.add_field('caption', caption)

        return request


@resource_mimetype('application/vnd.reviewboard.org.draft-screenshots')
class DraftScreenshotListResource(ScreenshotListResource):
    """The Draft Screenshot List resource specific base class."""
    pass


@resource_mimetype('application/vnd.reviewboard.org.review-request')
class ReviewRequestResource(ItemResource):
    """The Review Request resource specific base class."""

    @property
    def absolute_url(self):
        """Returns the absolute URL for the Review Request.

        The value of absolute_url is returned if it's defined.
        Otherwise the absolute URL is generated and returned.
        """
        if 'absolute_url' in self._fields:
            return self._fields['absolute_url']
        else:
            base_url = self._url.split('/api/')[0]
            return urljoin(base_url, self.url)

    @property
    def url(self):
        """Returns the relative URL to the Review Request.

        The value of 'url' is returned if it's defined. Otherwise, a relative
        URL is generated and returned.

        This provides compatibility with versions of Review Board older
        than 1.7.8, which do not have a 'url' field.
        """
        return self._fields.get('url', '/r/%s/' % self.id)

    @request_method_decorator
    def submit(self, description=None, changenum=None):
        """Submit a review request"""
        data = {
            'status': 'submitted',
        }

        if description:
            data['description'] = description

        if changenum:
            data['changenum'] = changenum

        return self.update(data=data, internal=True)

    @request_method_decorator
    def get_or_create_draft(self, **kwargs):
        request = self.get_draft(internal=True)
        request.method = 'POST'

        for name, value in six.iteritems(kwargs):
            request.add_field(name, value)

        return request

    def build_dependency_graph(self):
        """Build the dependency graph for the review request.

        Only review requests in the same repository as this one will be in the
        graph.

        A ValueError is raised if the graph would contain cycles.
        """
        def get_url(resource):
            """Get the URL of the resource."""
            if hasattr(resource, 'href'):
                return resource.href
            else:
                return resource.absolute_url

        # Even with the API cache, we don't want to be making more requests
        # than necessary. The review request resource will be cached by an
        # ETag, so there will still be a round trip if we don't cache them
        # here.
        review_requests_by_url = {}
        review_requests_by_url[self.absolute_url] = self

        def get_review_request_resource(resource):
            url = get_url(resource)

            if url not in review_requests_by_url:
                review_requests_by_url[url] = resource.get(expand='repository')

            return review_requests_by_url[url]

        repository = self.get_repository()

        graph = defaultdict(set)

        visited = set()

        unvisited = deque()
        unvisited.append(self)

        while unvisited:
            head = unvisited.popleft()

            if head in visited:
                continue

            visited.add(get_url(head))

            for tail in head.depends_on:
                tail = get_review_request_resource(tail)

                if path_exists(graph, tail.id, head.id):
                    raise ValueError('Circular dependencies.')

                # We don't want to include review requests for other
                # repositories, so we'll stop if we reach one. We also don't
                # want to re-land submitted review requests.
                if (repository.id == tail.repository.id and
                    tail.status != 'submitted'):
                    graph[head].add(tail)
                    unvisited.append(tail)

        graph.default_factory = None
        return graph


@resource_mimetype('application/vnd.reviewboard.org.diff-validation')
class ValidateDiffResource(DiffUploaderMixin, ItemResource):
    """The Validate Diff resource specific base class.

    Provides additional functionality to assist in the validation of diffs.
    """

    @request_method_decorator
    def validate_diff(self, repository, diff, parent_diff=None, base_dir=None,
                      base_commit_id=None, **kwargs):
        """Validate a diff."""
        request = self.prepare_upload_diff_request(
            diff,
            parent_diff=parent_diff,
            base_dir=base_dir,
            base_commit_id=base_commit_id,
            **kwargs)

        request.add_field('repository', repository)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request


@resource_mimetype('application/vnd.reviewboard.org.commit-validation')
class ValidateDiffCommitResource(ItemResource):
    """The commit validation resource specific base class."""

    @request_method_decorator
    def validate_commit(self, repository, diff, commit_id, parent_id,
                        parent_diff=None, base_commit_id=None,
                        validation_info=None, **kwargs):
        """Validate the diff for a commit.

        Args:
            repository (unicode):
                The name of the repository.

            diff (bytes):
                The contents of the diff to validate.

            commit_id (unicode):
                The ID of the commit being validated.

            parent_id (unicode):
                The ID of the parent commit.

            parent_diff (bytes, optional):
                The contents of the parent diff.

            base_commit_id (unicode, optional):
                The base commit ID.

            validation_info (unicode, optional):
                Validation information from a previous call to this resource.

            **kwargs (dict):
                Keyword arguments used to build the querystring.

        Returns:
            ValidateDiffCommitResource:
            The validation result.
        """
        request = HttpRequest(self._url, method='POST', query_args=kwargs)
        request.add_file('diff', 'diff', diff)
        request.add_field('repository', repository)
        request.add_field('commit_id', commit_id)
        request.add_field('parent_id', parent_id)

        if parent_diff:
            request.add_file('parent_diff', 'parent_diff', parent_diff)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        if validation_info:
            request.add_field('validation_info', validation_info)

        return request
