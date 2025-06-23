"""Tests for RBTools help command and rbt command help options."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import kgb

from rbtools import get_version_string
from rbtools.commands import main as rbt_main
from rbtools.commands.base.output import JSONOutput
from rbtools.testing import TestCase
from rbtools.utils.process import run_process

if TYPE_CHECKING:
    from collections.abc import Sequence


_rbt_path = rbt_main.__file__


class MainCommandTests(TestCase):
    """Tests for RBT help command and rbt command help options."""

    def test_help_command(self):
        """Testing RBT commands when running 'rbt help <command>'"""
        self._check_help_output(['help', 'alias'], 'alias')

    def test_help_options_before(self):
        """Testing RBT commands when running 'rbt --help <command>' or 'rbt
        -h <command>'
        """
        self._check_help_output(['--help', 'alias'], 'alias')
        self._check_help_output(['-h', 'alias'], 'alias')

    def test_help_options_after(self):
        """Testing RBT commands when running 'rbt <command> --help' or 'rbt
        <command> -h'
        """
        self._check_help_output(['alias', '--help'], 'alias')
        self._check_help_output(['alias', '-h'], 'alias')

    def test_help_invalid_command(self):
        """Testing RBT commands when running '--help' or '-h' with an
        invalid command
        """
        self._check_help_output(['invalid', '--help'],
                                'invalid', invalid=True)
        self._check_help_output(['invalid', '-h'], 'invalid',
                                invalid=True)
        self._check_help_output(['help', 'invalid'], 'invalid',
                                invalid=True)

    def test_help_multiple_args(self):
        """Testing RBT commands when running the help command or help
        options with multiple arguments present
        """
        self._check_help_output(['alias', 'extra_arg', '--help'], 'alias')
        self._check_help_output(['alias', 'extra_arg', '-h'], 'alias')
        self._check_help_output(['alias', '--help', 'extra_arg'], 'alias')
        self._check_help_output(['alias', '-h', 'extra_arg'], 'alias')
        self._check_help_output(['--help', 'alias', 'extra_arg'], 'alias')
        self._check_help_output(['-h', 'alias', 'extra_arg'], 'alias')
        self._check_help_output(['help', 'alias', 'extra_arg'], 'alias')

    def test_version_command(self):
        """Testing RBT commands when running 'rbt --version' and 'rbt -v"
        """
        self._check_version_output('--version')
        self._check_version_output('-v')

    def _check_help_output(
        self,
        args: Sequence[str],
        subcommand: str,
        invalid: bool = False,
    ) -> None:
        """Check if a specific rbt command's output exists in test output.

        Args:
            args (list of str):
                The ``rbt`` command arguments.

            subcommand (str):
                The rbt subcommand to run.

            invalid (bool, optional):
                If ``True``, check if output matches what is expected after
                running an invalid command. Otherwise, check if output
                matches what is expected after running a valid rbt command.
        """
        output = self._run_rbt(*args)

        if invalid:
            self.assertIn(f'No help found for {subcommand}', output)
        else:
            self.assertIn(f'usage: rbt {subcommand} [options]', output)

    def _check_version_output(
        self,
        version_arg: str,
    ) -> None:
        """Check if RBTools reports the correct version information.

        Args:
            version_arg (str):
                The version flag to pass to ``rbt``.
        """
        output = self._run_rbt(version_arg)

        rbt_version = get_version_string()
        python_version = '.'.join(
            f'{n}'
            for n in sys.version_info[:3]
        )

        self.assertEqual(
            output,
            f'RBTools {rbt_version} (Python {python_version})\n')

    def _run_rbt(self, *args) -> str:
        """Run rbt with the current Python and provided arguments.

        This will ensure the correct version of ``rbt`` is being run and with
        the current version of Python.

        Args:
            *args (tuple):
                The command line arguments to pass to ``rbt``.

        Returns:
            str:
            The output from the process.
        """
        return (
            run_process([sys.executable, '-W', 'ignore', _rbt_path, *args])
            .stdout
            .read()
        )


class JSONOutputTests(kgb.SpyAgency, TestCase):
    """Tests for JSON output wrapper for --json command.
    """

    def setUp(self):
        """Set up the test suite."""
        super(JSONOutputTests, self).setUp()

        self.json = JSONOutput(sys.stdout)

    def test_init(self):
        """Testing JSONOutput instantiates given stream object"""
        self.assertIs(self.json._output_stream, sys.stdout)
        self.assertEqual(len(self.json.raw), 0)

    def test_add(self):
        """Testing JSONOutput.add adds a key value pair to output"""
        self.json.add('key', 'value')

        self.assertEqual(self.json.raw['key'], 'value')

    def test_append(self):
        """Testing JSONOutput.append appends to list associated with a key"""
        self.json.add('test', [])
        self.json.append('test', 'test')

        self.assertEqual(self.json.raw['test'], ['test'])

        try:
            self.json.append('nonexistent', 'test')
        except KeyError:
            pass

        self.assertNotIn('nonexistent', self.json.raw)

    def test_add_error_without_key(self):
        """Testing JSONOutput.add_error without existing key"""
        self.json.add_error('test_error')

        self.assertEqual(self.json.raw['errors'], ['test_error'])

    def test_add_error_with_key(self):
        """Testing JSONOutput.add_error with existing key"""
        self.json.add_error('test_error')
        self.json.add_error('test_error2')
        self.assertEqual(self.json.raw['errors'],
                         ['test_error', 'test_error2'])

    def test_add_warning_without_key(self):
        """Testing JSONOutput.add_warning without existing key"""
        self.json.add_warning('test_warning')

        self.assertEqual(self.json.raw['warnings'], ['test_warning'])

    def test_add_warning_with_key(self):
        """Testing JSONOutput.add_warning with existing key"""
        self.json.add_warning('test_warning')
        self.json.add_warning('test_warning2')
        self.assertEqual(self.json.raw['warnings'],
                         ['test_warning', 'test_warning2'])
