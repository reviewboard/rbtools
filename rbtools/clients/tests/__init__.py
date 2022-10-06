"""Unit tests for RBTools clients."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, Generic, Optional, Type, TypeVar
from unittest import SkipTest

import kgb
from typing_extensions import Final, TypeAlias

from rbtools.api.capabilities import Capabilities
from rbtools.clients import BaseSCMClient
from rbtools.clients.errors import SCMClientDependencyError
from rbtools.deprecation import RemovedInRBTools40Warning
from rbtools.diffs.tools.errors import MissingDiffToolError
from rbtools.testing import TestCase
from rbtools.utils.filesystem import make_tempdir


_TestSCMClientType = TypeVar('_TestSCMClientType',
                             bound=BaseSCMClient,
                             covariant=True)
_TestSCMClientOptions: TypeAlias = Dict[str, Any]


class SCMClientTestCase(Generic[_TestSCMClientType],
                        kgb.SpyAgency,
                        TestCase):
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

    #: Default options always set for SCMClients.
    #:
    #: These will be set by :py:meth:`build_client` unless overridden.
    #:
    #: Version Added:
    #:     4.0
    #:
    #: Type:
    #:     dict
    DEFAULT_SCMCLIENT_OPTIONS: Final[_TestSCMClientOptions] = {
        'debug': True,
        'description': None,
        'disable_proxy': False,
        'guess_description': False,
        'guess_summary': False,
        'parent_branch': None,
        'password': None,
        'repository_url': None,
        'summary': None,
        'tracking': None,
        'username': None,
    }

    #: The client class.
    #:
    #: This is required by :py:meth:`build_client`.
    #:
    #: Version Added:
    #:     4.0
    #:
    #: Type:
    #:     type
    scmclient_cls: Optional[Type[_TestSCMClientType]] = None

    #: Custom default options for SCMClients.
    #:
    #: These will be set by :py:meth:`build_client` unless overridden,
    #: taking precedence after :py:attr:`DEFAULT_SCMCLIENT_OPTIONS`.
    #:
    #: Version Added:
    #:     4.0
    default_scmclient_options: _TestSCMClientOptions = {}

    #: Custom default capabilities for SCMClients.
    #:
    #: These will be set by :py:meth:`build_client` unless overridden.
    #:
    #: Version Added:
    #:     4.0
    default_scmclient_caps: Dict[str, Any] = {}

    #: The main checkout directory used by tests.
    #:
    #: This will store the result of :py:meth:`setup_checkout`. It may be
    #: ``None``.
    #:
    #: Version Added:
    #:     3.0
    #:
    #: Type:
    #:     str
    checkout_dir: Optional[str] = None

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
    def setup_checkout(
        cls,
        checkout_dir: str,
    ) -> Optional[str]:
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
            checkout_dir (str):
                The top-level directory in which checkouts should be placed.

        Returns:
            str:
            The main checkout directory. If multiple checkouts are created,
            return only the primary one that unit tests will be working with.

            This can be ``None`` if a checkout cannot or should not be
            populated.
        """
        return None

    def setUp(self):
        super(SCMClientTestCase, self).setUp()

        self.options = argparse.Namespace(
            **dict(self.DEFAULT_SCMCLIENT_OPTIONS,
                   **self.default_scmclient_options))

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

    def build_client(
        self,
        *,
        options: _TestSCMClientOptions = {},
        caps: Dict[str, Any] = {},
        client_kwargs: Dict[str, Any] = {},
        setup: bool = True,
        allow_dep_checks: bool = True,
        skip_if_deps_missing: bool = True,
        needs_diff: bool = False,
    ) -> _TestSCMClientType:
        """Build a client for testing.

        This gives the test a lot of control over the setup of the client
        and what checks can be performed.

        If a test needs to use diff functionality, it must specify
        ``needs_diff=True`` in order to pre-cache some state. The test will
        then be skipped if a compatible tool is not installed. Failing to
        set this and then creating a diff will result in an error.

        Version Added:
            4.0

        Args:
            options (dict, optional):
                Parsed command line options to pass to the client class.

                By default, :py:attr:`DEFAULT_SCMCLIENT_OPTIONS` and then
                :py:attr:`default_scmclient_options` will be set. ``options``
                may override anything in these.

            caps (dict, optional):
                Custom capabilities to simulate retrieving from the server.

                By defaut, :py:attr:`default_scmclient_caps` will be set.
                ``caps`` may override anything in these. Dictionaries will
                *not* be merged recursively.

            client_kwargs (dict, optional):
                Keyword arguments to pass to the client class.

            setup (bool, optional):
                Whether to call
                :py:meth:`~rbtools.clients.perforce.SCMClient.setup` on the
                client.

            allow_dep_checks (bool, optional):
                Whether to allow :py:meth:`~rbtools.clients.perforce.SCMClient.
                check_dependencies` to run on the client.

            skip_if_deps_missing (bool, optional):
                Whether to skip the unit test if dependencies are missing.

            needs_diff (bool, optional):
                Whether the test needs to work with diffs.

                If ``True``, and a compatible diff tool is not available, the
                test will be skipped.

                If ``False`` (the default), attempting to create a diff will
                result in an error.

        Returns:
            rbtools.clients.base.scmclient.BaseSCMClient:
            The client instance.
        """
        assert self.scmclient_cls is not None

        # Set any options from the caller.
        cmd_options = self.options

        for key, value in options.items():
            setattr(cmd_options, key, value)

        client = self.scmclient_cls(options=cmd_options, **client_kwargs)

        if caps or self.default_scmclient_caps:
            client.capabilities = Capabilities(
                dict(self.default_scmclient_caps, **caps))

        if not allow_dep_checks:
            self.spy_on(client.check_dependencies, call_original=False)

        if setup:
            try:
                client.setup()
            except SCMClientDependencyError as e:
                if skip_if_deps_missing:
                    raise SkipTest(str(e))
                else:
                    raise

        if needs_diff:
            # This will both cache the diff tool (so tests don't have to
            # account for the checks), and skip if not present.
            try:
                client.get_diff_tool()
            except MissingDiffToolError as e:
                raise SkipTest(
                    'A compatible diff tool (%s) is required for this test.'
                    % (', '.join(e.compatible_diff_tool_names)))
        else:
            # Make sure the caller never calls diff(). That's a test error.
            self.spy_on(
                client.diff,
                op=kgb.SpyOpRaise(Exception(
                    'This unit test called %s.diff(), but did not pass '
                    'needs_diff=True to build_client()!'
                    % type(client).__name__)))

        return client

    def normalize_diff_result(
        self,
        diff_result: Dict[str, Optional[bytes]],
        *,
        date_format: str = '%Y-%m-%d %H:%M:%S'
    ) -> Dict[str, Optional[bytes]]:
        """Normalize a diff result for comparison.

        This will ensure that dates are all normalized to a fixed date
        string, making it possible to compare for equality.

        Version Added:
            4.0

        Args:
            diff_result (dict):
                The diff result.

            date_format (str, optional):
                The optional date string format used to match and generate
                timestamps.

        Returns:
            dict:
            The normalized diff result.
        """
        self.assertIsInstance(diff_result, dict)

        format_patterns: Dict[bytes, bytes] = {
            b'%H': br'\d{2}',
            b'%M': br'\d{2}',
            b'%S': br'\d{2}',
            b'%Y': br'\d{4}',
            b'%b': br'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
            b'%d': br'\d{1,2}',
            b'%f': br'\d{6,9}',
            b'%m': br'\d{2}',
            b'%z': br'[-+]\d{4}(?:\d{2}(?:\.\d{6})?)?'
        }

        date_re = re.compile(
            re.sub(b'|'.join(format_patterns.keys()),
                   lambda m: format_patterns[m.group(0)],
                   date_format.encode('utf-8')))

        new_date = (
            datetime(2022, 1, 2, 12, 34, 56, tzinfo=timezone.utc)
            .strftime(date_format)
            .encode('utf-8')
        )

        for key in ('diff', 'parent_diff'):
            diff = diff_result.get(key)

            if diff:
                diff_result[key] = date_re.sub(new_date, diff)

        return diff_result


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
