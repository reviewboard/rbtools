"""Unit tests for client scanning."""

from __future__ import unicode_literals

import os

from rbtools.clients import scan_usable_client
from rbtools.clients.git import GitClient
from rbtools.clients.svn import SVNClient
from rbtools.clients.tests import SCMClientTests
from rbtools.utils.process import execute


class ScanningTests(SCMClientTests):
    """Unit tests for client scanning."""

    def test_scanning_nested_repos_1(self):
        """Testing scan_for_usable_client with nested repositories (git inside
        svn)
        """
        git_dir = os.path.join(self.testdata_dir, 'git-repo')
        svn_dir = os.path.join(self.testdata_dir, 'svn-repo')

        # Check out SVN first.
        clone_dir = self.chdir_tmp()
        execute(['svn', 'co', 'file://%s' % svn_dir, 'svn-repo'],
                env=None, ignore_errors=False, extra_ignore_errors=())
        svn_clone_dir = os.path.join(clone_dir, 'svn-repo')

        # Now check out git.
        git_clone_dir = os.path.join(svn_clone_dir, 'git-repo')
        os.mkdir(git_clone_dir)
        execute(['git', 'clone', git_dir, git_clone_dir],
                env=None, ignore_errors=False, extra_ignore_errors=())

        os.chdir(git_clone_dir)

        repository_info, tool = scan_usable_client({}, self.options)

        self.assertEqual(repository_info.local_path,
                         os.path.realpath(git_clone_dir))
        self.assertEqual(type(tool), GitClient)

    def test_scanning_nested_repos_2(self):
        """Testing scan_for_usable_client with nested repositories (svn inside
        git)
        """
        git_dir = os.path.join(self.testdata_dir, 'git-repo')
        svn_dir = os.path.join(self.testdata_dir, 'svn-repo')

        # Check out git first
        clone_dir = self.chdir_tmp()
        git_clone_dir = os.path.join(clone_dir, 'git-repo')
        os.mkdir(git_clone_dir)
        execute(['git', 'clone', git_dir, git_clone_dir],
                env=None, ignore_errors=False, extra_ignore_errors=())

        # Now check out svn.
        svn_clone_dir = os.path.join(git_clone_dir, 'svn-repo')
        os.chdir(git_clone_dir)
        execute(['svn', 'co', 'file://%s' % svn_dir, 'svn-repo'],
                env=None, ignore_errors=False, extra_ignore_errors=())

        os.chdir(svn_clone_dir)

        repository_info, tool = scan_usable_client({}, self.options)

        self.assertEqual(repository_info.local_path,
                         os.path.realpath(svn_clone_dir))
        self.assertEqual(type(tool), SVNClient)
