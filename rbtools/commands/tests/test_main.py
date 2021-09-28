"""Tests for RBTools help command and rbt command help options."""

from __future__ import unicode_literals

import io
import os.path
import sys

import kgb

from rbtools import get_version_string
from rbtools.commands import JSONOutput, main as rbt_main, OutputWrapper
from rbtools.utils.process import execute
from rbtools.utils.testbase import RBTestBase


_rbt_path = rbt_main.__file__


class MainCommandTests(RBTestBase):
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

    def _check_help_output(self, args, subcommand, invalid=False):
        """Check if a specific rbt command's output exists in test output.

        Args:
            args (list of unicode):
                The ``rbt`` command arguments.

            subcommand (unicode)
                The unicode string of the rbt command type.

            invalid (bool, optional):
                If ``True``, check if output matches what is expected after
                running an invalid command. Otherwise, check if output
                matches what is expected after running a valid rbt command.
        """
        output = self._run_rbt(*args)

        if invalid:
            self.assertIn('No help found for %s' % subcommand, output)
        else:
            self.assertIn('usage: rbt %s [options]' % subcommand, output)

    def _check_version_output(self, version_arg):
        """Check if RBTools reports the correct version information.

        Args:
            version_arg (unicode):
                The version flag to pass to ``rbt``.
        """
        output = self._run_rbt(version_arg)

        self.assertEqual(
            output,
            'RBTools %s (Python %d.%d.%d)\n'
            % (get_version_string(),
               sys.version_info[:3][0],
               sys.version_info[:3][1],
               sys.version_info[:3][2]))

    def _run_rbt(self, *args):
        """Run rbt with the current Python and provided arguments.

        This will ensure the correct version of ``rbt`` is being run and with
        the current version of Python.

        Args:
            *args (tuple):
                The command line arguments to pass to ``rbt``.

        Returns:
            unicode:
            The resulting output from the command.
        """
        return execute([sys.executable, _rbt_path] + list(args))


class JSONOutputTests(kgb.SpyAgency, RBTestBase):
    """Tests for JSON output wrapper for --json command.
    """

    def setUp(self):
        """Set up the test suite."""
        super(JSONOutputTests, self).setUp()

        self.json = JSONOutput(sys.stdout)

    def test_json_wrapper_initializes(self):
        """Testing JSONOutput instantiates given stream object.
        """
        self.assertIs(self.json._output_stream, sys.stdout)

    def test_json_wrapper_initiates(self):
        """Testing JSONOutput instantiates empty dictionary.
        """
        self.assertEqual(len(self.json._output), 0)

    def test_json_wrapper_add(self):
        """Testing JSONOutput.add adds a key value pair to output.
        """
        self.json.add('key', 'value')

        self.assertEqual(self.json._output['key'], 'value')

    def test_json_wrapper_append(self):
        """Testing JSONOutput.append appends to list associated with a key.
        """
        self.json.add('test', [])
        self.json.append('test', 'test')

        self.assertEqual(self.json._output['test'], ['test'])

        try:
            self.json.append('nonexistent', 'test')
        except KeyError:
            pass

        self.assertNotIn('nonexistent', self.json._output)

    def test_json_wrapper_add_error(self):
        """Testing JSONOutput.add_error will append to the errors key if it
        already exists and create a new errors key if it does not.
        """
        self.json.add_error('test_error')

        self.assertEqual(self.json._output['errors'], ['test_error'])

        self.json.add_error('test_error2')
        self.assertEqual(self.json._output['errors'],
                         ['test_error', 'test_error2'])
