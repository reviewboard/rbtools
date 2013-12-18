import os
import re
import sys
import time
from hashlib import md5
from random import randint
from tempfile import mktemp
from textwrap import dedent

from nose import SkipTest
from nose.tools import raises

from rbtools.api.capabilities import Capabilities
from rbtools.clients import RepositoryInfo
from rbtools.clients.bazaar import BazaarClient
from rbtools.clients.errors import OptionsCheckError, InvalidRevisionSpecError
from rbtools.clients.git import GitClient
from rbtools.clients.mercurial import MercurialClient
from rbtools.clients.perforce import PerforceClient, P4Wrapper
from rbtools.clients.svn import SVNRepositoryInfo, SVNClient
from rbtools.tests import OptionsStub
from rbtools.utils.filesystem import load_config_files, make_tempfile
from rbtools.utils.process import execute
from rbtools.utils.testbase import RBTestBase


class SCMClientTests(RBTestBase):
    def setUp(self):
        super(SCMClientTests, self).setUp()

        self.options = OptionsStub()

        self.clients_dir = os.path.dirname(__file__)


class GitClientTests(SCMClientTests):
    TESTSERVER = "http://127.0.0.1:8080"

    def _run_git(self, command):
        return execute(['git'] + command, env=None, split_lines=False,
                       ignore_errors=False, extra_ignore_errors=(),
                       translate_newlines=True)

    def _git_add_file_commit(self, file, data, msg):
        """Add a file to a git repository with the content of data
        and commit with msg.
        """
        foo = open(file, 'w')
        foo.write(data)
        foo.close()
        self._run_git(['add', file])
        self._run_git(['commit', '-m', msg])

    def _git_get_head(self):
        return self._run_git(['rev-parse', 'HEAD']).strip()

    def setUp(self):
        super(GitClientTests, self).setUp()

        if not self.is_exe_in_path('git'):
            raise SkipTest('git not found in path')

        self.set_user_home(os.path.join(self.clients_dir, 'homedir'))
        self.git_dir = os.path.join(self.clients_dir, 'testdata', 'git-repo')

        self.clone_dir = self.chdir_tmp()
        self._run_git(['clone', self.git_dir, self.clone_dir])
        self.client = GitClient(options=self.options)

        self.user_config = {}
        self.configs = []
        self.client.user_config = self.user_config
        self.client.configs = self.configs
        self.options.parent_branch = None

    def test_get_repository_info_simple(self):
        """Testing GitClient get_repository_info, simple case"""
        ri = self.client.get_repository_info()
        self.assertTrue(isinstance(ri, RepositoryInfo))
        self.assertEqual(ri.base_path, '')
        self.assertEqual(ri.path.rstrip("/.git"), self.git_dir)
        self.assertTrue(ri.supports_parent_diffs)
        self.assertFalse(ri.supports_changesets)

    def test_scan_for_server_simple(self):
        """Testing GitClient scan_for_server, simple case"""
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assertTrue(server is None)

    def test_scan_for_server_reviewboardrc(self):
        "Testing GitClient scan_for_server, .reviewboardrc case"""
        rc = open(os.path.join(self.clone_dir, '.reviewboardrc'), 'w')
        rc.write('REVIEWBOARD_URL = "%s"' % self.TESTSERVER)
        rc.close()
        self.client.user_config, configs = load_config_files(self.clone_dir)

        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)
        self.assertEqual(server, self.TESTSERVER)

    def test_scan_for_server_property(self):
        """Testing GitClient scan_for_server using repo property"""
        self._run_git(['config', 'reviewboard.url', self.TESTSERVER])
        ri = self.client.get_repository_info()

        self.assertEqual(self.client.scan_for_server(ri), self.TESTSERVER)

    def test_diff_simple(self):
        """Testing GitClient simple diff case"""
        self.client.get_repository_info()
        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 3)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)

    def test_diff_simple_multiple(self):
        """Testing GitClient simple diff with multiple commits case"""
        self.client.get_repository_info()

        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('foo.txt', FOO2, 'commit 1')
        self._git_add_file_commit('foo.txt', FOO3, 'commit 1')

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 3)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'c9a31264f773406edff57a8ed10d9acc')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)

    def test_diff_branch_diverge(self):
        """Testing GitClient diff with divergent branches"""
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._run_git(['checkout', '-b', 'mybranch', '--track',
                      'origin/master'])
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')
        self.client.get_repository_info()

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 3)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'cfb79a46f7a35b07e21765608a7852f7')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)

        self._run_git(['checkout', 'master'])
        self.client.get_repository_info()

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 3)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)

    def test_diff_tracking_no_origin(self):
        """Testing GitClient diff with a tracking branch, but no origin remote"""
        self._run_git(['remote', 'add', 'quux', self.git_dir])
        self._run_git(['fetch', 'quux'])
        self._run_git(['checkout', '-b', 'mybranch', '--track', 'quux/master'])

        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')

        self.client.get_repository_info()

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 3)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)

    def test_diff_local_tracking(self):
        """Testing GitClient diff with a local tracking branch"""
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')

        self._run_git(['checkout', '-b', 'mybranch', '--track', 'master'])
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')

        self.client.get_repository_info()

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 3)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'cfb79a46f7a35b07e21765608a7852f7')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)

    def test_diff_tracking_override(self):
        """Testing GitClient diff with option override for tracking branch"""
        self.options.tracking = 'origin/master'

        self._run_git(['remote', 'add', 'bad', self.git_dir])
        self._run_git(['fetch', 'bad'])
        self._run_git(['checkout', '-b', 'mybranch', '--track', 'bad/master'])

        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self.client.get_repository_info()

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 3)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)

    def test_diff_slash_tracking(self):
        """Testing GitClient diff with tracking branch that has slash in its name."""
        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'my/branch', '--track',
                       'origin/not-master'])
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')

        self.client.get_repository_info()

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 3)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'd2015ff5fd0297fd7f1210612f87b6b3')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)

    def test_parse_revision_spec_no_args(self):
        """Testing GitClient.parse_revision_spec with no specified revisions"""
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec()
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_no_args_parent(self):
        """Testing GitClient.parse_revision_spec with no specified revisions and a parent diff"""
        parent_base_commit_id = self._git_get_head()

        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'parent-branch', '--track',
                       'origin/not-master'])

        base_commit_id = self._git_get_head()

        self._run_git(['checkout', '-b', 'topic-branch'])

        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        self.options.parent_branch = 'parent-branch'

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec()
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' in revisions)
        self.assertEqual(revisions['parent_base'], parent_base_commit_id)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_one_arg(self):
        """Testing GitClient.parse_revision_spec with one specified revision"""
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec([tip_commit_id])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_one_arg_parent(self):
        """Testing GitClient.parse_revision_spec with one specified revision and a parent diff"""
        parent_base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO3, 'Commit 3')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec([tip_commit_id])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' in revisions)
        self.assertEqual(revisions['parent_base'], parent_base_commit_id)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_two_args(self):
        """Testing GitClient.parse_revision_spec with two specified revisions"""
        base_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'topic-branch'])
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec(['master', 'topic-branch'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_one_arg_two_revs(self):
        """Testing GitClient.parse_revision_spec with diff-since syntax"""
        base_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'topic-branch'])
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec(['master..topic-branch'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_one_arg_since_merge(self):
        """Testing GitClient.parse_revision_spec with diff-since-merge syntax"""
        base_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'topic-branch'])
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec(['master...topic-branch'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)


class MercurialTestBase(SCMClientTests):
    def setUp(self):
        super(MercurialTestBase, self).setUp()
        self._hg_env = {}

    def _run_hg(self, command, ignore_errors=False, extra_ignore_errors=()):
        # We're *not* doing `env = env or {}` here because
        # we want the caller to be able to *enable* reading
        # of user and system-level hgrc configuration.
        env = self._hg_env.copy()

        if not env:
            env = {
                'HGRCPATH': os.devnull,
                'HGPLAIN': '1',
            }

        return execute(['hg'] + command, env, split_lines=False,
                       ignore_errors=ignore_errors,
                       extra_ignore_errors=extra_ignore_errors,
                       translate_newlines=True)

    def _hg_add_file_commit(self, filename, data, msg, branch=None):
        outfile = open(filename, 'w')
        outfile.write(data)
        outfile.close()
        if branch:
            self._run_hg(['branch', branch])
        self._run_hg(['add', filename])
        self._run_hg(['commit', '-m', msg])


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

        self.hg_dir = os.path.join(self.clients_dir, 'testdata', 'hg-repo')
        self.clone_dir = self.chdir_tmp()

        self._run_hg(['clone', self.hg_dir, self.clone_dir])
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

    def testGetRepositoryInfoSimple(self):
        """Testing MercurialClient get_repository_info, simple case"""
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
        """Testing MercurialClient scan_for_server, simple case"""
        os.rename(self.clone_hgrc_path,
                  os.path.join(self.clone_dir, '._disabled_hgrc'))

        self.client.hgrc = {}
        self.client._load_hgrc()
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assertTrue(server is None)

    def testScanForServerWhenPresentInHgrc(self):
        """Testing MercurialClient scan_for_server when present in hgrc"""
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assertEqual(self.TESTSERVER, server)

    def testScanForServerReviewboardrc(self):
        """Testing MercurialClient scan_for_server when in .reviewboardrc"""
        rc = open(os.path.join(self.clone_dir, '.reviewboardrc'), 'w')
        rc.write('REVIEWBOARD_URL = "%s"' % self.TESTSERVER)
        rc.close()

        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)
        self.assertEqual(self.TESTSERVER, server)

    def testDiffSimple(self):
        """Testing MercurialClient diff, simple case"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '68c2bdccf52a4f0baddd0ac9f2ecb7d2')

    def testDiffSimpleMultiple(self):
        """Testing MercurialClient diff with multiple commits"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3')

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '9c8796936646be5c7349973b0fceacbd')

    def testDiffBranchDiverge(self):
        """Testing MercurialClient diff with diverged branch"""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')

        self._run_hg(['branch', 'diverged'])
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        self.client.get_repository_info()

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '6b12723baab97f346aa938005bc4da4d')

        self._run_hg(['update', '-C', 'default'])
        self.client.get_repository_info()

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '68c2bdccf52a4f0baddd0ac9f2ecb7d2')


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

        # Make sure hgsubversion is enabled.
        #
        # This will modify the .hgrc in the temp home directory created
        # for these tests.
        #
        # The "hgsubversion =" tells Mercurial to check for hgsubversion
        # in the default PYTHONPATH.
        fp = open('%s/.hgrc' % os.environ['HOME'], 'w')
        fp.write('[extensions]\n')
        fp.write('hgsubversion =\n')
        fp.close()

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
        output = self._run_hg(['svn', '--help'],
                              ignore_errors=True, extra_ignore_errors=(255))

        return not re.search("unknown command ['\"]svn['\"]", output, re.I)

    def tearDown(self):
        super(MercurialSubversionClientTests, self).tearDown()

        os.kill(self._svnserve_pid, 9)

    def _svn_add_file_commit(self, filename, data, msg, add_file=True):
        outfile = open(filename, 'w')
        outfile.write(data)
        outfile.close()

        if add_file:
            execute(['svn', 'add', filename], ignore_errors=True)

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
            self._svn_add_file_commit('foo.txt', data, 'foo commit %s' % i,
                                      add_file=(i == 0))

    def _get_testing_clone(self):
        self.clone_dir = os.path.join(self._tmpbase, 'checkout.hg')
        self._run_hg([
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
        """Testing MercurialClient (+svn) get_repository_info, simple case"""
        ri = self.client.get_repository_info()

        self.assertEqual('svn', self.client._type)
        self.assertEqual('/trunk', ri.base_path)
        self.assertEqual('svn://127.0.0.1:%s/svnrepo' % self._svnserve_port,
                         ri.path)

    def testCalculateRepositoryInfo(self):
        """
        Testing MercurialClient (+svn) _calculate_hgsubversion_repository_info properly determines repository and base paths.
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
        """Testing MercurialClient (+svn) scan_for_server, simple case"""
        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)

        self.assertTrue(server is None)

    def testScanForServerReviewboardrc(self):
        """Testing MercurialClient (+svn) scan_for_server in .reviewboardrc"""
        rc_filename = os.path.join(self.clone_dir, '.reviewboardrc')
        rc = open(rc_filename, 'w')
        rc.write('REVIEWBOARD_URL = "%s"' % self.TESTSERVER)
        rc.close()
        self.client.user_config, configs = load_config_files(self.clone_dir)

        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)

        self.assertEqual(self.TESTSERVER, server)

    def testScanForServerProperty(self):
        """Testing MercurialClient (+svn) scan_for_server in svn property"""
        os.chdir(self.svn_checkout)
        execute(['svn', 'update'])
        execute(['svn', 'propset', 'reviewboard:url', self.TESTSERVER,
                 self.svn_checkout])
        execute(['svn', 'commit', '-m', 'adding reviewboard:url property'])

        os.chdir(self.clone_dir)
        self._run_hg(['pull'])
        self._run_hg(['update', '-C'])

        ri = self.client.get_repository_info()

        self.assertEqual(self.TESTSERVER, self.client.scan_for_server(ri))

    def testDiffSimple(self):
        """Testing MercurialClient (+svn) diff, simple case"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO4, 'edit 4')

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '2eb0a5f2149232c43a1745d90949fcd5')

    def testDiffSimpleMultiple(self):
        """Testing MercurialClient (+svn) diff with multiple commits"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO4, 'edit 4')
        self._hg_add_file_commit('foo.txt', FOO5, 'edit 5')
        self._hg_add_file_commit('foo.txt', FOO6, 'edit 6')

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '3d007394de3831d61e477cbcfe60ece8')

    def testDiffOfRevision(self):
        """Testing MercurialClient (+svn) diff specifying a revision."""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO4, 'edit 4', branch='b')
        self._hg_add_file_commit('foo.txt', FOO5, 'edit 5', branch='b')
        self._hg_add_file_commit('foo.txt', FOO6, 'edit 6', branch='b')
        self._hg_add_file_commit('foo.txt', FOO4, 'edit 7', branch='b')

        result = self.client.diff(['3'])
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '2eb0a5f2149232c43a1745d90949fcd5')

        result = self.client.diff(['5'])
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '3d007394de3831d61e477cbcfe60ece8')


class SVNClientTests(SCMClientTests):
    def setUp(self):
        super(SVNClientTests, self).setUp()

        if not self.is_exe_in_path('svn'):
            raise SkipTest('svn not found in path')

        self.svn_dir = os.path.join(self.clients_dir, 'testdata', 'svn-repo')
        self.clone_dir = self.chdir_tmp()
        self._run_svn(['co', 'file://' + self.svn_dir, 'svn-repo'])
        os.chdir(os.path.join(self.clone_dir, 'svn-repo'))

        self.client = SVNClient(options=self.options)

    def _run_svn(self, command):
        return execute(['svn'] + command, env=None, split_lines=False,
                       ignore_errors=False, extra_ignore_errors=(),
                       translate_newlines=True)


    def _svn_add_file(self, filename, data, changelist=None):
        """Add a file to the test repo."""
        is_new = not os.path.exists(filename)

        f = open(filename, 'w')
        f.write(data)
        f.close()
        if is_new:
            self._run_svn(['add', filename])

        if changelist:
            self._run_svn(['changelist', changelist, filename])

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

    def test_parse_revision_spec_no_args(self):
        """Testing SVNClient.parse_revision_spec with no specified revisions"""
        revisions = self.client.parse_revision_spec()
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 3)
        self.assertEqual(revisions['tip'], '--rbtools-working-copy')

    def test_parse_revision_spec_one_revision(self):
        """Testing SVNClient.parse_revision_spec with one specified numeric revision"""
        revisions = self.client.parse_revision_spec(['3'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 2)
        self.assertEqual(revisions['tip'], 3)

    def test_parse_revision_spec_one_revision_changelist(self):
        """Testing SVNClient.parse_revision_spec with one specified changelist revision"""
        self._svn_add_file('foo.txt', FOO3, 'my-change')

        revisions = self.client.parse_revision_spec(['my-change'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 3)
        self.assertEqual(revisions['tip'],
                         SVNClient.REVISION_CHANGELIST_PREFIX + 'my-change')

    def test_parse_revision_spec_one_revision_nonexistant_changelist(self):
        """Testing SVNClient.parse_revision_spec with one specified invalid changelist revision"""
        self._svn_add_file('foo.txt', FOO3, 'my-change')

        self.assertRaises(
            InvalidRevisionSpecError,
            lambda: self.client.parse_revision_spec(['not-my-change']))

    def test_parse_revision_spec_one_arg_two_revisions(self):
        """Testing SVNClient.parse_revision_spec with R1:R2 syntax"""
        revisions = self.client.parse_revision_spec(['1:3'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1)
        self.assertEqual(revisions['tip'], 3)

    def test_parse_revision_spec_two_arguments(self):
        """Testing SVNClient.parse_revision_spec with two revisions"""
        revisions = self.client.parse_revision_spec(['1', '3'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1)
        self.assertEqual(revisions['tip'], 3)

    def test_parse_revision_spec_one_revision_url(self):
        """Testing SVNClient.parse_revision_spec with one revision and a repository URL"""
        self.options.repository_url = \
            'http://svn.apache.org/repos/asf/subversion/trunk'

        revisions = self.client.parse_revision_spec(['1549823'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1549822)
        self.assertEqual(revisions['tip'], 1549823)


    def test_parse_revision_spec_two_revisions_url(self):
        """Testing SVNClient.parse_revision_spec with R1:R2 syntax and a repository URL"""
        self.options.repository_url = \
            'http://svn.apache.org/repos/asf/subversion/trunk'

        revisions = self.client.parse_revision_spec(['1549823:1550211'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1549823)
        self.assertEqual(revisions['tip'], 1550211)


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

    def test_error_on_revision_range(self):
        """Testing PerforceClient with --revision-range causes an exit"""
        self.options.revision_range = "12345"
        client = PerforceClient(options=self.options)
        self.assertRaises(OptionsCheckError, client.check_options)

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
            def is_supported(self):
                return True

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
        self._compare_diff(diff, '75c07955a503fc1a32efc671c18ff618')

    def test_diff_with_moved_files_cap_on(self):
        """Testing PerforceClient.diff with moved files and capability on"""
        self._test_diff_with_moved_files(
            '5926515eaf4cf6d8257a52f7d9f0e530',
            caps={
                'scmtools': {
                    'perforce': {
                        'moved_files': True
                    }
                }
            })

    def test_diff_with_moved_files_cap_off(self):
        """Testing PerforceClient.diff with moved files and capability off"""
        self._test_diff_with_moved_files('2b9a7313c83ba21d90eadcc8408e437c')

    def _test_diff_with_moved_files(self, expected_diff_hash, caps={}):
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
        self._compare_diff(diff, expected_diff_hash)

    def _build_client(self):
        self.options.p4_client = 'myclient'
        self.options.p4_port = 'perforce.example.com:1666'
        self.options.p4_passwd = ''
        client = PerforceClient(self.P4DiffTestWrapper, options=self.options)
        client.p4d_version = (2012, 2)
        return client

    def _compare_diff(self, diff_info, expected_diff_hash):
        self.assertTrue(isinstance(diff_info, dict))
        self.assertEqual(len(diff_info), 1)
        self.assertTrue('diff' in diff_info)

        diff_content = re.sub('\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                              '1970-01-01 00:00:00',
                              diff_info['diff'])
        self.assertEqual(md5(diff_content).hexdigest(), expected_diff_hash)


class BazaarClientTests(SCMClientTests):
    def _bzr_cmd(self, command, *args, **kwargs):
        full_command = ["bzr"] + command

        result = execute(full_command, *args, **kwargs)

        return result

    def _bzr_add_file_commit(self, file, data, msg):
        """
        Add a file to a Bazaar repository with the content of data and commit
        with msg.
        """
        foo = open(file, "w")
        foo.write(data)
        foo.close()
        self._bzr_cmd(["add", file])
        self._bzr_cmd(["commit", "-m", msg, '--author', 'Test User'])

    def _compare_diffs(self, filename, full_diff, expected_diff_digest):
        """
        Testing that the full_diff for ``filename`` matches the ``expected_diff``.
        """
        diff_lines = full_diff.splitlines()

        self.assertEqual("=== modified file %r" % filename, diff_lines[0])
        self.assertTrue(diff_lines[1].startswith("--- %s\t" % filename))
        self.assertTrue(diff_lines[2].startswith("+++ %s\t" % filename))

        diff_body = "\n".join(diff_lines[3:])
        self.assertEqual(md5(diff_body).hexdigest(), expected_diff_digest)

    def setUp(self):
        super(BazaarClientTests, self).setUp()

        if not self.is_exe_in_path("bzr"):
            raise SkipTest("bzr not found in path")

        # Identify with bazaar so that the commands won't be sad.
        execute(['bzr', 'whoami', 'Test User'])

        self.orig_dir = os.getcwd()

        self.original_branch = self.chdir_tmp()
        self._bzr_cmd(["init", "."])
        self._bzr_add_file_commit("foo.txt", FOO, "initial commit")

        self.child_branch = mktemp()
        self._bzr_cmd(["branch", self.original_branch, self.child_branch])
        self.client = BazaarClient(options=self.options)
        os.chdir(self.orig_dir)

        self.user_config = {}
        self.configs = []
        self.client.user_config = self.user_config
        self.client.configs = self.configs
        self.options.parent_branch = None

    def test_get_repository_info_original_branch(self):
        """Testing BazaarClient get_repository_info with original branch"""
        os.chdir(self.original_branch)
        ri = self.client.get_repository_info()

        self.assertTrue(isinstance(ri, RepositoryInfo))
        self.assertEqual(os.path.realpath(ri.path),
                         os.path.realpath(self.original_branch))
        self.assertTrue(ri.supports_parent_diffs)

        self.assertEqual(ri.base_path, "/")
        self.assertFalse(ri.supports_changesets)

    def test_get_repository_info_child_branch(self):
        """Testing BazaarClient get_repository_info with child branch"""
        os.chdir(self.child_branch)
        ri = self.client.get_repository_info()

        self.assertTrue(isinstance(ri, RepositoryInfo))
        self.assertEqual(os.path.realpath(ri.path),
                         os.path.realpath(self.child_branch))
        self.assertTrue(ri.supports_parent_diffs)

        self.assertEqual(ri.base_path, "/")
        self.assertFalse(ri.supports_changesets)

    def test_get_repository_info_no_branch(self):
        """Testing BazaarClient get_repository_info, no branch"""
        self.chdir_tmp()
        ri = self.client.get_repository_info()
        self.assertEqual(ri, None)

    def test_diff_simple(self):
        """Testing BazaarClient simple diff case"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "delete and modify stuff")

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)

        self._compare_diffs('foo.txt', result['diff'],
                            'a6326b53933f8b255a4b840485d8e210')

    def test_diff_specific_files(self):
        """Testing BazaarClient diff with specific files"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "delete and modify stuff")
        self._bzr_add_file_commit("bar.txt", "baz", "added bar")

        result = self.client.diff(['foo.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)

        self._compare_diffs('foo.txt', result['diff'],
                            'a6326b53933f8b255a4b840485d8e210')

    def test_diff_simple_multiple(self):
        """Testing BazaarClient simple diff with multiple commits case"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        self._bzr_add_file_commit("foo.txt", FOO3, "commit 3")

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)

        self._compare_diffs('foo.txt', result['diff'],
                            '4109cc082dce22288c2f1baca9b107b6')

    def test_diff_parent(self):
        """Testing BazaarClient diff with changes only in the parent branch"""
        os.chdir(self.child_branch)
        self._bzr_add_file_commit("foo.txt", FOO1, "delete and modify stuff")

        grand_child_branch = mktemp()
        self._bzr_cmd(["branch", self.child_branch, grand_child_branch])
        os.chdir(grand_child_branch)

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)

        self.assertEqual(result['diff'], None)

    def test_diff_grand_parent(self):
        """Testing BazaarClient diff with changes between a 2nd level descendant"""
        os.chdir(self.child_branch)
        self._bzr_add_file_commit("foo.txt", FOO1, "delete and modify stuff")

        grand_child_branch = mktemp()
        self._bzr_cmd(["branch", self.child_branch, grand_child_branch])
        os.chdir(grand_child_branch)

        # Requesting the diff between the grand child branch and its grand
        # parent:
        self.options.parent_branch = self.original_branch

        result = self.client.diff(None)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 1)
        self.assertTrue('diff' in result)

        self._compare_diffs("foo.txt", result['diff'],
                            'a6326b53933f8b255a4b840485d8e210')

    def test_guessed_summary_and_description_in_diff(self):
        """Testing BazaarClient diff with summary and description guessed"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        self._bzr_add_file_commit("foo.txt", FOO3, "commit 3")

        self.options.guess_summary = True
        self.options.guess_description = True
        self.client.diff(None)

        self.assertEquals("commit 3", self.options.summary)

        description = self.options.description
        self.assertTrue("commit 1" in description, description)
        self.assertTrue("commit 2" in description, description)
        self.assertTrue("commit 3" in description, description)

    def test_guessed_summary_and_description_in_grand_parent_branch_diff(self):
        """
        Testing BazaarClient diff with summary and description guessed for grand parent branch.
        """
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        self._bzr_add_file_commit("foo.txt", FOO3, "commit 3")

        self.options.guess_summary = True
        self.options.guess_description = True

        grand_child_branch = mktemp()
        self._bzr_cmd(["branch", self.child_branch, grand_child_branch])
        os.chdir(grand_child_branch)

        # Requesting the diff between the grand child branch and its grand
        # parent:
        self.options.parent_branch = self.original_branch

        self.client.diff(None)

        self.assertEquals("commit 3", self.options.summary)

        description = self.options.description
        self.assertTrue("commit 1" in description, description)
        self.assertTrue("commit 2" in description, description)
        self.assertTrue("commit 3" in description, description)


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
