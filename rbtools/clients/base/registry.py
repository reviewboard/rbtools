"""Registry of available SCMClients.

Version Added:
    4.0
"""

from __future__ import annotations

import importlib
import logging
import sys
from collections import OrderedDict
from typing import Iterator, Type

if sys.version_info[:2] >= (3, 10):
    # Python >= 3.10
    from importlib.metadata import entry_points
else:
    # Python <= 3.9
    from importlib_metadata import entry_points

from rbtools.clients.base.scmclient import BaseSCMClient
from rbtools.clients.errors import SCMClientNotFoundError
from rbtools.deprecation import RemovedInRBTools50Warning


logger = logging.getLogger(__name__)


class SCMClientRegistry:
    """A registry for looking up and fetching available SCMClients.

    This keeps track of all available
    :py:class:`~rbtools.clients.base.scmclient.BaseSCMClient` subclasses
    available to RBTools. It supplies a built-in list of clients shipped with
    RBTools and ones provided by Python packages supplying a
    ``rbtools_scm_clients`` entry point group.

    Built-in SCMClients and ones in entry points are only loaded once per
    registry, and only if needed based on the operations performed. Listing
    will always ensure both sets of SCMClients are loaded.

    Legacy SCMClients provided by entry points will be assigned a
    :py:attr:`scmclient_id
    <rbtools.clients.base.scmclient.BaseSCMClient.scmclient_id>` based on the
    entry point name, if one is not already assigned, and will emit a warning.
    Starting in RBTools 5.0, custom SCMClients will need to explicitly set an
    ID.

    Version Added:
        4.0
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._scmclient_classes: OrderedDict[str, Type[BaseSCMClient]] = \
            OrderedDict()
        self._builtin_loaded = False
        self._entrypoints_loaded = False

    def __contains__(
        self,
        scmclient: str | Type[BaseSCMClient],
    ) -> bool:
        """Return whether a SCMClient type or ID is in the registry.

        Args:
            scmclient (str or type):
                The SCMClient ID or class type to check for.

        Returns:
            bool:
            ``True`` if the registry contains this client. ``False`` if it
            does not.

        Raises:
            TypeError:
                ``scmclient`` is not an ID or a SCMClient class.
        """
        if isinstance(scmclient, str):
            scmclient_id = scmclient
        else:
            try:
                scmclient_id = scmclient.scmclient_id
            except AttributeError:
                raise TypeError('%r is not a SCMClient ID or subclass.'
                                % scmclient)

        try:
            self.get(scmclient_id)

            return True
        except SCMClientNotFoundError:
            return False

    def __iter__(self) -> Iterator[Type[BaseSCMClient]]:
        """Iterate through all registered SCMClient classes.

        This will yield each built-in SCMClient, followed by each one provided
        by an entrypoint.

        This will force both sets of SCMClients to load, if not already loaded.

        Yields:
            type:
            A registered :py:class:`~rbtools.clients.base.scmclient
            .BaseSCMClient` subclass.
        """
        if not self._builtin_loaded:
            self._populate_builtin()

        if not self._entrypoints_loaded:
            self._populate_entrypoints()

        yield from self._scmclient_classes.values()

    def get(
        self,
        scmclient_id: str,
    ) -> Type[BaseSCMClient]:
        """Return a SCMClient class with the given ID.

        This will first check the built-in list of SCMClients. If not found,
        entry points will be loaded (if not already loaded), and the ID will
        be looked up amongst that set.

        Args:
            scmclient_id (str):
                The ID of the SCMClient.

        Returns:
            type:
            The registered :py:class:`~rbtools.clients.base.scmclient
            .BaseSCMClient` subclass for the given ID.

        Raises:
            rbtools.clients.errors.SCMClientNotFoundError:
                A client matching the ID could not be found.
        """
        if not self._builtin_loaded:
            self._populate_builtin()

        try:
            scmclient_cls = self._scmclient_classes[scmclient_id]
        except KeyError:
            scmclient_cls = None

            if not self._entrypoints_loaded:
                self._populate_entrypoints()

                try:
                    scmclient_cls = self._scmclient_classes[scmclient_id]
                except KeyError:
                    pass

        if scmclient_cls is None:
            raise SCMClientNotFoundError(scmclient_id)

        return scmclient_cls

    def register(
            self,
            scmclient_cls: Type[BaseSCMClient],
    ) -> None:
        """Register a SCMClient class.

        The class must have :py:attr:`scmclient_id
        <rbtools.clients.base.scmclient.BaseSCMClient.scmclient_id>` set, and
        it must be unique.

        Args:
            scmclient_cls (type):
                The class to register.

        Raises:
            ValueError:
                The SCMClient ID is unset or not unique.
        """
        if not self._builtin_loaded:
            self._populate_builtin()

        scmclient_id = getattr(scmclient_cls, 'scmclient_id', None)

        if not scmclient_id:
            raise ValueError(
                '%s.%s.scmclient_id must be set, and must be a unique value.'
                % (scmclient_cls.__module__,
                   scmclient_cls.__name__))

        existing_cls = self._scmclient_classes.get(scmclient_id)

        if existing_cls is not None:
            if existing_cls is scmclient_cls:
                raise ValueError('%s.%s is already registered.'
                                 % (scmclient_cls.__module__,
                                    scmclient_cls.__name__))
            else:
                raise ValueError(
                    'A SCMClient with an ID of "%s" is already registered: '
                    '%s.%s'
                    % (scmclient_id,
                       existing_cls.__module__,
                       existing_cls.__name__))

        self._scmclient_classes[scmclient_id] = scmclient_cls

    def _populate_builtin(self) -> None:
        """Populate the list of built-in SCMClient classes."""
        assert not self._builtin_loaded

        # Set this early, to avoid recursing when we call register().
        self._builtin_loaded = True

        builtin_scmclient_paths = (
            ('rbtools.clients.bazaar', 'BazaarClient'),
            ('rbtools.clients.clearcase', 'ClearCaseClient'),
            ('rbtools.clients.cvs', 'CVSClient'),
            ('rbtools.clients.git', 'GitClient'),
            ('rbtools.clients.mercurial', 'MercurialClient'),
            ('rbtools.clients.perforce', 'PerforceClient'),
            ('rbtools.clients.plastic', 'PlasticClient'),
            ('rbtools.clients.sos', 'SOSClient'),
            ('rbtools.clients.svn', 'SVNClient'),
            ('rbtools.clients.tfs', 'TFSClient'),
        )

        for mod_name, cls_name in builtin_scmclient_paths:
            try:
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, cls_name)

                self.register(cls)
            except Exception as e:
                logger.exception('Unexpected error looking up built-in '
                                 'SCMClient %s.%s: %s',
                                 mod_name, cls_name, e)

    def _populate_entrypoints(self) -> None:
        """Populate the list of entry point SCMClient classes."""
        assert not self._entrypoints_loaded

        self._entrypoints_loaded = True

        for ep in entry_points(group='rbtools_scm_clients'):
            try:
                cls = ep.load()

                if not getattr(cls, 'scmclient_id', None):
                    RemovedInRBTools50Warning.warn(
                        '%s.scmclient_id must be set, and must be a unique '
                        'value. You probably want to set it to "%s".'
                        % (cls.__name__, ep.name))

                    cls.scmclient_id = ep.name

                self.register(cls)
            except Exception as e:
                logger.exception('Unexpected error loading non-default '
                                 'SCMClient provided by Python entrypoint '
                                 '%r: %s',
                                 ep, e)


#: The main SCMClients registry used by RBTools.
#:
#: Version Added:
#:     4.0
scmclient_registry = SCMClientRegistry()
