"""Resource definitions for the RBTools Python API.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator, Mapping, MutableMapping
from functools import update_wrapper, wraps
from typing import (Any, Callable, ClassVar, Final, Optional, NoReturn,
                    TypeVar, TYPE_CHECKING, Union, cast)
from urllib.parse import urljoin

from typelets.json import JSONDict, JSONValue
from typing_extensions import NotRequired, ParamSpec, Self, TypedDict

from rbtools.api.request import HttpRequest, QueryArgs
from rbtools.api.utils import rem_mime_format

if TYPE_CHECKING:
    from rbtools.api.transport import Transport


#: Map from MIME type to resource class.
RESOURCE_MAP: dict[str, type[Resource]] = {}

#: The name of the links structure within a response payload.
LINKS_TOK: Final[str] = 'links'

#: The name of the expanded info structure within a response payload.
EXPANDED_TOKEN: Final[str] = '_expanded'

#: Keys within a link dict.
LINK_KEYS: set[str] = {'href', 'method', 'title', 'mimetype'}

#: Default attributes to exclude when processing a response.
_EXCLUDE_ATTRS: set[str] = {LINKS_TOK, EXPANDED_TOKEN, 'stat'}

#: Prefix for keys which should be stored in extra data.
_EXTRA_DATA_PREFIX: Final[str] = 'extra_data__'

#: URL for documentation on working with extra data.
_EXTRA_DATA_DOCS_URL: Final[str] = (
    'https://www.reviewboard.org/docs/manual/latest/webapi/2.0/extra-data/'
     '#storing-merging-json-data'
 )


_P = ParamSpec('_P')
_T = TypeVar('_T')


def request_method(
    f: Callable[_P, HttpRequest],
) -> Callable[_P, RequestMethodResult]:
    """Wrap a method returned from a resource to capture HttpRequests.

    When a method which returns HttpRequests is called, it will
    pass the method and arguments off to the transport to be executed.

    This wrapping allows the transport to skim arguments off the top
    of the method call, and modify any return values (such as executing
    a returned HttpRequest).

    However, if called with the ``internal`` argument set to True,
    the method itself will be executed and the value returned as-is.
    Thus, any method calls embedded inside the code for another method
    should use the ``internal`` argument to access the expected value.

    Version Changed:
        6.0:
        Moved and renamed from rbtools.api.decorators.request_method_decorator.

    Args:
        f (callable):
            The method to wrap.

    Returns:
        callable:
        The wrapped method.
    """
    @wraps(f)
    def request_method(
        self: Resource,
        *args,
        **kwargs,
    ) -> RequestMethodResult:
        if kwargs.pop('internal', False):
            return f(self, *args, **kwargs)
        else:
            def method_wrapper(*args, **kwargs) -> HttpRequest:
                return f(self, *args, **kwargs)

            return self._transport.execute_request_method(method_wrapper,
                                                          *args, **kwargs)

    return request_method


_STUB_ATTR_NAME = '_rbtools_api_stub'


def api_stub(
    f: Callable[_P, _T],
) -> Callable[_P, _T]:
    """Mark a method as being an API stub.

    Version Added:
        6.0

    Args:
        f (callable):
            The stub method.

    Returns:
        callable:
        The stub method.
    """
    setattr(f, _STUB_ATTR_NAME, True)

    return f


def is_api_stub(
    f: Callable[..., Any],
) -> bool:
    """Return whether a given method is an API stub.

    Version Added:
        6.0

    Args:
        f (callable):
            The method to check.

    Returns:
        bool:
        ``True`` if the method was decorated with :py:func:`api_stub`.
        ``False``, otherwise.
    """
    return getattr(f, _STUB_ATTR_NAME, False)


def replace_api_stub(
    obj: Resource,
    attr: str,
    stub: Callable[..., Any],
    implementation: Callable[..., Any],
) -> None:
    """Replace an API stub with a real implementation.

    Version Added:
        6.0

    Args:
        obj (Resource):
            The resource object which owns the method.

        attr (str):
            The name of the method.

        stub (callable):
            The stub method.

        implementation (callable):
            The method implementation.
    """
    update_wrapper(implementation, stub)
    delattr(implementation, _STUB_ATTR_NAME)
    setattr(obj, attr, implementation)


def _preprocess_fields(
    fields: JSONDict,
) -> Iterator[tuple[str, Union[str, bytes]]]:
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

        if not isinstance(value, (str, bytes)):
            value = str(value)

        if name.startswith(_EXTRA_DATA_PREFIX):
            # It's technically not a problem to send both an extra_data.<key>
            # and a JSON Patch or Merge Patch in the same request, but in
            # the future we may want to warn about it, just to help guide
            # users toward a single implementation.
            key = name.removeprefix(_EXTRA_DATA_PREFIX)
            name = f'extra_data.{key}'

        yield name, value


def _create_resource_for_field(
    parent_resource: Resource,
    field_payload: JSONDict,
    mimetype: Optional[str],
    url: str,
) -> Resource:
    """Create a resource instance based on field data.

    This will construct a resource instance for the payload of a field,
    using the given mimetype to identify it. This is intended for use with
    expanded resources or items in lists.

    Version Changed:
        6.0:
        * Removed ``item_mimetype`` parameter.
        * Made ``url`` parameter required.

    Args:
        parent_resource (Resource):
            The resource containing the field payload.

        field_payload (dict):
            The field payload to use as the new resource's payload.

        mimetype (str):
            The mimetype of the resource.

        url (str, optional):
            The URL of the resource, if one is available.
    """
    # We need to import this here to avoid circular imports.
    from rbtools.api.factory import create_resource

    return create_resource(transport=parent_resource._transport,
                           payload=field_payload,
                           url=url,
                           mime_type=mimetype,
                           guess_token=False)


@request_method
def _create(
    resource: Resource,
    data: Optional[dict[str, Any]] = None,
    query_args: Optional[dict[str, QueryArgs]] = None,
    *args,
    **kwargs,
) -> HttpRequest:
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

    Raises:
        rbtools.api.errors.APIError:
            The Review Board API returned an error.

        rbtools.api.errors.ServerInterfaceError:
            An error occurred while communicating with the server.
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


@request_method
def _delete(
    resource: Resource,
    *args,
    **kwargs: QueryArgs,
) -> HttpRequest:
    """Generate a DELETE request on a resource.

    Argrs:
        resource (Resource):
            The resource instance owning this method.

        *args (tuple, unused):
            Unused positional arguments.

        **kwargs (dict):
            Additional query arguments to include with the request.

    Returns:
        rbtools.api.request.HttpRequest:
        The HTTP request.

    Raises:
        rbtools.api.errors.APIError:
            The Review Board API returned an error.

        rbtools.api.errors.ServerInterfaceError:
            An error occurred while communicating with the server.
    """
    return HttpRequest(resource._links['delete']['href'], method='DELETE',
                       query_args=kwargs)


@request_method
def _get_self(
    resource: Resource,
    *args,
    **kwargs: QueryArgs,
) -> HttpRequest:
    """Generate a request for a resource's 'self' link.

    Args:
        resource (Resource):
            The resource instance owning this method.

        *args (tuple, unused):
            Unused positional arguments.

        **kwargs (dict):
            Additional query arguments to include with the request.

    Returns:
        rbtools.api.request.HttpRequest:
        The HTTP request.

    Raises:
        rbtools.api.errors.APIError:
            The Review Board API returned an error.

        rbtools.api.errors.ServerInterfaceError:
            An error occurred while communicating with the server.
    """
    return HttpRequest(resource._links['self']['href'], query_args=kwargs)


@request_method
def _update(
    resource: Resource,
    data: Optional[dict[str, Any]] = None,
    query_args: Optional[dict[str, QueryArgs]] = None,
    *args,
    **kwargs,
) -> HttpRequest:
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
            Data to send in the PUT request. This will be merged with
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
        The resulting HTTP PUT request for this update operation.

    Raises:
        rbtools.api.errors.APIError:
            The Review Board API returned an error.

        rbtools.api.errors.ServerInterfaceError:
            An error occurred while communicating with the server.
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
SPECIAL_LINKS: Mapping[
    str,
    tuple[str, Optional[Callable[..., RequestMethodResult]]]
] = {
    'create': ('create', _create),
    'delete': ('delete', _delete),
    'next': ('get_next', None),
    'prev': ('get_prev', None),
    'self': ('get_self', _get_self),
    'update': ('update', _update),
}


class ResourceLink(TypedDict):
    """Type for a link within a payload.

    Version Added:
        6.0
    """

    #: The link URL.
    href: str

    #: The HTTP method to use for the link.
    method: str

    #: The MIME type of the object located at the link.
    mimetype: NotRequired[str]

    #: The user-visible title of the object located at the link.
    title: NotRequired[str]


#: Type for link data within the payload.
#:
#: Version Added:
#:     6.0
ResourceLinks = dict[str, ResourceLink]


class ExpandInfo(TypedDict):
    """Information on expanded resources.

    This corresponds to :py:class:`djblets.webapi.resources.base._ExpandInfo`.

    Version Added:
        6.0
    """

    #: The MIME type of an expanded item resource.
    item_mimetype: str

    #: The MIME type of an expanded list resource.
    list_mimetype: NotRequired[str]

    #: The URL to an expanded list resource, if any.
    list_url: NotRequired[Optional[str]]


class Resource:
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

    #: Attributes which should be excluded when processing the payload.
    #:
    #: Version Changed:
    #:     6.0:
    #:     Changed the type from a list to a set.
    _excluded_attrs: ClassVar[set[str]] = set()

    ######################
    # Instance variables #
    ######################

    #: Information about expanded fields in the payload.
    _expanded_info: dict[str, ExpandInfo]

    #: The links for the resource.
    _links: ResourceLinks

    #: The full resource payload.
    _payload: JSONDict

    #: The key within the request payload for the resource data.
    #:
    #: If this is ``None``, the payload contains the resource data directly.
    _token: Optional[str]

    #: The API transport.
    _transport: Transport

    #: The resource URL.
    _url: str

    def __init__(
        self,
        transport: Transport,
        payload: JSONDict,
        url: str,
        token: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Initialize the resource.

        Args:
            transport (rbtools.api.transport.Transport):
                The API transport.

            payload (dict):
                The request payload.

            url (str):
                The URL for the resource.

            token (str, optional):
                The key within the request payload for the resource data.

            **kwargs (dict, unused):
                Unused keyword arguments.
        """
        self._url = url
        self._transport = transport
        self._token = token
        self._payload = payload

        # Determine where the links live in the payload. This
        # can either be at the root, or inside the resources
        # token.
        if LINKS_TOK in self._payload:
            self._links = cast(ResourceLinks, self._payload[LINKS_TOK])
        elif (token and isinstance(self._payload[token], dict) and
              (token_payload := self._payload[token]) and
              isinstance(token_payload, dict) and
              LINKS_TOK in token_payload):
            self._links = cast(ResourceLinks, token_payload[LINKS_TOK])
        else:
            self._payload[LINKS_TOK] = {}
            self._links = {}

        # If we've expanded any fields, we'll try to convert the expanded
        # payloads into resources. We can only do this if talking to
        # Review Board 4.0+.
        if EXPANDED_TOKEN in self._payload:
            self._expanded_info = cast(
                dict[str, ExpandInfo],
                self._payload[EXPANDED_TOKEN])
        elif (token and
              (token_payload := self._payload[token]) and
              isinstance(token_payload, dict) and
              EXPANDED_TOKEN in token_payload):
            self._expanded_info = cast(
                dict[str, ExpandInfo],
                token_payload[EXPANDED_TOKEN])
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

        # Generate request methods for any additional links the resource has.
        for link, body in self._links.items():
            if link not in SPECIAL_LINKS:
                setattr(self,
                        f'get_{link}',
                        lambda resource=self, url=body['href'], **kwargs: (
                            self._get_url(url, **kwargs)))

    def _wrap_field(
        self,
        field_payload: Any,
        field_name: Optional[str] = None,
        field_url: Optional[str] = None,
        field_mimetype: Optional[str] = None,
        list_item_mimetype: Optional[str] = None,
        force_resource: bool = False,
    ) -> Any:
        """Wrap the value of a field in a resource or field object.

        This determines a suitable wrapper for a field, turning it into
        a resource or a wrapper with utility methods that can be used to
        interact with the field or perform additional queries.

        Args:
            field_payload (object):
                The payload of the field. The type of value determines the
                way in which this is wrapped.

            field_name (str, optional):
                The name of the field being wrapped, if known.

                Version Added:
                    3.1

            field_url (str, optional):
                The URL representing the payload in the field, if one is
                available. If not provided, one may be computed, depending
                on the type and contents of the field.

            field_mimetype (str, optional):
                The mimetype used to represent the field. If provided, this
                may result in the wrapper being a :py:class:`Resource`
                subclass.

            list_item_mimetype (str, optional):
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
                        field_url = \
                            cast(str, field_payload['links']['self']['href'])
                    except KeyError:
                        field_url = ''

                return _create_resource_for_field(parent_resource=self,
                                                  field_payload=field_payload,
                                                  mimetype=field_mimetype,
                                                  url=field_url)
            elif field_name == 'extra_data':
                # If this is an extra_data field, we'll return a special
                # ExtraDataField.
                return ResourceExtraDataField(resource=self,
                                              fields=field_payload)
            elif ('href' in field_payload and
                  not set(field_payload.keys()) - LINK_KEYS):
                # If the payload consists solely of link-supported keys,
                # then we'll return a special ResourceLinkField.
                return ResourceLinkField(resource=self,
                                         field_payload=field_payload)
            else:
                # Anything else is treated as a standard dictionary, which
                # will be wrapped.
                return ResourceDictField(resource=self,
                                         fields=field_payload)
        elif isinstance(field_payload, list):
            return ResourceListField(self, field_payload,
                                     item_mimetype=list_item_mimetype)
        else:
            return field_payload

    @property
    def links(self) -> ResourceDictField:
        """The resource's links.

        This is a special property which allows direct access to the links
        dictionary for a resource. Unlike other properties which come from the
        resource fields, this one is only accessible as a property, and not
        using array syntax.
        """
        return ResourceDictField(self, self._links)

    @request_method
    def _get_url(
        self,
        url: str,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Make a GET request to a given URL.

        Args:
            url (str):
                The URL to fetch.

            **kwargs (dict):
                Additional query arguments to include with the request.

        Returns:
            rbtools.api.request.HttpRequest:
            The HTTP request.
        """
        return HttpRequest(url, query_args=kwargs)

    @property
    def rsp(self) -> JSONDict:
        """Return the response payload used to create the resource.

        Returns:
            dict:
            The response payload.
        """
        return self._payload


