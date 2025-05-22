"""Resource definitions for extensions.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    ListResource,
    resource_mimetype,
)

if TYPE_CHECKING:
    from typing import ClassVar


@resource_mimetype('application/vnd.reviewboard.org.extension')
class ExtensionItemResource(ItemResource):
    """Item resource for extensions.

    This corresponds to Review Board's :ref:`rb:webapi2.0-extension-resource`.

    Version Added:
        6.0
    """

    _excluded_links: ClassVar[set[str]] = {
        'admin_configure',
        'admin_database',
    }

    ######################
    # Instance variables #
    ######################

    #: The author of the extension
    author: str | None

    #: The author's website.
    author_url: str | None

    #: Whether or not the extension can be disabled.
    can_disable: bool

    #: Whether or not the extension can be enabled.
    can_enable: bool

    #: The class name for the extension.
    class_name: str

    #: Whether or not the extension is enabled.
    enabled: bool

    #: Whether or not the extension is installed.
    installed: bool

    #: Any errors captured while attempting to load the extension.
    load_error: str | None

    #: Whether or not the extension is currently loadable.
    #:
    #: An extension may be installed but missing, or may be broken due to a
    #: bug.
    loadable: bool

    #: The name of the extension
    name: str

    #: A summary of the extension's functionality.
    summary: str | None

    #: The installed version of the extension.
    version: str


@resource_mimetype('application/vnd.reviewboard.org.extensions')
class ExtensionListResource(ListResource[ExtensionItemResource]):
    """List resource for extensions.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-extension-list-resource`.

    Version Added:
        6.0
    """
