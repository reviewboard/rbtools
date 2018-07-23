"""Unit tests for GitClient."""

from __future__ import unicode_literals

import os
from hashlib import md5

import six
from kgb import SpyAgency
from nose import SkipTest

from rbtools.clients import RepositoryInfo
from rbtools.clients.errors import (MergeError,
                                    PushError,
                                    TooManyRevisionsError)
from rbtools.clients.git import GitClient
from rbtools.clients.tests import FOO1, FOO2, FOO3, FOO4, SCMClientTests
from rbtools.utils.console import edit_text
from rbtools.utils.filesystem import is_exe_in_path, load_config
from rbtools.utils.process import execute


class GitClientTests(SpyAgency, SCMClientTests):
    """Unit tests for GitClient."""

    TESTSERVER = 'http://127.0.0.1:8080'
    AUTHOR = type(
        str('Author'),
        (object,),
        {
            'fullname': 'name',
            'email': 'email'
        })

    def _run_git(self, command):
        return execute(['git'] + command, env=None, cwd=self.clone_dir,
                       split_lines=False, ignore_errors=False,
                       extra_ignore_errors=())

    def _git_add_file_commit(self, filename, data, msg):
        """Add a file to a git repository.

        Args:
            filename (unicode):
                The filename to write to.

            data (unicode):
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

    def setUp(self):
        if not is_exe_in_path('git'):
            raise SkipTest('git not found in path')

        super(GitClientTests, self).setUp()

        self.set_user_home(
            os.path.join(self.testdata_dir, 'homedir'))
        self.git_dir = os.path.join(self.testdata_dir, 'git-repo')

        self.clone_dir = self.chdir_tmp()
        self._run_git(['clone', self.git_dir, self.clone_dir])
        self.client = GitClient(options=self.options)

        self.options.parent_branch = None
        self.options.tracking = None

    def test_get_repository_info_simple(self):
        """Testing GitClient get_repository_info, simple case"""
        ri = self.client.get_repository_info()
        self.assertTrue(isinstance(ri, RepositoryInfo))
        self.assertEqual(ri.base_path, '')
        self.assertEqual(ri.path.rstrip('/.git'), self.git_dir)
        self.assertTrue(ri.supports_parent_diffs)
        self.assertFalse(ri.supports_changesets)

    def test_scan_for_server_simple(self):
        """Testing GitClient scan_for_server, simple case"""
        ri = self.client.get_repository_info()

        server = self.client.scan_for_server(ri)
        self.assertTrue(server is None)

    def test_scan_for_server_reviewboardrc(self):
        """Testing GitClient scan_for_server, .reviewboardrc case"""
        with self.reviewboardrc({'REVIEWBOARD_URL': self.TESTSERVER}):
            self.client.config = load_config()

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
        commit_id = self._git_get_head()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertTrue('commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_too_many_revisions(self):
        """Testing GitClient parse_revision_spec with too many revisions"""
        self.assertRaises(TooManyRevisionsError,
                          self.client.parse_revision_spec,
                          [1, 2, 3])

    def test_diff_simple_multiple(self):
        """Testing GitClient simple diff with multiple commits case"""
        self.client.get_repository_info()

        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('foo.txt', FOO2, 'commit 1')
        self._git_add_file_commit('foo.txt', FOO3, 'commit 1')
        commit_id = self._git_get_head()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertTrue('commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'c9a31264f773406edff57a8ed10d9acc')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_diff_exclude(self):
        """Testing GitClient simple diff with file exclusion"""
        self.client.get_repository_info()
        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('exclude.txt', FOO2, 'commit 2')
        commit_id = self._git_get_head()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions, exclude_patterns=['exclude.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_diff_exclude_in_subdir(self):
        """Testing GitClient simple diff with file exclusion in a subdir"""
        base_commit_id = self._git_get_head()

        os.mkdir('subdir')
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('subdir/exclude.txt', FOO2, 'commit 2')

        os.chdir('subdir')
        self.client.get_repository_info()

        commit_id = self._git_get_head()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions,
                                  exclude_patterns=['exclude.txt'])

        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_diff_exclude_root_pattern_in_subdir(self):
        """Testing GitClient diff with file exclusion in the repo root"""
        base_commit_id = self._git_get_head()

        os.mkdir('subdir')
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._git_add_file_commit('exclude.txt', FOO2, 'commit 2')
        os.chdir('subdir')

        self.client.get_repository_info()

        commit_id = self._git_get_head()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(
            revisions,
            exclude_patterns=[os.path.sep + 'exclude.txt'])

        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_diff_branch_diverge(self):
        """Testing GitClient diff with divergent branches"""
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._run_git(['checkout', '-b', 'mybranch', '--track',
                      'origin/master'])
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')
        commit_id = self._git_get_head()
        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertTrue('commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'cfb79a46f7a35b07e21765608a7852f7')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

        self._run_git(['checkout', 'master'])
        self.client.get_repository_info()
        commit_id = self._git_get_head()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertTrue('commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_diff_tracking_no_origin(self):
        """Testing GitClient diff with a tracking branch, but no origin
        remote"""
        self._run_git(['remote', 'add', 'quux', self.git_dir])
        self._run_git(['fetch', 'quux'])
        self._run_git(['checkout', '-b', 'mybranch', '--track', 'quux/master'])

        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO1, 'delete and modify stuff')
        commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertTrue('commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_diff_local_tracking(self):
        """Testing GitClient diff with a local tracking branch"""
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')

        self._run_git(['checkout', '-b', 'mybranch', '--track', 'master'])
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')
        commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertTrue('commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'cfb79a46f7a35b07e21765608a7852f7')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_diff_tracking_override(self):
        """Testing GitClient diff with option override for tracking branch"""
        self.options.tracking = 'origin/master'

        self._run_git(['remote', 'add', 'bad', self.git_dir])
        self._run_git(['fetch', 'bad'])
        self._run_git(['checkout', '-b', 'mybranch', '--track', 'bad/master'])

        base_commit_id = self._git_get_head()

        self._git_add_file_commit('foo.txt', FOO1, 'commit 1')
        commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertTrue('commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '69d4616cf985f6b10571036db744e2d8')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

    def test_diff_slash_tracking(self):
        """Testing GitClient diff with tracking branch that has slash in its
        name"""
        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'my/branch', '--track',
                       'origin/not-master'])
        base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'commit 2')
        commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(len(result), 4)
        self.assertTrue('diff' in result)
        self.assertTrue('parent_diff' in result)
        self.assertTrue('base_commit_id' in result)
        self.assertTrue('commit_id' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'd2015ff5fd0297fd7f1210612f87b6b3')
        self.assertEqual(result['parent_diff'], None)
        self.assertEqual(result['base_commit_id'], base_commit_id)
        self.assertEqual(result['commit_id'], commit_id)

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
        """Testing GitClient.parse_revision_spec with no specified revisions
        and a parent diff"""
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
        """Testing GitClient.parse_revision_spec with one specified revision
        and a parent diff"""
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
        """Testing GitClient.parse_revision_spec with two specified
        revisions"""
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
        """Testing GitClient.parse_revision_spec with diff-since-merge
        syntax"""
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

    def test_diff_finding_parent(self):
        """Testing GitClient.parse_revision_spec with target branch off a
        tracking branch not aligned with the remote"""
        # In this case, the parent must be the non-aligned tracking branch
        # and the parent_base must be the remote tracking branch.
        self.client.get_repository_info()

        self._git_add_file_commit('foo.txt', FOO1, 'on master')
        self._run_git(['checkout', 'not-master'])  # A remote branch
        parent_base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'on not-master')
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'topic-branch'])
        self._git_add_file_commit('foo.txt', FOO3, 'commit 2')
        self._git_add_file_commit('foo.txt', FOO4, 'commit 3')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec(
            ['topic-branch', '^not-master'])

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 3)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' in revisions)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)
        self.assertEqual(revisions['parent_base'], parent_base_commit_id)

    def test_diff_finding_parent_case_one(self):
        """Testing GitClient.parse_revision_spec with target branch off a
        tracking branch aligned with the remote"""
        # In this case, the parent_base should be the tracking branch aligned
        # with the remote.
        self.client.get_repository_info()

        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'not-master',
                       '--track', 'origin/not-master'])
        self.options.tracking = 'origin/not-master'
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO3, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec()

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 3)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)

        # Because parent_base == base, parent_base will not be in revisions.
        self.assertFalse('parent_base' in revisions)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_diff_finding_parent_case_two(self):
        """Testing GitClient.parse_revision_spec with target branch off
        a tracking branch with changes since the remote"""
        # In this case, the parent_base must be the remote tracking branch,
        # despite the fact that it is a few changes behind.
        self.client.get_repository_info()

        self._run_git(['fetch', 'origin'])
        self._run_git(['checkout', '-b', 'not-master',
                       '--track', 'origin/not-master'])
        parent_base_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'on not-master')
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO3, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec(['feature-branch',
                                                     '^not-master'])

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 3)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' in revisions)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)
        self.assertEqual(revisions['parent_base'], parent_base_commit_id)

    def test_diff_finding_parent_case_three(self):
        """Testing GitClient.parse_revision_spec with target branch off a
        branch not properly tracking the remote"""

        # In this case, the parent_base must be the remote tracking branch,
        # even though it is not properly being tracked.
        self.client.get_repository_info()

        self._run_git(['branch', '--no-track', 'not-master',
                       'origin/not-master'])
        self._run_git(['checkout', 'not-master'])
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO3, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec(['feature-branch',
                                                     '^not-master'])

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 2)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertFalse('parent_base' in revisions)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_diff_finding_parent_case_four(self):
        """Testing GitClient.parse_revision_spec with a target branch that
        merged a tracking branch off another tracking branch"""
        # In this case, the parent_base must be the base of the merge, because
        # the user will expect that the diff would show the merged changes.
        self.client.get_repository_info()

        self._run_git(['checkout', 'master'])
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO1, 'on feature-branch')
        self._run_git(['merge', 'origin/not-master'])
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec()

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 3)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('commit_id' in revisions)
        self.assertFalse('parent_base' in revisions)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)
        self.assertEqual(revisions['commit_id'], tip_commit_id)

    def test_diff_finding_parent_case_five(self):
        """Testing GitClient.parse_revision_spec with a target branch posted
        off a tracking branch that merged another tracking branch"""
        # In this case, the parent_base must be tracking branch that merged
        # the other tracking branch.
        self.client.get_repository_info()

        self._git_add_file_commit('foo.txt', FOO2, 'on master')
        self._run_git(['checkout', '-b', 'not-master',
                       '--track', 'origin/not-master'])
        self.options.tracking = 'origin/not-master'
        self._run_git(['merge', 'origin/master'])
        parent_commit_id = self._git_get_head()
        self._run_git(['checkout', '-b', 'feature-branch'])
        self._git_add_file_commit('foo.txt', FOO4, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

        revisions = self.client.parse_revision_spec()

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 3)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('commit_id' in revisions)
        self.assertFalse('parent_base' in revisions)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)
        self.assertEqual(revisions['commit_id'], tip_commit_id)

    def test_diff_finding_parent_case_six(self):
        """Testing GitClient.parse_revision_spec with a target branch posted
        off a remote branch without any tracking branches"""
        # In this case, the parent_base must be remote tracking branch. The
        # existence of a tracking branch shouldn't matter much.
        self.client.get_repository_info()

        self._run_git(['checkout', '-b', 'feature-branch',
                       'origin/not-master'])
        parent_commit_id = self._git_get_head()
        self._git_add_file_commit('foo.txt', FOO2, 'on feature-branch')
        tip_commit_id = self._git_get_head()

        self.client.get_repository_info()

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

        revisions = self.client.parse_revision_spec([])
        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 3)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('commit_id' in revisions)
        self.assertFalse('parent_base' in revisions)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)
        self.assertEqual(revisions['commit_id'], tip_commit_id)

    def test_diff_finding_parent_case_seven(self):
        """Testing GitClient.parse_revision_spec with a target branch posted
        off a remote branch that is aligned to the same commit as another
        remote branch"""
        # In this case, the parent_base must be common commit that the two
        # remote branches are aligned to.
        self.client.get_repository_info()

        # Since pushing data upstream to the test repo corrupts its state,
        # we clone the clone and use one clone as the remote for the other.
        self.git_dir = os.getcwd()
        self.clone_dir = self.chdir_tmp()
        self._run_git(['clone', self.git_dir, self.clone_dir])

        self.client.get_repository_info()

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

        revisions = self.client.parse_revision_spec(['feature-branch',
                                                     '^master'])

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 2)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertFalse('parent_base' in revisions)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_diff_finding_parent_case_eight(self):
        """Testing GitClient.parse_revision_spec with a target branch not
        up-to-date with a remote branch"""
        # In this case, there is no good way of detecting the remote branch we
        # are not up-to-date with, so the parent_base must be the common commit
        # that the target branch and remote branch share.
        self.client.get_repository_info()

        # Since pushing data upstream to the test repo corrupts its state,
        # we clone the clone and use one clone as the remote for the other.
        self.git_dir = os.getcwd()
        self.clone_dir = self.chdir_tmp()
        self._run_git(['clone', self.git_dir, self.clone_dir])

        self.client.get_repository_info()

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

        self.client.get_repository_info()
        tip_commit_id = self._git_get_head()

        revisions = self.client.parse_revision_spec(['feature-branch',
                                                     '^master'])

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 3)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' in revisions)
        self.assertEqual(revisions['parent_base'], parent_base_commit_id)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_diff_finding_parent_case_nine(self):
        """Testing GitClient.parse_revision_spec with a target branch that has
        branches from different remotes in its path"""

        # In this case, the other remotes should be ignored and the parent_base
        # should be some origin/*.
        self.client.get_repository_info()
        self._run_git(['checkout', 'not-master'])

        orig_clone = os.getcwd()
        self.clone_dir = self.chdir_tmp()
        self._run_git(['clone', self.git_dir, self.clone_dir])

        self.client.get_repository_info()

        # Adding the original clone as a second remote to our repository.
        self._run_git(['remote', 'add', 'not-origin', orig_clone])
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

        revisions = self.client.parse_revision_spec(['feature-branch',
                                                     '^master'])

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

        self.assertTrue(isinstance(revisions, dict))
        self.assertEqual(len(revisions), 3)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' in revisions)
        self.assertEqual(revisions['parent_base'], parent_base_commit_id)
        self.assertEqual(revisions['base'], parent_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_get_raw_commit_message(self):
        """Testing GitClient.get_raw_commit_message"""
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        self.client.get_repository_info()
        revisions = self.client.parse_revision_spec()

        self.assertEqual(self.client.get_raw_commit_message(revisions),
                         'Commit 2')

    def test_push_upstream_pull_exception(self):
        """Testing GitClient.push_upstream with an invalid remote branch"""
        # It must raise a PushError exception because the 'git pull' from an
        # invalid upstream branch will fail.
        with self.assertRaisesRegexp(PushError,
                                     'Could not determine remote for branch '
                                     '"non-existent-branch".'):
            self.client.push_upstream('non-existent-branch')

    def test_push_upstream_no_push_exception(self):
        """Testing GitClient.push_upstream with 'git push' disabled"""
        # Set the push url to be an invalid one.
        self._run_git(['remote', 'set-url', '--push', 'origin', 'bad-url'])

        with self.assertRaisesRegexp(PushError,
                                     'Could not push branch "master" to '
                                     'upstream\.'):
            self.client.push_upstream('master')

    def test_merge_invalid_destination(self):
        """Testing GitClient.merge with an invalid destination branch"""
        # It must raise a MergeError exception because 'git checkout' to the
        # invalid destination branch will fail.
        try:
            self.client.merge('master', 'non-existent-branch',
                              'commit message', self.AUTHOR)
        except MergeError as e:
            self.assertTrue(six.text_type(e).startswith(
                'Could not checkout to branch "non-existent-branch"'))
        else:
            self.fail('Expected MergeError')

    def test_merge_invalid_target(self):
        """Testing GitClient.merge with an invalid target branch"""
        # It must raise a MergeError exception because 'git merge' from an
        # invalid target branch will fail.
        try:
            self.client.merge('non-existent-branch', 'master',
                              'commit message', self.AUTHOR)
        except MergeError as e:
            self.assertTrue(six.text_type(e).startswith(
                'Could not merge branch "non-existent-branch"'))
        else:
            self.fail('Expected MergeError')

    def test_merge_with_squash(self):
        """Testing GitClient.merge with squash set to True"""
        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with the '--squash' flag (and not with the
        # '--no-ff' flag.
        self.spy_on(execute)

        self.client.get_repository_info()

        # Since pushing data upstream to the test repo corrupts its state,
        # we clone the clone and use one clone as the remote for the other.
        # We need to push data upstrem for the merge to work.
        self.git_dir = os.getcwd()
        self.clone_dir = self.chdir_tmp()
        self._run_git(['clone', self.git_dir, self.clone_dir])

        self.client.get_repository_info()

        self._run_git(['checkout', '-b', 'new-branch'])
        self._git_add_file_commit('foo1.txt', FOO1, 'on new-branch')
        self._run_git(['push', 'origin', 'new-branch'])

        self.client.merge('new-branch', 'master', 'message', self.AUTHOR,
                          True)

        self.assertEqual(execute.spy.calls[-2].args[0],
                         ['git', 'merge', 'new-branch', '--squash',
                          '--no-commit'])

    def test_merge_without_squash(self):
        """Testing GitClient.merge with squash set to False"""
        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with the '--no-ff' flag (and not with the
        # '--squash' flag).
        self.spy_on(execute)

        self.client.get_repository_info()

        # Since pushing data upstream to the test repo corrupts its state,
        # we clone the clone and use one clone as the remote for the other.
        # We need to push data upstrem for the merge to work.
        self.git_dir = os.getcwd()
        self.clone_dir = self.chdir_tmp()
        self._run_git(['clone', self.git_dir, self.clone_dir])

        self.client.get_repository_info()

        self._run_git(['checkout', '-b', 'new-branch'])
        self._git_add_file_commit('foo1.txt', FOO1, 'on new-branch')
        self._run_git(['push', 'origin', 'new-branch'])

        self.client.merge('new-branch', 'master', 'message', self.AUTHOR,
                          False)

        self.assertEqual(execute.spy.calls[-2].args[0],
                         ['git', 'merge', 'new-branch', '--no-ff',
                          '--no-commit'])

    def test_create_commit_run_editor(self):
        """Testing GitClient.create_commit with run_editor set to True"""
        # We use a KGB function spy to check if edit_text is called, and then
        # we intercept the call returning a custom commit message. We then
        # ensure that execute is called with that custom commit message.
        self.spy_on(edit_text, call_fake=lambda message: 'new_message')
        self.spy_on(execute)

        foo = open('foo.txt', 'w')
        foo.write('change')
        foo.close()

        self.client.create_commit('old_message', self.AUTHOR, True,
                                  ['foo.txt'])

        self.assertTrue(edit_text.spy.called)
        self.assertEqual(execute.spy.last_call.args[0],
                         ['git', 'commit', '-m', 'new_message',
                          '--author="name <email>"'])

    def test_create_commit_without_run_editor(self):
        """Testing GitClient.create_commit with run_editor set to False"""
        # We use a KGB function spy to check if edit_text is not called. We set
        # it up so that if edit_text was called, we intercept the call returning
        # a custom commit message. However, since we are expecting edit_text to
        # not be called, we ensure that execute is called with the old commit
        # message (and not the custom new one).
        self.spy_on(edit_text, call_fake=lambda message: 'new_message')
        self.spy_on(execute)

        foo = open('foo.txt', 'w')
        foo.write('change')
        foo.close()

        self.client.create_commit('old_message', self.AUTHOR, False,
                                  ['foo.txt'])

        self.assertFalse(edit_text.spy.called)
        self.assertEqual(execute.spy.last_call.args[0],
                         ['git', 'commit', '-m', 'old_message',
                          '--author="name <email>"'])

    def test_create_commit_all_files(self):
        """Testing GitClient.create_commit with all_files set to True"""
        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with 'git add --all :/' (and not with 'git add
        # <filenames>').
        self.spy_on(execute)

        foo = open('foo.txt', 'w')
        foo.write('change')
        foo.close()

        self.client.create_commit('message', self.AUTHOR, False, [], True)

        self.assertEqual(execute.spy.calls[0].args[0],
                         ['git', 'add', '--all', ':/'])

    def test_create_commit_without_all_files(self):
        """Testing GitClient.create_commit with all_files set to False"""
        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with 'git add <filenames>' (and not with 'git add
        # --all :/').
        self.spy_on(execute)

        foo = open('foo.txt', 'w')
        foo.write('change')
        foo.close()

        self.client.create_commit('message', self.AUTHOR, False, ['foo.txt'],
                                  False)

        self.assertEqual(execute.spy.calls[0].args[0],
                         ['git', 'add', 'foo.txt'])

    def test_delete_branch_with_merged_only(self):
        """Testing GitClient.delete_branch with merged_only set to True"""
        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with the -d flag (and not the -D flag).
        self.spy_on(execute)

        self._run_git(['branch', 'new-branch'])

        self.client.delete_branch('new-branch', True)

        self.assertTrue(execute.spy.called)
        self.assertEqual(execute.spy.last_call.args[0],
                         ['git', 'branch', '-d', 'new-branch'])

    def test_delete_branch_without_merged_only(self):
        """Testing GitClient.delete_branch with merged_only set to False"""
        # We use a KGB function spy to check if execute is called with the
        # right arguments i.e. with the -D flag (and not the -d flag).
        self.spy_on(execute)

        self._run_git(['branch', 'new-branch'])

        self.client.delete_branch('new-branch', False)

        self.assertTrue(execute.spy.called)
        self.assertEqual(execute.spy.last_call.args[0],
                         ['git', 'branch', '-D', 'new-branch'])
