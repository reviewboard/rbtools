"""Unit tests for command initialization.

Version Added:
    5.1
"""

from __future__ import annotations

import argparse
from typing import Any

from rbtools.clients import RepositoryInfo
from rbtools.clients.git import GitClient
from rbtools.commands.base.commands import (BaseCommand,
                                            BaseMultiCommand,
                                            BaseSubCommand)
from rbtools.commands.base.options import Option
from rbtools.testing import CommandTestsMixin, TestCase


class _TestCommand(BaseCommand):
    """Command class that does nothing.

    Version Changed:
        5.4:
        Renamed to ``_TestCommand`` to make sure it doesn't get picked up
        by the test runner.

    Version Added:
        5.1
    """

    needs_api = True
    needs_repository = True

    option_list = [
        BaseCommand.server_options,
        BaseCommand.repository_options,
    ]

    def main(self, *args) -> int:
        """Run the command.

        Args:
            *args (tuple):
                Positional arguments for the command.

        Returns:
            int:
            The return code for the process.
        """
        return 0


class _TestSubCommand(BaseSubCommand):
    """Sub Command class that does nothing.

    Version Added:
        5.4
    """

    name = 'sub'
    needs_api = True

    option_list = [
        BaseCommand.server_options,
    ]

    def main(self, *args) -> int:
        """Run the command.

        Args:
            *args (tuple):
                Positional arguments for the command.

        Returns:
            int:
            The return code for the process.
        """
        return 0


class _TestMultiCommand(BaseMultiCommand):
    """Multi command class that does nothing.

    Version Added:
        5.1
    """
    subcommands = [_TestSubCommand]

    common_subcommand_option_list = [
        Option('--bar',
               dest='bar',
               action='store_true',
               default=False,
               help='Test bar description.'),
    ]

    def main(self, *args) -> int:
        """Run the command.

        Args:
            *args (tuple):
                Positional arguments for the command.

        Returns:
            int:
            The return code for the process.
        """
        return 0


class CommandInitializationTests(CommandTestsMixin[_TestCommand], TestCase):
    """Unit tests for command initialization.

    Version Added:
        5.1
    """

    command_cls = _TestCommand

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

        # Store _TestCommand's option list so that we can modify it in
        # tests and then restore it afterwards.
        self.original_option_list = self.command_cls.option_list.copy()

    def tearDown(self):
        """Tear down the test case."""
        self.command_cls.option_list = self.original_option_list

        super().tearDown()

    def test_no_server_url(self) -> None:
        """Testing with no configured server URL"""
        repo_info = RepositoryInfo(path='/path')
        tool = GitClient()

        result = self.run_command(repository_info=repo_info,
                                  tool=tool,
                                  server_url='')

        self.assertEqual(result['exit_code'], 1)
        self.assertEqual(
            result['json']['errors'],
            ['Unable to find a Review Board server for this source '
             'code tree.'])

    def test_server_url_with_reviewboardrc(self) -> None:
        """Testing server URL initialization from .reviewboardrc"""
        config: dict[str, Any] = {
            'REVIEWBOARD_URL': 'http://reviews.example.com/',
        }

        repo_info = RepositoryInfo(path='/path')
        tool = GitClient()

        with self.reviewboardrc(config):
            result = self.run_command(repository_info=repo_info,
                                      tool=tool,
                                      server_url='')

        command = result['command']
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(command.server_url,
                         'http://reviews.example.com/')

    def test_server_url_with_trees_config(self) -> None:
        """Testing server URL initialization with TREES= in .reviewboardrc"""
        config: dict[str, Any] = {
            'REVIEWBOARD_URL': 'http://reviews.example.com/',
            'TREES': {
                '/path': {
                    'REVIEWBOARD_URL': 'http://reviews2.example.com/',
                },
            },
        }

        repo_info = RepositoryInfo(path='/path')
        tool = GitClient()

        with self.reviewboardrc(config):
            result = self.run_command(repository_info=repo_info,
                                      tool=tool,
                                      server_url='')

        command = result['command']
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(command.server_url,
                         'http://reviews2.example.com/')

    def test_with_deprecated_option(self) -> None:
        """Testing warning and help output when passing a deprecated option"""
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2.]'))

    def test_with_deprecated_and_removed_in_option(self) -> None:
        """Testing warning and help output when passing a deprecated option
        that also has a removal version
        """
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2',
                   removed_in='6.0'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2 '
            'and will be removed in 6.0.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2 and will be removed in 6.0.]'))

    def test_with_deprecated_and_replacement_option(self) -> None:
        """Testing warning and help output when passing a deprecated option
        that also has a replacement option
        """
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2',
                   replacement='--debug'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2. '
            'Use --debug instead.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2. Use --debug instead.]'))

    def test_with_deprecated_full_option(self) -> None:
        """Testing warning and help output when passing a deprecated option
        that also has a replacement option and a removal version
        """
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2',
                   removed_in='6.0',
                   replacement='--debug'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2 '
            'and will be removed in 6.0. Use --debug instead.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2 and will be removed in 6.0. '
                  'Use --debug instead.]'))


