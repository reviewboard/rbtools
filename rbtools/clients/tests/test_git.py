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
from rbtools.clients.tests import FOO1, FOO2, FOO3, SCMClientTests
from rbtools.utils.console import edit_text
from rbtools.utils.filesystem import load_config
from rbtools.utils.process import execute


class GitClientTests(SpyAgency, SCMClientTests):
    """Unit tests for GitClient."""

    TESTSERVER = "http://127.0.0.1:8080"
    AUTHOR = type(
        b'Author',
        (object,),
        {
            'fullname': 'name',
            'email': 'email'
        })

    def _run_git(self, command):
        return execute(['git'] + command, env=None, split_lines=False,
                       ignore_errors=False, extra_ignore_errors=(),
                       translate_newlines=True)

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
        foo = open(filename, 'w')
        foo.write(data)
        foo.close()
        self._run_git(['add', filename])
        self._run_git(['commit', '-m', msg])

    def _git_get_head(self):
        return self._run_git(['rev-parse', 'HEAD']).strip()

    def setUp(self):
        super(GitClientTests, self).setUp()

        if not self.is_exe_in_path('git'):
            raise SkipTest('git not found in path')

        self.set_user_home(
            os.path.join(self.testdata_dir, 'homedir'))
        self.git_dir = os.path.join(self.testdata_dir, 'git-repo')

        self.clone_dir = self.chdir_tmp()
        self._run_git(['clone', self.git_dir, self.clone_dir])
        self.client = GitClient(options=self.options)

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
        """Testing GitClient scan_for_server, .reviewboardrc case"""
        rc = open(os.path.join(self.clone_dir, '.reviewboardrc'), 'w')
        rc.write('REVIEWBOARD_URL = "%s"' % self.TESTSERVER)
        rc.close()
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
        """Testing GitClient simple diff with file exclusion."""
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
        os.chdir('subdir')
        self._git_add_file_commit('exclude.txt', FOO2, 'commit 2')

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
        """Testing GitClient diff with file exclusion in the repo root."""
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

    def test_get_raw_commit_message(self):
        """Testing GitClient.get_raw_commit_message"""
        self._git_add_file_commit('foo.txt', FOO2, 'Commit 2')
        self.client.get_repository_info()
        revisions = self.client.parse_revision_spec()

        self.assertEqual(self.client.get_raw_commit_message(revisions),
                         'Commit 2')

    def test_push_upstream_pull_exception(self):
        """Testing GitClient.push_upstream with an invalid remote branch.

        It must raise a PushError exception because the 'git pull' from an
        invalid upstream branch will fail.
        """
        try:
            self.client.push_upstream('non-existent-branch')
        except PushError as e:
            self.assertEqual(six.text_type(e),
                             'Could not pull changes from upstream.')
        else:
            self.fail('Expected PushError')

    def test_push_upstream_no_push_exception(self):
        """Testing GitClient.push_upstream with 'git push' disabled.

        We set the push url to be an invalid one, which should normally cause
        the 'git push' to fail. However, push_upstream() must not fail (must
        not raise a PushError) because it gets its origin_url from the Git
        config, which still contains a valid fetch url.
        """
        self._run_git(['remote', 'set-url', '--push', 'origin', 'bad-url'])

        # This line should not raise an exception.
        self.client.push_upstream('master')

    def test_merge_invalid_destination(self):
        """Testing GitClient.merge with an invalid destination branch.

        It must raise a MergeError exception because 'git checkout' to the
        invalid destination branch will fail.
        """
        try:
            self.client.merge('master', 'non-existent-branch',
                              'commit message', self.AUTHOR)
        except MergeError as e:
            self.assertTrue(six.text_type(e).startswith(
                "Could not checkout to branch 'non-existent-branch'"))
        else:
            self.fail('Expected MergeError')

    def test_merge_invalid_target(self):
        """Testing GitClient.merge with an invalid target branch.

        It must raise a MergeError exception because 'git merge' from an
        invalid target branch will fail.
        """
        try:
            self.client.merge('non-existent-branch', 'master',
                              'commit message', self.AUTHOR)
        except MergeError as e:
            self.assertTrue(six.text_type(e).startswith(
                "Could not merge branch 'non-existent-branch'"))
        else:
            self.fail('Expected MergeError')

    def test_merge_with_squash(self):
        """Testing GitClient.merge with squash set to True.

        We use a KGB function spy to check if execute is called with the
        right arguments i.e. with the '--squash' flag (and not with the
        '--no-ff' flag.
        """
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
        """Testing GitClient.merge with squash set to False.

        We use a KGB function spy to check if execute is called with the
        right arguments i.e. with the '--no-ff' flag (and not with the
        '--squash' flag).
        """
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
        """Testing GitClient.create_commit with run_editor set to True.

        We use a KGB function spy to check if edit_text is called, and then
        we intercept the call returning a custom commit message. We then
        ensure that execute is called with that custom commit message.
        """
        self.spy_on(edit_text, call_fake=self.return_new_message)
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
        """Testing GitClient.create_commit with run_editor set to False.

        We use a KGB function spy to check if edit_text is not called. We set
        it up so that if edit_text was called, we intercept the call returning
        a custom commit message. However, since we are expecting edit_text to
        not be called, we ensure that execute is called with the old commit
        message (and not the custom new one).
        """
        self.spy_on(edit_text, call_fake=self.return_new_message)
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
        """Testing GitClient.create_commit with all_files set to True.

        We use a KGB function spy to check if execute is called with the
        right arguments i.e. with 'git add --all :/' (and not with 'git add
        <filenames>').
        """
        self.spy_on(execute)

        foo = open('foo.txt', 'w')
        foo.write('change')
        foo.close()

        self.client.create_commit('message', self.AUTHOR, False, [], True)

        self.assertEqual(execute.spy.calls[0].args[0],
                         ['git', 'add', '--all', ':/'])

    def test_create_commit_without_all_files(self):
        """Testing GitClient.create_commit with all_files set to False.

        We use a KGB function spy to check if execute is called with the
        right arguments i.e. with 'git add <filenames>' (and not with 'git add
        --all :/').
        """
        self.spy_on(execute)

        foo = open('foo.txt', 'w')
        foo.write('change')
        foo.close()

        self.client.create_commit('message', self.AUTHOR, False, ['foo.txt'],
                                  False)

        self.assertEqual(execute.spy.calls[0].args[0],
                         ['git', 'add', 'foo.txt'])

    def test_delete_branch_with_merged_only(self):
        """Testing GitClient.delete_branch with merged_only set to True.

        We use a KGB function spy to check if execute is called with the
        right arguments i.e. with the -d flag (and not the -D flag).
        """
        self.spy_on(execute)

        self._run_git(['branch', 'new-branch'])

        self.client.delete_branch('new-branch', True)

        self.assertTrue(execute.spy.called)
        self.assertEqual(execute.spy.last_call.args[0],
                         ['git', 'branch', '-d', 'new-branch'])

    def test_delete_branch_without_merged_only(self):
        """Testing GitClient.delete_branch with merged_only set to False.

        We use a KGB function spy to check if execute is called with the
        right arguments i.e. with the -D flag (and not the -d flag).
        """
        self.spy_on(execute)

        self._run_git(['branch', 'new-branch'])

        self.client.delete_branch('new-branch', False)

        self.assertTrue(execute.spy.called)
        self.assertEqual(execute.spy.last_call.args[0],
                         ['git', 'branch', '-D', 'new-branch'])

    def return_new_message(self, message):
        return 'new_message'
