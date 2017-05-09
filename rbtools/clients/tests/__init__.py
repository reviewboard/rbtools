"""Unit tests for RBTools clients."""

from __future__ import unicode_literals

import os

from rbtools.tests import OptionsStub
from rbtools.utils.testbase import RBTestBase


class SCMClientTests(RBTestBase):
    """Base class for RBTools client unit tests."""

    def setUp(self):
        super(SCMClientTests, self).setUp()

        self.options = OptionsStub()
        self.testdata_dir = os.path.join(os.path.dirname(__file__), 'testdata')


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
