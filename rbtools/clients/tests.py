import os
import re
import sys
import time
from nose import SkipTest
from nose.tools import raises
from random import randint
from textwrap import dedent

from rbtools.api.capabilities import Capabilities
from rbtools.clients import RepositoryInfo
from rbtools.clients.git import GitClient
from rbtools.clients.mercurial import MercurialClient
from rbtools.clients.perforce import PerforceClient, P4Wrapper
from rbtools.clients.svn import SVNRepositoryInfo
from rbtools.tests import OptionsStub
from rbtools.utils.filesystem import load_config_files, make_tempfile
from rbtools.utils.process import execute
from rbtools.utils.testbase import RBTestBase


class SCMClientTests(RBTestBase):
    def setUp(self):
        self.options = OptionsStub()


class GitClientTests(SCMClientTests):
    TESTSERVER = "http://127.0.0.1:8080"

    def _gitcmd(self, command, env=None, split_lines=False,
                ignore_errors=False, extra_ignore_errors=(),
                translate_newlines=True, git_dir=None):
        if git_dir:
            full_command = ['git', '--git-dir=%s/.git' % git_dir]
        else:
            full_command = ['git']

        full_command.extend(command)

        return execute(full_command, env, split_lines, ignore_errors,
                       extra_ignore_errors, translate_newlines)

    def _git_add_file_commit(self, file, data, msg):
        """Add a file to a git repository with the content of data
        and commit with msg.
        """
        foo = open(file, 'w')
        foo.write(data)
        foo.close()
        self._gitcmd(['add', file])
        self._gitcmd(['commit', '-m', msg])

    def setUp(self):
        super(GitClientTests, self).setUp()

        if not self.is_exe_in_path('git'):
            raise SkipTest('git not found in path')

        self.git_dir = self.chdir_tmp()
        self._gitcmd(['init'], git_dir=self.git_dir)
        foo = open(os.path.join(self.git_dir, 'foo.txt'), 'w')
        foo.write(FOO)
        foo.close()

        self._gitcmd(['add', 'foo.txt'])
        self._gitcmd(['commit', '-m', 'initial commit'])

        self.clone_dir = self.chdir_tmp(self.git_dir)
        self._gitcmd(['clone', self.git_dir, self.clone_dir])
        self.client = GitClient(options=self.options)

        self.user_config = {}
        self.configs = []
        self.client.user_config = self.user_config
        self.client.configs = self.configs
        self.options.parent_branch = None

    def test_get_repository_info_simple(self):
        """Test GitClient get_repository_info, simple case"""
        ri = self.client.get_repository_info()
        self.assert_(isinstance(ri, RepositoryInfo))
        self.assertEqual(ri.base_path, '')
        self.assertEqual(ri.path.rstrip("/.git"), self.git_dir)
        self.assertTrue(ri.supports_parent_diffs)
        self.assertFalse(ri.supports_changesets)

    def test_scan_for_server_simple(self):
        """Test GitClient scan_for_server, simple case"""
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assert_(server is None)

    def test_scan_for_server_reviewboardrc(self):
        "Test GitClient scan_for_server, .reviewboardrc case"""
        rc = open(os.path.join(self.clone_dir, '.reviewboardrc'), 'w')
        rc.write('REVIEWBOARD_URL = "%s"' % self.TESTSERVER)
        rc.close()
        self.client.user_config, configs = load_config_files(self.clone_dir)

        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)
        self.assertEqual(server, self.TESTSERVER)

    def test_scan_for_server_property(self):
        """Test GitClient scan_for_server using repo property"""
        self._gitcmd(['config', 'reviewboard.url', self.TESTSERVER])
        ri = self.client.get_repository_info()

        self.assertEqual(self.client.scan_for_server(ri), self.TESTSERVER)

    def test_diff_simple(self):
        """Test GitClient simple diff case"""
        diff = "diff --git a/foo.txt b/foo.txt\n" \
               "index 634b3e8ff85bada6f928841a9f2c505560840b3a..5e98e9540e1" \
               "b741b5be24fcb33c40c1c8069c1fb 100644\n" \
               "--- a/foo.txt\n" \
               "+++ b/foo.txt\n" \
               "@@ -6,7 +6,4 @@ multa quoque et bello passus, dum conderet u" \
               "rbem,\n" \
               " inferretque deos Latio, genus unde Latinum,\n" \
               " Albanique patres, atque altae moenia Romae.\n" \
               " Musa, mihi causas memora, quo numine laeso,\n" \
               "-quidve dolens, regina deum tot volvere casus\n" \
               "-insignem pietate virum, tot adire labores\n" \
               "-impulerit. Tantaene animis caelestibus irae?\n" \
               " \n"
        self.client.get_repository_info()
        self._git_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')

        self.assertEqual(self.client.diff(None), (diff, None))

    def test_diff_simple_multiple(self):
        """Test GitClient simple diff with multiple commits case"""
        diff = "diff --git a/foo.txt b/foo.txt\n" \
               "index 634b3e8ff85bada6f928841a9f2c505560840b3a..63036ed3fca" \
               "fe870d567a14dd5884f4fed70126c 100644\n" \
               "--- a/foo.txt\n" \
               "+++ b/foo.txt\n" \
               "@@ -1,12 +1,11 @@\n" \
               " ARMA virumque cano, Troiae qui primus ab oris\n" \
               "+ARMA virumque cano, Troiae qui primus ab oris\n" \
               " Italiam, fato profugus, Laviniaque venit\n" \
               " litora, multum ille et terris iactatus et alto\n" \
               " vi superum saevae memorem Iunonis ob iram;\n" \
               "-multa quoque et bello passus, dum conderet urbem,\n" \
               "+dum conderet urbem,\n" \
               " inferretque deos Latio, genus unde Latinum,\n" \
               " Albanique patres, atque altae moenia Romae.\n" \
               "+Albanique patres, atque altae moenia Romae.\n" \
               " Musa, mihi causas memora, quo numine laeso,\n" \
               "-quidve dolens, regina deum tot volvere casus\n" \
               "-insignem pietate virum, tot adire labores\n" \
               "-impulerit. Tantaene animis caelestibus irae?\n" \
               " \n"
        self.client.get_repository_info()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('foo.txt', FOO2, 'commit 1')
        self._git_add_file_commit('foo.txt', FOO3, 'commit 1')

        self.assertEqual(self.client.diff(None), (diff, None))

    def test_diff_branch_diverge(self):
        """Test GitClient diff with divergent branches"""
        diff1 = "diff --git a/foo.txt b/foo.txt\n" \
                "index 634b3e8ff85bada6f928841a9f2c505560840b3a..e619c1387f" \
                "5feb91f0ca83194650bfe4f6c2e347 100644\n" \
                "--- a/foo.txt\n" \
                "+++ b/foo.txt\n" \
                "@@ -1,4 +1,6 @@\n" \
                " ARMA virumque cano, Troiae qui primus ab oris\n" \
                "+ARMA virumque cano, Troiae qui primus ab oris\n" \
                "+ARMA virumque cano, Troiae qui primus ab oris\n" \
                " Italiam, fato profugus, Laviniaque venit\n" \
                " litora, multum ille et terris iactatus et alto\n" \
                " vi superum saevae memorem Iunonis ob iram;\n" \
                "@@ -6,7 +8,4 @@ multa quoque et bello passus, dum conderet " \
                "urbem,\n" \
                " inferretque deos Latio, genus unde Latinum,\n" \
                " Albanique patres, atque altae moenia Romae.\n" \
                " Musa, mihi causas memora, quo numine laeso,\n" \
                "-quidve dolens, regina deum tot volvere casus\n" \
                "-insignem pietate virum, tot adire labores\n" \
                "-impulerit. Tantaene animis caelestibus irae?\n" \
                " \n"
        diff2 = "diff --git a/foo.txt b/foo.txt\n" \
                "index 634b3e8ff85bada6f928841a9f2c505560840b3a..5e98e9540e1" \
                "b741b5be24fcb33c40c1c8069c1fb 100644\n" \
                "--- a/foo.txt\n" \
                "+++ b/foo.txt\n" \
                "@@ -6,7 +6,4 @@ multa quoque et bello passus, dum conderet "\
                "urbem,\n" \
                " inferretque deos Latio, genus unde Latinum,\n" \
                " Albanique patres, atque altae moenia Romae.\n" \
                " Musa, mihi causas memora, quo numine laeso,\n" \
                "-quidve dolens, regina deum tot volvere casus\n" \
                "-insignem pietate virum, tot adire labores\n" \
                "-impulerit. Tantaene animis caelestibus irae?\n" \
                " \n"
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._gitcmd(['checkout', '-b', 'mybranch', '--track',
                      'origin/master'])
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')
        self.client.get_repository_info()
        self.assertEqual(self.client.diff(None), (diff1, None))

        self._gitcmd(['checkout', 'master'])
        self.client.get_repository_info()
        self.assertEqual(self.client.diff(None), (diff2, None))

    def test_diff_tracking_no_origin(self):
        """Test GitClient diff with a tracking branch, but no origin remote"""
        diff = "diff --git a/foo.txt b/foo.txt\n" \
               "index 634b3e8ff85bada6f928841a9f2c505560840b3a..5e98e9540e1b" \
               "741b5be24fcb33c40c1c8069c1fb 100644\n" \
               "--- a/foo.txt\n" \
               "+++ b/foo.txt\n" \
               "@@ -6,7 +6,4 @@ multa quoque et bello passus, dum conderet " \
               "urbem,\n" \
               " inferretque deos Latio, genus unde Latinum,\n" \
               " Albanique patres, atque altae moenia Romae.\n" \
               " Musa, mihi causas memora, quo numine laeso,\n" \
               "-quidve dolens, regina deum tot volvere casus\n" \
               "-insignem pietate virum, tot adire labores\n" \
               "-impulerit. Tantaene animis caelestibus irae?\n" \
               " \n"
        self._gitcmd(['remote', 'add', 'quux', self.git_dir])
        self._gitcmd(['fetch', 'quux'])
        self._gitcmd(['checkout', '-b', 'mybranch', '--track', 'quux/master'])
        self._git_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')

        self.client.get_repository_info()

        self.assertEqual(self.client.diff(None), (diff, None))

    def test_diff_local_tracking(self):
        """Test GitClient diff with a local tracking branch"""
        diff = "diff --git a/foo.txt b/foo.txt\n" \
               "index 634b3e8ff85bada6f928841a9f2c505560840b3a..e619c1387f5" \
               "feb91f0ca83194650bfe4f6c2e347 100644\n" \
               "--- a/foo.txt\n" \
               "+++ b/foo.txt\n" \
               "@@ -1,4 +1,6 @@\n" \
               " ARMA virumque cano, Troiae qui primus ab oris\n" \
               "+ARMA virumque cano, Troiae qui primus ab oris\n" \
               "+ARMA virumque cano, Troiae qui primus ab oris\n" \
               " Italiam, fato profugus, Laviniaque venit\n" \
               " litora, multum ille et terris iactatus et alto\n" \
               " vi superum saevae memorem Iunonis ob iram;\n" \
               "@@ -6,7 +8,4 @@ multa quoque et bello passus, dum conderet " \
               "urbem,\n" \
               " inferretque deos Latio, genus unde Latinum,\n" \
               " Albanique patres, atque altae moenia Romae.\n" \
               " Musa, mihi causas memora, quo numine laeso,\n" \
               "-quidve dolens, regina deum tot volvere casus\n" \
               "-insignem pietate virum, tot adire labores\n" \
               "-impulerit. Tantaene animis caelestibus irae?\n" \
               " \n"
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')

        self._gitcmd(['checkout', '-b', 'mybranch', '--track', 'master'])
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')

        self.client.get_repository_info()
        self.assertEqual(self.client.diff(None), (diff, None))

    def test_diff_tracking_override(self):
        """Test GitClient diff with option override for tracking branch"""
        diff = "diff --git a/foo.txt b/foo.txt\n" \
               "index 634b3e8ff85bada6f928841a9f2c505560840b3a..5e98e9540e1" \
               "b741b5be24fcb33c40c1c8069c1fb 100644\n" \
               "--- a/foo.txt\n" \
               "+++ b/foo.txt\n" \
               "@@ -6,7 +6,4 @@ multa quoque et bello passus, dum conderet " \
               "urbem,\n" \
               " inferretque deos Latio, genus unde Latinum,\n" \
               " Albanique patres, atque altae moenia Romae.\n" \
               " Musa, mihi causas memora, quo numine laeso,\n" \
               "-quidve dolens, regina deum tot volvere casus\n" \
               "-insignem pietate virum, tot adire labores\n" \
               "-impulerit. Tantaene animis caelestibus irae?\n" \
               " \n"
        self.options.tracking = 'origin/master'

        self._gitcmd(['remote', 'add', 'bad', self.git_dir])
        self._gitcmd(['fetch', 'bad'])
        self._gitcmd(['checkout', '-b', 'mybranch', '--track', 'bad/master'])

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')

        self.client.get_repository_info()
        self.assertEqual(self.client.diff(None), (diff, None))

    def test_diff_slash_tracking(self):
        """
        Test GitClient diff with tracking branch that has slash in its name.
        """
        diff = "diff --git a/foo.txt b/foo.txt\n" \
               "index 5e98e9540e1b741b5be24fcb33c40c1c8069c1fb..e619c1387f5f" \
               "eb91f0ca83194650bfe4f6c2e347 100644\n" \
               "--- a/foo.txt\n" \
               "+++ b/foo.txt\n" \
               "@@ -1,4 +1,6 @@\n" \
               " ARMA virumque cano, Troiae qui primus ab oris\n" \
               "+ARMA virumque cano, Troiae qui primus ab oris\n" \
               "+ARMA virumque cano, Troiae qui primus ab oris\n" \
               " Italiam, fato profugus, Laviniaque venit\n" \
               " litora, multum ille et terris iactatus et alto\n" \
               " vi superum saevae memorem Iunonis ob iram;\n"
        os.chdir(self.git_dir)
        self._gitcmd(['checkout', '-b', 'not-master'])
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')

        os.chdir(self.clone_dir)
        self._gitcmd(['fetch', 'origin'])
        self._gitcmd(['checkout', '-b', 'my/branch', '--track',
                      'origin/not-master'])
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')

        self.client.get_repository_info()
        self.assertEqual(self.client.diff(None), (diff, None))


