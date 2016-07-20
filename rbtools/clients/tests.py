from __future__ import print_function, unicode_literals

import json
import os
import re
import sys
import time
from hashlib import md5
from functools import wraps
from random import randint
from tempfile import mktemp
from textwrap import dedent

import six
from kgb import SpyAgency
from nose import SkipTest
from six.moves import cStringIO as StringIO
from six.moves.urllib.request import urlopen

from rbtools.api.capabilities import Capabilities
from rbtools.api.client import RBClient
from rbtools.api.tests import MockResponse
from rbtools.clients import RepositoryInfo
from rbtools.clients.bazaar import BazaarClient
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    MergeError,
                                    PushError,
                                    TooManyRevisionsError)
from rbtools.clients.git import GitClient
from rbtools.clients.mercurial import MercurialClient
from rbtools.clients.perforce import PerforceClient, P4Wrapper
from rbtools.clients.svn import SVNRepositoryInfo, SVNClient
from rbtools.tests import OptionsStub
from rbtools.utils.checks import is_valid_version
from rbtools.utils.console import edit_text
from rbtools.utils.filesystem import load_config, make_tempfile
from rbtools.utils.process import execute
from rbtools.utils.testbase import RBTestBase


class SCMClientTests(RBTestBase):
    def setUp(self):
        super(SCMClientTests, self).setUp()

        self.options = OptionsStub()

        self.clients_dir = os.path.dirname(__file__)


