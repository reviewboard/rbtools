"""Unit tests for command initialization.

Version Added:
    5.1
"""

from __future__ import annotations

from typing import Any

from rbtools.clients import RepositoryInfo
from rbtools.clients.git import GitClient
from rbtools.commands.base.commands import BaseCommand
from rbtools.testing import CommandTestsMixin, TestCase


class TestCommand(BaseCommand):
    """Command class that does nothing.

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


class CommandInitializationTests(CommandTestsMixin[TestCommand], TestCase):
    """Unit tests for command initialization.

    Version Added:
        5.1
    """

    command_cls = TestCommand

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