class MercurialTestBase(SCMClientTests):

    def setUp(self):
        super(MercurialTestBase, self).setUp()
        self._hg_env = {}

    def _hgcmd(self, command, split_lines=False,
                ignore_errors=False, extra_ignore_errors=(),
                translate_newlines=True, hg_dir=None):
        if hg_dir:
            full_command = ['hg', '--cwd', hg_dir]
        else:
            full_command = ['hg']

        # We're *not* doing `env = env or {}` here because
        # we want the caller to be able to *enable* reading
        # of user and system-level hgrc configuration.
        env = self._hg_env.copy()

        if not env:
            env = {
                'HGRCPATH': os.devnull,
                'HGPLAIN': '1',
            }

        full_command.extend(command)

        return execute(full_command, env, split_lines, ignore_errors,
                       extra_ignore_errors, translate_newlines)

    def _hg_add_file_commit(self, filename, data, msg, branch=None):
        outfile = open(filename, 'w')
        outfile.write(data)
        outfile.close()
        if branch:
            self._hgcmd(['branch', branch])
        self._hgcmd(['add', filename])
        self._hgcmd(['commit', '-m', msg])


class MercurialClientTests(MercurialTestBase):
    TESTSERVER = 'http://127.0.0.1:8080'
    CLONE_HGRC = dedent("""
    [paths]
    default = %(hg_dir)s
    cloned = %(clone_dir)s

    [reviewboard]
    url = %(test_server)s

    [diff]
    git = true
    """).rstrip()

    def setUp(self):
        super(MercurialClientTests, self).setUp()
        if not self.is_exe_in_path('hg'):
            raise SkipTest('hg not found in path')

        self.hg_dir = self.chdir_tmp()
        self._hgcmd(['init'], hg_dir=self.hg_dir)
        foo = open(os.path.join(self.hg_dir, 'foo.txt'), 'w')
        foo.write(FOO)
        foo.close()

        self._hgcmd(['add', 'foo.txt'])
        self._hgcmd(['commit', '-m', 'initial commit'])

        self.clone_dir = self.chdir_tmp(self.hg_dir)
        self._hgcmd(['clone', self.hg_dir, self.clone_dir])
        self.client = MercurialClient(options=self.options)

        clone_hgrc = open(self.clone_hgrc_path, 'wb')
        clone_hgrc.write(self.CLONE_HGRC % {
            'hg_dir': self.hg_dir,
            'clone_dir': self.clone_dir,
            'test_server': self.TESTSERVER,
        })
        clone_hgrc.close()

        self.client.get_repository_info()
        self.user_config = {}
        self.configs = []
        self.client.user_config = self.user_config
        self.client.configs = self.configs
        self.options.parent_branch = None

    @property
    def clone_hgrc_path(self):
        return os.path.join(self.clone_dir, '.hg', 'hgrc')

    @property
    def hgrc_path(self):
        return os.path.join(self.hg_dir, '.hg', 'hgrc')

    def testGetRepositoryInfoSimple(self):
        """Test MercurialClient get_repository_info, simple case"""
        ri = self.client.get_repository_info()

        self.assertTrue(isinstance(ri, RepositoryInfo))
        self.assertEqual('', ri.base_path)

        hgpath = ri.path

        if os.path.basename(hgpath) == '.hg':
            hgpath = os.path.dirname(hgpath)

        self.assertEqual(self.hg_dir, hgpath)
        self.assertTrue(ri.supports_parent_diffs)
        self.assertFalse(ri.supports_changesets)

    def testScanForServerSimple(self):
        """Test MercurialClient scan_for_server, simple case"""
        os.rename(self.clone_hgrc_path,
            os.path.join(self.clone_dir, '._disabled_hgrc'))

        self.client.hgrc = {}
        self.client._load_hgrc()
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assertTrue(server is None)

    def testScanForServerWhenPresentInHgrc(self):
        """Test MercurialClient scan_for_server when present in hgrc"""
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assertEqual(self.TESTSERVER, server)

    def testScanForServerReviewboardrc(self):
        """Test MercurialClient scan_for_server when in .reviewboardrc"""
        rc = open(os.path.join(self.clone_dir, '.reviewboardrc'), 'w')
        rc.write('REVIEWBOARD_URL = "%s"' % self.TESTSERVER)
        rc.close()

        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)
        self.assertEqual(self.TESTSERVER, server)

    def testDiffSimple(self):
        """Test MercurialClient diff, simple case"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')

        diff_result = self.client.diff(None)
        self.assertEqual((EXPECTED_HG_DIFF_0, None), diff_result)

    def testDiffSimpleMultiple(self):
        """Test MercurialClient diff with multiple commits"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3')

        diff_result = self.client.diff(None)

        self.assertEqual((EXPECTED_HG_DIFF_1, None), diff_result)

    def testDiffBranchDiverge(self):
        """Test MercurialClient diff with diverged branch"""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')

        self._hgcmd(['branch', 'diverged'])
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        self.client.get_repository_info()

        self.assertEqual((EXPECTED_HG_DIFF_2, None), self.client.diff(None))

        self._hgcmd(['update', '-C', 'default'])
        self.client.get_repository_info()

        self.assertEqual((EXPECTED_HG_DIFF_3, None), self.client.diff(None))


