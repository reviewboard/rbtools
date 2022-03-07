"""Tests for RBTools setup-repo command."""

from __future__ import unicode_literals

import os

from kgb import SpyAgency

from rbtools.api.resource import ItemResource
from rbtools.api.tests.base import TestWithPayloads
from rbtools.commands.setup_repo import SetupRepo
from rbtools.testing import TestCase
from rbtools.testing.transport import TestTransport
from rbtools.utils.console import confirm_select, get_input


class SetupRepoTest(SpyAgency, TestWithPayloads, TestCase):
    """Tests for rbt setup-repo command."""

    def test_prompt_rb_repository_repos_found(self):
        """Testing setup-repo reads and processes existing repos"""
        setup = self._create_setup_repo_command()
        setup.default_transport_cls = TestTransport('testmockurl')
        mock_api_root = setup.default_transport_cls.get_root()

        self.spy_on(get_input, call_fake=lambda *args, **kwargs: '1')
        self.spy_on(confirm_select)
        self.spy_on(setup._display_rb_repositories)

        output = setup.prompt_rb_repository(
            local_tool_name='Git',
            server_tool_names='Git',
            repository_paths='testpath',
            api_root=mock_api_root)

        self.assertTrue(setup._display_rb_repositories.called)
        self.assertIsInstance(output, ItemResource)

    def test_prompt_rb_repository_no_repos_found(self):
        """Testing setup-repo does not show repo prompt if no repo exists"""
        setup = self._create_setup_repo_command()
        setup.default_transport_cls = TestTransport(
            'testmockurl',
            list_payload=TestWithPayloads.list_payload_no_repos,
        )
        mock_api_root = setup.default_transport_cls.get_root()

        self.spy_on(setup._display_rb_repositories)

        output = setup.prompt_rb_repository(
            local_tool_name='Git',
            server_tool_names='Git',
            repository_paths='testpath',
            api_root=mock_api_root)

        self.assertFalse(setup._display_rb_repositories.called)
        self.assertIsNone(output)

    def test_generate_config_file(self):
        """Testing setup-repo generates a config file"""
        self.chdir_tmp()
        setup = self._create_setup_repo_command()
        test_path = os.path.join(os.getcwd(), '.reviewboardrc')

        setup.generate_config_file(test_path, [])

        self.assertTrue(os.path.exists(test_path))
        self.assertTrue(os.path.isfile(test_path))

    def test_generate_config_file_contents(self):
        """Testing setup-repo assigns proper values to config file"""
        self.chdir_tmp()
        setup = self._create_setup_repo_command()
        test_path = os.path.join(os.getcwd(), '.reviewboardrc')

        setup.generate_config_file(test_path, [
            ('REVIEWBOARD_URL', 'testserver'),
            ('REPOSITORY', 'testrepo'),
            ('REPOSITORY_TYPE', 'Git'),
        ])

        with open(test_path, 'r') as fp:
            config_lines = fp.readlines()

        self.assertTrue(os.path.isfile(test_path))
        self.assertEqual(
            config_lines,
            [
                'REVIEWBOARD_URL = "testserver"\n',
                'REPOSITORY = "testrepo"\n',
                'REPOSITORY_TYPE = "Git"\n',
            ])

    def test_server_options(self):
        """Testing setup-repo properly saves valid server options"""
        setup = self._create_setup_repo_command(args=[
            '--server', 'testserver',
            '--username', 'testname',
            '--password', 'testpassword',
            '--ext-auth-cookies', '{}',
            '--api-token', 'testtoken123',
            '--disable-cache',
            '--disable-proxy',
            '--disable-ssl-verification',
            '--cache-location', '/test/filelocation',
            '--disable-cache-storage',
        ])
        options = setup.options

        self.assertEqual(options.server, 'testserver')
        self.assertEqual(options.username, 'testname')
        self.assertEqual(options.password, 'testpassword')
        self.assertEqual(options.ext_auth_cookies, '{}')
        self.assertEqual(options.api_token, 'testtoken123')
        self.assertTrue(options.disable_cache)
        self.assertFalse(options.enable_proxy)
        self.assertTrue(options.disable_ssl_verification)
        self.assertEqual(options.cache_location, '/test/filelocation')
        self.assertTrue(options.in_memory_cache)

    def test_perforce_options(self):
        """Testing setup-repo properly saves valid perforce options"""
        setup = self._create_setup_repo_command(args=[
            '--p4-client', 'testp4client',
            '--p4-port', 'testp4port',
            '--p4-passwd', 'testp4password',
        ])
        options = setup.options

        self.assertEqual(options.p4_client, 'testp4client')
        self.assertEqual(options.p4_port, 'testp4port')
        self.assertEqual(options.p4_passwd, 'testp4password')

    def test_tfs_options(self):
        """Testing setup-repo properly saves valid TFS options"""
        setup = self._create_setup_repo_command(args=[
            '--tfs-login', 'testtfslogin',
            '--tf-cmd', 'test/tfs/command',
            '--tfs-shelveset-owner', 'testtfs-owner',
        ])
        options = setup.options

        self.assertEqual(options.tfs_login, 'testtfslogin')
        self.assertEqual(options.tf_cmd, 'test/tfs/command')
        self.assertEqual(options.tfs_shelveset_owner, 'testtfs-owner')

    def _create_setup_repo_command(self, fields=None, args=None):
        """Create an argument parser for setup-repo with given extra fields.

        Args:
            fields (list of unicode):
                A list of key=value formatted unicode strings for the field
                argument.

            args (list of unicode):
                A list of command line arguments to be passed to the parser.

                The command line will receive each item in the list.

        Returns:
            rbtools.commands.post.SetupRepo:
            An instance of the setup-repo command
        """
        setup = SetupRepo()
        argv = ['rbt', 'setup-repo']

        if args is not None:
            argv += args

        parser = setup.create_arg_parser(argv)
        setup.options = parser.parse_args(argv[2:])

        if fields is not None:
            setup.options.fields = fields

        return setup
