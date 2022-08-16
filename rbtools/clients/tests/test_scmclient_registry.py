"""Unit tests for rbtools.clients.base.registry.

Version Added:
    4.0
"""

import re
import sys

if sys.version_info[:2] >= (3, 10):
    # Python >= 3.10
    from importlib.metadata import EntryPoint, entry_points
else:
    # Python <= 3.9
    from importlib_metadata import EntryPoint, entry_points

import kgb

from rbtools.clients.base.scmclient import BaseSCMClient
from rbtools.clients.base.registry import SCMClientRegistry
from rbtools.clients.bazaar import BazaarClient
from rbtools.clients.clearcase import ClearCaseClient
from rbtools.clients.cvs import CVSClient
from rbtools.clients.errors import SCMClientNotFoundError
from rbtools.clients.git import GitClient
from rbtools.clients.mercurial import MercurialClient
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.plastic import PlasticClient
from rbtools.clients.sos import SOSClient
from rbtools.clients.svn import SVNClient
from rbtools.clients.tfs import TFSClient
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.testing import TestCase


class MySCMClient1(BaseSCMClient):
    scmclient_id = 'my_client1'


class MySCMClient2(BaseSCMClient):
    pass


class SCMClientRegistryTests(kgb.SpyAgency, TestCase):
    """Unit tests for SCMClientRegistry."""

    def tearDown(self):
        super().tearDown()

        # Tests will end up patching MySCMClient2.scmtool_id. Unset this.
        MySCMClient2.scmclient_id = None

    def test_init(self):
        """Testing SCMClientRegistry.__init__"""
        registry = SCMClientRegistry()

        self.assertEqual(registry._scmclient_classes, {})
        self.assertFalse(registry._builtin_loaded)
        self.assertFalse(registry._entrypoints_loaded)

    def test_iter(self):
        """Testing SCMClientRegistry.__iter__"""
        registry = SCMClientRegistry()

        self._add_fake_entrypoints([
            EntryPoint(name='my_client1',
                       value='%s:MySCMClient1' % __name__,
                       group='rbtools_scm_clients'),
            EntryPoint(name='my_client2',
                       value='%s:MySCMClient2' % __name__,
                       group='rbtools_scm_clients'),
        ])

        message = re.escape(
            'MySCMClient2.scmclient_id must be set, and must be a unique '
            'value. You probably want to set it to "my_client2".'
        )

        with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
            self.assertEqual(
                list(registry),
                [
                    BazaarClient,
                    ClearCaseClient,
                    CVSClient,
                    GitClient,
                    MercurialClient,
                    PerforceClient,
                    PlasticClient,
                    SOSClient,
                    SVNClient,
                    TFSClient,
                    MySCMClient1,
                    MySCMClient2,
                ])

        self.assertTrue(registry._builtin_loaded)
        self.assertTrue(registry._entrypoints_loaded)

    def test_get_with_builtin(self):
        """Testing SCMClientRegistry.get with built-in SCMClient"""
        registry = SCMClientRegistry()

        self.assertIs(registry.get('git'), GitClient)
        self.assertTrue(registry._builtin_loaded)
        self.assertFalse(registry._entrypoints_loaded)

    def test_get_with_entrypoint(self):
        """Testing SCMClientRegistry.get with entry point SCMClient"""
        registry = SCMClientRegistry()

        self._add_fake_entrypoints([
            EntryPoint(name='my_client1',
                       value='%s:MySCMClient1' % __name__,
                       group='rbtools_scm_clients'),
        ])

        self.assertIs(registry.get('my_client1'), MySCMClient1)
        self.assertTrue(registry._builtin_loaded)
        self.assertTrue(registry._entrypoints_loaded)

    def test_get_with_entrypoint_no_scmclient_id(self):
        """Testing SCMClientRegistry.get with entry point SCMClient with no
        scmclient_id set
        """
        registry = SCMClientRegistry()

        self._add_fake_entrypoints([
            EntryPoint(name='my_client2',
                       value='%s:MySCMClient2' % __name__,
                       group='rbtools_scm_clients'),
        ])

        message = re.escape(
            'MySCMClient2.scmclient_id must be set, and must be a unique '
            'value. You probably want to set it to "my_client2".'
        )

        with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
            scmclient_cls = registry.get('my_client2')

        self.assertIs(scmclient_cls, MySCMClient2)
        self.assertTrue(registry._builtin_loaded)
        self.assertTrue(registry._entrypoints_loaded)

    def test_get_with_entrypoint_and_missing(self):
        """Testing SCMClientRegistry.get with entry point SCMClient missing"""
        registry = SCMClientRegistry()

        self._add_fake_entrypoints([
            EntryPoint(name='xxx',
                       value='%s:XXX' % __name__,
                       group='rbtools_scm_clients'),
        ])

        message = re.escape(
            'No client support was found for "xxx".'
        )

        with self.assertRaisesRegex(SCMClientNotFoundError, message) as ctx:
            registry.get('xxx')

        self.assertEqual(ctx.exception.scmclient_id, 'xxx')
        self.assertTrue(registry._builtin_loaded)
        self.assertTrue(registry._entrypoints_loaded)

    def test_register(self):
        """Testing SCMClientRegistry.register"""
        registry = SCMClientRegistry()
        registry.register(MySCMClient1)

        self.assertTrue(registry._builtin_loaded)
        self.assertFalse(registry._entrypoints_loaded)

        # This will have triggered a load of defaults, but not entry points.
        self.assertEqual(
            list(registry),
            [
                BazaarClient,
                ClearCaseClient,
                CVSClient,
                GitClient,
                MercurialClient,
                PerforceClient,
                PlasticClient,
                SOSClient,
                SVNClient,
                TFSClient,
                MySCMClient1,
            ])

    def test_register_with_no_scmclient_id(self):
        """Testing SCMClientRegistry.register with no scmclient_id"""
        registry = SCMClientRegistry()

        message = re.compile(
            'MySCMClient2.scmclient_id must be set, and must be a unique '
            'value.'
        )

        with self.assertRaisesRegex(ValueError, message):
            registry.register(MySCMClient2)

        self.assertTrue(registry._builtin_loaded)
        self.assertFalse(registry._entrypoints_loaded)
        self.assertNotIn(MySCMClient1, registry)

    def test_register_with_already_registered(self):
        """Testing SCMClientRegistry.register with class already registered"""
        registry = SCMClientRegistry()

        message = re.compile('GitClient is already registered.')

        with self.assertRaisesRegex(ValueError, message):
            registry.register(GitClient)

        self.assertTrue(registry._builtin_loaded)
        self.assertFalse(registry._entrypoints_loaded)
        self.assertNotIn(MySCMClient1, registry)

    def test_register_with_id_already_used(self):
        """Testing SCMClientRegistry.register with ID already used"""
        class MyGitClient(BaseSCMClient):
            scmclient_id = 'git'

        registry = SCMClientRegistry()

        message = re.compile(
            'A SCMClient with an ID of "git" is already registered: '
            'rbtools.clients.git.GitClient'
        )

        with self.assertRaisesRegex(ValueError, message):
            registry.register(MyGitClient)

        self.assertTrue(registry._builtin_loaded)
        self.assertFalse(registry._entrypoints_loaded)
        self.assertNotIn(MySCMClient1, registry)

    def _add_fake_entrypoints(self, entrypoints):
        self.spy_on(entry_points, op=kgb.SpyOpMatchAny([
            {
                'args': (),
                'kwargs': {
                    'group': 'rbtools_scm_clients',
                },
                'op': kgb.SpyOpReturn(entrypoints),
            },
        ]))
