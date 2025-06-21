"""Unit tests for client scanning."""

from __future__ import annotations

import os

from rbtools.clients import scan_usable_client
from rbtools.clients.git import GitClient
from rbtools.clients.svn import SVNClient
from rbtools.clients.tests import SCMClientTestCase
from rbtools.utils.process import run_process


class ScanningTests(SCMClientTestCase[None]):
    """Unit tests for client scanning."""

    def setUp(self) -> None:
        """Set up the scanning tests."""
        super().setUp()

        # Clear out the SVN info cache.
        from rbtools.clients import SCMCLIENTS

        if SCMCLIENTS and 'svn' in SCMCLIENTS:
            SCMCLIENTS['svn']._svn_info_cache = {}

    def test_scanning_nested_repos_1(self) -> None:
        """Testing scan_for_usable_client with nested repositories (git inside
        svn)
        """
        git_dir = os.path.join(self.testdata_dir, 'git-repo')
        svn_dir = os.path.join(self.testdata_dir, 'svn-repo')

        # Check out SVN first.
        clone_dir = self.chdir_tmp()
        run_process(['svn', 'co', f'file://{svn_dir}', 'svn-repo'])
        svn_clone_dir = os.path.join(clone_dir, 'svn-repo')

        # Now check out git.
        git_clone_dir = os.path.join(svn_clone_dir, 'git-repo')
        os.mkdir(git_clone_dir)
        run_process(['git', 'clone', git_dir, git_clone_dir])

        os.chdir(git_clone_dir)

        repository_info, tool = scan_usable_client({}, self.options)
        assert repository_info is not None

        self.assertEqual(repository_info.local_path,
                         os.path.realpath(git_clone_dir))
        self.assertEqual(type(tool), GitClient)

    def test_scanning_nested_repos_2(self) -> None:
        """Testing scan_for_usable_client with nested repositories (svn inside
        git)
        """
        git_dir = os.path.join(self.testdata_dir, 'git-repo')
        svn_dir = os.path.join(self.testdata_dir, 'svn-repo')

        # Check out git first
        clone_dir = self.chdir_tmp()
        git_clone_dir = os.path.join(clone_dir, 'git-repo')
        os.mkdir(git_clone_dir)
        run_process(['git', 'clone', git_dir, git_clone_dir])

        # Now check out svn.
        svn_clone_dir = os.path.join(git_clone_dir, 'svn-repo')
        os.chdir(git_clone_dir)
        run_process(['svn', 'co', f'file://{svn_dir}', 'svn-repo'])

        os.chdir(svn_clone_dir)

        repository_info, tool = scan_usable_client({}, self.options)
        assert repository_info is not None

        self.assertEqual(repository_info.local_path,
                         os.path.realpath(svn_clone_dir))
        self.assertEqual(type(tool), SVNClient)
