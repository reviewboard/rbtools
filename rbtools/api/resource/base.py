"""Resource definitions for the RBTools Python API.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator, MutableMapping
from typing import Any, Optional
from urllib.parse import urljoin

from rbtools.api.decorators import request_method_decorator
from rbtools.api.request import HttpRequest
from rbtools.api.utils import rem_mime_format


RESOURCE_MAP = {}
LINKS_TOK = 'links'
EXPANDED_TOKEN = '_expanded'
LINK_KEYS = {'href', 'method', 'title', 'mimetype'}
_EXCLUDE_ATTRS = [LINKS_TOK, EXPANDED_TOKEN, 'stat']
_EXTRA_DATA_PREFIX = 'extra_data__'


_EXTRA_DATA_DOCS_URL = (
    'https://www.reviewboard.org/docs/manual/4.0/webapi/2.0/extra-data/'
    '#storing-merging-json-data'
)


def resource_mimetype(mimetype):
    """Set the mimetype for the decorated class in the resource map."""
    def wrapper(cls):
        RESOURCE_MAP[mimetype] = cls
        return cls

    return wrapper


def _preprocess_fields(fields):
    """Pre-process request fields.

    Any ``extra_data_json`` (JSON Merge Patch) or ``extra_data_json_patch``
    (JSON Patch) fields will be serialized to JSON and stored.

    Any :samp:`extra_data__{key}` fields will be converted to
    :samp:`extra_data.{key}` fields, which will be handled by the Review Board
    API. These cannot store complex types.

    Version Changed:
        3.1:
        Added support for ``extra_data_json`` and ``extra_data_json_patch``.

    Args:
        fields (dict):
            A mapping of field names to field values.

    Yields:
        tuple:
        A 2-tuple of:

        1. The normalized field name to send in the request.
        2. The normalized value to send.
    """
    field_names = set(fields.keys())

    # Serialize the JSON Merge Patch or JSON Patch payloads first.
    for norm_field_name, field_name in (('extra_data:json',
                                         'extra_data_json'),
                                        ('extra_data:json-patch',
                                         'extra_data_json_patch')):
        if field_name in field_names:
            field_names.remove(field_name)

            yield (
                norm_field_name,
                json.dumps(fields[field_name],
                           sort_keys=True,
                           separators=(',', ':')),
            )

    for name in sorted(field_names):
        value = fields[name]

        if name.startswith(_EXTRA_DATA_PREFIX):
            # It's technically not a problem to send both an extra_data.<key>
            # and a JSON Patch or Merge Patch in the same request, but in
            # the future we may want to warn about it, just to help guide
            # users toward a single implementation.
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

    Any ``extra_data_json`` (JSON Merge Patch) or ``extra_data_json_patch``
    (JSON Patch) fields will be serialized to JSON and stored.

    Any :samp:`extra_data__{key}` fields will be converted to
    :samp:`extra_data.{key}` fields, which will be handled by the Review Board
    API. These cannot store complex types.

    Version Changed:
        3.1:
        Added support for ``extra_data_json`` and ``extra_data_json_patch``.

    Args:
        resource (Resource):
            The resource instance owning this create method.

        data (dict, optional):
            Data to send in the POST request. This will be merged with
            ``**kwargs``.

        query_args (dict, optional):
            Optional query arguments for the URL.

        *args (tuple, unused):
            Unused positional arguments.

        **kwargs (dict):
            Keyword arguments representing additional fields to set in the
            request. This will be merged with ``data``.

    Returns:
        rbtools.api.request.HttpRequest:
        The resulting HTTP POST request for this create operation.
    """
    request = HttpRequest(resource._links['create']['href'],
                          method='POST',
                          query_args=query_args)

    field_data = kwargs

    if data:
        field_data.update(data)

    for name, value in _preprocess_fields(field_data):
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

    Any ``extra_data_json`` (JSON Merge Patch) or ``extra_data_json_patch``
    (JSON Patch) fields will be serialized to JSON and stored.

    Any :samp:`extra_data__{key}` fields will be converted to
    :samp:`extra_data.{key}` fields, which will be handled by the Review Board
    API. These cannot store complex types.

    Version Changed:
        3.1:
        Added support for ``extra_data_json`` and ``extra_data_json_patch``.

    Args:
        resource (Resource):
            The resource instance owning this create method.

        data (dict, optional):
            Data to send in the POST request. This will be merged with
            ``**kwargs``.

        query_args (dict, optional):
            Optional query arguments for the URL.

        *args (tuple, unused):
            Unused positional arguments.

        **kwargs (dict):
            Keyword arguments representing additional fields to set in the
            request. This will be merged with ``data``.

    Returns:
        rbtools.api.request.HttpRequest:
        The resulting HTTP PUT request for this create operation.
    """
    request = HttpRequest(resource._links['update']['href'], method='PUT',
                          query_args=query_args)

    field_data = kwargs

    if data:
        field_data.update(data)

    for name, value in _preprocess_fields(field_data):
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
        for link, method in SPECIAL_LINKS.items():
            if link in self._links and method[1]:
                setattr(self,
                        method[0],
                        lambda resource=self, meth=method[1], **kwargs: (
                            meth(resource, **kwargs)))

        # Generate request methods for any additional links
        # the resource has.
        for link, body in self._links.items():
            if link not in SPECIAL_LINKS:
                setattr(self,
                        'get_%s' % link,
                        lambda resource=self, url=body['href'], **kwargs: (
                            self._get_url(url, **kwargs)))

    def _wrap_field(self, field_payload, field_name=None, field_url=None,
                    field_mimetype=None, list_item_mimetype=None,
                    force_resource=False):
        """Wrap the value of a field in a resource or field object.

        This determines a suitable wrapper for a field, turning it into
        a resource or a wrapper with utility methods that can be used to
        interact with the field or perform additional queries.

        Args:
            field_payload (object):
                The payload of the field. The type of value determines the
                way in which this is wrapped.

            field_name (unicode, optional):
                The name of the field being wrapped, if known.

                Version Added:
                    3.1

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
               :py:class:`ResourceListField`,
               :py:class:`ResourceLinkField`, or
               :py:class:`ResourceExtraDataField`).
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
                # If this is an extra_data field, we'll return a special
                # ExtraDataField.
                #
                # If the payload consists solely of link-supported keys,
                # then we'll return a special ResourceLinkField.
                #
                # Anything else is treated as a standard dictionary, which
                # will be wrapped.
                if field_name == 'extra_data':
                    return ResourceExtraDataField(resource=self,
                                                  fields=field_payload)
                elif ('href' in field_payload and
                      not set(field_payload.keys()) - LINK_KEYS):
                    return ResourceLinkField(resource=self,
                                             fields=field_payload)
                else:
                    return ResourceDictField(resource=self,
                                             fields=field_payload)
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


