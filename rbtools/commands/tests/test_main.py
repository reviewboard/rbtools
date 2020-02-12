"""Tests for RBTools help command and rbt command help options."""

from __future__ import unicode_literals

from rbtools.utils.process import execute
from rbtools.utils.testbase import RBTestBase


class HelpCommandTests(RBTestBase):
    """Tests for RBT help command and rbt command help options."""

    def test_help_command(self):
        """Testing RBT commands when running 'rbt help <command>'"""
        self._check_help_output(['rbt', 'help', 'alias'], 'alias')

    def test_help_options_before(self):
        """Testing RBT commands when running 'rbt --help <command>' or 'rbt
        -h <command>'
        """
        self._check_help_output(['rbt', '--help', 'alias'], 'alias')
        self._check_help_output(['rbt', '-h', 'alias'], 'alias')

    def test_help_options_after(self):
        """Testing RBT commands when running 'rbt <command> --help' or 'rbt
        <command> -h'
         """
        self._check_help_output(['rbt', 'alias', '--help'], 'alias')
        self._check_help_output(['rbt', 'alias', '-h'], 'alias')

    def test_help_invalid_command(self):
        """Testing RBT commands when running '--help' or '-h' with an
        invalid command
         """
        self._check_help_output(['rbt', 'invalid', '--help'],
                                'invalid', invalid=True)
        self._check_help_output(['rbt', 'invalid', '-h'], 'invalid',
                                invalid=True)
        self._check_help_output(['rbt', 'help', 'invalid'], 'invalid',
                                invalid=True)

    def test_help_multiple_args(self):
        """Testing RBT commands when running the help command or help
        options with multiple arguments present
        """
        self._check_help_output(['rbt', 'alias', 'extra_arg', '--help'],
                                'alias')
        self._check_help_output(['rbt', 'alias', 'extra_arg', '-h'], 'alias')
        self._check_help_output(['rbt', 'alias', '--help', 'extra_arg'],
                                'alias')
        self._check_help_output(['rbt', 'alias', '-h', 'extra_arg'], 'alias')
        self._check_help_output(['rbt', '--help', 'alias', 'extra_arg'],
                                'alias')
        self._check_help_output(['rbt', '-h', 'alias', 'extra_arg'], 'alias')
        self._check_help_output(['rbt', 'help', 'alias', 'extra_arg'], 'alias')

    def _check_help_output(self, command, subcommand, invalid=False):
        """Check if a specific rbt command's output exists in test output.

        Args:
            command (list of unicode):
                The rbt command used for testing.

            subcommand (unicode)
                The unicode string of the rbt command type.

            invalid (bool, optional):
                If ``True``, check if output matches what is expected after
                running an invalid command. Otherwise, check if output
                matches what is expected after running a valid rbt command.
        """
        try:
            output = execute(command)
        except Exception as e:
            self.fail(e)

        if invalid:
            self.assertIn('No help found for %s' % subcommand, output)
        else:
            self.assertIn('usage: rbt %s [options]' % subcommand, output)
