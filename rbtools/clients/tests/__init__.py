"""Unit tests for RBTools clients."""

from __future__ import unicode_literals

import os
import shutil

from rbtools.deprecation import RemovedInRBTools40Warning
from rbtools.tests import OptionsStub
from rbtools.testing import TestCase
from rbtools.utils.filesystem import make_tempdir


class SCMClientTestCase(TestCase):
    """Base class for RBTools SCM client unit tests.

    This takes care of suite-wide and per-test setup common to SCM unit tests.

    During suite setup, :py:meth:`setup_checkout` is called, which can handle
    cloning/checking out as many or as few repositories needed for the suite.
    Those will be backed up and then restored for each test run, avoiding the
    cost of repeated clones/checkouts.

    Version Changed:
        3.0:
        * Renamed from ``SCMClientTests`` to ``SCMClientTestCase``.
        * Added support for centralized clone/checkout management and caching.
    """

    #: The main checkout directory used by tests.
    #:
    #: This will store the result of :py:meth:`setup_checkout`. It may be
    #: ``None``.
    #:
    #: Version Added:
    #:     3.0
    #:
    #: Type:
    #:     unicode
    checkout_dir = None

    @classmethod
    def setUpClass(cls):
        super(SCMClientTestCase, cls).setUpClass()

        cls.testdata_dir = os.path.join(os.path.dirname(__file__), 'testdata')

        # We'll set up a common suite-wide temp directory for storing both the
        # cached copy of the checkout(s) needed by the suite, and a working
        # area copy (which unit tests can modify).
        #
        # To ensure paths are always correct, checkouts will be placed in the
        # working directory, and then moved to the "main" directory.
        cls._checkout_base_dir = make_tempdir(track=False)
        cls._checkout_cache_dir = os.path.join(cls._checkout_base_dir,
                                               'cache')
        cls._checkout_working_dir = os.path.join(cls._checkout_base_dir,
                                                 'working')

        cls.checkout_dir = cls.setup_checkout(cls._checkout_working_dir)

        if cls.checkout_dir:
            shutil.move(cls._checkout_working_dir, cls._checkout_cache_dir)

    @classmethod
    def tearDownClass(cls):
        super(SCMClientTestCase, cls).tearDownClass()

        shutil.rmtree(cls._checkout_base_dir)

    @classmethod
    def setup_checkout(cls, checkout_dir):
        """Populate any clones/checkouts needed by the test suite.

        Subclasses can override this to populate as many or as few checkouts
        needed by the suite. Checkouts must either be in ``checkout_dir`, or
        in subdirectories inside of it. They're responsible for the creation
        of ``checkout_dir``, if it's to be used.

        This is also a good place to set any class-wide variables pointing to
        paths or state surrounding the repository, or to populate initial
        content for repositories.

        Implementations should return ``None`` if they're unable to checkout
        a repository (for instance, if the SCM's tools are not available).

        Version Added:
            3.0

        Args:
            checkout_dir (unicode):
                The top-level directory in which checkouts should be placed.

        Returns:
            unicode:
            The main checkout directory. If multiple checkouts are created,
            return only the primary one that unit tests will be working with.

            This can be ``None`` if a checkout cannot or should not be
            populated.
        """
        return None

    def setUp(self):
        super(SCMClientTestCase, self).setUp()

        self.options = OptionsStub()

        if self.checkout_dir:
            # Copy over any main/backup repositories back into the working
            # directory, so tests can manipulate it.
            if os.path.exists(self._checkout_working_dir):
                shutil.rmtree(self._checkout_working_dir)

            shutil.copytree(self._checkout_cache_dir,
                            self._checkout_working_dir)

            # Make sure any commands that are run default to working out of
            # the primary checkout directory.
            os.chdir(self.checkout_dir)


class SCMClientTests(SCMClientTestCase):
    """Legacy class for SCM client test suites.

    Deprecated:
        3.0:
        Subclasses should use :py:class:`SCMClientTestCase` instead.
    """

    @classmethod
    def setUpClass(cls):
        RemovedInRBTools40Warning.warn(
            '%r should subclass rbtools.clients.tests.SCMClientTestCase '
            'instead of SCMClientTests.'
            % cls)

        super(SCMClientTests, cls).setUpClass()


FOO = b"""\
ARMA virumque cano, Troiae qui primus ab oris
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
vi superum saevae memorem Iunonis ob iram;
multa quoque et bello passus, dum conderet urbem,
inferretque deos Latio, genus unde Latinum,
Albanique patres, atque altae moenia Romae.
Musa, mihi causas memora, quo numine laeso,
quidve dolens, regina deum tot volvere casus
insignem pietate virum, tot adire labores
impulerit. Tantaene animis caelestibus irae?

"""

FOO1 = b"""\
ARMA virumque cano, Troiae qui primus ab oris
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
vi superum saevae memorem Iunonis ob iram;
multa quoque et bello passus, dum conderet urbem,
inferretque deos Latio, genus unde Latinum,
Albanique patres, atque altae moenia Romae.
Musa, mihi causas memora, quo numine laeso,

"""

FOO2 = b"""\
ARMA virumque cano, Troiae qui primus ab oris
ARMA virumque cano, Troiae qui primus ab oris
ARMA virumque cano, Troiae qui primus ab oris
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
vi superum saevae memorem Iunonis ob iram;
multa quoque et bello passus, dum conderet urbem,
inferretque deos Latio, genus unde Latinum,
Albanique patres, atque altae moenia Romae.
Musa, mihi causas memora, quo numine laeso,

"""

FOO3 = b"""\
ARMA virumque cano, Troiae qui primus ab oris
ARMA virumque cano, Troiae qui primus ab oris
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
vi superum saevae memorem Iunonis ob iram;
dum conderet urbem,
inferretque deos Latio, genus unde Latinum,
Albanique patres, atque altae moenia Romae.
Albanique patres, atque altae moenia Romae.
Musa, mihi causas memora, quo numine laeso,

"""

FOO4 = b"""\
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
vi superum saevae memorem Iunonis ob iram;
dum conderet urbem,





inferretque deos Latio, genus unde Latinum,
Albanique patres, atque altae moenia Romae.
Musa, mihi causas memora, quo numine laeso,

"""

FOO5 = b"""\
litora, multum ille et terris iactatus et alto
Italiam, fato profugus, Laviniaque venit
vi superum saevae memorem Iunonis ob iram;
dum conderet urbem,
Albanique patres, atque altae moenia Romae.
Albanique patres, atque altae moenia Romae.
Musa, mihi causas memora, quo numine laeso,
inferretque deos Latio, genus unde Latinum,

ARMA virumque cano, Troiae qui primus ab oris
ARMA virumque cano, Troiae qui primus ab oris
"""

FOO6 = b"""\
ARMA virumque cano, Troiae qui primus ab oris
ARMA virumque cano, Troiae qui primus ab oris
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
vi superum saevae memorem Iunonis ob iram;
dum conderet urbem, inferretque deos Latio, genus
unde Latinum, Albanique patres, atque altae
moenia Romae. Albanique patres, atque altae
moenia Romae. Musa, mihi causas memora, quo numine laeso,

"""
