"""Tests for RBTools alias command."""

from rbtools.commands.alias import Alias
from rbtools.testing import CommandTestsMixin, TestCase


class AliasCommandTests(CommandTestsMixin, TestCase):
    """Tests for rbt alias commmand."""

    command_cls = Alias

    def test_alias_list_defined(self):
        """Testing rbt alias --list with defined aliases"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
                'alias2': 'command2',
            }
        }

        with self.reviewboardrc(config):
            result = self.run_command(args=['--list'])

        self.assertTrue(result['command'].options.list_aliases)
        self.assertEqual(result['exit_code'], 0)

        output = result['stdout']
        self.assertIn(b'alias1 = command1', output)
        self.assertIn(b'alias2 = command2', output)

    def test_alias_list_undefined(self):
        """Testing rbt alias --list with no defined aliases"""
        config = {
            'ALIASES': {},
        }

        with self.reviewboardrc(config):
            result = self.run_command(args=['--list'])

        self.assertTrue(result['command'].options.list_aliases)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['stdout'], b'')

    def test_alias_list_debug(self):
        """Testing rbt alias --list with debug option"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
                'alias2': 'command2',
            }
        }

        with self.reviewboardrc(config):
            result = self.run_command(args=['--list', '-d'])

        command = result['command']
        self.assertTrue(command.options.list_aliases)
        self.assertTrue(command.options.debug)
        self.assertEqual(result['exit_code'], 0)

    def test_alias_dry_run_defined(self):
        """Testing rbt alias --dry-run with a defined alias"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
                'alias2': 'command2',
            }
        }

        with self.reviewboardrc(config):
            result = self.run_command(args=['--dry-run', 'alias1'])

        self.assertTrue(result['command'].options.dry_run_alias)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['stdout'], b'rbt command1\n')

    def test_alias_dry_run_undefined(self):
        """Testing rbt alias --dry-run with an undefined alias"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
            }
        }

        with self.reviewboardrc(config):
            result = self.run_command(args=['--dry-run', 'alias2'])
            self.assertEqual(result['command'].options.dry_run_alias,
                             'alias2')
            self.assertEqual(result['exit_code'], 1)
            self.assertEqual(result['stderr'],
                             b'ERROR: No such alias "alias2"\n')

    def test_alias_dry_run_no_arg(self):
        """Testing rbt alias --dry-run with no alias argument provided"""
        config = {
            'ALIASES': {},
        }

        with self.reviewboardrc(config):
            result = self.run_command(args=['--dry-run'])

            # The argument parser will output to the real sys.stderr, so we
            # can't capture the output. Instead, check the error code.
            self.assertEqual(result['exit_code'], 2)

    def test_alias_dry_run_debug(self):
        """Testing rbt alias --dry-run with debug option"""
        config = {
            'ALIASES': {
                'alias1': 'command1',
                'alias2': 'command2',
            }
        }

        with self.reviewboardrc(config):
            result = self.run_command(args=['--dry-run', 'alias2', '-d'])

            command = result['command']
            self.assertTrue(command.options.dry_run_alias)
            self.assertTrue(command.options.debug)
            self.assertEqual(result['exit_code'], 0)
