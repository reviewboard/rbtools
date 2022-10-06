"""Unit tests for rbtools.diffs.tools.registry.DiffToolsRegistry.

Version Added:
    4.0
"""

import inspect

import kgb

from rbtools.diffs.tools.backends.apple import AppleDiffTool
from rbtools.diffs.tools.backends.gnu import GNUDiffTool
from rbtools.diffs.tools.base import BaseDiffTool
from rbtools.diffs.tools.errors import MissingDiffToolError
from rbtools.diffs.tools.registry import DiffToolsRegistry
from rbtools.testing import TestCase


class DiffToolsRegistryTests(kgb.SpyAgency, TestCase):
    """Unit tests for rbtools.diffs.tools.registry.DiffToolsRegistry."""

    def setUp(self):
        super().setUp()

        self.registry = DiffToolsRegistry()

        # Standardize some responses.
        self.spy_on(GNUDiffTool.get_install_instructions,
                    op=kgb.SpyOpReturn('Install by doing a thing.'))

    def test_iter_diff_tool_classes(self):
        """Testing DiffToolsRegistry.iterate_diff_tool_classes"""
        classes = self.registry.iter_diff_tool_classes()

        self.assertTrue(inspect.isgenerator(classes))
        self.assertEqual(set(classes),
                         {AppleDiffTool, GNUDiffTool})

    def test_get_diff_tool_class_with_found(self):
        """Testing DiffToolsRegistry.get_diff_tool_class with ID found"""
        self.assertIs(self.registry.get_diff_tool_class('gnu'),
                      GNUDiffTool)

    def test_get_diff_tool_class_with_not_found(self):
        """Testing DiffToolsRegistry.get_diff_tool_class with ID not found"""
        self.assertIsNone(self.registry.get_diff_tool_class('xxx'))

    def test_get_available(self):
        """Testing DiffToolsRegistry.get_available"""
        self.spy_on(GNUDiffTool.check_available,
                    owner=GNUDiffTool,
                    op=kgb.SpyOpReturn(True))

        self.assertIsInstance(self.registry.get_available(),
                              GNUDiffTool)

    def test_get_available_with_ids(self):
        """Testing DiffToolsRegistry.get_available and specific IDs"""
        self.spy_on(GNUDiffTool.check_available,
                    owner=GNUDiffTool,
                    op=kgb.SpyOpReturn(True))

        self.assertIsInstance(self.registry.get_available({'gnu'}),
                              GNUDiffTool)

    def test_get_available_and_not_found(self):
        """Testing DiffToolsRegistry.get_available and no compatible tool
        found
        """
        self.spy_on(BaseDiffTool.setup,
                    owner=BaseDiffTool,
                    call_original=False)

        message = (
            "A compatible command line diff tool (Apple Diff, GNU Diff) was "
            "not found on the system. This is required in order to generate "
            "diffs, and will need to be installed and placed in your system "
            "path.\n"
            "\n"
            "Install by doing a thing.\n"
            "\n"
            "If you're running an older version of RBTools, you may also "
            "need to upgrade."
        )

        with self.assertRaisesMessage(MissingDiffToolError, message):
            self.registry.get_available()

    def test_get_available_with_ids_and_not_found(self):
        """Testing DiffToolsRegistry.get_available with specific IDs and no
        compatible tool found
        """
        self.spy_on(BaseDiffTool.setup,
                    owner=BaseDiffTool,
                    call_original=False)

        message = (
            "A compatible command line diff tool (xxx) was not found on "
            "the system. This is required in order to generate diffs, and "
            "will need to be installed and placed in your system path.\n"
            "\n"
            "If you're running an older version of RBTools, you may also "
            "need to upgrade."
        )

        with self.assertRaisesMessage(MissingDiffToolError, message):
            self.registry.get_available({'xxx'})

    def test_get_available_with_setup_error(self):
        """Testing DiffToolsRegistry.get_available with setup error"""
        self.spy_on(AppleDiffTool.check_available,
                    owner=AppleDiffTool,
                    op=kgb.SpyOpRaise(TypeError('oh no')))
        self.spy_on(GNUDiffTool.check_available,
                    owner=GNUDiffTool,
                    op=kgb.SpyOpRaise(TypeError('oh no')))

        message = (
            "A compatible command line diff tool (Apple Diff, GNU Diff) was "
            "not found on the system. This is required in order to generate "
            "diffs, and will need to be installed and placed in your system "
            "path.\n"
            "\n"
            "Install by doing a thing.\n"
            "\n"
            "If you're running an older version of RBTools, you may also "
            "need to upgrade."
        )

        with self.assertLogs(level='ERROR') as logs:
            with self.assertRaisesMessage(MissingDiffToolError, message):
                self.registry.get_available()

        self.assertEqual(
            logs.output[0].splitlines()[0],
            'ERROR:rbtools.diffs.tools.registry:Unexpected error setting up '
            'and checking for diff tool "gnu": oh no')

    def test_register(self):
        """Testing DiffToolsRegistry.register"""
        class MyDiffTool(BaseDiffTool):
            diff_tool_id = 'my-diff-tool'
            name = 'My Diff Tool'

        self.registry.register(MyDiffTool)

        self.assertIn(MyDiffTool, self.registry.iter_diff_tool_classes())

    def test_register_with_missing_id(self):
        """Testing DiffToolsRegistry.register with missing diff_tool_id"""
        class MyDiffTool(BaseDiffTool):
            pass

        message = 'MyDiffTool.diff_tool_id must be set.'

        with self.assertRaisesMessage(ValueError, message):
            self.registry.register(MyDiffTool)

    def test_register_with_conflict(self):
        """Testing DiffToolsRegistry.register with conflicting ID"""
        class MyDiffTool(BaseDiffTool):
            diff_tool_id = 'gnu'

        message = (
            'Another diff tool with ID "gnu" (<class \''
            'rbtools.diffs.tools.backends.gnu.GNUDiffTool\'>) is already '
            'registered.'
        )

        with self.assertRaisesMessage(ValueError, message):
            self.registry.register(MyDiffTool)