class MultiCommandInitializationTests(CommandTestsMixin[_TestMultiCommand],
                                      TestCase):
    """Unit tests for multi command initialization.

    Version Added:
        5.4
    """

    command_cls = _TestMultiCommand

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

        # Store the multi command and all sub commands' option lists so that
        # we can modify it in tests and then restore it afterwards.
        self.original_common_option_list = \
            self.command_cls.common_subcommand_option_list.copy()

        self.original_subcommand_option_lists = [
            subcommand.option_list.copy()
            for subcommand in self.command_cls.subcommands
        ]

    def tearDown(self):
        """Tear down the test case."""
        self.command_cls.common_subcommand_option_list = \
            self.original_common_option_list

        for i, subcommand in enumerate(self.command_cls.subcommands):
            subcommand.option_list = self.original_subcommand_option_lists[i]

        super().tearDown()

    def test_with_common_deprecated_option(self) -> None:
        """Testing warning and help output when passing a common deprecated
        option
        """
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.common_subcommand_option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['sub', '--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2.]'))

    def test_with_common_deprecated_and_removed_in_option(self) -> None:
        """Testing warning and help output when passing a common deprecated
        option that also has a removal version
        """
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.common_subcommand_option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2',
                   removed_in='6.0'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['sub', '--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2 '
            'and will be removed in 6.0.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2 and will be removed in 6.0.]'))

    def test_with_common_deprecated_and_replacement_option(self) -> None:
        """Testing warning and help output when passing a common deprecated
        option that also has a replacement option
        """
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.common_subcommand_option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2',
                   replacement='--debug'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['sub', '--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2. '
            'Use --debug instead.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2. Use --debug instead.]'))

    def test_with_common_deprecated_full_option(self) -> None:
        """Testing warning and help output when passing a common deprecated
        option that also has a replacement option and a removal version
        """
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.common_subcommand_option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2',
                   removed_in='6.0',
                   replacement='--debug'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['sub', '--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2 '
            'and will be removed in 6.0. Use --debug instead.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2 and will be removed in 6.0. '
                  'Use --debug instead.]'))

    def test_with_sub_deprecated_option(self) -> None:
        """Testing warning and help output when passing a sub command's
        deprecated option
        """
        self.spy_on(argparse.ArgumentParser.add_argument,
                    owner=argparse.ArgumentParser)
        self.command_cls.subcommands[0].option_list.append(
            Option('--foo',
                   dest='foo',
                   action='store_true',
                   default=False,
                   help='Test foo description.',
                   deprecated_in='5.2'))

        with self.assertLogs(level='WARNING') as ctx:
            self.run_command(args=['sub', '--foo'])

        self.assertEqual(
            ctx.output[0],
            'WARNING:root:Option --foo is deprecated as of RBTools 5.2.')
        self.assert_spy_called_with(
            argparse.ArgumentParser.add_argument,
            '--foo',
            action='store_true',
            default=False,
            dest='foo',
            help=('Test foo description.\n'
                  '[Deprecated since 5.2.]'))
