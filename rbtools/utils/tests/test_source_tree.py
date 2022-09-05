"""Unit tests for rbtools.utils.source_tree."""

from __future__ import annotations

import os

import kgb

from rbtools.clients import RepositoryInfo
from rbtools.clients.errors import SCMClientDependencyError
from rbtools.clients.git import GitClient
from rbtools.clients.mercurial import MercurialClient
from rbtools.clients.svn import SVNClient
from rbtools.testing import TestCase
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_tempdir
from rbtools.utils.process import execute
from rbtools.utils.source_tree import scan_scmclients_for_path


class ScanSCMClientsForPathTests(kgb.SpyAgency, TestCase):
    """Unit tests for scan_scmclients_for_path."""

    def test_with_single_match(self):
        """Testing scan_scmclients_for_path with single match"""
        tempdir = make_tempdir()
        git_dir = os.path.realpath(os.path.join(tempdir, 'my-repo.git'))

        execute(['git', 'init', git_dir])

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            })

        self.assertTrue(scan_result.found)
        self.assertEqual(scan_result.local_path, git_dir)
        self.assertIsInstance(scan_result.scmclient, GitClient)
        self.assertEqual(scan_result.scmclient_errors, {})

        # Check the repository information.
        repository_info = scan_result.repository_info
        assert repository_info is not None

        self.assertEqual(repository_info.path,
                         os.path.join(git_dir, '.git'))
        self.assertEqual(repository_info.base_path, '')
        self.assertEqual(repository_info.local_path, git_dir)

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 1)

        candidate = scan_result.candidates[0]
        self.assertEqual(candidate.local_path, git_dir)
        self.assertIsInstance(candidate.scmclient, GitClient)

    def test_with_no_match(self):
        """Testing scan_scmclients_for_path with single match"""
        tempdir = make_tempdir()

        scan_result = scan_scmclients_for_path(
            path=tempdir,
            scmclient_kwargs={
                'options': {},
            })

        self.assertFalse(scan_result.found)
        self.assertIsNone(scan_result.local_path)
        self.assertIsNone(scan_result.scmclient)
        self.assertIsNone(scan_result.repository_info)
        self.assertEqual(scan_result.scmclient_errors, {})
        self.assertEqual(len(scan_result.candidates), 0)

    def test_with_nested_repos(self):
        """Testing scan_scmclients_for_path with nested repositories and
        multiple matches
        """
        tempdir = make_tempdir()
        hg_dir = os.path.realpath(os.path.join(tempdir, 'hg-repo'))
        git_dir = os.path.join(hg_dir, 'git-repo')

        execute(['hg', 'init', hg_dir])
        execute(['git', 'init', git_dir])

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            })

        self.assertTrue(scan_result.found)
        self.assertEqual(scan_result.local_path, git_dir)
        self.assertIsInstance(scan_result.scmclient, GitClient)
        self.assertEqual(scan_result.scmclient_errors, {})

        # Check the repository information.
        repository_info = scan_result.repository_info
        assert repository_info is not None

        self.assertEqual(repository_info.path,
                         os.path.join(git_dir, '.git'))
        self.assertEqual(repository_info.base_path, '')
        self.assertEqual(repository_info.local_path, git_dir)

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 2)

        candidate = scan_result.candidates[0]
        self.assertEqual(candidate.local_path, git_dir)
        self.assertIsInstance(candidate.scmclient, GitClient)

        candidate = scan_result.candidates[1]
        self.assertEqual(candidate.local_path, hg_dir)
        self.assertIsInstance(candidate.scmclient, MercurialClient)

    def test_with_nested_repos_and_scmclient_ids_match(self):
        """Testing scan_scmclients_for_path with nested repositories and
        scmclient_ids= with match
        """
        tempdir = make_tempdir()
        hg_dir = os.path.realpath(os.path.join(tempdir, 'hg-repo'))
        git_dir = os.path.join(hg_dir, 'git-repo')

        execute(['hg', 'init', hg_dir])
        execute(['git', 'init', git_dir])

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            },
            scmclient_ids=[MercurialClient.scmclient_id])

        self.assertTrue(scan_result.found)
        self.assertEqual(scan_result.local_path, hg_dir)
        self.assertIsInstance(scan_result.scmclient, MercurialClient)
        self.assertEqual(scan_result.scmclient_errors, {})

        # Check the repository information.
        repository_info = scan_result.repository_info
        assert repository_info is not None

        self.assertEqual(repository_info.path, hg_dir)
        self.assertEqual(repository_info.base_path, '/')
        self.assertEqual(repository_info.local_path, hg_dir)

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 1)

        candidate = scan_result.candidates[0]
        self.assertEqual(candidate.local_path, hg_dir)
        self.assertIsInstance(candidate.scmclient, MercurialClient)

    def test_with_nested_repos_and_scmclient_ids_no_match(self):
        """Testing scan_scmclients_for_path with nested repositories and
        scmclient_ids= with no match
        """
        tempdir = make_tempdir()
        hg_dir = os.path.realpath(os.path.join(tempdir, 'hg-repo'))
        git_dir = os.path.join(hg_dir, 'git-repo')

        execute(['hg', 'init', hg_dir])
        execute(['git', 'init', git_dir])

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            },
            scmclient_ids=[SVNClient.scmclient_id])

        self.assertFalse(scan_result.found)
        self.assertIsNone(scan_result.local_path)
        self.assertIsNone(scan_result.scmclient)
        self.assertIsNone(scan_result.repository_info)
        self.assertEqual(scan_result.scmclient_errors, {})
        self.assertEqual(len(scan_result.candidates), 0)

    def test_with_check_remote_true_and_match(self):
        """Testing scan_scmclients_for_path with check_remote=True and
        remote-only match
        """
        tempdir = make_tempdir()
        git_dir = os.path.realpath(os.path.join(tempdir, 'git-repo'))

        execute(['git', 'init', git_dir])

        self.spy_on(MercurialClient.is_remote_only,
                    owner=MercurialClient,
                    op=kgb.SpyOpReturn(True))
        self.spy_on(MercurialClient.get_repository_info,
                    owner=MercurialClient,
                    op=kgb.SpyOpReturn(RepositoryInfo(
                        path='xxx')))

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            })

        self.assertTrue(scan_result.found)
        self.assertIsNone(scan_result.local_path)
        self.assertIsInstance(scan_result.scmclient, MercurialClient)
        self.assertEqual(scan_result.scmclient_errors, {})

        # Check the repository information.
        repository_info = scan_result.repository_info
        assert repository_info is not None

        self.assertEqual(repository_info.path, 'xxx')

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 1)

        candidate = scan_result.candidates[0]
        self.assertIsNone(candidate.local_path)
        self.assertIsInstance(candidate.scmclient, MercurialClient)

    def test_with_check_remote_false(self):
        """Testing scan_scmclients_for_path with check_remote=False"""
        tempdir = make_tempdir()
        git_dir = os.path.realpath(os.path.join(tempdir, 'git-repo'))

        execute(['git', 'init', git_dir])

        self.spy_on(MercurialClient.is_remote_only,
                    owner=MercurialClient,
                    op=kgb.SpyOpReturn(True))
        self.spy_on(MercurialClient.get_repository_info,
                    owner=MercurialClient,
                    op=kgb.SpyOpReturn(RepositoryInfo(
                        path='xxx')))

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            },
            check_remote=False)

        self.assertTrue(scan_result.found)
        self.assertEqual(scan_result.local_path, git_dir)
        self.assertIsInstance(scan_result.scmclient, GitClient)
        self.assertEqual(scan_result.scmclient_errors, {})

        # Check the repository information.
        repository_info = scan_result.repository_info
        assert repository_info is not None

        self.assertEqual(repository_info.path,
                         os.path.join(git_dir, '.git'))
        self.assertEqual(repository_info.base_path, '')
        self.assertEqual(repository_info.local_path, git_dir)

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 1)

        candidate = scan_result.candidates[0]
        self.assertEqual(candidate.local_path, git_dir)
        self.assertIsInstance(candidate.scmclient, GitClient)

    def test_with_scmclient_errors_from_init(self):
        """Testing scan_scmclients_for_path with scmclient_errors from
        SCMClient initialization
        """
        tempdir = make_tempdir()
        git_dir = os.path.realpath(os.path.join(tempdir, 'git-repo'))

        e = Exception('oh no')

        execute(['git', 'init', git_dir])

        self.spy_on(MercurialClient.__init__,
                    owner=MercurialClient,
                    op=kgb.SpyOpRaise(e))

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            })

        self.assertTrue(scan_result.found)
        self.assertEqual(scan_result.local_path, git_dir)
        self.assertIsInstance(scan_result.scmclient, GitClient)

        # Check the repository information.
        repository_info = scan_result.repository_info
        assert repository_info is not None

        self.assertEqual(repository_info.path,
                         os.path.join(git_dir, '.git'))
        self.assertEqual(repository_info.base_path, '')
        self.assertEqual(repository_info.local_path, git_dir)

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 1)

        candidate = scan_result.candidates[0]
        self.assertEqual(candidate.local_path, git_dir)
        self.assertIsInstance(candidate.scmclient, GitClient)

        # Check the errors.
        self.assertEqual(scan_result.scmclient_errors, {
            'mercurial': e,
        })

    def test_with_scmclient_errors_from_is_remote_only(self):
        """Testing scan_scmclients_for_path with scmclient_errors from
        SCMClient.is_remote_only()
        """
        tempdir = make_tempdir()
        git_dir = os.path.realpath(os.path.join(tempdir, 'git-repo'))

        e = Exception('oh no')

        execute(['git', 'init', git_dir])

        self.spy_on(MercurialClient.is_remote_only,
                    owner=MercurialClient,
                    op=kgb.SpyOpRaise(e))

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            })

        self.assertTrue(scan_result.found)
        self.assertEqual(scan_result.local_path, git_dir)
        self.assertIsInstance(scan_result.scmclient, GitClient)

        # Check the repository information.
        repository_info = scan_result.repository_info
        assert repository_info is not None

        self.assertEqual(repository_info.path,
                         os.path.join(git_dir, '.git'))
        self.assertEqual(repository_info.base_path, '')
        self.assertEqual(repository_info.local_path, git_dir)

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 1)

        candidate = scan_result.candidates[0]
        self.assertEqual(candidate.local_path, git_dir)
        self.assertIsInstance(candidate.scmclient, GitClient)

        # Check the errors.
        self.assertEqual(scan_result.scmclient_errors, {
            'mercurial': e,
        })

    def test_with_scmclient_errors_from_get_local_path(self):
        """Testing scan_scmclients_for_path with scmclient_errors from
        SCMClient.get_local_path()
        """
        tempdir = make_tempdir()
        git_dir = os.path.realpath(os.path.join(tempdir, 'git-repo'))

        e = Exception('oh no')

        execute(['git', 'init', git_dir])

        self.spy_on(MercurialClient.get_local_path,
                    owner=MercurialClient,
                    op=kgb.SpyOpRaise(e))

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            })

        self.assertTrue(scan_result.found)
        self.assertEqual(scan_result.local_path, git_dir)
        self.assertIsInstance(scan_result.scmclient, GitClient)

        # Check the repository information.
        repository_info = scan_result.repository_info
        assert repository_info is not None

        self.assertEqual(repository_info.path,
                         os.path.join(git_dir, '.git'))
        self.assertEqual(repository_info.base_path, '')
        self.assertEqual(repository_info.local_path, git_dir)

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 1)

        candidate = scan_result.candidates[0]
        self.assertEqual(candidate.local_path, git_dir)
        self.assertIsInstance(candidate.scmclient, GitClient)

        # Check the errors.
        self.assertEqual(scan_result.scmclient_errors, {
            'mercurial': e,
        })

    def test_with_scmclient_errors_from_get_repository_info(self):
        """Testing scan_scmclients_for_path with scmclient_errors from
        SCMClient.get_repository_info()
        """
        tempdir = make_tempdir()
        git_dir = os.path.realpath(os.path.join(tempdir, 'git-repo'))

        e = Exception('oh no')

        execute(['git', 'init', git_dir])

        self.spy_on(GitClient.get_repository_info,
                    owner=GitClient,
                    op=kgb.SpyOpRaise(e))

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_kwargs={
                'options': {},
            })

        self.assertFalse(scan_result.found)
        self.assertIsNone(scan_result.local_path)
        self.assertIsNone(scan_result.scmclient)

        # Check the candidates.
        self.assertEqual(len(scan_result.candidates), 1)

        candidate = scan_result.candidates[0]
        self.assertEqual(candidate.local_path, git_dir)
        self.assertIsInstance(candidate.scmclient, GitClient)

        # Check the errors.
        self.assertEqual(scan_result.scmclient_errors, {
            'git': e,
        })

    def test_with_dependency_errors(self):
        """Testing scan_scmclients_for_path with dependency_errors"""
        tempdir = make_tempdir()
        git_dir = os.path.realpath(os.path.join(tempdir, 'git-repo'))

        execute(['git', 'init', git_dir])

        # Make sure all dep checks fail.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        # And make sure we don't call any of the source tree introspection
        # methods.
        self.spy_on(GitClient.get_local_path)
        self.spy_on(GitClient.get_repository_info)
        self.spy_on(MercurialClient.get_local_path)
        self.spy_on(MercurialClient.get_repository_info)

        scan_result = scan_scmclients_for_path(
            path=git_dir,
            scmclient_ids=[
                'git',
                'mercurial',
            ],
            scmclient_kwargs={
                'options': {},
            })

        self.assertFalse(scan_result.found)
        self.assertIsNone(scan_result.local_path)
        self.assertIsNone(scan_result.scmclient)
        self.assertIsNone(scan_result.repository_info)
        self.assertEqual(scan_result.candidates, [])
        self.assertEqual(scan_result.scmclient_errors, {})

        # Check that we received dependency errors for both.
        #
        # We won't bother with the contents of the errors, as those are
        # covered by the unit tests for each SCMClient.
        dep_errors = scan_result.dependency_errors
        self.assertEqual(set(dep_errors.keys()), {'git', 'mercurial'})
        self.assertIsInstance(dep_errors['git'], SCMClientDependencyError)
        self.assertIsInstance(dep_errors['mercurial'],
                              SCMClientDependencyError)