class GitClientTests(SpyAgency, SCMClientTests):
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

    def _git_add_file_commit(self, file, data, msg):
        """Add a file to a git repository with the content of data and commit with msg."""
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

        self.set_user_home(
            os.path.join(self.clients_dir, 'testdata', 'homedir'))
        self.git_dir = os.path.join(self.clients_dir, 'testdata', 'git-repo')

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
        """Testing GitClient diff with a tracking branch, but no origin remote"""
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
        """Testing GitClient diff with tracking branch that has slash in its name."""
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

        self.assertTrue(execute.spy.called_with(['git', 'merge', 'new-branch',
                                                 '--squash', '--no-commit'],
                                                ignore_errors=True,
                                                return_error_code=True))

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

        self.assertTrue(execute.spy.called_with(['git', 'merge', 'new-branch',
                                                 '--no-ff', '--no-commit'],
                                                ignore_errors=True,
                                                return_error_code=True))

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
        self.assertTrue(execute.spy.last_called_with(
            ['git', 'commit', '-m', 'new_message', '--author="name <email>"']))

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
        self.assertTrue(execute.spy.last_called_with(
            ['git', 'commit', '-m', 'old_message', '--author="name <email>"']))

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

        self.assertTrue(execute.spy.called_with(['git', 'add', '--all',
                                                 ':/']))

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

        self.assertTrue(execute.spy.called_with(['git', 'add', 'foo.txt']))

    def test_delete_branch_with_merged_only(self):
        """Testing GitClient.delete_branch with merged_only set to True.

        We use a KGB function spy to check if execute is called with the
        right arguments i.e. with the -d flag (and not the -D flag).
        """
        self.spy_on(execute)

        self._run_git(['branch', 'new-branch'])

        self.client.delete_branch('new-branch', True)

        self.assertTrue(execute.spy.called)
        self.assertTrue(execute.spy.last_called_with(['git', 'branch', '-d',
                                                      'new-branch']))

    def test_delete_branch_without_merged_only(self):
        """Testing GitClient.delete_branch with merged_only set to False.

        We use a KGB function spy to check if execute is called with the
        right arguments i.e. with the -D flag (and not the -d flag).
        """
        self.spy_on(execute)

        self._run_git(['branch', 'new-branch'])

        self.client.delete_branch('new-branch', False)

        self.assertTrue(execute.spy.called)
        self.assertTrue(execute.spy.last_called_with(['git', 'branch', '-D',
                                                      'new-branch']))

    def return_new_message(self, message):
        return 'new_message'


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
        rc = open(os.path.join(self.clone_dir, '.reviewboardrc'), 'w')
        rc.write('REVIEWBOARD_URL = "%s"' % self.TESTSERVER)
        rc.close()
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
        """Testing MercurialClient diff with file exclusion."""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('exclude.txt', FOO2, 'commit 2')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions, exclude_patterns=['exclude.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '68c2bdccf52a4f0baddd0ac9f2ecb7d2')

    def test_diff_exclude_empty(self):
        """Testing MercurialClient diff with empty file exclusion."""
        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')
        self._hg_add_file_commit('empty.txt', '', 'commit 2')

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
        """Testing MercurialClient parent diffs with a diverged branch and --parent option"""
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
        """Testing MercurialClient guess summary & description 1 commit."""
        self.options.guess_summary = True
        self.options.guess_description = True

        self._hg_add_file_commit('foo.txt', FOO1, 'commit 1')

        revisions = self.client.parse_revision_spec([])
        commit_message = self.client.get_commit_message(revisions)

        self.assertEqual(commit_message['summary'], 'commit 1')

    def test_guess_summary_description_two(self):
        """Testing MercurialClient guess summary & description 2 commits."""
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
        """Testing MercurialClient guess summary & description 3 commits."""
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
        """Testing MercurialClient guess summary & description middle commit commit."""
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
            raise SkipTest(msg).with_traceback(sys.exc_info()[2])

        self._spin_up_client()
        self._stub_in_config_and_options()

    def _has_hgsubversion(self):
        try:
            output = self._run_hg(['svn', '--help'], ignore_errors=True,
                                  extra_ignore_errors=(255))
        except OSError:
            return False

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
        self.options.parent_branch = None

    def testGetRepositoryInfoSimple(self):
        """Testing MercurialClient (+svn) get_repository_info, simple case"""
        ri = self.client.get_repository_info()

        self.assertEqual('svn', self.client._type)
        self.assertEqual('/trunk', ri.base_path)
        self.assertEqual('svn://127.0.0.1:%s/svnrepo' % self._svnserve_port,
                         ri.path)

    def testCalculateRepositoryInfo(self):
        """Testing MercurialClient (+svn) _calculate_hgsubversion_repository_info properly determines repository and base paths."""
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
        """Testing MercurialClient (+svn) diff specifying a revision."""
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


def svn_version_set_hash(svn16_hash, svn17_hash):
    """Pass the appropriate hash to the wrapped function.

    SVN 1.6 and 1.7+ will generate slightly different output for ``svn diff``
    when generating the diff with a working copy. This works around that by
    checking the installed SVN version and passing the appropriate hash.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(self):
            self.client.get_repository_info()

            if self.client.subversion_client_version < (1, 7):
                return f(self, svn16_hash)
            else:
                return f(self, svn17_hash)

        return wrapped
    return decorator


class SVNRepositoryInfoTests(SpyAgency, SCMClientTests):
    """Unit tests for rbtools.clients.svn.SVNRepositoryInfo."""

    payloads = {
        'http://localhost:8080/api/': {
            'mimetype': 'application/vnd.reviewboard.org.root+json',
            'rsp': {
                'uri_templates': {},
                'links': {
                    'self': {
                        'href': 'http://localhost:8080/api/',
                        'method': 'GET',
                    },
                    'repositories': {
                        'href': 'http://localhost:8080/api/repositories/',
                        'method': 'GET',
                    },
                },
                'stat': 'ok',
            },
        },
        'http://localhost:8080/api/repositories/?tool=Subversion': {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [
                    {
                        # This one doesn't have a mirror_path, to emulate
                        # Review Board 1.6.
                        'id': 1,
                        'name': 'SVN Repo 1',
                        'path': 'https://svn1.example.com/',
                        'links': {
                            'info': {
                                'href': ('https://localhost:8080/api/'
                                         'repositories/1/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                    {
                        'id': 2,
                        'name': 'SVN Repo 2',
                        'path': 'https://svn2.example.com/',
                        'mirror_path': 'svn+ssh://svn2.example.com/',
                        'links': {
                            'info': {
                                'href': ('https://localhost:8080/api/'
                                         'repositories/2/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                ],
                'links': {
                    'next': {
                        'href': ('http://localhost:8080/api/repositories/'
                                 '?tool=Subversion&page=2'),
                        'method': 'GET',
                    },
                },
                'total_results': 3,
                'stat': 'ok',
            },
        },
        'http://localhost:8080/api/repositories/?tool=Subversion&page=2': {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [
                    {
                        'id': 3,
                        'name': 'SVN Repo 3',
                        'path': 'https://svn3.example.com/',
                        'mirror_path': 'svn+ssh://svn3.example.com/',
                        'links': {
                            'info': {
                                'href': ('https://localhost:8080/api/'
                                         'repositories/3/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                ],
                'total_results': 3,
                'stat': 'ok',
            },
        },
        'https://localhost:8080/api/repositories/1/info/': {
            'mimetype': 'application/vnd.reviewboard.org.repository-info+json',
            'rsp': {
                'info': {
                    'uuid': 'UUID-1',
                    'url': 'https://svn1.example.com/',
                    'root_url': 'https://svn1.example.com/',
                },
                'stat': 'ok',
            },
        },
        'https://localhost:8080/api/repositories/2/info/': {
            'mimetype': 'application/vnd.reviewboard.org.repository-info+json',
            'rsp': {
                'info': {
                    'uuid': 'UUID-2',
                    'url': 'https://svn2.example.com/',
                    'root_url': 'https://svn2.example.com/',
                },
                'stat': 'ok',
            },
        },
        'https://localhost:8080/api/repositories/3/info/': {
            'mimetype': 'application/vnd.reviewboard.org.repository-info+json',
            'rsp': {
                'info': {
                    'uuid': 'UUID-3',
                    'url': 'https://svn3.example.com/',
                    'root_url': 'https://svn3.example.com/',
                },
                'stat': 'ok',
            },
        },
    }

    def setUp(self):
        super(SVNRepositoryInfoTests, self).setUp()

        self.spy_on(urlopen, call_fake=self._urlopen)

        self.api_client = RBClient('http://localhost:8080/')
        self.root_resource = self.api_client.get_root()

    def test_find_server_repository_info_with_path_match(self):
        """Testing SVNRepositoryInfo.find_server_repository_info with
        path matching
        """
        info = SVNRepositoryInfo('https://svn1.example.com/', '/', '')

        repo_info = info.find_server_repository_info(self.root_resource)
        self.assertEqual(repo_info, info)
        self.assertEqual(repo_info.repository_id, 1)

    def test_find_server_repository_info_with_mirror_path_match(self):
        """Testing SVNRepositoryInfo.find_server_repository_info with
        mirror_path matching
        """
        info = SVNRepositoryInfo('svn+ssh://svn2.example.com/', '/', '')

        repo_info = info.find_server_repository_info(self.root_resource)
        self.assertEqual(repo_info, info)
        self.assertEqual(repo_info.repository_id, 2)

    def test_find_server_repository_info_with_uuid_match(self):
        """Testing SVNRepositoryInfo.find_server_repository_info with
        UUID matching
        """
        info = SVNRepositoryInfo('svn+ssh://blargle/', '/', 'UUID-3')

        repo_info = info.find_server_repository_info(self.root_resource)
        self.assertNotEqual(repo_info, info)
        self.assertEqual(repo_info.repository_id, 3)

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

    def _urlopen(self, request):
        url = request.get_full_url()

        try:
            payload = self.payloads[url]
        except KeyError:
            return MockResponse(404, {}, json.dumps({
                'rsp': {
                    'stat': 'fail',
                    'err': {
                        'code': 100,
                        'msg': 'Object does not exist',
                    },
                },
            }))

        return MockResponse(
            200,
            {
                'Content-Type': payload['mimetype'],
            },
            json.dumps(payload['rsp']))


class SVNClientTests(SCMClientTests):
    def setUp(self):
        super(SVNClientTests, self).setUp()

        if not self.is_exe_in_path('svn'):
            raise SkipTest('svn not found in path')

        self.svn_dir = os.path.join(self.clients_dir, 'testdata', 'svn-repo')
        self.clone_dir = self.chdir_tmp()
        self.svn_repo_url = 'file://' + self.svn_dir
        self._run_svn(['co', self.svn_repo_url, 'svn-repo'])
        os.chdir(os.path.join(self.clone_dir, 'svn-repo'))

        self.client = SVNClient(options=self.options)
        self.options.svn_show_copies_as_adds = None

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

    def _svn_add_dir(self, dirname):
        """Add a directory to the test repo."""
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        self._run_svn(['add', dirname])

    def test_parse_revision_spec_no_args(self):
        """Testing SVNClient.parse_revision_spec with no specified revisions"""
        revisions = self.client.parse_revision_spec()
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 'BASE')
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
        self.assertEqual(revisions['base'], 'BASE')
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

    def test_parse_revision_spec_invalid_spec(self):
        """Testing SVNClient.parse_revision_spec with invalid specifications"""
        self.assertRaises(InvalidRevisionSpecError,
                          self.client.parse_revision_spec,
                          ['aoeu'])
        self.assertRaises(InvalidRevisionSpecError,
                          self.client.parse_revision_spec,
                          ['aoeu', '1234'])
        self.assertRaises(TooManyRevisionsError,
                          self.client.parse_revision_spec,
                          ['1', '2', '3'])

    def test_parse_revision_spec_non_unicode_log(self):
        """Testing SVNClient.parse_revision_spec with a non-utf8 log entry"""
        # Note: the svn log entry for commit r2 contains one non-utf8 character
        revisions = self.client.parse_revision_spec(['2'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1)
        self.assertEqual(revisions['tip'], 2)

    @svn_version_set_hash('6613644d417f7c90f83f3a2d16b1dad5',
                          '7630ea80056a7340d93a556e9af60c63')
    def test_diff_exclude(self, md5sum):
        """Testing SVNClient diff with file exclude patterns"""
        self._svn_add_file('bar.txt', FOO1)
        self._svn_add_file('exclude.txt', FOO2)

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions,
                                  exclude_patterns=['exclude.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self.assertEqual(md5(result['diff']).hexdigest(), md5sum)

    def test_diff_exclude_in_subdir(self):
        """Testing SVNClient diff with exclude patterns in a subdir"""
        self._svn_add_file('foo.txt', FOO1)
        self._svn_add_dir('subdir')
        self._svn_add_file(os.path.join('subdir', 'exclude.txt'), FOO2)

        os.chdir('subdir')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(
            revisions,
            exclude_patterns=['exclude.txt'])

        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self.assertEqual(result['diff'], '')

    def test_diff_exclude_root_pattern_in_subdir(self):
        """Testing SVNClient diff with repo exclude patterns in a subdir"""
        self._svn_add_file('exclude.txt', FOO1)
        self._svn_add_dir('subdir')

        os.chdir('subdir')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(
            revisions,
            exclude_patterns=[os.path.join(os.path.sep, 'exclude.txt'),
                              '.'])

        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self.assertEqual(result['diff'], '')

    @svn_version_set_hash('043befc507b8177a0f010dc2cecc4205',
                          '1b68063237c584d38a9a3ddbdf1f72a2')
    def test_same_diff_multiple_methods(self, md5_sum):
        """Testing SVNClient identical diff generated from root, subdirectory,
        and via target"""

        # Test diff generation for a single file, where 'svn diff' is invoked
        # from three different locations.  This should result in an identical
        # diff for all three cases.  Add a new subdirectory and file
        # (dir1/A.txt) which will be the lone change captured in the diff.
        # Cases:
        #  1) Invoke 'svn diff' from checkout root.
        #  2) Invoke 'svn diff' from dir1/ subdirectory.
        #  3) Create dir2/ subdirectory parallel to dir1/.  Invoke 'svn diff'
        #     from dir2/ where '../dir1/A.txt' is provided as a specific
        #     target.
        #
        # This test is inspired by #3749 which broke cases 2 and 3.

        self._svn_add_dir('dir1')
        self._svn_add_file('dir1/A.txt', FOO3)

        # Case 1: Generate diff from checkout root.
        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

        # Case 2: Generate diff from dir1 subdirectory.
        os.chdir('dir1')
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

        # Case 3: Generate diff from dir2 subdirectory, but explicitly target
        # only ../dir1/A.txt.
        os.chdir('..')
        self._svn_add_dir('dir2')
        os.chdir('dir2')
        result = self.client.diff(revisions, ['../dir1/A.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

    @svn_version_set_hash('902d662a110400f7470294b2d9e72d36',
                          '13803373ded9af750384a4601d5173ce')
    def test_diff_non_unicode_characters(self, md5_sum):
        """Testing SVNClient diff with a non-utf8 file"""
        self._svn_add_file('A.txt', '\xe2'.encode('iso-8859-1'))
        self._run_svn(['propset', 'svn:mime-type', 'text/plain', 'A.txt'])

        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

    @svn_version_set_hash('79cbd5c4974f97d173ee87c50fa9cff2',
                          'bfa99e54b8c23b97b1dee23d2763c4fd')
    def test_diff_non_unicode_filename(self, md5_sum):
        """Testing SVNClient diff with a non-utf8 filename"""
        self.options.svn_show_copies_as_adds = 'y'

        filename = '\xe2'
        self._run_svn(['copy', 'foo.txt', filename])
        self._run_svn(['propset', 'svn:mime-type', 'text/plain', filename])

        # Generate identical diff from checkout root and via changelist.

        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

        self._run_svn(['changelist', 'cl1', filename])
        revisions = self.client.parse_revision_spec(['cl1'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

    def test_diff_non_unicode_filename_repository_url(self):
        """Testing SVNClient diff with a non-utf8 filename via repository_url
        option"""
        self.options.repository_url = self.svn_repo_url

        # Note: commit r4 adds one file with a non-utf8 character in both its
        # filename and content.
        revisions = self.client.parse_revision_spec(['4'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         '60c4d21f4d414da947f4e7273e6d1326')

    def test_show_copies_as_adds_enabled(self):
        """Testing SVNClient with --show-copies-as-adds functionality
        enabled"""
        self.check_show_copies_as_adds('y', 'ac1835240ec86ee14ddccf1f2236c442')

    def test_show_copies_as_adds_disabled(self):
        """Testing SVNClient with --show-copies-as-adds functionality
        disabled"""
        self.check_show_copies_as_adds('n', 'd41d8cd98f00b204e9800998ecf8427e')

    def check_show_copies_as_adds(self, state, md5str):
        """Helper function to evaluate --show-copies-as-adds"""
        self.client.get_repository_info()

        # Ensure valid SVN client version.
        if not is_valid_version(self.client.subversion_client_version,
                                self.client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise SkipTest('Subversion client is too old to test '
                           '--show-copies-as-adds.')

        self.options.svn_show_copies_as_adds = state

        self._svn_add_dir('dir1')
        self._svn_add_dir('dir2')
        self._run_svn(['copy', 'foo.txt', 'dir1'])

        # Generate identical diff via several methods:
        #  1) from checkout root
        #  2) via changelist
        #  3) from checkout root when all relevant files belong to a changelist
        #  4) via explicit include target

        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5str)

        self._run_svn(['changelist', 'cl1', 'dir1/foo.txt'])
        revisions = self.client.parse_revision_spec(['cl1'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5str)

        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5str)

        self._run_svn(['changelist', '--remove', 'dir1/foo.txt'])

        os.chdir('dir2')
        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions, ['../dir1'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5str)

    def test_history_scheduled_with_commit_nominal(self):
        """Testing SVNClient.history_scheduled_with_commit nominal cases"""
        self.client.get_repository_info()

        # Ensure valid SVN client version.
        if not is_valid_version(self.client.subversion_client_version,
                                self.client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise SkipTest('Subversion client is too old to test '
                           'history_scheduled_with_commit().')

        self._svn_add_dir('dir1')
        self._svn_add_dir('dir2')
        self._run_svn(['copy', 'foo.txt', 'dir1'])

        # Squash stderr to prevent error message in test output.
        sys.stderr = StringIO()

        # Ensure SystemExit is raised when attempting to generate diff via
        # several methods:
        #  1) from checkout root
        #  2) via changelist
        #  3) from checkout root when all relevant files belong to a changelist
        #  4) via explicit include target

        revisions = self.client.parse_revision_spec()
        self.assertRaises(SystemExit, self.client.diff, revisions)

        self._run_svn(['changelist', 'cl1', 'dir1/foo.txt'])
        revisions = self.client.parse_revision_spec(['cl1'])
        self.assertRaises(SystemExit, self.client.diff, revisions)

        revisions = self.client.parse_revision_spec()
        self.assertRaises(SystemExit, self.client.diff, revisions)

        self._run_svn(['changelist', '--remove', 'dir1/foo.txt'])

        os.chdir('dir2')
        revisions = self.client.parse_revision_spec()
        self.assertRaises(SystemExit, self.client.diff, revisions, ['../dir1'])

    def test_history_scheduled_with_commit_special_case_non_local_mods(self):
        """Testing SVNClient.history_scheduled_with_commit is bypassed when
        diff is not for local modifications in a working copy"""
        self.client.get_repository_info()

        # Ensure valid SVN client version.
        if not is_valid_version(self.client.subversion_client_version,
                                self.client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise SkipTest('Subversion client is too old to test '
                           'history_scheduled_with_commit().')

        # While within a working copy which contains a scheduled commit with
        # addition-with-history, ensure history_scheduled_with_commit() is not
        # executed when generating a diff between two revisions either
        # 1) locally or 2) via --reposistory-url option.

        self._run_svn(['copy', 'foo.txt', 'foo_copy.txt'])
        revisions = self.client.parse_revision_spec(['1:2'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'ed154720a7459c2649cab4d2fa34fa93')

        self.options.repository_url = self.svn_repo_url
        revisions = self.client.parse_revision_spec(['2'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'ed154720a7459c2649cab4d2fa34fa93')

    def test_history_scheduled_with_commit_special_case_exclude(self):
        """Testing SVNClient.history_scheduled_with_commit with exclude file"""
        self.client.get_repository_info()

        # Ensure valid SVN client version.
        if not is_valid_version(self.client.subversion_client_version,
                                self.client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise SkipTest('Subversion client is too old to test '
                           'history_scheduled_with_commit().')

        # Lone file with history is also excluded.  In this case there should
        # be no SystemExit raised and an (empty) diff should be produced. Test
        # from checkout root and via changelist.

        self._run_svn(['copy', 'foo.txt', 'foo_copy.txt'])
        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions, [], ['foo_copy.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'd41d8cd98f00b204e9800998ecf8427e')

        self._run_svn(['changelist', 'cl1', 'foo_copy.txt'])
        revisions = self.client.parse_revision_spec(['cl1'])
        result = self.client.diff(revisions, [], ['foo_copy.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'd41d8cd98f00b204e9800998ecf8427e')


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

        p4 = TestWrapper(None)
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

        p4 = TestWrapper(None)
        info = p4.info()

        self.assertEqual(len(info), 5)
        self.assertEqual(info['User name'], 'myuser')
        self.assertEqual(info['Client name'], 'myclient')
        self.assertEqual(info['Client host'], 'myclient.example.com')
        self.assertEqual(info['Client root'], '/path/to/client')
        self.assertEqual(info['Server uptime'], '111:43:38')


class PerforceClientTests(SCMClientTests):
    class P4DiffTestWrapper(P4Wrapper):
        def __init__(self, options):
            super(
                PerforceClientTests.P4DiffTestWrapper, self).__init__(options)

            self._timestamp = time.mktime(time.gmtime(0))

        def fstat(self, depot_path, fields=[]):
            assert depot_path in self.fstat_files

            fstat_info = self.fstat_files[depot_path]

            for field in fields:
                assert field in fstat_info

            return fstat_info

        def opened(self, changenum):
            return [info for info in self.repo_files
                    if info['change'] == changenum]

        def print_file(self, depot_path, out_file):
            for info in self.repo_files:
                if depot_path == '%s#%s' % (info['depotFile'], info['rev']):
                    fp = open(out_file, 'w')
                    fp.write(info['text'])
                    fp.close()
                    return
            assert False

        def where(self, depot_path):
            assert depot_path in self.where_files

            return [{
                'path': self.where_files[depot_path],
            }]

        def change(self, changenum):
            return [{
                'Change': str(changenum),
                'Date': '2013/01/02 22:33:44',
                'User': 'joe@example.com',
                'Status': 'pending',
                'Description': 'This is a test.\n',
            }]

        def info(self):
            return {
                'Client root': '/',
            }

        def run_p4(self, *args, **kwargs):
            assert False

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
                    'Client root': os.getcwd(),
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = PerforceClient(TestWrapper)
        info = client.get_repository_info()

        self.assertNotEqual(info, None)
        self.assertEqual(info.path, SERVER_PATH)
        self.assertEqual(client.p4d_version, (2012, 2))

    def test_repository_info_outside_client_root(self):
        """Testing PerforceClient.get_repository_info outside client root"""
        SERVER_PATH = 'perforce.example.com:1666'

        class TestWrapper(P4Wrapper):
            def is_supported(self):
                return True

            def info(self):
                return {
                    'Client root': '/',
                    'Server address': SERVER_PATH,
                    'Server version': 'P4D/FREEBSD60X86_64/2012.2/525804 '
                                      '(2012/09/18)',
                }

        client = PerforceClient(TestWrapper)
        info = client.get_repository_info()

        self.assertEqual(info, None)

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

    def test_diff_with_pending_changelist(self):
        """Testing PerforceClient.diff with a pending changelist"""
        client = self._build_client()
        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': 'This is a mess.\n',
            },
            {
                'depotFile': '//mydepot/test/COPYING',
                'rev': '1',
                'action': 'add',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
            {
                'depotFile': '//mydepot/test/Makefile',
                'rev': '3',
                'action': 'delete',
                'change': '12345',
                'text': 'all: all\n',
            },
        ]

        readme_file = make_tempfile()
        copying_file = make_tempfile()
        makefile_file = make_tempfile()
        client.p4.print_file('//mydepot/test/README#3', readme_file)
        client.p4.print_file('//mydepot/test/COPYING#1', copying_file)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
            '//mydepot/test/COPYING': copying_file,
            '//mydepot/test/Makefile': makefile_file,
        }

        revisions = client.parse_revision_spec(['12345'])
        diff = client.diff(revisions)
        self._compare_diff(diff, '07aa18ff67f9aa615fcda7ecddcb354e')

    def test_diff_for_submitted_changelist(self):
        """Testing PerforceClient.diff with a submitted changelist"""
        class TestWrapper(self.P4DiffTestWrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'submitted',
                    'Description': 'My change description\n',
                }]

            def filelog(self, path):
                return [
                    {
                        'change0': '12345',
                        'action0': 'edit',
                        'rev0': '3',
                        'depotFile': '//mydepot/test/README',
                    }
                ]

        client = PerforceClient(TestWrapper)
        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': 'This is a mess.\n',
            },
        ]

        readme_file = make_tempfile()
        client.p4.print_file('//mydepot/test/README#3', readme_file)

        client.p4.where_files = {
            '//mydepot/test/README': readme_file,
        }
        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'edit',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README',
                'rev': '3',
                'action': 'edit',
                'change': '',
                'text': 'This is a mess.\n',
            },
        ]

        revisions = client.parse_revision_spec(['12345'])
        diff = client.diff(revisions)
        self._compare_diff(diff, '8af5576f5192ca87731673030efb5f39',
                           expect_changenum=False)

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
        self._test_diff_with_moved_files('20e5ab395e170dce1b062a796e6c2c13')

    def _test_diff_with_moved_files(self, expected_diff_hash, caps={}):
        client = self._build_client()
        client.capabilities = Capabilities(caps)
        client.p4.repo_files = [
            {
                'depotFile': '//mydepot/test/README',
                'rev': '2',
                'action': 'move/delete',
                'change': '12345',
                'text': 'This is a test.\n',
            },
            {
                'depotFile': '//mydepot/test/README-new',
                'rev': '1',
                'action': 'move/add',
                'change': '12345',
                'text': 'This is a mess.\n',
            },
            {
                'depotFile': '//mydepot/test/COPYING',
                'rev': '2',
                'action': 'move/delete',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
            {
                'depotFile': '//mydepot/test/COPYING-new',
                'rev': '1',
                'action': 'move/add',
                'change': '12345',
                'text': 'Copyright 2013 Joe User.\n',
            },
        ]

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

        revisions = client.parse_revision_spec(['12345'])
        diff = client.diff(revisions)
        self._compare_diff(diff, expected_diff_hash)

    def _build_client(self):
        self.options.p4_client = 'myclient'
        self.options.p4_port = 'perforce.example.com:1666'
        self.options.p4_passwd = ''
        client = PerforceClient(self.P4DiffTestWrapper, options=self.options)
        client.p4d_version = (2012, 2)
        return client

    def _compare_diff(self, diff_info, expected_diff_hash,
                      expect_changenum=True):
        self.assertTrue(isinstance(diff_info, dict))
        self.assertTrue('diff' in diff_info)
        if expect_changenum:
            self.assertTrue('changenum' in diff_info)

        diff_content = re.sub(br'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                              br'1970-01-01 00:00:00',
                              diff_info['diff'])
        self.assertEqual(md5(diff_content).hexdigest(), expected_diff_hash)

    def test_parse_revision_spec_no_args(self):
        """Testing PerforceClient.parse_revision_spec with no specified revisions"""
        client = self._build_client()

        revisions = client.parse_revision_spec()
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertEqual(
            revisions['base'], PerforceClient.REVISION_CURRENT_SYNC)
        self.assertEqual(
            revisions['tip'],
            PerforceClient.REVISION_PENDING_CLN_PREFIX + 'default')

    def test_parse_revision_spec_pending_cln(self):
        """Testing PerforceClient.parse_revision_spec with a pending changelist"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'pending',
                    'Description': 'My change description\n',
                }]
        client = PerforceClient(TestWrapper)

        revisions = client.parse_revision_spec(['12345'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(
            revisions['base'], PerforceClient.REVISION_CURRENT_SYNC)
        self.assertEqual(
            revisions['tip'],
            PerforceClient.REVISION_PENDING_CLN_PREFIX + '12345')

    def test_parse_revision_spec_submitted_cln(self):
        """Testing PerforceClient.parse_revision_spec with a submitted changelist"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'submitted',
                    'Description': 'My change description\n',
                }]

        client = PerforceClient(TestWrapper)

        revisions = client.parse_revision_spec(['12345'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], '12344')
        self.assertEqual(revisions['tip'], '12345')

    def test_parse_revision_spec_shelved_cln(self):
        """Testing PerforceClient.parse_revision_spec with a shelved changelist"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return [{
                    'Change': '12345',
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Status': 'shelved',
                    'Description': 'My change description\n',
                }]
        client = PerforceClient(TestWrapper)

        revisions = client.parse_revision_spec(['12345'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(
            revisions['base'], PerforceClient.REVISION_CURRENT_SYNC)
        self.assertEqual(
            revisions['tip'],
            PerforceClient.REVISION_PENDING_CLN_PREFIX + '12345')

    def test_parse_revision_spec_two_args(self):
        """Testing PerforceClient.parse_revision_spec with two changelists"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                change = {
                    'Change': str(changelist),
                    'Date': '2013/12/19 11:32:45',
                    'User': 'example',
                    'Description': 'My change description\n',
                }

                if changelist == '99' or changelist == '100':
                    change['Status'] = 'submitted'
                elif changelist == '101':
                    change['Status'] = 'pending'
                elif changelist == '102':
                    change['Status'] = 'shelved'
                else:
                    assert False

                return [change]

        client = PerforceClient(TestWrapper)

        revisions = client.parse_revision_spec(['99', '100'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], '99')
        self.assertEqual(revisions['tip'], '100')

        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['99', '101'])
        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['99', '102'])
        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['101', '100'])
        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['102', '100'])
        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['102', '10284'])

    def test_parse_revision_spec_invalid_spec(self):
        """Testing PerforceClient.parse_revision_spec with invalid specifications"""
        class TestWrapper(P4Wrapper):
            def change(self, changelist):
                return []

        client = PerforceClient(TestWrapper)

        self.assertRaises(InvalidRevisionSpecError,
                          client.parse_revision_spec,
                          ['aoeu'])

        self.assertRaises(TooManyRevisionsError,
                          client.parse_revision_spec,
                          ['1', '2', '3'])

    def test_diff_exclude(self):
        """Testing PerforceClient.normalize_exclude_patterns"""
        repo_root = self.chdir_tmp()
        os.mkdir('subdir')
        cwd = os.getcwd()

        class ExcludeWrapper(P4Wrapper):
            def info(self):
                return {
                    'Client root': repo_root,
                }

        client = PerforceClient(ExcludeWrapper)

        patterns = [
            "//depot/path",
            os.path.join(os.path.sep, "foo"),
            "foo",
        ]

        normalized_patterns = [
            # Depot paths should remain unchanged.
            patterns[0],
            # "Absolute" paths (i.e., ones that begin with a path separator)
            # should be relative to the repository root.
            os.path.join(repo_root, patterns[1][1:]),
            # Relative paths should be relative to the current working
            # directory.
            os.path.join(cwd, patterns[2]),
        ]

        result = client.normalize_exclude_patterns(patterns)

        self.assertEqual(result, normalized_patterns)

class BazaarClientTests(SCMClientTests):
    def setUp(self):
        super(BazaarClientTests, self).setUp()

        if not self.is_exe_in_path("bzr"):
            raise SkipTest("bzr not found in path")

        self.set_user_home(
            os.path.join(self.clients_dir, 'testdata', 'homedir'))

        self.orig_dir = os.getcwd()

        self.original_branch = self.chdir_tmp()
        self._run_bzr(["init", "."])
        self._bzr_add_file_commit("foo.txt", FOO, "initial commit")

        self.child_branch = mktemp()
        self._run_bzr(["branch", self.original_branch, self.child_branch])
        self.client = BazaarClient(options=self.options)
        os.chdir(self.orig_dir)

        self.options.parent_branch = None

    def _run_bzr(self, command, *args, **kwargs):
        return execute(['bzr'] + command, *args, **kwargs)

    def _bzr_add_file_commit(self, file, data, msg):
        """Add a file to a Bazaar repository with the content of data and commit with msg."""
        with open(file, 'w') as foo:
            foo.write(data)
        self._run_bzr(["add", file])
        self._run_bzr(["commit", "-m", msg, '--author', 'Test User'])

    def _compare_diffs(self, filename, full_diff, expected_diff_digest,
                       change_type='modified'):
        """Testing that the full_diff for ``filename`` matches the ``expected_diff``."""
        diff_lines = full_diff.splitlines()

        self.assertEqual(('=== %s file \'%s\''
                          % (change_type, filename)).encode('utf-8'),
                         diff_lines[0])
        self.assertTrue(diff_lines[1].startswith(
            ('--- %s\t' % filename).encode('utf-8')))
        self.assertTrue(diff_lines[2].startswith(
            ('+++ %s\t' % filename).encode('utf-8')))

        diff_body = b'\n'.join(diff_lines[3:])
        self.assertEqual(md5(diff_body).hexdigest(), expected_diff_digest)

    def _count_files_in_diff(self, diff):
        return len([
            line
            for line in diff.split(b'\n')
            if line.startswith(b'===')
        ])

    def test_get_repository_info_original_branch(self):
        """Testing BazaarClient get_repository_info with original branch"""
        os.chdir(self.original_branch)
        ri = self.client.get_repository_info()

        self.assertTrue(isinstance(ri, RepositoryInfo))
        self.assertEqual(os.path.realpath(ri.path),
                         os.path.realpath(self.original_branch))
        self.assertTrue(ri.supports_parent_diffs)

        self.assertEqual(ri.base_path, '/')
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

    def test_too_many_revisions(self):
        """Testing BazaarClient parse_revision_spec with too many revisions"""
        self.assertRaises(TooManyRevisionsError,
                          self.client.parse_revision_spec,
                          [1, 2, 3])

    def test_diff_simple(self):
        """Testing BazaarClient simple diff case"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "delete and modify stuff")

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self._compare_diffs('foo.txt', result['diff'],
                            'a6326b53933f8b255a4b840485d8e210')

    def test_diff_exclude(self):
        """Testing BazaarClient diff with file exclusion."""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        self._bzr_add_file_commit("exclude.txt", FOO2, "commit 2")

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions, exclude_patterns=['exclude.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self._compare_diffs('foo.txt', result['diff'],
                            'a6326b53933f8b255a4b840485d8e210')

        self.assertEqual(self._count_files_in_diff(result['diff']), 1)

    def test_diff_exclude_in_subdir(self):
        """Testing BazaarClient diff with file exclusion in a subdirectory."""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit('foo.txt', FOO1, 'commit 1')

        os.mkdir('subdir')
        os.chdir('subdir')

        self._bzr_add_file_commit('exclude.txt', FOO2, 'commit 2')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions,
                                  exclude_patterns=['exclude.txt', '.'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self._compare_diffs('foo.txt', result['diff'],
                            'a6326b53933f8b255a4b840485d8e210')

        self.assertEqual(self._count_files_in_diff(result['diff']), 1)

    def test_diff_exclude_root_pattern_in_subdir(self):
        """Testing BazaarClient diff with file exclusion in the repo root."""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit('exclude.txt', FOO2, 'commit 1')

        os.mkdir('subdir')
        os.chdir('subdir')

        self._bzr_add_file_commit('foo.txt', FOO1, 'commit 2')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(
            revisions,
            exclude_patterns=[os.path.sep + 'exclude.txt',
                              os.path.sep + 'subdir'])

        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self._compare_diffs(os.path.join('subdir', 'foo.txt'), result['diff'],
                            '4deffcb296180fa166eddff2512bd0e4',
                            change_type='added')

    def test_diff_specific_files(self):
        """Testing BazaarClient diff with specific files"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "delete and modify stuff")
        self._bzr_add_file_commit("bar.txt", "baz", "added bar")

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions, ['foo.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self._compare_diffs('foo.txt', result['diff'],
                            'a6326b53933f8b255a4b840485d8e210')

    def test_diff_simple_multiple(self):
        """Testing BazaarClient simple diff with multiple commits case"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        self._bzr_add_file_commit("foo.txt", FOO3, "commit 3")

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self._compare_diffs('foo.txt', result['diff'],
                            '4109cc082dce22288c2f1baca9b107b6')

    def test_diff_parent(self):
        """Testing BazaarClient diff with changes only in the parent branch"""
        os.chdir(self.child_branch)
        self._bzr_add_file_commit("foo.txt", FOO1, "delete and modify stuff")

        grand_child_branch = mktemp()
        self._run_bzr(["branch", self.child_branch, grand_child_branch])
        os.chdir(grand_child_branch)

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self.assertEqual(result['diff'], None)

    def test_diff_grand_parent(self):
        """Testing BazaarClient diff with changes between a 2nd level descendant"""
        os.chdir(self.child_branch)
        self._bzr_add_file_commit("foo.txt", FOO1, "delete and modify stuff")

        grand_child_branch = mktemp()
        self._run_bzr(["branch", self.child_branch, grand_child_branch])
        os.chdir(grand_child_branch)

        # Requesting the diff between the grand child branch and its grand
        # parent:
        self.options.parent_branch = self.original_branch

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self._compare_diffs("foo.txt", result['diff'],
                            'a6326b53933f8b255a4b840485d8e210')

    def test_guessed_summary_and_description(self):
        """Testing BazaarClient guessing summary and description"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        self._bzr_add_file_commit("foo.txt", FOO3, "commit 3")

        self.options.guess_summary = True
        self.options.guess_description = True
        revisions = self.client.parse_revision_spec([])
        commit_message = self.client.get_commit_message(revisions)

        self.assertEqual("commit 3", commit_message['summary'])

        description = commit_message['description']
        self.assertTrue("commit 1" in description)
        self.assertTrue("commit 2" in description)
        self.assertFalse("commit 3" in description)

    def test_guessed_summary_and_description_in_grand_parent_branch(self):
        """Testing BazaarClient guessing summary and description for grand parent branch."""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        self._bzr_add_file_commit("foo.txt", FOO3, "commit 3")

        self.options.guess_summary = True
        self.options.guess_description = True

        grand_child_branch = mktemp()
        self._run_bzr(["branch", self.child_branch, grand_child_branch])
        os.chdir(grand_child_branch)

        # Requesting the diff between the grand child branch and its grand
        # parent:
        self.options.parent_branch = self.original_branch

        revisions = self.client.parse_revision_spec([])
        commit_message = self.client.get_commit_message(revisions)

        self.assertEqual("commit 3", commit_message['summary'])

        description = commit_message['description']
        self.assertTrue("commit 1" in description)
        self.assertTrue("commit 2" in description)
        self.assertFalse("commit 3" in description)

    def test_guessed_summary_and_description_with_revision_range(self):
        """Testing BazaarClient guessing summary and description with a revision range."""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        self._bzr_add_file_commit("foo.txt", FOO3, "commit 3")

        self.options.guess_summary = True
        self.options.guess_description = True
        revisions = self.client.parse_revision_spec(['2..3'])
        commit_message = self.client.get_commit_message(revisions)
        print(commit_message)

        self.assertEqual("commit 2", commit_message['summary'])
        self.assertEqual("commit 2", commit_message['description'])

    def test_parse_revision_spec_no_args(self):
        """Testing BazaarClient.parse_revision_spec with no specified revisions"""
        os.chdir(self.child_branch)

        base_commit_id = self.client._get_revno()
        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        tip_commit_id = self.client._get_revno()

        revisions = self.client.parse_revision_spec()
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_one_arg(self):
        """Testing BazaarClient.parse_revision_spec with one specified revision"""
        os.chdir(self.child_branch)

        base_commit_id = self.client._get_revno()
        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        tip_commit_id = self.client._get_revno()

        revisions = self.client.parse_revision_spec([tip_commit_id])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_one_arg_parent(self):
        """Testing BazaarClient.parse_revision_spec with one specified revision and a parent diff"""
        os.chdir(self.original_branch)
        parent_base_commit_id = self.client._get_revno()

        grand_child_branch = mktemp()
        self._run_bzr(["branch", self.child_branch, grand_child_branch])
        os.chdir(grand_child_branch)

        base_commit_id = self.client._get_revno()
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        tip_commit_id = self.client._get_revno()

        self.options.parent_branch = self.child_branch

        revisions = self.client.parse_revision_spec([tip_commit_id])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('parent_base' in revisions)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertEqual(revisions['parent_base'], parent_base_commit_id)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_one_arg_split(self):
        """Testing BazaarClient.parse_revision_spec with R1..R2 syntax"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        base_commit_id = self.client._get_revno()
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        tip_commit_id = self.client._get_revno()

        revisions = self.client.parse_revision_spec(
            ['%s..%s' % (base_commit_id, tip_commit_id)])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('parent_base' not in revisions)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)

    def test_parse_revision_spec_two_args(self):
        """Testing BazaarClient.parse_revision_spec with two revisions"""
        os.chdir(self.child_branch)

        self._bzr_add_file_commit("foo.txt", FOO1, "commit 1")
        base_commit_id = self.client._get_revno()
        self._bzr_add_file_commit("foo.txt", FOO2, "commit 2")
        tip_commit_id = self.client._get_revno()

        revisions = self.client.parse_revision_spec(
            [base_commit_id, tip_commit_id])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('parent_base' not in revisions)
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertEqual(revisions['base'], base_commit_id)
        self.assertEqual(revisions['tip'], tip_commit_id)


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