class ResourceDictField(MutableMapping):
    """Wrapper for dictionaries returned from a resource.

    Items fetched from this dictionary may be wrapped as a resource or
    resource field container.

    Changes cannot be made to resource dictionaries. Instead, changes must be
    made using :py:meth:`Resource.update` calls.

    Version Changed:
        3.1:
        This class now operates like a standard dictionary, but blocks any
        changes (which were misleading and could not be used to save state
        in any prior version).
    """

    def __init__(self, resource, fields):
        """Initialize the field.

        Args:
            resource (Resource):
                The parent resource that owns this field.

            fields (dict):
                The dictionary contents from the payload.
        """
        super(ResourceDictField, self).__init__()

        self._resource = resource
        self._fields = fields

    def __getattr__(self, name):
        """Return the value of a key from the field as an attribute reference.

        The resulting value will be wrapped as a resource or resource field
        if appropriate.

        Args:
            name (unicode):
                The name of the key.

        Returns:
            object:
            The value of the field.

        Raises:
            AttributeError:
                The provided key name was not found in the dictionary.
        """
        try:
            return self._wrap_field(name)
        except KeyError:
            raise AttributeError('This dictionary resource for %s does not '
                                 'have an attribute "%s".'
                                 % (self._resource.__class__.__name__, name))

    def __getitem__(self, name):
        """Return the value of a key from the field as an item lookup.

        The resulting value will be wrapped as a resource or resource field
        if appropriate.

        Args:
            name (unicode):
                The name of the key.

        Returns:
            object:
            The value of the field.

        Raises:
            KeyError:
                The provided key name was not found in the dictionary.
        """
        try:
            return self._wrap_field(name)
        except KeyError:
            raise KeyError('This dictionary resource for %s does not have '
                           'a key "%s".'
                           % (self._resource.__class__.__name__, name))

    def __delitem__(self, name):
        """Delete an item from the dictionary.

        This will raise an exception stating that changes are not allowed
        and offering an alternative.

        Args:
            name (unicode, unused):
                The name of the key to delete.

        Raises:
            AttributeError:
                An error stating that changes are not allowed.
        """
        self._raise_immutable()

    def __setitem__(self, name, value):
        """Set an item in the dictionary.

        This will raise an exception stating that changes are not allowed
        and offering an alternative.

        Args:
            name (unicode, unused):
                The name of the key to set.

        Raises:
            AttributeError:
                An error stating that changes are not allowed.
        """
        self._raise_immutable()

    def __len__(self):
        """Return the number of items in the dictionary.

        Returns:
            int:
            The number of items.
        """
        return len(self._fields)

    def __iter__(self):
        """Iterate through the dictionary.

        Yields:
            object:
            Each item in the dictionary.
        """
        yield from self._fields.keys()

    def __repr__(self):
        """Return a string representation of the dictionary field.

        Returns:
            unicode:
            The string representation.
        """
        return '%s(resource=%r, fields=%r)' % (
            self.__class__.__name__,
            self._resource,
            self._fields)

    def fields(self):
        """Iterate through all fields in the dictionary.

        This will yield each field name in the dictionary. This is the same
        as calling :py:meth:`keys` or simply ``for field in dict_field``.

        Yields:
            str:
            Each field in this dictionary.
        """
        yield from self

    def _wrap_field(self, field_name):
        """Conditionally return a wrapped version of a field's value.

        This will wrap content according to the resource's wrapping logic.

        Args:
            field_name (unicode):
                The name of the field to wrap.

        Returns:
            object:
            The wrapped object or field value.

        Raises:
            KeyError:
                The field could not be found in this dictionary.
        """
        # This may raise an exception, which will be handled by the caller.
        return self._resource._wrap_field(self._fields[field_name],
                                          field_name=field_name)

    def _raise_immutable(self):
        """Raise an exception stating that the dictionary is immutable.

        Version Added:
            3.1

        Raises:
            AttributeError:
                An error stating that changes are not allowed.
        """
        raise AttributeError(
            'Attributes cannot be modified directly on this dictionary. To '
            'change values, issue a .update(attr=value, ...) call on the '
            'parent resource.')


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