class MercurialSubversionClientTests(MercurialTestBase):
    TESTSERVER = "http://127.0.0.1:8080"

    def __init__(self, *args, **kwargs):
        self._tmpbase = ''
        self.clone_dir = ''
        self.svn_repo = ''
        self.svn_checkout = ''
        self.client = None
        self._svnserve_pid = 0
        self._max_svnserve_pid_tries = 12
        self._svnserve_port = os.environ.get('SVNSERVE_PORT')
        self._required_exes = ('svnadmin', 'svnserve', 'svn')
        MercurialTestBase.__init__(self, *args, **kwargs)

    def setUp(self):
        super(MercurialSubversionClientTests, self).setUp()
        self._hg_env = {'FOO': 'BAR'}

        for exe in self._required_exes:
            if not self.is_exe_in_path(exe):
                raise SkipTest('missing svn stuff!  giving up!')

        if not self._has_hgsubversion():
            raise SkipTest('unable to use `hgsubversion` extension!  '
                                'giving up!')

        if not self._tmpbase:
            self._tmpbase = self.create_tmp_dir()

        self._create_svn_repo()
        self._fire_up_svnserve()
        self._fill_in_svn_repo()

        try:
            self._get_testing_clone()
        except (OSError, IOError):
            msg = 'could not clone from svn repo!  skipping...'
            raise SkipTest(msg), None, sys.exc_info()[2]

        self._spin_up_client()
        self._stub_in_config_and_options()

    def _has_hgsubversion(self):
        output = self._hgcmd(['svn', '--help'],
                             ignore_errors=True, extra_ignore_errors=(255))

        return not re.search("unknown command ['\"]svn['\"]", output, re.I)

    def tearDown(self):
        super(MercurialSubversionClientTests, self).tearDown()

        os.kill(self._svnserve_pid, 9)

    def _svn_add_file_commit(self, filename, data, msg):
        outfile = open(filename, 'w')
        outfile.write(data)
        outfile.close()
        execute(['svn', 'add', filename])
        execute(['svn', 'commit', '-m', msg])

    def _create_svn_repo(self):
        self.svn_repo = os.path.join(self._tmpbase, 'svnrepo')
        execute(['svnadmin', 'create', self.svn_repo])

    def _fire_up_svnserve(self):
        if not self._svnserve_port:
            self._svnserve_port = str(randint(30000, 40000))

        pid_file = os.path.join(self._tmpbase, 'svnserve.pid')
        execute(['svnserve', '--pid-file', pid_file, '-d',
                 '--listen-port', self._svnserve_port, '-r', self._tmpbase])

        for i in range(0, self._max_svnserve_pid_tries):
            try:
                self._svnserve_pid = int(open(pid_file).read().strip())
                return

            except (IOError, OSError):
                time.sleep(0.25)

        # This will re-raise the last exception, which will be either
        # IOError or OSError if the above fails and this branch is reached
        raise

    def _fill_in_svn_repo(self):
        self.svn_checkout = os.path.join(self._tmpbase, 'checkout.svn')
        execute(['svn', 'checkout', 'file://%s' % self.svn_repo,
                 self.svn_checkout])
        os.chdir(self.svn_checkout)

        for subtree in ('trunk', 'branches', 'tags'):
            execute(['svn', 'mkdir', subtree])

        execute(['svn', 'commit', '-m', 'filling in T/b/t'])
        os.chdir(os.path.join(self.svn_checkout, 'trunk'))

        for i, data in enumerate([FOO, FOO1, FOO2]):
            self._svn_add_file_commit('foo.txt', data, 'foo commit %s' % i)

    def _get_testing_clone(self):
        self.clone_dir = os.path.join(self._tmpbase, 'checkout.hg')
        self._hgcmd([
            'clone', 'svn://127.0.0.1:%s/svnrepo' % self._svnserve_port,
            self.clone_dir,
        ])

    def _spin_up_client(self):
        os.chdir(self.clone_dir)
        self.client = MercurialClient(options=self.options)

    def _stub_in_config_and_options(self):
        self.user_config = {}
        self.configs = []
        self.client.user_config = self.user_config
        self.client.configs = self.configs
        self.options.parent_branch = None

    def testGetRepositoryInfoSimple(self):
        """Test MercurialClient (+svn) get_repository_info, simple case"""
        ri = self.client.get_repository_info()

        self.assertEqual('svn', self.client._type)
        self.assertEqual('/trunk', ri.base_path)
        self.assertEqual('svn://127.0.0.1:%s/svnrepo' % self._svnserve_port,
                        ri.path)

    def testCalculateRepositoryInfo(self):
        """
        Test MercurialClient (+svn) _calculate_hgsubversion_repository_info
        properly determines repository and base paths.

        """
        info = (
            "URL: svn+ssh://testuser@svn.example.net/repo/trunk\n"
            "Repository Root: svn+ssh://testuser@svn.example.net/repo\n"
            "Repository UUID: bfddb570-5023-0410-9bc8-bc1659bf7c01\n"
            "Revision: 9999\n"
            "Node Kind: directory\n"
            "Last Changed Author: user\n"
            "Last Changed Rev: 9999\n"
            "Last Changed Date: 2012-09-05 18:04:28 +0000 (Wed, 05 Sep 2012)")

        repo_info = self.client._calculate_hgsubversion_repository_info(info)

        self.assertEqual(repo_info.path, "svn+ssh://svn.example.net/repo")
        self.assertEqual(repo_info.base_path, "/trunk")

    def testScanForServerSimple(self):
        """Test MercurialClient (+svn) scan_for_server, simple case"""
        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)

        self.assertTrue(server is None)

    def testScanForServerReviewboardrc(self):
        """Test MercurialClient (+svn) scan_for_server in .reviewboardrc"""
        rc_filename = os.path.join(self.clone_dir, '.reviewboardrc')
        rc = open(rc_filename, 'w')
        rc.write('REVIEWBOARD_URL = "%s"' % self.TESTSERVER)
        rc.close()
        self.client.user_config, configs = load_config_files(self.clone_dir)

        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)

        self.assertEqual(self.TESTSERVER, server)

    def testScanForServerProperty(self):
        """Test MercurialClient (+svn) scan_for_server in svn property"""
        os.chdir(self.svn_checkout)
        execute(['svn', 'update'])
        execute(['svn', 'propset', 'reviewboard:url', self.TESTSERVER,
                 self.svn_checkout])
        execute(['svn', 'commit', '-m', 'adding reviewboard:url property'])

        os.chdir(self.clone_dir)
        self._hgcmd(['pull'])
        self._hgcmd(['update', '-C'])

        ri = self.client.get_repository_info()

        self.assertEqual(self.TESTSERVER, self.client.scan_for_server(ri))

    def testDiffSimple(self):
        """Test MercurialClient (+svn) diff, simple case"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO4, 'edit 4')

        self.assertEqual(EXPECTED_HG_SVN_DIFF_0, self.client.diff(None)[0])

    def testDiffSimpleMultiple(self):
        """Test MercurialClient (+svn) diff with multiple commits"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO4, 'edit 4')
        self._hg_add_file_commit('foo.txt', FOO5, 'edit 5')
        self._hg_add_file_commit('foo.txt', FOO6, 'edit 6')

        self.assertEqual(EXPECTED_HG_SVN_DIFF_1, self.client.diff(None)[0])

    def testDiffOfRevision(self):
        """Test MercurialClient (+svn) diff specifying a revision."""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO4, 'edit 4', branch='b')
        self._hg_add_file_commit('foo.txt', FOO5, 'edit 5', branch='b')
        self._hg_add_file_commit('foo.txt', FOO6, 'edit 6', branch='b')
        self._hg_add_file_commit('foo.txt', FOO4, 'edit 7', branch='b')

        self.assertEqual(EXPECTED_HG_SVN_DIFF_0, self.client.diff(['3'])[0])
        self.assertEqual(EXPECTED_HG_SVN_DIFF_1, self.client.diff(['5'])[0])