_TResourceClass = TypeVar('_TResourceClass', bound=type[Resource])


def resource_mimetype(
    mimetype: str,
) -> Callable[[_TResourceClass], _TResourceClass]:
    """Set the mimetype for the decorated class in the resource map.

    Args:
        mimetype (str):
            The MIME type for the resource.

    Returns:
        callable:
        A decorator to apply to a resource class.
    """
    def wrapper(cls: _TResourceClass) -> _TResourceClass:
        RESOURCE_MAP[mimetype] = cls
        return cls

    return wrapper


#: The resulting type of a resource method.
#:
#: Version Added:
#:     6.0
RequestMethodResult = Union[HttpRequest, Resource, None]


class ResourceDictField(MutableMapping[str, Any]):
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

    ######################
    # Instance variables #
    ######################

    #: The wrapped fields dictionary.
    _fields: dict[str, Any]

    #: The resource which owns this field.
    _resource: Resource

    def __init__(
        self,
        resource: Resource,
        fields: dict[str, Any],
    ) -> None:
        """Initialize the field.

        Args:
            resource (Resource):
                The parent resource that owns this field.

            fields (dict):
                The dictionary contents from the payload.
        """
        super().__init__()

        self._resource = resource
        self._fields = fields

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        """Return the value of a key from the field as an attribute reference.

        The resulting value will be wrapped as a resource or resource field
        if appropriate.

        Args:
            name (str):
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
            raise AttributeError(
                f'This dictionary resource for '
                f'{self._resource.__class__.__name__} does not have an '
                f'attribute "{name}".')

    def __getitem__(
        self,
        name: str,
    ) -> Any:
        """Return the value of a key from the field as an item lookup.

        The resulting value will be wrapped as a resource or resource field
        if appropriate.

        Args:
            name (str):
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
            raise KeyError(
                f'This dictionary resource for '
                f'{self._resource.__class__.__name__} does not have a key '
                f'"{name}".')

    def __delitem__(
        self,
        name: str,
    ) -> None:
        """Delete an item from the dictionary.

        This will raise an exception stating that changes are not allowed
        and offering an alternative.

        Args:
            name (str, unused):
                The name of the key to delete.

        Raises:
            AttributeError:
                An error stating that changes are not allowed.
        """
        self._raise_immutable()

    def __setitem__(
        self,
        name: str,
        value: Any,
    ) -> None:
        """Set an item in the dictionary.

        This will raise an exception stating that changes are not allowed
        and offering an alternative.

        Args:
            name (str, unused):
                The name of the key to set.

            value (object, unused):
                The value to set.

        Raises:
            AttributeError:
                An error stating that changes are not allowed.
        """
        self._raise_immutable()

    def __len__(self) -> int:
        """Return the number of items in the dictionary.

        Returns:
            int:
            The number of items.
        """
        return len(self._fields)

    def __iter__(self) -> Iterator[Any]:
        """Iterate through the dictionary.

        Yields:
            object:
            Each item in the dictionary.
        """
        yield from self._fields.keys()

    def __repr__(self) -> str:
        """Return a string representation of the dictionary field.

        Returns:
            str:
            The string representation.
        """
        return (f'{self.__class__.__name__}(resource={self._resource!r}, '
                f'fields={self._fields!r})')

    def fields(self) -> Iterator[str]:
        """Iterate through all fields in the dictionary.

        This will yield each field name in the dictionary. This is the same
        as calling :py:meth:`keys` or simply ``for field in dict_field``.

        Yields:
            str:
            Each field in this dictionary.
        """
        yield from self

    def _wrap_field(
        self,
        field_name: str,
    ) -> Any:
        """Conditionally return a wrapped version of a field's value.

        This will wrap content according to the resource's wrapping logic.

        Args:
            field_name (str):
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

    def _raise_immutable(self) -> NoReturn:
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

    ######################
    # Instance variables #
    ######################

    #: The API transport.
    _transport: Transport

    def __init__(
        self,
        resource: Resource,
        field_payload: JSONDict,
    ) -> None:
        """Initialize the resource.

        Args:
            resource (Resource):
                The resource which owns this field.

            field_payload (dict):
                The field content.
        """
        super().__init__(resource, field_payload)
        self._transport = resource._transport

    @request_method
    def get(
        self,
        **query_args: QueryArgs,
    ) -> HttpRequest:
        """Fetch the link.

        Args:
            **query_args (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.request.HttpRequest:
            The HTTP request.
        """
        return HttpRequest(self._fields['href'], query_args=query_args)


class ResourceExtraDataField(ResourceDictField):
    """Wrapper for extra_data fields on resources.

    Version Added:
        3.1
    """

    def copy(self) -> dict[str, Any]:
        """Return a copy of the dictionary's fields.

        A copy of the original ``extra_data`` content will be returned,
        without any field wrapping.

        Returns:
            dict:
            The copy of the dictionary.
        """
        return copy.deepcopy(self._fields)

    def _wrap_field(
        self,
        field_name: str,
    ) -> Union[JSONValue, ResourceExtraDataField]:
        """Conditionally return a wrapped version of a field's value.

        This will wrap dictionaries in another
        :py:class:`ResourceExtraDataField`, and otherwise leave everything
        else unwrapped (preventing list-like or links-like payloads from
        being wrapped in their respective field types).

        Args:
            field_name (str):
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

    def _raise_immutable(self) -> NoReturn:
        """Raise an exception stating that the dictionary is immutable.

        Raises:
            AttributeError:
                An error stating that changes are not allowed.
        """
        raise AttributeError(
            f'extra_data attributes cannot be modified directly on this '
            f'dictionary. To make a mutable copy of this and all its '
            f'contents, call .copy(). To set or change extra_data state, '
            f'issue a .update(extra_data_json={{...}}) for a JSON Merge '
            f'Patch request or .update(extra_data_json_patch=[...]) for a '
            f'JSON Patch request on the parent resource. See '
            f'{_EXTRA_DATA_DOCS_URL} for the format for these operations.')


class ResourceListField(list[Any]):
    """Wrapper for lists returned from a resource.

    Acts as a normal list, but wraps any returned items.
    """

    ######################
    # Instance variables #
    ######################

    #: The resource which owns the field.
    _resource: Resource

    #: The MIME type of items in the list.
    _item_mimetype: Optional[str]

    def __init__(
        self,
        resource: Resource,
        list_field: list[Any],
        item_mimetype: Optional[str] = None,
    ) -> None:
        """Initialize the field.

        Args:
            resource (Resource):
                The resource which owns this field.

            list_field (list):
                The list contents.

            item_mimetype (str, optional):
                The mimetype of the list items.
        """
        super().__init__(list_field)

        self._resource = resource
        self._item_mimetype = item_mimetype

    def __getitem__(
        self,
        key: int,
    ) -> Any:
        """Return the item at the given index.

        Args:
            key (int):
                The index to fetch.

        Returns:
            object:
            The item at the given index.
        """
        item = super().__getitem__(key)

        return self._resource._wrap_field(item,
                                          field_mimetype=self._item_mimetype)

    def __iter__(self) -> Iterator[Any]:
        """Iterate through the list.

        Yields:
            object:
            Each item in the list.
        """
        for item in super().__iter__():
            yield self._resource._wrap_field(
                item,
                field_mimetype=self._item_mimetype)

    def __repr__(self) -> str:
        """Return a string representation of the field.

        Returns:
            str:
            A string representation of the field.
        """
        return (f'{self.__class__.__name__}(resource={self._resource}, '
                f'item_mimetype={self._item_mimetype}, '
                f'list_field={super().__repr__()})')


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

    ######################
    # Instance variables #
    ######################

    #: The fields payload data.
    _fields: JSONDict

    def __init__(
        self,
        transport: Transport,
        payload: JSONDict,
        url: str,
        token: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Initialize the resource.

        Args:
            transport (rbtools.api.transport.Transport):
                The API transport.

            payload (dict):
                The resource payload.

            url (str):
                The resource URL.

            token (str, optional):
                The key within the request payload for the resource data.

            **kwargs (dict, unused):
                Unused keyword arguments.
        """
        super().__init__(transport, payload, url, token=token, **kwargs)
        self._fields = {}

        # Determine the body of the resource's data.
        if token is not None:
            data = cast(JSONDict, self._payload[token])
        else:
            data = self._payload

        excluded_attrs = self._excluded_attrs | _EXCLUDE_ATTRS

        for name, value in data.items():
            if name not in excluded_attrs:
                self._fields[name] = value

    def __getattr__(
        self,
        name: str,
    ) -> Any:
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
            raise AttributeError(
                f'This {self.__class__.__name__} does not have an attribute '
                f'"{name}".')

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

    def __getitem__(
        self,
        key: str,
    ) -> Any:
        """Return the value for an attribute on the resource.

        If the attribute represents an expanded resource, and there's
        information available on the expansion (available in Review Board
        4.0+), then a resource instance will be returned.

        If the attribute otherwise represents a dictionary, list, or a link,
        a wrapper may be returned.

        Args:
            key (str):
                The name of the attribute.

        Returns:
            object:
            The attribute value, or a wrapper or resource representing that
            value.

        Raises:
            KeyError:
                A field with the given attribute name was not found.
        """
        try:
            return self.__getattr__(key)
        except AttributeError:
            raise KeyError

    def __contains__(
        self,
        key: str,
    ) -> bool:
        """Return whether the resource has a field with the given name.

        Args:
            key (str):
                The name of the field.

        Returns:
            bool:
            Whether a field with the given name exists.
        """
        return key in self._fields

    def iterfields(self) -> Iterator[str]:
        """Iterate through all field names in the resource.

        Yields:
            str:
            The name of each field name.
        """
        yield from self._fields

    def iteritems(self) -> Iterator[tuple[str, Any]]:
        """Iterate through all field/value pairs in the resource.

        Yields:
            tuple:
            A tuple in ``(field_name, value)`` form.
        """
        for key in self.iterfields():
            yield key, self.__getattr__(key)

    def __repr__(self) -> str:
        """Return a string representation of the resource.

        Returns:
            str:
            A string representation of the resource.
        """
        return (f'{self.__class__.__name__}(transport={self._transport}, '
                f'payload={self._payload}, url={self._url}, '
                f'token={self._token})')


class CountResource(ItemResource):
    """Resource returned by a query with 'counts-only' true.

    When a resource is requested using 'counts-only', the payload will
    not contain the regular fields for the resource. In order to
    special case all payloads of this form, this class is used for
    resource construction.
    """

    def __init__(
        self,
        transport: Transport,
        payload: JSONDict,
        url: str,
        **kwargs,
    ) -> None:
        """Initialize the resource.

        Args:
            transport (rbtools.api.transport.Transport):
                The API transport.

            payload (dict):
                The response payload.

            url (str):
                The URL for the resource.

            **kwargs (dict, unused):
                Unused keyword arguments.
        """
        super().__init__(transport, payload, url, token=None)

    @request_method
    def get_self(
        self,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Generate an GET request for the resource list.

        This will return an HttpRequest to retrieve the list resource
        which this resource is a count for. Any query arguments used
        in the request for the count will still be present, only the
        'counts-only' argument will be removed

        Args:
            **kwargs (dict):
                Query arguments to include with the request.
        """
        # TODO: Fix this. It is generating a new request for a URL with
        # 'counts-only' set to False, but RB treats the  argument being set
        # to any value as true.
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

    #: The number of items in the current page.
    #:
    #: Type:
    #:     int
    num_items: int

    #: The total number of results in the list across all pages.
    #:
    #: This is commonly set for most list resources, but is not always
    #: guaranteed to be available. Callers should check to make sure this is
    #: not ``None``.
    #:
    #: Type:
    #:     int
    total_results: Optional[int]

    #: The raw items in the list payload.
    _item_list: list[JSONValue]

    #: The MIME type of items in the list.
    _item_mime_type: Optional[str]

    def __init__(
        self,
        transport: Transport,
        payload: JSONDict,
        url: str,
        token: Optional[str] = None,
        item_mime_type: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Initialize the resource.

        Args:
            transport (rbtools.api.transport.Transport):
                The API transport.

            payload (dict or list):
                The payload data.

            url (str):
                The URL for the resource.

            token (str, optional):
                The key within the request payload for the resource data.

            item_mime_type (str, optional):
                The mimetype of the items within the list.

            **kwargs (dict):
                Keyword arguments to pass through to the base class.
        """
        super().__init__(transport, payload, url, token=token, **kwargs)
        self._item_mime_type = item_mime_type

        # The token must always be present for list resources.
        assert token is not None

        self._item_list = cast(list[JSONValue], payload[token])

        self.num_items = len(self._item_list)
        self.total_results = cast(int, payload.get('total_results'))

    def __len__(self) -> int:
        """Return the length of the list.

        Returns:
            int:
            The number of items in the list.
        """
        return self.num_items

    def __nonzero__(self) -> bool:
        """Return whether the list is non-zero.

        Returns:
            bool:
            ``True``, always.
        """
        return self.__bool__()

    def __bool__(self) -> bool:
        """Return whether the list is truthy.

        Returns:
            bool:
            ``True``, always.
        """
        return True

    def __getitem__(
        self,
        index: int,
    ) -> Any:
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

    def __iter__(self) -> Iterator[Any]:
        """Iterate through the items.

        Yields:
            object:
            Each item in the list.
        """
        for i in range(self.num_items):
            yield self[i]

    @request_method
    def get_next(
        self,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Return the next page of results.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.request.HttpRequest):
            The HTTP request.

        Raises:
            StopIteration:
                There are no more pages of results.
        """
        if 'next' not in self._links:
            raise StopIteration()

        return HttpRequest(self._links['next']['href'], query_args=kwargs)

    @request_method
    def get_prev(
        self,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Return the previous page of results.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.request.HttpRequest):
            The HTTP request.

        Raises:
            StopIteration:
                There are no previous pages of results.
        """
        if 'prev' not in self._links:
            raise StopIteration()

        return HttpRequest(self._links['prev']['href'], query_args=kwargs)

    @request_method
    def get_item(
        self,
        pk: int,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Retrieve the item resource with the corresponding primary key.

        Args:
            pk (int):
                The primary key of the item to fetch.

            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.request.HttpRequest:
            The HTTP request.
        """
        return HttpRequest(urljoin(self._url, f'{pk}/'),
                           query_args=kwargs)

    @property
    def all_pages(self) -> Iterator[Self]:
        """Yield all pages of item resources.

        Each page of resources is itself an instance of the same
        ``ListResource`` class.
        """
        page = self

        while True:
            yield page

            try:
                page = cast(Self, page.get_next())
            except StopIteration:
                break

    @property
    def all_items(self) -> Iterator[Any]:
        """Yield all item resources in all pages of this resource.

        Yields:
            Any:
            All items in the list.
        """
        for page in self.all_pages:
            yield from page

    def __repr__(self) -> str:
        """Return a string representation of the resource.

        """
        return (f'{self.__class__.__name__}(transport={self._transport}, '
                f'payload={self._payload}, url={self._url}, '
                f'token={self._token}, item_mime_type={self._item_mime_type})')
