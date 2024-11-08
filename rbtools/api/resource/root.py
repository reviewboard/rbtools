"""Resource definitions for the API root.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

import re
from typing import ClassVar, Optional, TYPE_CHECKING, cast

from packaging.version import parse as parse_version
from typelets.json import JSONDict

from rbtools.api.cache import MINIMUM_VERSION
from rbtools.api.request import HttpRequest
from rbtools.api.resource.base import (
    ItemResource,
    ResourceDictField,
    request_method,
    resource_mimetype,
)

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs
    from rbtools.api.transport import Transport


@resource_mimetype('application/vnd.reviewboard.org.root')
class RootResource(ItemResource):
    """The Root resource specific base class.

    Provides additional methods for fetching any resource directly
    using the uri templates. A method of the form "get_<uri-template-name>"
    is called to retrieve the HttpRequest corresponding to the
    resource. Template replacement values should be passed in as a
    dictionary to the values parameter.
    """

    #: Capabilities for the Review Board server.
    capabilities: ResourceDictField

    _excluded_attrs: ClassVar[set[str]] = {'uri_templates'}
    _TEMPLATE_PARAM_RE = re.compile(r'\{(?P<key>[A-Za-z_0-9]*)\}')

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
                The resource payload.

            url (str):
                The resource URL.

            **kwargs (dict, unused):
                Unused keyword arguments.
        """
        super().__init__(transport, payload, url, token=None)

        # Generate methods for accessing resources directly using
        # the uri-templates.
        for name, url in payload['uri_templates'].items():
            attr_name = f'get_{name}'

            if not hasattr(self, attr_name):
                setattr(self,
                        attr_name,
                        lambda resource=self, url=url, **kwargs: (
                            self._get_template_request(url, **kwargs)))

        product = cast(JSONDict, payload.get('product', {}))
        server_version = cast(Optional[str], product.get('package_version'))

        if (server_version is None or
            parse_version(server_version) < parse_version(MINIMUM_VERSION)):
            # This version is too old to safely support caching (there were
            # bugs before this version). Disable caching.
            transport.disable_cache()

    @request_method
    def _get_template_request(
        self,
        url_template: str,
        values: Optional[dict[str, str]] = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Generate an HttpRequest from a uri-template.

        This will replace each '{variable}' in the template with the
        value from kwargs['variable'], or if it does not exist, the
        value from values['variable']. The resulting url is used to
        create an HttpRequest.

        Args:
            url_template (str):
                The URL template.

            values (dict, optional):
                The values to use for replacing template variables.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.Resource:
            The resource at the given URL.
        """
        if values is None:
            values = {}

        def get_template_value(
            m: re.Match[str],
        ) -> str:
            key = m.group('key')

            try:
                return str(kwargs.pop(key, None) or values[key])
            except KeyError:
                raise ValueError(
                    f'Template was not provided a value for "{key}"')

        url = self._TEMPLATE_PARAM_RE.sub(get_template_value, url_template)
        return HttpRequest(url, query_args=kwargs)