class SVNClientTests(SCMClientTests):
    def setUp(self):
        super(SVNClientTests, self).setUp()

    def test_relative_paths(self):
        """Testing SVNRepositoryInfo._get_relative_path"""
        info = SVNRepositoryInfo('http://svn.example.com/svn/', '/', '')
        self.assertEqual(info._get_relative_path('/foo', '/bar'), None)
        self.assertEqual(info._get_relative_path('/', '/trunk/myproject'),
                         None)
        self.assertEqual(info._get_relative_path('/trunk/myproject', '/'),
                         '/trunk/myproject')
        self.assertEqual(
            info._get_relative_path('/trunk/myproject', ''),
            '/trunk/myproject')
        self.assertEqual(
            info._get_relative_path('/trunk/myproject', '/trunk'),
            '/myproject')
        self.assertEqual(
            info._get_relative_path('/trunk/myproject', '/trunk/myproject'),
            '/')


class P4WrapperTests(RBTestBase):
    def is_supported(self):
        return True

    def test_counters(self):
        """Testing P4Wrapper.counters"""
        class TestWrapper(P4Wrapper):
            def run_p4(self, cmd, *args, **kwargs):
                return [
                    'a = 1\n',
                    'b = 2\n',
                    'c = 3\n',
                ]

        p4 = TestWrapper()
        info = p4.counters()

        self.assertEqual(len(info), 3)
        self.assertEqual(info['a'], '1')
        self.assertEqual(info['b'], '2')
        self.assertEqual(info['c'], '3')

    def test_info(self):
        """Testing P4Wrapper.info"""
        class TestWrapper(P4Wrapper):
            def run_p4(self, cmd, *args, **kwargs):
                return [
                    'User name: myuser\n',
                    'Client name: myclient\n',
                    'Client host: myclient.example.com\n',
                    'Client root: /path/to/client\n',
                    'Server uptime: 111:43:38\n',
                ]

        p4 = TestWrapper()
        info = p4.info()

        self.assertEqual(len(info), 5)
        self.assertEqual(info['User name'], 'myuser')
        self.assertEqual(info['Client name'], 'myclient')
        self.assertEqual(info['Client host'], 'myclient.example.com')
        self.assertEqual(info['Client root'], '/path/to/client')
        self.assertEqual(info['Server uptime'], '111:43:38')


