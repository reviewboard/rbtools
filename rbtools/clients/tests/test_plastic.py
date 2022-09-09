"""Unit tests for PlasticClient."""

import kgb

from rbtools.clients.errors import SCMClientDependencyError
from rbtools.clients.tests import SCMClientTestCase
from rbtools.clients.plastic import PlasticClient
from rbtools.utils.checks import check_install


class PlasticClientTests(SCMClientTestCase):
    """Unit tests for PlasticClient."""

    scmclient_cls = PlasticClient

    def test_check_dependencies_with_found(self):
        """Testing PlasticClient.check_dependencies with cm found"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['cm', 'version'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cm', 'version'])

    def test_check_dependencies_with_missing(self):
        """Testing PlasticClient.check_dependencies with dependencies
        missing
        """
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools ('cm') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['cm', 'version'])
