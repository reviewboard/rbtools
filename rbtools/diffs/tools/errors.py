"""Errors for working with diff tools.

Version Added:
    4.0
"""

from typing import Iterable, List, Optional, cast


class MissingDiffToolError(Exception):
    """Error indicating a compatible diff tool is missing.

    The error message contains all the compatible tools that were checked,
    along with any relevant installation instructions for those tools.

    Version Added:
        4.0
    """

    #: A list of compatible diff tool IDs that could not be found.
    #:
    #: Type:
    #:     list of str
    compatible_diff_tool_ids: List[str]

    #: A list of compatible diff tool names that could not be found.
    #:
    #: Type:
    #:     list of str
    compatible_diff_tool_names: List[str]

    def __init__(
        self,
        registry,
        compatible_diff_tool_ids: Optional[Iterable[str]] = None,
    ) -> None:
        """Initialize the error.

        Args:
            registry (rbtools.diffs.tools.registry.DiffToolsRegistry):
                The registry that threw this error.

            compatible_diff_tool_ids (list or set, optional):
                The compatible diff tool IDs that were checked.
        """
        if not compatible_diff_tool_ids:
            compatible_diff_tool_ids = sorted(
                _diff_tool_cls.diff_tool_id
                for _diff_tool_cls in registry.iter_diff_tool_classes()
            )

        compatible_diff_tool_names: List[str] = []
        instructions: List[str] = []

        for diff_tool_id in compatible_diff_tool_ids:
            diff_tool_cls = registry.get_diff_tool_class(diff_tool_id)

            if diff_tool_cls is not None:
                compatible_diff_tool_names.append(diff_tool_cls.name)
                diff_tool_instructions = \
                    diff_tool_cls.get_install_instructions()

                if diff_tool_instructions:
                    instructions.append(diff_tool_instructions)
            else:
                compatible_diff_tool_names.append(diff_tool_id)

        self.compatible_diff_tool_ids = \
            cast(List[str], compatible_diff_tool_ids)
        self.compatible_diff_tool_names = compatible_diff_tool_names

        message = [
            'A compatible command line diff tool (%s) was not found on the '
            'system. This is required in order to generate diffs, and will '
            'need to be installed and placed in your system path.'
            % ', '.join(compatible_diff_tool_names),
        ]
        message += instructions
        message.append(
            "If you're running an older version of RBTools, you may also "
            "need to upgrade.",
        )

        super(MissingDiffToolError, self).__init__('\n\n'.join(message))
