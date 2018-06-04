"""Unit tests for MercurialClient."""

from __future__ import unicode_literals

import os
import re
import sys
import time
from hashlib import md5
from random import randint
from textwrap import dedent

import six
from six.moves import range
from nose import SkipTest

from rbtools.clients import RepositoryInfo
from rbtools.clients.mercurial import MercurialClient
from rbtools.clients.tests import (FOO, FOO1, FOO2, FOO3, FOO4, FOO5, FOO6,
                                   SCMClientTests)
from rbtools.utils.filesystem import is_exe_in_path, load_config, make_tempdir
from rbtools.utils.process import execute


class MercurialTestBase(SCMClientTests):
    """Base class for all Mercurial unit tests."""

    def setUp(self):
        if six.PY3:
            # Mercurial is working on Python 3 support but it's still quite
            # broken, especially with any out-of-core extensions installed
            # (like hgsubversion). Just skip it for now.
            raise SkipTest

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
                       results_unicode=False)

    def _hg_add_file_commit(self, filename, data, msg, branch=None):
        with open(filename, 'wb') as f:
            f.write(data)

        if branch:
            self._run_hg(['branch', branch])

        self._run_hg(['add', filename])
        self._run_hg(['commit', '-m', msg])


class MercurialClientTests(MercurialTestBase):
    """Unit tests for MercurialClient."""

    TESTSERVER = 'http://127.0.0.1:8080'
    CLONE_HGRC = dedent("""
    [ui]
    username = test user <user at example.com>

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
        if not is_exe_in_path('hg'):
            raise SkipTest('hg not found in path')

        self.hg_dir = os.path.join(self.testdata_dir, 'hg-repo')
        self.clone_dir = self.chdir_tmp()

        self._run_hg(['clone', self.hg_dir, self.clone_dir])
        self.client = MercurialClient(options=self.options)

        clone_hgrc = open(self.clone_hgrc_path, 'w')
        clone_hgrc.write(self.CLONE_HGRC % {
            'hg_dir': self.hg_dir,
            'clone_dir': self.clone_dir,
            'test_server': self.TESTSERVER,
        })
        clone_hgrc.close()

        self.options.parent_branch = None

    def _hg_get_tip(self):
        return self._run_hg(['identify']).split()[0]

    @property
    def clone_hgrc_path(self):
        return os.path.join(self.clone_dir, '.hg', 'hgrc')

    def test_get_repository_info_simple(self):
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

    def test_scan_for_server_simple(self):
        """Testing MercurialClient scan_for_server, simple case"""
        os.rename(self.clone_hgrc_path,
                  os.path.join(self.clone_dir, '._disabled_hgrc'))

        self.client.hgrc = {}
        self.client._load_hgrc()
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assertTrue(server is None)

    def test_scan_for_server_when_present_in_hgrc(self):
        """Testing MercurialClient scan_for_server when present in hgrc"""
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assertEqual(self.TESTSERVER, server)

    def test_scan_for_server_reviewboardrc(self):
        """Testing MercurialClient scan_for_server when in .reviewboardrc"""
        with self.reviewboardrc({'REVIEWBOARD_URL': self.TESTSERVER}):
            self.client.config = load_config()

            ri = self.client.get_repository_info()
            server = self.client.scan_for_server(ri)
            self.assertEqual(self.TESTSERVER, server)

    def test_diff_simple(self):
        """Testing MercurialClient diff, simple case"""
        self._hg_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '68c2bdccf52a4f0baddd0ac9f2ecb7d2')

    def test_diff_simple_multiple(self):
        """Testing MercurialClient diff with multiple commits"""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '9c8796936646be5c7349973b0fceacbd')

    def test_diff_exclude(self):
        """Testing MercurialClient diff with file exclusion"""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('exclude.txt', FOO2, 'commit 2')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions, exclude_patterns=['exclude.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '68c2bdccf52a4f0baddd0ac9f2ecb7d2')

    def test_diff_exclude_empty(self):
        """Testing MercurialClient diff with empty file exclusion"""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('empty.txt', b'', 'commit 2')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions, exclude_patterns=['empty.txt'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '68c2bdccf52a4f0baddd0ac9f2ecb7d2')

    def test_diff_branch_diverge(self):
        """Testing MercurialClient diff with diverged branch"""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')

        self._run_hg(['branch', 'diverged'])
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '6b12723baab97f346aa938005bc4da4d')

        self._run_hg(['update', '-C', 'default'])

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '68c2bdccf52a4f0baddd0ac9f2ecb7d2')

    def test_diff_parent_diff_simple(self):
        """Testing MercurialClient parent diffs with a simple case"""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3')

        revisions = self.client.parse_revision_spec(['2', '3'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('parent_diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '7a897f68a9dc034fc1e42fe7a33bb808')
        self.assertEqual(md5(result['parent_diff']).hexdigest(),
                         '5cacbd79800a9145f982dcc0908b6068')

    def test_diff_parent_diff_branch_diverge(self):
        """Testing MercurialClient parent diffs with a diverged branch"""

        # This test is very similar to test_diff_parent_diff_simple except
        # we throw a branch into the mix.
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._run_hg(['branch', 'diverged'])
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3')

        revisions = self.client.parse_revision_spec(['2', '3'])
        result = self.client.diff(revisions)
        self.assertTrue('parent_diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '7a897f68a9dc034fc1e42fe7a33bb808')
        self.assertEqual(md5(result['parent_diff']).hexdigest(),
                         '5cacbd79800a9145f982dcc0908b6068')

    def test_diff_parent_diff_simple_with_arg(self):
        """Testing MercurialClient parent diffs with a diverged branch and
        --parent option"""
        # This test is very similar to test_diff_parent_diff_simple except
        # we use the --parent option to post without explicit revisions
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3')

        self.options.parent_branch = '2'

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('parent_diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '7a897f68a9dc034fc1e42fe7a33bb808')
        self.assertEqual(md5(result['parent_diff']).hexdigest(),
                         '5cacbd79800a9145f982dcc0908b6068')

    def test_parse_revision_spec_no_args(self):
        """Testing MercurialClient.parse_revision_spec with no arguments"""
        base = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        tip = self._hg_get_tip()

        revisions = self.client.parse_revision_spec([])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base)
        self.assertEqual(revisions['tip'], tip)

    def test_parse_revision_spec_one_arg_periods(self):
        """Testing MercurialClient.parse_revision_spec with r1..r2 syntax"""
        base = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        tip = self._hg_get_tip()

        revisions = self.client.parse_revision_spec(['0..1'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base)
        self.assertEqual(revisions['tip'], tip)

    def test_parse_revision_spec_one_arg_colons(self):
        """Testing MercurialClient.parse_revision_spec with r1::r2 syntax"""
        base = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        tip = self._hg_get_tip()

        revisions = self.client.parse_revision_spec(['0..1'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base)
        self.assertEqual(revisions['tip'], tip)

    def test_parse_revision_spec_one_arg(self):
        """Testing MercurialClient.parse_revision_spec with one revision"""
        base = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        tip = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')

        revisions = self.client.parse_revision_spec(['1'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base)
        self.assertEqual(revisions['tip'], tip)

    def test_parse_revision_spec_two_args(self):
        """Testing MercurialClient.parse_revision_spec with two revisions"""
        base = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        tip = self._hg_get_tip()

        revisions = self.client.parse_revision_spec(['0', '2'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base)
        self.assertEqual(revisions['tip'], tip)

    def test_parse_revision_spec_parent_base(self):
        """Testing MercurialClient.parse_revision_spec with parent base"""
        start_base = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        commit1 = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2')
        commit2 = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3')
        commit3 = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO4, 'commit 4')
        commit4 = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO5, 'commit 5')

        self.assertEqual(
            self.client.parse_revision_spec(['1', '2']),
            dict(base=commit1, tip=commit2, parent_base=start_base))

        self.assertEqual(
            self.client.parse_revision_spec(['4']),
            dict(base=commit3, tip=commit4, parent_base=start_base,
                 commit_id=commit4))

        self.assertEqual(
            self.client.parse_revision_spec(['2', '4']),
            dict(base=commit2, tip=commit4, parent_base=start_base))

    def test_guess_summary_description_one(self):
        """Testing MercurialClient guess summary & description 1 commit"""
        self.options.guess_summary = True
        self.options.guess_description = True

        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')

        revisions = self.client.parse_revision_spec([])
        commit_message = self.client.get_commit_message(revisions)

        self.assertEqual(commit_message['summary'], 'commit 1')

    def test_guess_summary_description_two(self):
        """Testing MercurialClient guess summary & description 2 commits"""
        self.options.guess_summary = True
        self.options.guess_description = True

        self._hg_add_file_commit('foo.txt', FOO1, 'summary 1\n\nbody 1')
        self._hg_add_file_commit('foo.txt', FOO2, 'summary 2\n\nbody 2')

        revisions = self.client.parse_revision_spec([])
        commit_message = self.client.get_commit_message(revisions)

        self.assertEqual(commit_message['summary'], 'summary 1')
        self.assertEqual(commit_message['description'],
                         'body 1\n\nsummary 2\n\nbody 2')

    def test_guess_summary_description_three(self):
        """Testing MercurialClient guess summary & description 3 commits"""
        self.options.guess_summary = True
        self.options.guess_description = True

        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1\n\ndesc1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2\n\ndesc2')
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3\n\ndesc3')

        revisions = self.client.parse_revision_spec([])
        commit_message = self.client.get_commit_message(revisions)

        self.assertEqual(commit_message['summary'], 'commit 1')
        self.assertEqual(commit_message['description'],
                         'desc1\n\ncommit 2\n\ndesc2\n\ncommit 3\n\ndesc3')

    def test_guess_summary_description_one_middle(self):
        """Testing MercurialClient guess summary & description middle commit"""
        self.options.guess_summary = True
        self.options.guess_description = True

        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1\n\ndesc1')
        self._hg_add_file_commit('foo.txt', FOO2, 'commit 2\n\ndesc2')
        tip = self._hg_get_tip()
        self._hg_add_file_commit('foo.txt', FOO3, 'commit 3\n\ndesc3')

        revisions = self.client.parse_revision_spec([tip])
        commit_message = self.client.get_commit_message(revisions)

        self.assertEqual(commit_message['summary'], 'commit 2')
        self.assertEqual(commit_message['description'], 'desc2')


class MercurialSubversionClientTests(MercurialTestBase):
    """Unit tests for hgsubversion."""

    TESTSERVER = 'http://127.0.0.1:8080'

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
            if not is_exe_in_path(exe):
                raise SkipTest('missing svn stuff!  giving up!')

        if not self._has_hgsubversion():
            raise SkipTest('unable to use `hgsubversion` extension!  '
                           'giving up!')

        if not self._tmpbase:
            self._tmpbase = make_tempdir()

        self._create_svn_repo()
        self._fire_up_svnserve()
        self._fill_in_svn_repo()

        try:
            self._get_testing_clone()
        except (OSError, IOError):
            msg = 'could not clone from svn repo!  skipping...'
            raise SkipTest(msg).with_traceback(sys.exc_info()[2])

        self._spin_up_client()
        self._stub_in_config_and_options()

    def _has_hgsubversion(self):
        try:
            output = self._run_hg(['svn', '--help'], ignore_errors=True,
                                  extra_ignore_errors=(255))
        except OSError:
            return False

        return not re.search('unknown command [\'"]svn[\'"]', output, re.I)

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
        execute(['svnserve', '--single-thread', '--pid-file', pid_file, '-d',
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
        self.options.parent_branch = None

    def testGetRepositoryInfoSimple(self):
        """Testing MercurialClient (+svn) get_repository_info, simple case"""
        ri = self.client.get_repository_info()

        self.assertEqual('svn', self.client._type)
        self.assertEqual('/trunk', ri.base_path)
        self.assertEqual('svn://127.0.0.1:%s/svnrepo' % self._svnserve_port,
                         ri.path)

    def testCalculateRepositoryInfo(self):
        """Testing MercurialClient (+svn)
        _calculate_hgsubversion_repository_info properly determines repository
        and base paths"""
        info = (
            'URL: svn+ssh://testuser@svn.example.net/repo/trunk\n'
            'Repository Root: svn+ssh://testuser@svn.example.net/repo\n'
            'Repository UUID: bfddb570-5023-0410-9bc8-bc1659bf7c01\n'
            'Revision: 9999\n'
            'Node Kind: directory\n'
            'Last Changed Author: user\n'
            'Last Changed Rev: 9999\n'
            'Last Changed Date: 2012-09-05 18:04:28 +0000 (Wed, 05 Sep 2012)')

        repo_info = self.client._calculate_hgsubversion_repository_info(info)

        self.assertEqual(repo_info.path, 'svn+ssh://svn.example.net/repo')
        self.assertEqual(repo_info.base_path, '/trunk')

    def testScanForServerSimple(self):
        """Testing MercurialClient (+svn) scan_for_server, simple case"""
        ri = self.client.get_repository_info()
        server = self.client.scan_for_server(ri)

        self.assertTrue(server is None)

    def testScanForServerReviewboardrc(self):
        """Testing MercurialClient (+svn) scan_for_server in .reviewboardrc"""
        with self.reviewboardrc({'REVIEWBOARD_URL': self.TESTSERVER}):
            self.client.config = load_config()

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

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '2eb0a5f2149232c43a1745d90949fcd5')
        self.assertEqual(result['parent_diff'], None)

    def testDiffSimpleMultiple(self):
        """Testing MercurialClient (+svn) diff with multiple commits"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO4, 'edit 4')
        self._hg_add_file_commit('foo.txt', FOO5, 'edit 5')
        self._hg_add_file_commit('foo.txt', FOO6, 'edit 6')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '3d007394de3831d61e477cbcfe60ece8')
        self.assertEqual(result['parent_diff'], None)

    def testDiffOfRevision(self):
        """Testing MercurialClient (+svn) diff specifying a revision"""
        self.client.get_repository_info()

        self._hg_add_file_commit('foo.txt', FOO4, 'edit 4', branch='b')
        self._hg_add_file_commit('foo.txt', FOO5, 'edit 5', branch='b')
        self._hg_add_file_commit('foo.txt', FOO6, 'edit 6', branch='b')
        self._hg_add_file_commit('foo.txt', FOO4, 'edit 7', branch='b')

        revisions = self.client.parse_revision_spec(['3'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '2eb0a5f2149232c43a1745d90949fcd5')
        self.assertEqual(result['parent_diff'], None)
