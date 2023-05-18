"""Tests for RBTools setup-repo command."""

import os

from kgb import SpyAgency

from rbtools.api.resource import ItemResource
from rbtools.commands.setup_repo import SetupRepo
from rbtools.testing import CommandTestsMixin, TestCase
from rbtools.testing.transport import TestTransport
from rbtools.utils.console import confirm_select, get_input


class SetupRepoTest(CommandTestsMixin, TestCase):
    """Tests for rbt setup-repo command."""

    command_cls = SetupRepo

    def test_prompt_rb_repository_repos_found(self):
        """Testing SetupRepo.prompt_rb_repository with matching repository"""
        def setup_transport(transport):
            transport.add_repository_urls(path='testpath',
                                          tool='Git')

        setup = self.create_command(setup_transport_func=setup_transport)
        api_root = setup.get_api(self.DEFAULT_SERVER_URL)[1]

        self.spy_on(get_input, call_fake=lambda *args, **kwargs: '1')
        self.spy_on(confirm_select)
        self.spy_on(setup._display_rb_repositories)

        output = setup.prompt_rb_repository(
            local_tool_name='Git',
            server_tool_names='Git',
            repository_paths='testpath',
            api_root=api_root)

        self.assertSpyCalled(setup._display_rb_repositories)
        self.assertIsInstance(output, ItemResource)

    def test_prompt_rb_repository_no_repos_found(self):
        """Testing SetupRepo.prompt_rb_repository without matching repository
        """
        setup = self.create_command()
        api_root = setup.get_api(self.DEFAULT_SERVER_URL)[1]

        self.spy_on(setup._display_rb_repositories)

        output = setup.prompt_rb_repository(
            local_tool_name='Git',
            server_tool_names='Git',
            repository_paths='testpath',
            api_root=api_root)

        self.assertSpyNotCalled(setup._display_rb_repositories)
        self.assertIsNone(output)

    def test_generate_config_file(self):
        """Testing SetupRepo.generate_config_file without options"""
        setup = self.create_command()
        test_path = os.path.join(os.getcwd(), '.reviewboardrc')

        setup.generate_config_file(test_path, [])

        self.assertTrue(os.path.exists(test_path))
        self.assertTrue(os.path.isfile(test_path))

    def test_generate_config_file_contents(self):
        """Testing SetupRepo.generate_config_file with options"""
        setup = self.create_command()
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
        """Testing SetupRepo argument parsing"""
        setup = self.create_command(
            args=[
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
            ],
            server_url=None)
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
        """Testing SetupRepo argument parsing with Perforce options"""
        setup = self.create_command(args=[
            '--p4-client', 'testp4client',
            '--p4-port', 'testp4port',
            '--p4-passwd', 'testp4password',
        ])
        options = setup.options

        self.assertEqual(options.p4_client, 'testp4client')
        self.assertEqual(options.p4_port, 'testp4port')
        self.assertEqual(options.p4_passwd, 'testp4password')

    def test_tfs_options(self):
        """Testing SetupRepo argument parsing with TFS options"""
        setup = self.create_command(args=[
            '--tfs-login', 'testtfslogin',
            '--tf-cmd', 'test/tfs/command',
            '--tfs-shelveset-owner', 'testtfs-owner',
        ])
        options = setup.options

        self.assertEqual(options.tfs_login, 'testtfslogin')
        self.assertEqual(options.tf_cmd, 'test/tfs/command')
        self.assertEqual(options.tfs_shelveset_owner, 'testtfs-owner')