class ResourceExtraDataField(ResourceDictField):
    """Wrapper for extra_data fields on resources.

    Version Added:
        3.1
    """

    def copy(self):
        """Return a copy of the dictionary's fields.

        A copy of the original ``extra_data`` content will be returned,
        without any field wrapping.

        Returns:
            dict:
            The copy of the dictionary.
        """
        return copy.deepcopy(self._fields)

    def _wrap_field(self, field_name):
        """Conditionally return a wrapped version of a field's value.

        This will wrap dictionaries in another
        :py:class:`ResourceExtraDataField`, and otherwise leave everything
        else unwrapped (preventing list-like or links-like payloads from
        being wrapped in their respective field types).

        Args:
            field_name (unicode):
                The name of the field to wrap.

        Returns:
            object:
            The wrapped object or field value.

        Raises:
            KeyError:
                The field could not be found in this dictionary.
        """
        # This may raise an exception, which will be handled by the caller.
        value = self._fields[field_name]

        if isinstance(value, dict):
            return ResourceExtraDataField(resource=self._resource,
                                          fields=value)

        # Leave everything else unwrapped.
        return value

    def _raise_immutable(self):
        """Raise an exception stating that the dictionary is immutable.

        Raises:
            AttributeError:
                An error stating that changes are not allowed.
        """
        raise AttributeError(
            'extra_data attributes cannot be modified directly on this '
            'dictionary. To make a mutable copy of this and all its contents, '
            'call .copy(). To set or change extra_data state, issue a '
            '.update(extra_data_json={...}) for a JSON Merge Patch request or '
            '.update(extra_data_json_patch=[...]) for a JSON Patch request '
            'on the parent resource. See %s for the format for these '
            'operations.'
            % _EXTRA_DATA_DOCS_URL)


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

        for name, value in data.items():
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
                field_name=name,
                field_payload=field_payload,
                field_mimetype=expand_info.get('item_mimetype'))
        elif isinstance(field_payload, list):
            value = self._wrap_field(
                field_name=name,
                field_payload=field_payload,
                field_url=expand_info.get('list_url'),
                field_mimetype=expand_info.get('list_mimetype'),
                list_item_mimetype=expand_info.get('item_mimetype'))
        else:
            value = self._wrap_field(field_payload,
                                     field_name=name)

        return value

    def __getitem__(self, key):
        try:
            return self.__getattr__(key)
        except AttributeError:
            raise KeyError

    def __contains__(self, key):
        return key in self._fields

    def iterfields(self) -> Iterator[str]:
        """Iterate through all field names in the resource.

        Yields:
            str:
            The name of each field name.
        """
        for key in self._fields:
            yield key

    def iteritems(self) -> Iterator[str, Any]:
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

    ######################
    # Instance variables #
    ######################

    #: The total number of results in the list across all pages.
    #:
    #: This is commonly set for most list resources, but is not always
    #: guaranteed to be available. Callers should check to make sure this is
    #: not ``None``.
    #:
    #: Type:
    #:     int
    total_results: Optional[int]

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
        self.total_results = payload.get('total_results')

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
