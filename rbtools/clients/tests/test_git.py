"""Unit tests for GitClient."""

from __future__ import unicode_literals

import os
import re
import unittest
from typing import Any, List

import kgb

from rbtools.clients import PatchAuthor, RepositoryInfo
from rbtools.clients.errors import (CreateCommitError,
                                    MergeError,
                                    PushError,
                                    SCMClientDependencyError,
                                    TooManyRevisionsError)
from rbtools.clients.git import GitClient, get_git_candidates
from rbtools.clients.tests import FOO1, FOO2, FOO3, FOO4, SCMClientTestCase
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import is_exe_in_path
from rbtools.utils.process import execute


class GitClientTests(SCMClientTestCase):
    """Unit tests for GitClient."""

    scmclient_cls = GitClient

    TESTSERVER = 'http://127.0.0.1:8080'
    AUTHOR = PatchAuthor(full_name='name',
                         email='email')

    _git: str = ''

    @classmethod
    def setup_checkout(cls, checkout_dir):
        """Populate a Git checkout.

        This will create a checkout of the sample Git repository stored
        in the :file:`testdata` directory, along with a child clone and a
        grandchild clone.

        Args:
            checkout_dir (unicode):
                The top-level directory in which the clones will be placed.

        Returns:
            The main checkout directory, or ``None`` if :command:`git` isn't
            in the path.
        """
        scmclient = GitClient()

        if not scmclient.has_dependencies():
            return

        cls._git = scmclient.git

        cls.git_dir = os.path.join(cls.testdata_dir, 'git-repo')
        cls.clone_dir = checkout_dir

        orig_clone_dir = os.path.join(checkout_dir, 'orig')
        child_clone_dir = os.path.join(checkout_dir, 'child')
        grandchild_clone_dir = os.path.join(checkout_dir, 'grandchild')

        os.mkdir(checkout_dir, 0o700)
        cls._run_git(['clone', cls.git_dir, orig_clone_dir])
        cls._run_git(['clone', orig_clone_dir, child_clone_dir])
        cls._run_git(['clone', child_clone_dir, grandchild_clone_dir])

        cls.orig_clone_dir = orig_clone_dir
        cls.child_clone_dir = child_clone_dir
        cls.grandchild_clone_dir = grandchild_clone_dir

        return orig_clone_dir

    @classmethod
    def _run_git(
        cls,
        command: List[str],
    ) -> Any:
        """Run git with the provided arguments.

        Args:
            command (list of str):
                The arguments to pass to :command:`git`.

        Returns:
            object:
            The result of the :py:func:`~rbtools.utils.process.execute` call.
        """
        return execute([cls._git] + command,
                       env=None,
                       split_lines=False,
                       ignore_errors=False,
                       extra_ignore_errors=())

    def setUp(self):
        super(GitClientTests, self).setUp()

        self.set_user_home(os.path.join(self.testdata_dir, 'homedir'))

    def _git_add_file_commit(self, filename, data, msg):
        """Add a file to a git repository.

        Args:
            filename (unicode):
                The filename to write to.

            data (bytes):
                The content of the file to write.

            msg (unicode):
                The commit message to use.
        """
        with open(filename, 'wb') as f:
            f.write(data)

        self._run_git(['add', filename])
        self._run_git(['commit', '-m', msg])

    def _git_get_head(self):
        return self._run_git(['rev-parse', 'HEAD']).strip()

    def test_check_dependencies_with_git_found(self):
        """Testing GitClient.check_dependencies with git found"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['git', '--help'],),
                'op': kgb.SpyOpReturn(True),
            },
            {
                'args': (['git.cmd', '--help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['git', '--help'])

        self.assertEqual(client.git, 'git')

    def test_check_dependencies_with_gitcmd_found_on_windows(self):
        """Testing GitClient.check_dependencies with git.cmd found on Windows
        """
        self.spy_on(
            get_git_candidates,
            op=kgb.SpyOpReturn(get_git_candidates(target_platform='windows')))

        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['git', '--help'],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': (['git.cmd', '--help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 2)
        self.assertSpyCalledWith(check_install.calls[0], ['git', '--help'])
        self.assertSpyCalledWith(check_install.calls[1], ['git.cmd', '--help'])

        self.assertEqual(client.git, 'git.cmd')

    def test_check_dependencies_with_missing(self):
        """Testing GitClient.check_dependencies with dependencies
        missing
        """
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools ('git') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['git', '--help'])

    def test_check_dependencies_with_missing_on_windows(self):
        """Testing GitClient.check_dependencies with dependencies
        missing on Windows
        """
        self.spy_on(
            get_git_candidates,
            op=kgb.SpyOpReturn(get_git_candidates(target_platform='windows')))

        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools (one of ('git', 'git.cmd')) are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 2)
        self.assertSpyCalledWith(check_install, ['git', '--help'])
        self.assertSpyCalledWith(check_install, ['git.cmd', '--help'])

    def test_git_with_deps_missing(self):
        """Testing GitClient.git with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # git(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        # This will fall back to "git" even if dependencies are missing.
        self.assertEqual(client.git, 'git')

        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['git', '--help'])

    def test_git_with_deps_not_checked(self):
        """Testing GitClient.git with dependencies not
        checked
        """
        # A False value is used just to ensure git() bails early,
        # and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either GitClient.setup() or '
            'GitClient.has_dependencies() must be called before other '
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
            client.git

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['git', '--help'])

    def test_get_local_path_with_deps_missing(self):
        """Testing GitClient.get_local_path with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_local_path(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            local_path = client.get_local_path()

        self.assertIsNone(local_path)

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "git --help" or "git.cmd --help": skipping Git')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['git', '--help'])

    def test_get_local_path_with_deps_not_checked(self):
        """Testing GitClient.get_local_path with dependencies not
        checked
        """
        # A False value is used just to ensure get_local_path() bails early,
        # and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either GitClient.setup() or '
            'GitClient.has_dependencies() must be called before other '
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_local_path()

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "git --help" or "git.cmd --help": skipping Git')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['git', '--help'])

    def test_get_repository_info_simple(self):
        """Testing GitClient get_repository_info, simple case"""
        client = self.build_client()
        ri = client.get_repository_info()

        self.assertIsInstance(ri, RepositoryInfo)
        self.assertEqual(ri.base_path, '')
        self.assertEqual(ri.path.rstrip('/.git'), self.git_dir)

    def test_get_repository_info_with_deps_missing(self):
        """Testing GitClient.get_repository_info with dependencies
        missing
        """
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_repository_info(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            repository_info = client.get_repository_info()

        self.assertIsNone(repository_info)

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "git --help" or "git.cmd --help": skipping Git')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['git', '--help'])

    def test_get_repository_info_with_deps_not_checked(self):
        """Testing GitClient.get_repository_info with dependencies
        not checked
        """
        # A False value is used just to ensure get_repository_info() bails
        # early, and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either GitClient.setup() or '
            'GitClient.has_dependencies() must be called before other '
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_repository_info()

        self.assertEqual(
            ctx.records[0].msg,
            'Unable to execute "git --help" or "git.cmd --help": skipping Git')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['git', '--help'])

    def test_scan_for_server_simple(self):
        """Testing GitClient scan_for_server, simple case"""
        client = self.build_client()
        ri = client.get_repository_info()

        server = client.scan_for_server(ri)
        self.assertIsNone(server)

    def test_scan_for_server_property(self):
        """Testing GitClient scan_for_server using repo property"""
        client = self.build_client()

        self._run_git(['config', 'reviewboard.url', self.TESTSERVER])
        ri = client.get_repository_info()

        self.assertEqual(client.scan_for_server(ri), self.TESTSERVER)

    def test_diff_simple(self):
        """Testing GitClient simple diff case"""
        client = self.build_client()
        client.get_repository_info()
        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')
        commit_id = self._git_get_head()

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'base_commit_id': base_commit_id,
                'commit_id': commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,7 +6,4 @@ multa quoque et bello passus, '
                    b'dum conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_too_many_revisions(self):
        """Testing GitClient parse_revision_spec with too many revisions"""
        client = self.build_client()

        with self.assertRaises(TooManyRevisionsError):
            client.parse_revision_spec([1, 2, 3])

    def test_diff_simple_multiple(self):
        """Testing GitClient simple diff with multiple commits case"""
        client = self.build_client()
        client.get_repository_info()

        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('foo.txt', FOO2, 'commit 1')
        self._git_add_file_commit('foo.txt', FOO3, 'commit 1')
        commit_id = self._git_get_head()

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'base_commit_id': base_commit_id,
                'commit_id': commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'63036ed3fcafe870d567a14dd5884f4fed70126c 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -1,12 +1,11 @@\n ARMA virumque cano, Troiae '
                    b'qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b' Italiam, fato profugus, Laviniaque venit\n'
                    b' litora, multum ille et terris iactatus et alto\n'
                    b' vi superum saevae memorem Iunonis ob iram;\n'
                    b'-multa quoque et bello passus, dum conderet urbem,\n'
                    b'+dum conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_diff_exclude(self):
        """Testing GitClient simple diff with file exclusion"""
        client = self.build_client()
        client.get_repository_info()
        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('exclude.txt', FOO2, 'commit 2')
        commit_id = self._git_get_head()

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions, exclude_patterns=['exclude.txt']),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,7 +6,4 @@ multa quoque et bello passus, dum '
                    b'conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_diff_exclude_in_subdir(self):
        """Testing GitClient simple diff with file exclusion in a subdir"""
        client = self.build_client()
        base_commit_id = self._git_get_head()

        os.mkdir('subdir')
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('subdir/exclude.txt', FOO2, 'commit 2')

        os.chdir('subdir')
        client.get_repository_info()

        commit_id = self._git_get_head()
        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions, exclude_patterns=['exclude.txt']),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,7 +6,4 @@ multa quoque et bello passus, dum '
                    b'conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_diff_exclude_root_pattern_in_subdir(self):
        """Testing GitClient diff with file exclusion in the repo root"""
        client = self.build_client()
        base_commit_id = self._git_get_head()

        os.mkdir('subdir')
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('exclude.txt', FOO2, 'commit 2')
        os.chdir('subdir')

        client.get_repository_info()

        commit_id = self._git_get_head()
        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions,
                        exclude_patterns=[os.path.sep + 'exclude.txt']),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,7 +6,4 @@ multa quoque et bello passus, dum '
                    b'conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_diff_branch_diverge(self):
        """Testing GitClient diff with divergent branches"""
        client = self.build_client()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._run_git(['checkout', '-b', 'mybranch', '--track',
                      'origin/master'])
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')
        commit_id = self._git_get_head()
        client.get_repository_info()

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'e619c1387f5feb91f0ca83194650bfe4f6c2e347 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -1,4 +1,6 @@\n'
                    b' ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b' Italiam, fato profugus, Laviniaque venit\n'
                    b' litora, multum ille et terris iactatus et alto\n'
                    b' vi superum saevae memorem Iunonis ob iram;\n'
                    b'@@ -6,7 +8,4 @@ multa quoque et bello passus, dum '
                    b'conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

        self._run_git(['checkout', 'master'])
        client.get_repository_info()
        commit_id = self._git_get_head()

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,7 +6,4 @@ multa quoque et bello passus, dum '
                    b'conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_diff_tracking_no_origin(self):
        """Testing GitClient diff with a tracking branch, but no origin remote
        """
        client = self.build_client()

        self._run_git(['remote', 'add', 'quux', self.git_dir])
        self._run_git(['fetch', 'quux'])
        self._run_git(['checkout', '-b', 'mybranch', '--track', 'quux/master'])

        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')
        commit_id = self._git_get_head()

        client.get_repository_info()

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,7 +6,4 @@ multa quoque et bello passus, dum '
                    b'conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_diff_local_tracking(self):
        """Testing GitClient diff with a local tracking branch"""
        client = self.build_client()

        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')

        self._run_git(['checkout', '-b', 'mybranch', '--track', 'master'])
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')
        commit_id = self._git_get_head()

        client.get_repository_info()

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'e619c1387f5feb91f0ca83194650bfe4f6c2e347 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -1,4 +1,6 @@\n'
                    b' ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b' Italiam, fato profugus, Laviniaque venit\n'
                    b' litora, multum ille et terris iactatus et alto\n'
                    b' vi superum saevae memorem Iunonis ob iram;\n'
                    b'@@ -6,7 +8,4 @@ multa quoque et bello passus, dum '
                    b'conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_diff_tracking_override(self):
        """Testing GitClient diff with option override for tracking branch"""
        client = self.build_client(options={
            'tracking': 'origin/master',
        })

        self._run_git(['remote', 'add', 'bad', self.git_dir])
        self._run_git(['fetch', 'bad'])
        self._run_git(['checkout', '-b', 'mybranch', '--track', 'bad/master'])

        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        commit_id = self._git_get_head()

        client.get_repository_info()
        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,7 +6,4 @@ multa quoque et bello passus, dum '
                    b'conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
                'parent_diff': None,
            })

    def test_diff_slash_tracking(self):
        """Testing GitClient diff with tracking branch that has slash in its
        name
        """
        client = self.build_client()

        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'my/branch', '--track',
                       'origin/not-master'])
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')
        commit_id = self._git_get_head()

        client.get_repository_info()
        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'commit_id': commit_id,
                'base_commit_id': base_commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 5e98e9540e1b741b5be24fcb33c40c1c8069c1fb..'
                    b'e619c1387f5feb91f0ca83194650bfe4f6c2e347 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -1,4 +1,6 @@\n'
                    b' ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b' Italiam, fato profugus, Laviniaque venit\n'
                    b' litora, multum ille et terris iactatus et alto\n'
                    b' vi superum saevae memorem Iunonis ob iram;\n'
                ),
                'parent_diff': None,
            })

    def test_parse_revision_spec_no_args(self):
        """Testing GitClient.parse_revision_spec with no specified revisions"""
        client = self.build_client()

        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': base_commit_id,
                'commit_id': tip_commit_id,
                'tip': tip_commit_id,
            })

    def test_parse_revision_spec_no_args_parent(self):
        """Testing GitClient.parse_revision_spec with no specified revisions
        and a parent diff
        """
        client = self.build_client(options={
            'parent_branch': 'parent-branch',
        })
        parent_base_commit_id = self._git_get_head()

        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'parent-branch', '--track',
                       'origin/not-master'])
        parent_base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        base_commit_id = self._git_get_head()

        self._run_git(['checkout', '-b', 'topic-branch'])

        self._git_add_file_commit('foo.txt', FOO3, 'Commit 3')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': base_commit_id,
                'commit_id': tip_commit_id,
                'parent_base': parent_base_commit_id,
                'tip': tip_commit_id,
            })

    def test_parse_revision_spec_one_arg(self):
        """Testing GitClient.parse_revision_spec with one specified revision"""
        client = self.build_client()

        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        self.assertEqual(
            client.parse_revision_spec([tip_commit_id]),
            {
                'base': base_commit_id,
                'commit_id': tip_commit_id,
                'tip': tip_commit_id,
            })

    def test_parse_revision_spec_one_arg_parent(self):
        """Testing GitClient.parse_revision_spec with one specified revision
        and a parent diff
        """
        client = self.build_client()

        parent_base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO3, 'Commit 3')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        self.assertEqual(
            client.parse_revision_spec([tip_commit_id]),
            {
                'base': base_commit_id,
                'commit_id': tip_commit_id,
                'parent_base': parent_base_commit_id,
                'tip': tip_commit_id,
            })

    def test_parse_revision_spec_two_args(self):
        """Testing GitClient.parse_revision_spec with two specified
        revisions
        """
        client = self.build_client()

        base_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'topic-branch'])
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        self.assertEqual(
            client.parse_revision_spec(['master', 'topic-branch']),
            {
                'base': base_commit_id,
                'tip': tip_commit_id,
            })

    def test_parse_revision_spec_one_arg_two_revs(self):
        """Testing GitClient.parse_revision_spec with diff-since syntax"""
        client = self.build_client()

        base_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'topic-branch'])
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        self.assertEqual(
            client.parse_revision_spec(['master...topic-branch']),
            {
                'base': base_commit_id,
                'tip': tip_commit_id,
            })

    def test_parse_revision_spec_one_arg_since_merge(self):
        """Testing GitClient.parse_revision_spec with diff-since-merge
        syntax
        """
        client = self.build_client()

        base_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'topic-branch'])
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        self.assertEqual(
            client.parse_revision_spec(['master...topic-branch']),
            {
                'base': base_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent(self):
        """Testing GitClient.parse_revision_spec with target branch off a
        tracking branch not aligned with the remote
        """
        client = self.build_client()

        # In this case, the parent must be the non-aligned tracking branch
        # and the parent_base must be the remote tracking branch.
        client.get_repository_info()

        self._git_add_file_commit('foo.txt', FOO1, 'on master')
        self._run_git(['checkout', 'not-master'])  # A remote branch
        parent_base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'on not-master')
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'topic-branch'])
        self._git_add_file_commit('foo.txt', FOO3, 'commit 2')
        self._git_add_file_commit('foo.txt', FOO4, 'commit 3')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        # revisions =
        #     {
        #         'base': u'357c1b9',
        #         'tip': u'10c5cd3',
        #         'parent_base': u'0e88e51',
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * 7c17015 (master) on master
        #     | * 10c5cd3 (HEAD -> topic-branch) commit 3
        #     | * 00c99f9 commit 2
        #     | * 357c1b9 (not-master) on not-master
        #     | * 0e88e51 (origin/not-master) Commit 2
        #     |/
        #     * 18c5c09 (origin/master, origin/HEAD) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec(['topic-branch', '^not-master']),
            {
                'base': parent_commit_id,
                'parent_base': parent_base_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_one(self):
        """Testing GitClient.parse_revision_spec with target branch off a
        tracking branch aligned with the remote
        """
        client = self.build_client(options={
            'tracking': 'origin/not-master',
        })

        # In this case, the parent_base should be the tracking branch aligned
        # with the remote.
        client.get_repository_info()

        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'not-master',
                       '--track', 'origin/not-master'])
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO3, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        # revisions =
        #     {
        #         'commit_id': u'0a5734a',
        #         'base': u'0e88e51',
        #         'tip': u'0a5734a',
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * 0a5734a (HEAD -> feature-branch) on feature-branch
        #     * 0e88e51 (origin/not-master, not-master) Commit 2
        #     * 18c5c09 (origin/master, origin/HEAD, master) Commit 1
        #     * e6a3577 Initial Commit
        #
        # Because parent_base == base, parent_base will not be in revisions.
        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': parent_commit_id,
                'commit_id': tip_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_two(self):
        """Testing GitClient.parse_revision_spec with target branch off
        a tracking branch with changes since the remote
        """
        client = self.build_client()

        # In this case, the parent_base must be the remote tracking branch,
        # despite the fact that it is a few changes behind.
        client.get_repository_info()

        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'not-master',
                       '--track', 'origin/not-master'])
        parent_base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'on not-master')
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO3, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        # revisions =
        #     {
        #         'base': u'b0f5d74',
        #         'tip': u'8b5d1b9',
        #         'parent_base': u'0e88e51',
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * 8b5d1b9 (HEAD -> feature-branch) on feature-branch
        #     * b0f5d74 (not-master) on not-master
        #     * 0e88e51 (origin/not-master) Commit 2
        #     * 18c5c09 (origin/master, origin/HEAD, master) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec(['feature-branch', '^not-master']),
            {
                'base': parent_commit_id,
                'parent_base': parent_base_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_three(self):
        """Testing GitClient.parse_revision_spec with target branch off a
        branch not properly tracking the remote
        """
        client = self.build_client()

        # In this case, the parent_base must be the remote tracking branch,
        # even though it is not properly being tracked.
        client.get_repository_info()

        self._run_git(['branch', '--no-track', 'not-master',
                       'origin/not-master'])
        self._run_git(['checkout', 'not-master'])
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO3, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        # revisions =
        #     {
        #         'base': u'0e88e51',
        #         'tip': u'58981f2',
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * 58981f2 (HEAD -> feature-branch) on feature-branch
        #     * 0e88e51 (origin/not-master, not-master) Commit 2
        #     * 18c5c09 (origin/master, origin/HEAD, master) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec(['feature-branch', '^not-master']),
            {
                'base': parent_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_four(self):
        """Testing GitClient.parse_revision_spec with a target branch that
        merged a tracking branch off another tracking branch
        """
        client = self.build_client()

        # In this case, the parent_base must be the base of the merge, because
        # the user will expect that the diff would show the merged changes.
        client.get_repository_info()

        self._run_git(['checkout', 'master'])
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO1, 'on feature-branch')
        self._run_git(['merge', 'origin/not-master'])
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        # revisions =
        #     {
        #         'commit_id': u'bef8dcd',
        #         'base': u'18c5c09',
        #         'tip': u'bef8dcd',
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     *   bef8dcd (HEAD -> feature-branch) Merge remote-tracking branch
        #                 'origin/not-master' into feature-branch
        #     |\
        #     | * 0e88e51 (origin/not-master) Commit 2
        #     * | a385539 on feature-branch
        #     |/
        #     * 18c5c09 (origin/master, origin/HEAD, master) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': parent_commit_id,
                'commit_id': tip_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_five(self):
        """Testing GitClient.parse_revision_spec with a target branch posted
        off a tracking branch that merged another tracking branch
        """
        client = self.build_client(options={
            'tracking': 'origin/not-master',
        })

        # In this case, the parent_base must be tracking branch that merged
        # the other tracking branch.
        client.get_repository_info()

        self._git_add_file_commit('foo.txt', FOO2, 'on master')
        self._run_git(['checkout', '-b', 'not-master',
                       '--track', 'origin/not-master'])
        self._run_git(['merge', 'origin/master'])
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO4, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        # revisions =
        #     {
        #         'commit_id': u'ebf2e89',
        #         'base': u'0e88e51',
        #         'tip': u'ebf2e89'
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * ebf2e89 (HEAD -> feature-branch) on feature-branch
        #     * 0e88e51 (origin/not-master, not-master) Commit 2
        #     | * 7e202ff (master) on master
        #     |/
        #     * 18c5c09 (origin/master, origin/HEAD) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': parent_commit_id,
                'commit_id': tip_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_six(self):
        """Testing GitClient.parse_revision_spec with a target branch posted
        off a remote branch without any tracking branches
        """
        client = self.build_client()

        # In this case, the parent_base must be remote tracking branch. The
        # existence of a tracking branch shouldn't matter much.
        client.get_repository_info()

        self._run_git(['checkout', '-b', 'feature-branch',
                       'origin/not-master'])
        parent_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        client.get_repository_info()

        # revisions =
        #     {
        #         'commit_id': u'19da590',
        #         'base': u'0e88e51',
        #         'tip': u'19da590',
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * 19da590 (HEAD -> feature-branch) on feature-branch
        #     * 0e88e51 (origin/not-master) Commit 2
        #     * 18c5c09 (origin/master, origin/HEAD, master) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec([]),
            {
                'base': parent_commit_id,
                'commit_id': tip_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_seven(self):
        """Testing GitClient.parse_revision_spec with a target branch posted
        off a remote branch that is aligned to the same commit as another
        remote branch
        """
        client = self.build_client()

        # In this case, the parent_base must be common commit that the two
        # remote branches are aligned to.
        client.get_repository_info()

        # Since pushing data upstream to the test repo corrupts its state,
        # we need to use the child clone.
        os.chdir(self.child_clone_dir)

        client.get_repository_info()

        self._run_git(['checkout', '-b', 'remote-branch1'])
        self._git_add_file_commit('foo1.txt', FOO1, 'on remote-branch1')
        self._run_git(['push', 'origin', 'remote-branch1'])
        self._run_git(['checkout', '-b', 'remote-branch2'])
        self._git_add_file_commit('foo2.txt', FOO1, 'on remote-branch2')
        self._run_git(['push', 'origin', 'remote-branch2'])

        self._run_git(['checkout', 'master'])
        self._run_git(['merge', 'remote-branch1'])
        self._run_git(['merge', 'remote-branch2'])
        self._git_add_file_commit('foo3.txt', FOO1, 'on master')
        parent_commit_id = self._git_get_head()

        self._run_git(['push', 'origin', 'master:remote-branch1'])
        self._run_git(['push', 'origin', 'master:remote-branch2'])

        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo4.txt', FOO1, 'on feature-branch')

        tip_commit_id = self._git_get_head()

        # revisions =
        #     {
        #         'base': u'bf0036b',
        #         'tip': u'dadae87',
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * dadae87 (HEAD -> feature-branch) on feature-branch
        #     * bf0036b (origin/remote-branch2, origin/remote-branch1, master)
        #                                                            on master
        #     * 5f48441 (remote-branch2) on remote-branch2
        #     * eb40eaf (remote-branch1) on remote-branch1
        #     * 18c5c09 (origin/master, origin/HEAD) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec(['feature-branch', '^master']),
            {
                'base': parent_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_eight(self):
        """Testing GitClient.parse_revision_spec with a target branch not
        up-to-date with a remote branch
        """
        client = self.build_client()

        # In this case, there is no good way of detecting the remote branch we
        # are not up-to-date with, so the parent_base must be the common commit
        # that the target branch and remote branch share.
        client.get_repository_info()

        # Since pushing data upstream to the test repo corrupts its state,
        # we need to use the child clone.
        os.chdir(self.child_clone_dir)

        client.get_repository_info()

        self._run_git(['checkout', 'master'])
        self._git_add_file_commit('foo.txt', FOO1, 'on master')

        parent_base_commit_id = self._git_get_head()

        self._run_git(['checkout', '-b', 'remote-branch1'])
        self._git_add_file_commit('foo1.txt', FOO1, 'on remote-branch1')
        self._run_git(['push', 'origin', 'remote-branch1'])

        self._run_git(['checkout', 'master'])
        self._git_add_file_commit('foo2.txt', FOO1, 'on master')
        parent_commit_id = self._git_get_head()

        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo3.txt', FOO1, 'on feature-branch')

        client.get_repository_info()
        tip_commit_id = self._git_get_head()

        # revisions =
        #     {
        #         'base': u'318f050',
        #         'tip': u'6e37a00',
        #         'parent_base': u'0ff6635'
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * 6e37a00 (HEAD -> feature-branch) on feature-branch
        #     * 318f050 (master) on master
        #     | * 9ad7b1f (origin/remote-branch1, remote-branch1)
        #     |/                                on remote-branch1
        #     * 0ff6635 on master
        #     * 18c5c09 (origin/master, origin/HEAD) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec(['feature-branch', '^master']),
            {
                'base': parent_commit_id,
                'parent_base': parent_base_commit_id,
                'tip': tip_commit_id,
            })

    def test_diff_finding_parent_case_nine(self):
        """Testing GitClient.parse_revision_spec with a target branch that has
        branches from different remotes in its path
        """
        client = self.build_client()

        # In this case, the other remotes should be ignored and the parent_base
        # should be some origin/*.
        client.get_repository_info()
        self._run_git(['checkout', 'not-master'])

        # Since pushing data upstream to the test repo corrupts its state,
        # we need to use the child clone.
        os.chdir(self.grandchild_clone_dir)

        client.get_repository_info()

        # Adding the original clone as a second remote to our repository.
        self._run_git(['remote', 'add', 'not-origin', self.orig_clone_dir])
        self._run_git(['fetch', 'not-origin'])
        parent_base_commit_id = self._git_get_head()

        self._run_git(['checkout', 'master'])
        self._run_git(['merge', 'not-origin/master'])

        self._git_add_file_commit('foo1.txt', FOO1, 'on master')
        self._run_git(['push', 'not-origin', 'master:master'])
        self._git_add_file_commit('foo2.txt', FOO1, 'on master')
        parent_commit_id = self._git_get_head()

        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo3.txt', FOO1, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        # revisions =
        #     {
        #         'base': u'6f23ed0',
        #         'tip': u'8703f95',
        #         'parent_base': u'18c5c09',
        #     }
        #
        # `git log --graph --all --decorate --oneline` =
        #     * 8703f95 (HEAD -> feature-branch) on feature-branch
        #     * 6f23ed0 (master) on master
        #     * f6236bf (not-origin/master) on master
        #     | * 0e88e51 (origin/not-master, not-origin/not-master) Commit 2
        #     |/
        #     * 18c5c09 (origin/master, origin/HEAD) Commit 1
        #     * e6a3577 Initial Commit
        self.assertEqual(
            client.parse_revision_spec(['feature-branch', '^master']),
            {
                'base': parent_commit_id,
                'parent_base': parent_base_commit_id,
                'tip': tip_commit_id,
            })

    def test_get_raw_commit_message(self):
        """Testing GitClient.get_raw_commit_message"""
        client = self.build_client()

        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        client.get_repository_info()
        revisions = client.parse_revision_spec()

        self.assertEqual(client.get_raw_commit_message(revisions),
                         'Commit 2')

    def test_push_upstream_pull_exception(self):
        """Testing GitClient.push_upstream with an invalid remote branch"""
        client = self.build_client()

        # It must raise a PushError exception because the 'git pull' from an
        # invalid upstream branch will fail.
        with self.assertRaisesMessage(PushError,
                                      'Could not determine remote for branch '
                                      '"non-existent-branch".'):
            client.push_upstream('non-existent-branch')

    def test_push_upstream_no_push_exception(self):
        """Testing GitClient.push_upstream with 'git push' disabled"""
        client = self.build_client()

        # Set the push url to be an invalid one.
        self._run_git(['remote', 'set-url', '--push', 'origin', 'bad-url'])

        with self.assertRaisesMessage(PushError,
                                      'Could not push branch "master" to '
                                      'upstream.'):
            client.push_upstream('master')

    def test_merge_invalid_destination(self):
        """Testing GitClient.merge with an invalid destination branch"""
        client = self.build_client()

        # It must raise a MergeError exception because 'git checkout' to the
        # invalid destination branch will fail.
        try:
            client.merge(target='master',
                         destination='non-existent-branch',
                         message='commit message',
                         author=self.AUTHOR)
        except MergeError as e:
            self.assertTrue(str(e).startswith(
                'Could not checkout to branch "non-existent-branch"'))
        else:
            self.fail('Expected MergeError')

    def test_merge_invalid_target(self):
        """Testing GitClient.merge with an invalid target branch"""
        client = self.build_client()

        # It must raise a MergeError exception because 'git merge' from an
        # invalid target branch will fail.
        try:
            client.merge(target='non-existent-branch',
                         destination='master',
                         message='commit message',
                         author=self.AUTHOR)
        except MergeError as e:
            self.assertTrue(str(e).startswith(
                'Could not merge branch "non-existent-branch"'))
        else:
            self.fail('Expected MergeError')

    def test_merge_with_squash(self):
        """Testing GitClient.merge with squash set to True"""
        client = self.build_client()

        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with the '--squash' flag (and not with the
        # '--no-ff' flag.
        self.spy_on(execute)

        client.get_repository_info()

        # Since pushing data upstream to the test repo corrupts its state,
        # we need to use the child clone.
        os.chdir(self.child_clone_dir)

        client.get_repository_info()

        self._run_git(['checkout', '-b', 'new-branch'])
        self._git_add_file_commit('foo1.txt', FOO1, 'on new-branch')
        self._run_git(['push', 'origin', 'new-branch'])

        client.merge(target='new-branch',
                     destination='master',
                     message='message',
                     author=self.AUTHOR,
                     squash=True)

        self.assertSpyCalledWith(
            execute.calls[-2],
            ['git', 'merge', 'new-branch', '--squash', '--no-commit'])

    def test_merge_without_squash(self):
        """Testing GitClient.merge with squash set to False"""
        client = self.build_client()

        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with the '--no-ff' flag (and not with the
        # '--squash' flag).
        self.spy_on(execute)

        client.get_repository_info()

        # Since pushing data upstream to the test repo corrupts its state,
        # we need to use the child clone.
        os.chdir(self.child_clone_dir)

        client.get_repository_info()

        self._run_git(['checkout', '-b', 'new-branch'])
        self._git_add_file_commit('foo1.txt', FOO1, 'on new-branch')
        self._run_git(['push', 'origin', 'new-branch'])

        client.merge(target='new-branch',
                     destination='master',
                     message='message',
                     author=self.AUTHOR,
                     squash=False)

        self.assertSpyCalledWith(
            execute.calls[-2],
            ['git', 'merge', 'new-branch', '--no-ff', '--no-commit'])

    def test_create_commit_with_run_editor_true(self):
        """Testing GitClient.create_commit with run_editor set to True"""
        client = self.build_client()

        self.spy_on(execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='Test commit message.',
                             author=self.AUTHOR,
                             run_editor=True,
                             files=['foo.txt'])

        self.assertSpyLastCalledWith(
            execute,
            ['git', 'commit', '-m', 'TEST COMMIT MESSAGE.',
             '--author', 'name <email>'])

    def test_create_commit_with_run_editor_false(self):
        """Testing GitClient.create_commit with run_editor set to False"""
        client = self.build_client()

        self.spy_on(execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='Test commit message.',
                             author=self.AUTHOR,
                             run_editor=False,
                             files=['foo.txt'])

        self.assertSpyLastCalledWith(
            execute,
            ['git', 'commit', '-m', 'Test commit message.',
             '--author', 'name <email>'])

    def test_create_commit_with_all_files_true(self):
        """Testing GitClient.create_commit with all_files set to True"""
        client = self.build_client()

        self.spy_on(execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='message',
                             author=self.AUTHOR,
                             run_editor=False,
                             files=[],
                             all_files=True)

        self.assertSpyCalledWith(
            execute.calls[0],
            ['git', 'add', '--all', ':/'])
        self.assertSpyLastCalledWith(
            execute,
            ['git', 'commit', '-m', 'message', '--author', 'name <email>'])

    def test_create_commit_with_all_files_false(self):
        """Testing GitClient.create_commit with all_files set to False"""
        client = self.build_client()

        self.spy_on(execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='message',
                             author=self.AUTHOR,
                             run_editor=False,
                             files=['foo.txt'],
                             all_files=False)

        self.assertSpyCalledWith(
            execute.calls[0],
            ['git', 'add', 'foo.txt'])
        self.assertSpyLastCalledWith(
            execute,
            ['git', 'commit', '-m', 'message', '--author', 'name <email>'])

    def test_create_commit_with_empty_commit_message(self):
        """Testing GitClient.create_commit with empty commit message"""
        client = self.build_client()

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        message = (
            "A commit message wasn't provided. The patched files are in "
            "your tree and are staged for commit, but haven't been "
            "committed. Run `git commit` to commit them."
        )

        with self.assertRaisesMessage(CreateCommitError, message):
            client.create_commit(message='',
                                 author=self.AUTHOR,
                                 run_editor=True,
                                 files=['foo.txt'])

    def test_create_commit_without_author(self):
        """Testing GitClient.create_commit without author information"""
        client = self.build_client()

        self.spy_on(execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='Test commit message.',
                             author=None,
                             run_editor=True,
                             files=['foo.txt'])

        self.assertSpyLastCalledWith(
            execute,
            ['git', 'commit', '-m', 'TEST COMMIT MESSAGE.'])

    def test_delete_branch_with_merged_only(self):
        """Testing GitClient.delete_branch with merged_only set to True"""
        client = self.build_client()

        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with the -d flag (and not the -D flag).
        self.spy_on(execute)

        self._run_git(['branch', 'new-branch'])

        client.delete_branch('new-branch', merged_only=True)

        self.assertSpyLastCalledWith(
            execute,
            ['git', 'branch', '-d', 'new-branch'])

    def test_delete_branch_without_merged_only(self):
        """Testing GitClient.delete_branch with merged_only set to False"""
        client = self.build_client()

        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with the -D flag (and not the -d flag).
        self.spy_on(execute)

        self._run_git(['branch', 'new-branch'])

        client.delete_branch('new-branch', merged_only=False)

        self.assertSpyLastCalledWith(
            execute,
            ['git', 'branch', '-D', 'new-branch'])

    def test_get_parent_branch_with_non_master_default(self):
        """Testing GitClient._get_parent_branch with a non-master default
        branch
        """
        client = self.build_client()

        # Since pushing data upstream to the test repo corrupts its state,
        # we need to use the child clone.
        os.chdir(self.child_clone_dir)

        self._run_git(['branch', '-m', 'master', 'main'])
        self._run_git(['push', '-u', 'origin', 'main'])

        client.get_repository_info()

        self.assertEqual(client._get_parent_branch(), 'origin/main')