class PerforceClientTests(SCMClientTests):
    class P4DiffTestWrapper(P4Wrapper):
        def __init__(self):
            self._timestamp = time.mktime(time.gmtime(0))

        def describe(self, changenum, password):
            return [
                'Change 12345 by joe@example on 2013/01/02 22:33:44 '
                '*pending*\n',
                '\n',
                '\tThis is a test.\n',
                '\n',
                'Affected files ...\n',
                '\n',
            ] + [
                '... %s %s\n' % (depot_path, info['action'])
                for depot_path, info in self.repo_files.iteritems()
                if info['change'] == changenum
            ]

        def fstat(self, depot_path, fields=[]):
            assert depot_path in self.fstat_files

            fstat_info = self.fstat_files[depot_path]

            for field in fields:
                assert field in fstat_info

            return fstat_info

        def opened(self, changenum):
            return [
                '%s - %s change %s (text)\n'
                % (depot_path, info['action'], changenum)
                for depot_path, info in self.repo_files.iteritems()
                if info['change'] == changenum
            ]

        def print_file(self, depot_path, out_file):
            assert depot_path in self.repo_files

            fp = open(out_file, 'w')
            fp.write(self.repo_files[depot_path]['text'])
            fp.close()

        def where(self, depot_path):
            assert depot_path in self.where_files

            return [{
                'path': self.where_files[depot_path],
            }]

        def run_p4(self, *args, **kwargs):
            assert False

    @raises(SystemExit)
    def test_error_on_revision_range(self):
        """Testing PerforceClient with --revision-range causes an exit"""
        self.options.revision_range = "12345"
        client = PerforceClient(options=self.options)
        client.check_options()

    def test_scan_for_server_counter_with_reviewboard_url(self):
        """Testing PerforceClient.scan_for_server_counter with reviewboard.url"""
        RB_URL = 'http://reviewboard.example.com/'

        class TestWrapper(P4Wrapper):
            def counters(self):
                return {
                    'reviewboard.url': RB_URL,
                    'foo': 'bar',
                }

        client = PerforceClient(TestWrapper)
        url = client.scan_for_server_counter(None)

        self.assertEqual(url, RB_URL)

    def test_repository_info(self):
        """Testing PerforceClient.get_repository_info"""
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def info(self):
                return {
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = PerforceClient(TestWrapper)
        info = client.get_repository_info()

        self.assertNotEqual(info, None)
        self.assertEqual(info.path, SERVER_PATH)
        self.assertEqual(client.p4d_version, (2012, 2))

    def test_scan_for_server_counter_with_reviewboard_url_encoded(self):
        """Testing PerforceClient.scan_for_server_counter with encoded reviewboard.url.http:||"""
        URL_KEY = 'reviewboard.url.http:||reviewboard.example.com/'
        RB_URL = 'http://reviewboard.example.com/'

        class TestWrapper(P4Wrapper):
            def counters(self):
                return {
                    URL_KEY: '1',
                    'foo': 'bar',
                }

        client = PerforceClient(TestWrapper)
        url = client.scan_for_server_counter(None)

        self.assertEqual(url, RB_URL)

    def test_diff_with_changenum(self):
        """Testing PerforceClient.diff with changenums"""
        client = self._build_client()
        client.p4.repo_files = {
            '//mydepot/test/README#2': {
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            '//mydepot/test/README#3': {
                'action': 'edit',
                'change': '',
                'text': 'This is a mess.\n',
            },
            '//mydepot/test/COPYING#1': {
                'action': 'add',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
            '//mydepot/test/Makefile#3': {
                'action': 'delete',
                'change': '12345',
                'text': 'all: all\n',
            },
        }

        readme_file = make_tempfile()
        copying_file = make_tempfile()
        client.p4.print_file('//mydepot/test/README#3', readme_file)
        client.p4.print_file('//mydepot/test/COPYING#1', copying_file)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/COPYING': copying_file,
        }

        diff = client.diff(['12345'])
        self._compare_diff(diff,
            '--- //mydepot/test/README\t//mydepot/test/README#2\n'
            '+++ //mydepot/test/README\t1970-01-01 00:00:00\n'
            '@@ -1 +1 @@\n'
            '-This is a test.\n'
            '+This is a mess.\n'
            '--- //mydepot/test/COPYING\t//mydepot/test/COPYING#1\n'
            '+++ //mydepot/test/COPYING\t1970-01-01 00:00:00\n'
            '@@ -0,0 +1 @@\n'
            '+Copyright 2013 Joe User.\n'
            '--- //mydepot/test/Makefile\t//mydepot/test/Makefile#3\n'
            '+++ //mydepot/test/Makefile\t1970-01-01 00:00:00\n'
            '@@ -1 +0,0 @@\n'
            '-all: all\n')

    def test_diff_with_moved_files_cap_on(self):
        """Testing PerforceClient.diff with moved files and capability on"""
        self._test_diff_with_moved_files(
            'Moved from: //mydepot/test/README\n'
            'Moved to: //mydepot/test/README-new\n'
            '--- //mydepot/test/README\t//mydepot/test/README#2\n'
            '+++ //mydepot/test/README-new\t1970-01-01 00:00:00\n'
            '@@ -1 +1 @@\n'
            '-This is a test.\n'
            '+This is a mess.\n'
            '==== //mydepot/test/COPYING#2 ==MV== '
            '//mydepot/test/COPYING-new ====\n\n',
            caps={
                'diffs': {
                    'moved_files': True
                }
            })

    def test_diff_with_moved_files_cap_off(self):
        """Testing PerforceClient.diff with moved files and capability off"""
        self._test_diff_with_moved_files(
            '--- //mydepot/test/README-new\t//mydepot/test/README-new#1\n'
            '+++ //mydepot/test/README-new\t1970-01-01 00:00:00\n'
            '@@ -0,0 +1 @@\n'
            '+This is a mess.\n'
            '--- //mydepot/test/README\t//mydepot/test/README#2\n'
            '+++ //mydepot/test/README\t1970-01-01 00:00:00\n'
            '@@ -1 +0,0 @@\n'
            '-This is a test.\n'
            '--- //mydepot/test/COPYING-new\t//mydepot/test/COPYING-new#1\n'
            '+++ //mydepot/test/COPYING-new\t1970-01-01 00:00:00\n'
            '@@ -0,0 +1 @@\n'
            '+Copyright 2013 Joe User.\n'
            '--- //mydepot/test/COPYING\t//mydepot/test/COPYING#2\n'
            '+++ //mydepot/test/COPYING\t1970-01-01 00:00:00\n'
            '@@ -1 +0,0 @@\n'
            '-Copyright 2013 Joe User.\n')

    def _test_diff_with_moved_files(self, expected_diff, caps={}):
        client = self._build_client()
        client.capabilities = Capabilities(caps)
        client.p4.repo_files = {
            '//mydepot/test/README#2': {
                'action': 'move/delete',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            '//mydepot/test/README-new#1': {
                'action': 'move/add',
                'change': '12345',
                'text': 'This is a mess.\n',
            },
            '//mydepot/test/COPYING#2': {
                'action': 'move/delete',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
            '//mydepot/test/COPYING-new#1': {
                'action': 'move/add',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
        }

        readme_file = make_tempfile()
        copying_file = make_tempfile()
        readme_file_new = make_tempfile()
        copying_file_new = make_tempfile()
        client.p4.print_file('//mydepot/test/README#2', readme_file)
        client.p4.print_file('//mydepot/test/COPYING#2', copying_file)
        client.p4.print_file('//mydepot/test/README-new#1', readme_file_new)
        client.p4.print_file('//mydepot/test/COPYING-new#1', copying_file_new)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/COPYING': copying_file,
            '//mydepot/test/README-new': readme_file_new,
            '//mydepot/test/COPYING-new': copying_file_new,
        }

        client.p4.fstat_files = {
            '//mydepot/test/README': {
                'clientFile': readme_file,
                'movedFile': '//mydepot/test/README-new',
            },
            '//mydepot/test/README-new': {
                'clientFile': readme_file_new,
                'depotFile': '//mydepot/test/README-new',
            },
            '//mydepot/test/COPYING': {
                'clientFile': copying_file,
                'movedFile': '//mydepot/test/COPYING-new',
            },
            '//mydepot/test/COPYING-new': {
                'clientFile': copying_file_new,
                'depotFile': '//mydepot/test/COPYING-new',
            },
        }

        diff = client.diff(['12345'])
        self._compare_diff(diff, expected_diff)

    def _build_client(self):
        self.options.p4_client = 'myclient'
        self.options.p4_port = 'perforce.example.com:1666'
        self.options.p4_passwd = ''
        client = PerforceClient(self.P4DiffTestWrapper, options=self.options)
        client.p4d_version = (2012, 2)
        return client

    def _compare_diff(self, diff, expected_diff):
        self.assertNotEqual(diff[0], None)
        self.assertEqual(diff[1], None)
        diff_content = re.sub('\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                              '1970-01-01 00:00:00',
                              diff[0])
        self.assertEqual(diff_content, expected_diff)
        self.assertEqual(diff[1], None)


FOO = """\
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

FOO1 = """\
ARMA virumque cano, Troiae qui primus ab oris
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
vi superum saevae memorem Iunonis ob iram;
multa quoque et bello passus, dum conderet urbem,
inferretque deos Latio, genus unde Latinum,
Albanique patres, atque altae moenia Romae.
Musa, mihi causas memora, quo numine laeso,

"""

FOO2 = """\
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

FOO3 = """\
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

FOO4 = """\
Italiam, fato profugus, Laviniaque venit
litora, multum ille et terris iactatus et alto
vi superum saevae memorem Iunonis ob iram;
dum conderet urbem,





inferretque deos Latio, genus unde Latinum,
Albanique patres, atque altae moenia Romae.
Musa, mihi causas memora, quo numine laeso,

"""

FOO5 = """\
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

FOO6 = """\
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

EXPECTED_HG_DIFF_0 = """\
diff --git a/foo.txt b/foo.txt
--- a/foo.txt
+++ b/foo.txt
@@ -6,7 +6,4 @@
 inferretque deos Latio, genus unde Latinum,
 Albanique patres, atque altae moenia Romae.
 Musa, mihi causas memora, quo numine laeso,
-quidve dolens, regina deum tot volvere casus
-insignem pietate virum, tot adire labores
-impulerit. Tantaene animis caelestibus irae?
 \n"""

EXPECTED_HG_DIFF_1 = """\
diff --git a/foo.txt b/foo.txt
--- a/foo.txt
+++ b/foo.txt
@@ -1,12 +1,11 @@
+ARMA virumque cano, Troiae qui primus ab oris
 ARMA virumque cano, Troiae qui primus ab oris
 Italiam, fato profugus, Laviniaque venit
 litora, multum ille et terris iactatus et alto
 vi superum saevae memorem Iunonis ob iram;
-multa quoque et bello passus, dum conderet urbem,
+dum conderet urbem,
 inferretque deos Latio, genus unde Latinum,
 Albanique patres, atque altae moenia Romae.
+Albanique patres, atque altae moenia Romae.
 Musa, mihi causas memora, quo numine laeso,
-quidve dolens, regina deum tot volvere casus
-insignem pietate virum, tot adire labores
-impulerit. Tantaene animis caelestibus irae?
 \n"""

EXPECTED_HG_DIFF_2 = """\
diff --git a/foo.txt b/foo.txt
--- a/foo.txt
+++ b/foo.txt
@@ -1,3 +1,5 @@
+ARMA virumque cano, Troiae qui primus ab oris
+ARMA virumque cano, Troiae qui primus ab oris
 ARMA virumque cano, Troiae qui primus ab oris
 Italiam, fato profugus, Laviniaque venit
 litora, multum ille et terris iactatus et alto
"""

EXPECTED_HG_DIFF_3 = """\
diff --git a/foo.txt b/foo.txt
--- a/foo.txt
+++ b/foo.txt
@@ -6,7 +6,4 @@
 inferretque deos Latio, genus unde Latinum,
 Albanique patres, atque altae moenia Romae.
 Musa, mihi causas memora, quo numine laeso,
-quidve dolens, regina deum tot volvere casus
-insignem pietate virum, tot adire labores
-impulerit. Tantaene animis caelestibus irae?
 \n"""

EXPECTED_HG_SVN_DIFF_0 = """\
Index: foo.txt
===================================================================
--- foo.txt\t(revision 4)
+++ foo.txt\t(working copy)
@@ -1,4 +1,1 @@
-ARMA virumque cano, Troiae qui primus ab oris
-ARMA virumque cano, Troiae qui primus ab oris
-ARMA virumque cano, Troiae qui primus ab oris
 Italiam, fato profugus, Laviniaque venit
@@ -6,3 +3,8 @@
 vi superum saevae memorem Iunonis ob iram;
-multa quoque et bello passus, dum conderet urbem,
+dum conderet urbem,
+
+
+
+
+
 inferretque deos Latio, genus unde Latinum,
"""

EXPECTED_HG_SVN_DIFF_1 = """\
Index: foo.txt
===================================================================
--- foo.txt\t(revision 4)
+++ foo.txt\t(working copy)
@@ -1,2 +1,1 @@
-ARMA virumque cano, Troiae qui primus ab oris
 ARMA virumque cano, Troiae qui primus ab oris
@@ -6,6 +5,6 @@
 vi superum saevae memorem Iunonis ob iram;
-multa quoque et bello passus, dum conderet urbem,
-inferretque deos Latio, genus unde Latinum,
-Albanique patres, atque altae moenia Romae.
-Musa, mihi causas memora, quo numine laeso,
+dum conderet urbem, inferretque deos Latio, genus
+unde Latinum, Albanique patres, atque altae
+moenia Romae. Albanique patres, atque altae
+moenia Romae. Musa, mihi causas memora, quo numine laeso,
 \n"""
