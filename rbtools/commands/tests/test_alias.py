"""Tests for RBTools alias command."""

from __future__ import unicode_literals

from rbtools.commands.alias import Alias
from rbtools.testing import TestCase
from rbtools.utils.process import execute


class AliasCommandTests(TestCase):
    """Tests for rbt alias commmand."""

    def test_alias_list_defined(self):
        """Testing alias --list with defined aliases"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
                'alias2': 'command2',
            }
        }

        with self.reviewboardrc(config, use_temp_dir=True):
            alias = self._create_alias_command(args=['--list'])
            output = execute(['rbt', 'alias', '--list'])
            self.assertIn('alias1 = command1', output)
            self.assertIn('alias2 = command2', output)
            self.assertTrue(alias.options.list_aliases)

    def test_alias_list_undefined(self):
        """Testing alias --list with no defined aliases"""
        config = {
            'ALIASES': {},
        }

        with self.reviewboardrc(config, use_temp_dir=True):
            output = execute(['rbt', 'alias', '--list'])
            self.assertEqual(output, '')

    def test_alias_list_debug(self):
        """Testing alias --list with debug option"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
                'alias2': 'command2',
            }
        }

        with self.reviewboardrc(config, use_temp_dir=True):
            alias = self._create_alias_command(args=['--list', '-d'])
            self.assertTrue(alias.options.list_aliases)
            self.assertTrue(alias.options.debug)

    def test_alias_dry_run_defined(self):
        """Testing alias --dry-run with a defined alias"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
                'alias2': 'command2',
            }
        }

        with self.reviewboardrc(config, use_temp_dir=True):
            output = execute(['rbt', 'alias', '--dry-run', 'alias1'])
            alias = self._create_alias_command(args=['--dry-run', 'alias1'])
            self.assertIn('command1', output)
            self.assertTrue(alias.options.dry_run_alias)

    def test_alias_dry_run_undefined(self):
        """Testing alias --dry-run with an undefined alias"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
            }
        }

        with self.reviewboardrc(config, use_temp_dir=True):
            alias = self._create_alias_command(args=['--dry-run', 'alias2'])
            self.assertEqual(alias.options.dry_run_alias, 'alias2')
            self.assertRaises(Exception, execute, ['rbt', 'alias', '--dry-run',
                                                   'alias2'])

    def test_alias_dry_run_no_arg(self):
        """Testing alias --dry-run with no alias argument provided"""
        config = {
            'ALIASES': {},
        }

        with self.reviewboardrc(config, use_temp_dir=True):
            self.assertRaises(Exception, execute, ['rbt', 'alias',
                                                   '--dry-run'])

    def test_alias_dry_run_debug(self):
        """Testing alias --dry-run with debug option"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
                'alias2': 'command2',
            }
        }

        with self.reviewboardrc(config, use_temp_dir=True):
            alias = self._create_alias_command(args=['--dry-run', 'alias2',
                                                     '-d'])
            self.assertTrue(alias.options.dry_run_alias)
            self.assertTrue(alias.options.debug)

    def _create_alias_command(self, fields=None, args=None):
        """Create an argument parser for alias with given extra fields.

        Args:
            fields (list of unicode):
                A list of key=value formatted unicode strings for the field
                arugment.

            args (list of unicode):
                A list of command line arguments to be passed to the parser.

        Returns:
            rbtools.commands.alias.Alias:
            An instance of the Alias command.
        """
        alias = Alias()
        argv = ['rbt', 'alias']

        if args is not None:
            argv += args

        parser = alias.create_arg_parser(argv)
        alias.options = parser.parse_args(argv[2:])

        if fields is not None:
            alias.options.fields = fields

        return alias
