"""Tests for RBTools setup-completion command.

Version Added:
    5.0
"""

from rbtools.commands.setup_completion import SetupCompletion
from rbtools.testing import CommandTestsMixin, TestCase


class SetupCompletionTest(CommandTestsMixin[SetupCompletion], TestCase):
    """Tests for rbt setup-completion command.

    Version Added:
        5.0
    """

    command_cls = SetupCompletion

    def test_with_bash(self) -> None:
        """Testing SetupCompletion with bash"""
        result = self.run_command(args=['bash'])

        self.assertEqual(result['exit_code'], 0)
        self.assertIn(b'complete -o default -F _rbt_commands rbt',
                      result['stdout'])

    def test_with_zsh(self) -> None:
        """Testing SetupCompletion with zsh"""
        result = self.run_command(args=['zsh'])

        self.assertEqual(result['exit_code'], 0)
        self.assertIn(b'#compdef rbt', result['stdout'])

    def test_with_unsupported(self) -> None:
        """Testing SetupCompletion with unsupported shell"""
        result = self.run_command(args=['xxx'])

        self.assertEqual(result['exit_code'], 1)
        self.assertEqual(
            result['stderr'],
            b'ERROR: Shell completions for xxx are not supported.\n')

    def test_with_shell_env(self) -> None:
        """Testing SetupCompletion with $SHELL"""
        with self.env({'SHELL': '/path/to/bash'}):
            result = self.run_command()
            self.assertIn(b'complete -o default -F _rbt_commands rbt',
                          result['stdout'])

        with self.env({'SHELL': '/path/to/zsh'}):
            result = self.run_command()
            self.assertIn(b'compdef rbt', result['stdout'])

    def test_with_json(self) -> None:
        """Testing SetupCompletion with --json"""
        result = self.run_command(args=['--json', 'zsh'])

        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['stderr'], b'')
        self.assertEqual(result['stdout'], b'')

        json_data = result['json']
        self.assertEqual(json_data['status'], 'success')
        self.assertIn('#compdef rbt', json_data['script'])

    def test_with_shell_unknown(self) -> None:
        """Testing SetupCompletion with shell unknown"""
        with self.env({'SHELL': ''}):
            result = self.run_command()

        self.assertEqual(result['exit_code'], 1)
        self.assertEqual(
            result['stderr'],
            b'ERROR: Your current shell was not found. Please re-run `rbt '
            b'setup-completion` with your shell (bash or zsh) as an '
            b'argument.\n')
