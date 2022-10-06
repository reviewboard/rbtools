"""Registry of available diff tools.

Version Added:
    4.0
"""

import logging
from typing import Dict, Iterable, Iterator, List, Optional, Type

from rbtools.diffs.tools.backends.apple import AppleDiffTool
from rbtools.diffs.tools.backends.gnu import GNUDiffTool
from rbtools.diffs.tools.base import BaseDiffTool
from rbtools.diffs.tools.errors import MissingDiffToolError


logger = logging.getLogger(__name__)


class DiffToolsRegistry:
    """A registry managing known and available diff tools.

    This provides functionality for querying and registering diff tools classes
    and instances.

    As a single diff tool instance can be used for multiple operations, the
    registry will cache any created instances and return them the next time
    they're needed, instead of creating a new instance every time. This avoids
    the up-front cost of checking for tool availability more than once.

    The registry provides a built-in list of supported tools. For future
    extensibility, additional tools can be registered as well.

    Version Added:
        4.0
    """

    ######################
    # Instance variables #
    ######################

    #: A mapping of diff tool IDs to classes.
    #:
    #: Type:
    #:     dict
    _diff_tool_classes: Dict[str, Type[BaseDiffTool]]

    #: A list of all diff tool instances.
    #:
    #: Type:
    #:     list
    _diff_tools: List[BaseDiffTool]

    #: Whether the list of default classes have been populated.
    #:
    #: Type:
    #:     bool
    _classes_populated: bool

    #: Whether the list of instances have been populated.
    #:
    #: Type:
    #:     bool
    _instances_populated: bool

    def __init__(self):
        """Initialize the registry."""
        self._diff_tools = []
        self._diff_tool_classes = {}
        self._classes_populated = False
        self._instances_populated = False

    def iter_diff_tool_classes(self) -> Iterator[Type[BaseDiffTool]]:
        """Iterate through all registered diff tool classes.

        This does not guarantee order.

        Yields:
            type:
            Each registered subclass of
            :py:class:`~rbtools.diffs.tools.base.diff_tool.BaseDiffTool`.
        """
        self._populate_classes()

        yield from self._diff_tool_classes.values()

    def get_diff_tool_class(
        self,
        diff_tool_id: str,
    ) -> Optional[Type[BaseDiffTool]]:
        """Return a diff tool class with the given ID.

        If the ID could not be found, this will return ``None``.

        Args:
            diff_tool_id (str):
                The ID of the diff tool to return.

        Returns:
            type:
            The diff tool class, or ``None`` if not found.
        """
        self._populate_classes()

        return self._diff_tool_classes.get(diff_tool_id)

    def get_available(
        self,
        compatible_diff_tool_ids: Optional[Iterable[str]] = None,
    ) -> BaseDiffTool:
        """Return an available diff tool out of an optional set of IDs.

        This will attempt to find an available diff tool that, optionally
        restricting results to a set of compatible diff tool IDs.

        The instance is cached for future lookups.

        Args:
            compatible_diff_tool_ids (set, optional):
                An optional set of compatible diff tool IDs.

        Returns:
            rbtools.diffs.tools.base.diff_tool.BaseDiffTool:
            The available diff tool instance.

        Raises:
            rbtools.diffs.tools.errors.MissingDiffToolError:
                A compatible diff tool could not be found.
        """
        self._populate_instances()

        diff_tools = self._diff_tools

        if diff_tools:
            if compatible_diff_tool_ids is None:
                return diff_tools[0]

            if not isinstance(compatible_diff_tool_ids, set):
                compatible_diff_tool_ids = set(compatible_diff_tool_ids)

            for diff_tool in diff_tools:
                if diff_tool.diff_tool_id in compatible_diff_tool_ids:
                    return diff_tool

        raise MissingDiffToolError(
            registry=self,
            compatible_diff_tool_ids=compatible_diff_tool_ids)

    def register(
        self,
        diff_tool_cls: Type[BaseDiffTool],
    ) -> None:
        """Register a diff tool class.

        To be usable, a tool must be registered before any operations are
        performed that return an instantiated tool.

        Args:
            diff_tool_cls (type):
                The diff tool class to register.
        """
        self._populate_classes()

        self._register(diff_tool_cls)

    def reset(self) -> None:
        """Reset the registry to an empty state.

        This is primarily intended for unit testing, to ensure that any
        new attempts to fetch tools will result in fresh instances.
        """
        self._classes_populated = False
        self._instances_populated = False
        self._diff_tool_classes = {}
        self._diff_tools = []

    def _populate_classes(self) -> None:
        """Populate all the default diff tool classes.

        Any errors encountered will be logged.
        """
        if self._classes_populated:
            return

        for diff_tool_cls in self._get_defaults():
            try:
                self._register(diff_tool_cls)
            except ValueError as e:
                logger.error(e)

        self._classes_populated = True

    def _populate_instances(self) -> None:
        """Populate all available diff tool instances.

        This will attempt to instantiate and set up each diff tool, checking
        for availability. Only available diff tools will be in the final
        results.
        """
        if self._instances_populated:
            return

        self._populate_classes()

        logger.debug('[diff tool scan] Scanning for installed diff tools...')

        diff_tools: List[BaseDiffTool] = []

        for diff_tool_cls in self.iter_diff_tool_classes():
            diff_tool = diff_tool_cls()

            try:
                diff_tool.setup()
            except Exception as e:
                logger.exception('Unexpected error setting up and '
                                 'checking for diff tool "%s": %s',
                                 diff_tool_cls.diff_tool_id, e)
                continue

            if diff_tool.available:
                logger.debug('[diff tool scan] Found %s (%s)',
                             diff_tool.name,
                             diff_tool.version_info)
                diff_tools.append(diff_tool)

        if not diff_tools:
            # Log this as a debug. It may be fine not to have a diff tool
            # at this stage. Explicit error handling will be left to when
            # we fetch or check for a diff tool.
            logger.debug('[diff tool scan] No diff tools found (tried %r)',
                         list(self.iter_diff_tool_classes()))

        self._diff_tools = diff_tools
        self._instances_populated = True

        logger.debug('[diff tool scan] Scan complete.')

    def _get_defaults(self) -> List[Type[BaseDiffTool]]:
        """Return the default list of diff tool classes.

        Returns:
            list of type:
            The list of diff tool classes.
        """
        # These are in the order most likely to be encountered across supported
        # systems.
        return [
            GNUDiffTool,
            AppleDiffTool,
        ]

    def _register(
        self,
        diff_tool_cls: Type[BaseDiffTool],
    ) -> None:
        """Internal method to register a diff tool class.

        This takes care of registering without triggering a population of
        default tools.

        Args:
            diff_tool_cls (type):
                The diff tool class to register.
        """
        diff_tool_id = diff_tool_cls.diff_tool_id

        if not diff_tool_id:
            raise ValueError('%s.diff_tool_id must be set.'
                             % diff_tool_cls.__name__)

        if diff_tool_id in self._diff_tool_classes:
            raise ValueError(
                'Another diff tool with ID "%s" (%r) is already registered.'
                % (diff_tool_id,
                   self._diff_tool_classes[diff_tool_id]))

        self._diff_tool_classes[diff_tool_id] = diff_tool_cls


#: The main diff tools registry.
#:
#: Version Added:
#:     4.0
#:
#: Type:
#:     DiffToolsRegistry
diff_tools_registry = DiffToolsRegistry()
