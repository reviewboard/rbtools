"""Unit tests for JujutsuClient.

Version Added:
    6.0
"""

from __future__ import annotations

import os
from typing import ClassVar, Optional

import kgb

from rbtools.clients.base.repository import RepositoryInfo
from rbtools.clients.errors import (
    AmendError,
    PushError,
    SCMError,
    SCMClientDependencyError,
    TooManyRevisionsError,
)
from rbtools.clients.jujutsu import JujutsuClient
from rbtools.clients.tests import (FOO, FOO1, FOO2, FOO3, FOO4,
                                   SCMClientTestCase)
from rbtools.diffs.patches import Patch, PatchAuthor
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_tempdir
from rbtools.utils.process import run_process


class BaseJujutsuClientTests(SCMClientTestCase[JujutsuClient]):
    """Base class for unit tests for JujutsuClient.

    Version Added:
        6.0
    """

    #: The SCMClient class to instantiate.
    scmclient_cls = JujutsuClient

    #: The git repository to clone.
    git_upstream: ClassVar[str]

    #: The directory of the repository clone to use for tests.
    jj_dir: ClassVar[str]

    @classmethod
    def setup_checkout(
        cls,
        checkout_dir: str,
    ) -> Optional[str]:
        """Populate a Jujutsu checkout.

        This will create a Jujutsu clone of the sample Git repository stored in
        the :file:`testdata` directory.

        Args:
            checkout_dir (str):
                The top-level directory in which the clone will be placed.

        Returns:
            str:
            The main checkout directory, or ``None`` if the dependencies for
            the tool are not installed.
        """
        scmclient = JujutsuClient()

        if not scmclient.has_dependencies():
            return None

        cls.git_upstream = os.path.join(cls.testdata_dir, 'git-repo')
        cls.jj_dir = checkout_dir

        run_process(['jj', 'git', 'clone', cls.git_upstream, checkout_dir])

        return checkout_dir

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

        self.set_user_home(os.path.join(self.testdata_dir, 'homedir'))
        os.environ['JJ_USER'] = 'Test user'
        os.environ['JJ_EMAIL'] = 'test@example.com'

    def _add_file_to_repo(
        self,
        *,
        filename: str,
        data: bytes,
        message: str,
        commit: bool = True,
    ) -> None:
        """Add a file and optionally commit the result.

        Args:
            filename (str):
                The filename to add.

            data (bytes):
                The content of the file.

            message (str):
                The commit message.

            commit (bool, optional):
                Whether to finalize the commit and start a new change.
        """
        with open(filename, 'wb') as f:
            f.write(data)

        run_process(['jj', 'describe', '-m', message])

        if commit:
            run_process(['jj', 'new'])


class JujutsuClientTests(BaseJujutsuClientTests):
    """Unit tests for JujutsuClient.

    Version Added:
        6.0
    """

    def test_check_dependencies_found(self) -> None:
        """Testing JujutsuClient.check_dependencies with all dependencies
        found
        """
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['git', '--help'],),
                'op': kgb.SpyOpReturn(True),
            },
            {
                'args': (['jj', '--help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 2)
        self.assertSpyCalledWith(check_install, ['git', '--help'])
        self.assertSpyCalledWith(check_install, ['jj', '--help'])

    def test_check_dependencies_missing_jj(self) -> None:
        """Testing JujutsuClient.check_dependencies with ``jj`` missing"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['git', '--help'],),
                'op': kgb.SpyOpReturn(True),
            },
            {
                'args': (['jj', '--help'],),
                'op': kgb.SpyOpReturn(False),
            },
        ]))

        client = self.build_client(setup=False)

        message = "Command line tools ('jj') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

    def test_check_dependencies_missing_git(self) -> None:
        """Testing JujutsuClient.check_dependencies with ``git`` missing"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['git', '--help'],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': (['jj', '--help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)

        message = "Command line tools ('git') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

    def test_get_repository_info(self) -> None:
        """Testing JujutsuClient.get_repository_info"""
        client = self.build_client()
        info = client.get_repository_info()
        assert info is not None

        self.assertIsInstance(info, RepositoryInfo)
        self.assertEqual(info.base_path, '')
        self.assertEqual(info.path, self.git_upstream)
        self.assertEqual(info.local_path,
                         os.path.realpath(self.jj_dir))

    def test_parse_revision_spec_no_revisions(self) -> None:
        """Testing JujutsuClient.parse_revision_spec with no specified
        revisions
        """
        client = self.build_client()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')

        base = client._get_change_id('master@origin')
        tip = client._get_change_id('@')

        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': base,
                'commit_id': tip,
                'tip': tip,
            })

    def test_parse_revision_spec_no_revisions_with_parent(self) -> None:
        """Testing JujutsuClient.parse_revision_spec with no specified
        revisions and a parent diff
        """
        client = self.build_client(options={
            'parent_branch': 'parent',
        })
        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Parent commit')

        run_process(['jj', 'bookmark', 'create', 'parent'])

        self._add_file_to_repo(filename='foo2.txt', data=FOO2,
                               message='Child commit')

        parent_base = client._get_change_id('master@origin')
        base = client._get_change_id('parent')
        tip = client._get_change_id('@')

        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': base,
                'commit_id': tip,
                'parent_base': parent_base,
                'tip': tip,
            })

    def test_parse_revision_spec_one_revision(self) -> None:
        """Testing JujutsuClient.parse_revision_spec with one specified
        revision
        """
        client = self.build_client()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')

        tip = client._get_change_id('@')
        base = client._get_change_id('@-')
        parent_base = client._get_change_id('master@origin')

        self._add_file_to_repo(filename='foo2.txt', data=FOO2,
                               message='Commit 2')

        self.assertEqual(
            client.parse_revision_spec([tip]),
            {
                'base': base,
                'commit_id': tip,
                'parent_base': parent_base,
                'tip': tip,
            })

    def test_parse_revision_spec_one_revision_with_parent(self) -> None:
        """Testing JujutsuClient.parse_revision_spec with one specified
        revision and a parent diff
        """
        client = self.build_client(options={
            'parent_branch': 'parent',
        })
        parent_base = client._get_change_id('master@origin')

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Parent commit')
        run_process(['jj', 'bookmark', 'create', 'parent'])

        self._add_file_to_repo(filename='foo2.txt', data=FOO2,
                               message='Child commit 1')

        base = client._get_change_id('@')

        self._add_file_to_repo(filename='foo3.txt', data=FOO3,
                               message='Child commit 2')

        tip = client._get_change_id('@')

        self._add_file_to_repo(filename='foo4.txt', data=FOO4,
                               message='Child commit 3')

        self.assertEqual(
            client.parse_revision_spec([tip]),
            {
                'base': base,
                'commit_id': tip,
                'parent_base': parent_base,
                'tip': tip,
            })

    def test_parse_revision_spec_two_revisions(self) -> None:
        """Testing JujutsuClient.parse_revision_spec with two specified
        revisions
        """
        client = self.build_client(options={
            'parent_branch': 'parent',
        })
        parent_base = client._get_change_id('master@origin')

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Parent commit')
        run_process(['jj', 'bookmark', 'create', 'parent'])

        self._add_file_to_repo(filename='foo2.txt', data=FOO2,
                               message='Child commit 1')

        base = client._get_change_id('@')

        self._add_file_to_repo(filename='foo3.txt', data=FOO3,
                               message='Child commit 2')
        self._add_file_to_repo(filename='foo4.txt', data=FOO4,
                               message='Child commit 3')

        tip = client._get_change_id('@')

        self._add_file_to_repo(filename='foo.txt', data=FOO4,
                               message='Child commit 4')

        self.assertEqual(
            client.parse_revision_spec([base, tip]),
            {
                'base': base,
                'commit_id': tip,
                'parent_base': parent_base,
                'tip': tip,
            })

    def test_parse_revision_spec_too_many_revisions(self) -> None:
        """Testing JujutsuClient.parse_revision_spec with too many revisions
        """
        client = self.build_client()

        with self.assertRaises(TooManyRevisionsError):
            client.parse_revision_spec(['1', '2', '3'])

    def test_diff_with_working_copy(self) -> None:
        """Testing JujutsuClient.diff with the working copy change"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        base_commit_id = client._get_change_id('@-')

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1', commit=False)
        commit_id = client._get_change_id('@')

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
                    b'@@ -6,7 +6,4 @@\n'
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

    def test_diff_with_multiple_commits(self) -> None:
        """Testing JujutsuClient.diff with multiple commits"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        base_commit_id = client._get_change_id('@-')

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='foo.txt', data=FOO2,
                               message='Commit 2')
        self._add_file_to_repo(filename='foo.txt', data=FOO3,
                               message='Commit 3', commit=False)

        commit_id = client._get_change_id('@')

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

    def test_diff_with_exclude_patterns(self) -> None:
        """Testing JujutsuClient.diff with file exclusion"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()
        base_commit_id = client._get_change_id('@-')

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='exclude.txt', data=FOO2,
                               message='Commit 2', commit=False)
        commit_id = client._get_change_id('@')

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
                    b'@@ -6,7 +6,4 @@\n'
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

    def test_diff_exclude_in_subdir(self) -> None:
        """Testing JujutsuClient.diff with file exclusion in a subdir"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()
        base_commit_id = client._get_change_id('@-')

        os.mkdir('subdir')
        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='subdir/exclude.txt', data=FOO2,
                               message='Commit 2', commit=False)

        os.chdir('subdir')

        commit_id = client._get_change_id('@')
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
                    b'@@ -6,7 +6,4 @@\n'
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

    def test_diff_with_exclude_patterns_root_pattern_in_subdir(self) -> None:
        """Testing JujutsuClient.diff with file exclusion in the repo root"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()
        base_commit_id = client._get_change_id('@-')

        os.mkdir('subdir')
        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='exclude.txt', data=FOO2,
                               message='Commit 2', commit=False)
        os.chdir('subdir')

        commit_id = client._get_change_id('@')
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
                    b'@@ -6,7 +6,4 @@\n'
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

    def test_get_raw_commit_message(self) -> None:
        """Testing JujutsuClient.get_raw_commit_message"""
        client = self.build_client()

        self._add_file_to_repo(filename='foo.txt', data=FOO2,
                               message='Working copy commit', commit=False)
        client.get_repository_info()
        revisions = client.parse_revision_spec([])

        self.assertEqual(client.get_raw_commit_message(revisions),
                         'Working copy commit')

    def test_get_raw_commit_message_with_revision_range(self) -> None:
        """Testing JujutsuClient.get_raw_commit_message with a revision
        range
        """
        client = self.build_client()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='foo.txt', data=FOO2,
                               message='Commit 2')
        self._add_file_to_repo(filename='foo.txt', data=FOO3,
                               message='Working copy commit', commit=False)
        client.get_repository_info()
        revisions = client.parse_revision_spec(['trunk()', '@-'])

        self.assertEqual(client.get_raw_commit_message(revisions),
                         'Commit 1\nCommit 2')

    def test_get_commit_history(self) -> None:
        """Testing JujutsuClient.get_commit_history"""
        client = self.build_client()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='foo.txt', data=FOO2,
                               message='Commit 2')
        self._add_file_to_repo(filename='foo.txt', data=FOO3,
                               message='Working copy commit', commit=False)
        client.get_repository_info()
        revisions = client.parse_revision_spec(['trunk()', '@'])

        commits = client.get_commit_history(revisions)
        assert commits is not None

        self.assertEqual(len(commits), 3)
        self.assertEqual(commits[0]['commit_message'], 'Commit 1')
        self.assertEqual(commits[1]['commit_message'], 'Commit 2')
        self.assertEqual(commits[2]['commit_message'], 'Working copy commit')
        self.assertEqual(commits[0]['commit_id'], commits[1]['parent_id'])
        self.assertEqual(commits[1]['commit_id'], commits[2]['parent_id'])

    def test_get_file_content(self) -> None:
        """Testing JujutsuClient.get_file_content"""
        client = self.build_client()
        client.get_repository_info()

        # This is just a blob which exists in the existing testdata git repo.
        self.assertEqual(
            client.get_file_content(
                filename='foo.txt',
                revision='634b3e8ff85bada6f928841a9f2c505560840b3a'),
            FOO)

    def test_get_file_content_invalid_revision(self) -> None:
        """Testing JujutsuClient.get_file_content with an invalid revision"""
        client = self.build_client()
        client.get_repository_info()

        with self.assertRaises(SCMError):
            client.get_file_content(
                filename='foo.txt',
                revision='634b3e8ff85bada6f928841a9000000000000000')

    def test_get_file_size(self) -> None:
        """Testing JujutsuClient.get_file_size"""
        client = self.build_client()
        client.get_repository_info()

        # This is just a blob which exists in the existing testdata git repo.
        self.assertEqual(
            client.get_file_size(
                filename='foo.txt',
                revision='634b3e8ff85bada6f928841a9f2c505560840b3a'),
            len(FOO))

    def test_get_file_size_invalid_revision(self) -> None:
        """Testing JujutsuClient.get_file_size with an invalid revision"""
        client = self.build_client()
        client.get_repository_info()

        with self.assertRaises(SCMError):
            client.get_file_size(
                filename='foo.txt',
                revision='634b3e8ff85bada6f928841a9000000000000000')

    def test_get_current_bookmark(self) -> None:
        """Testing JujutsuClient.get_current_bookmark"""
        client = self.build_client()
        client.get_repository_info()

        run_process(['jj', 'bookmark', 'create', 'current-bookmark'])

        self.assertEqual(client.get_current_bookmark(), 'current-bookmark')

    def test_amend_commit_description(self) -> None:
        """Testing JujutsuClient.amend_commit_description"""
        client = self.build_client()
        client.get_repository_info()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit', commit=False)

        change = client._get_change_id('@')

        client.amend_commit_description('New commit message')

        description = (
            run_process(['jj', 'log', '-T', 'description', '--no-graph', '-r',
                         change])
            .stdout
            .read()
        )

        self.assertEqual(description, 'New commit message\n')

    def test_amend_commit_description_non_editing_change(self) -> None:
        """Testing JujutsuClient.amend_commit_description with a change which
        is not the current working copy (@)
        """
        client = self.build_client()
        client.get_repository_info()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='foo.txt', data=FOO2,
                               message='Commit 2', commit=False)

        change = client._get_change_id('@-')
        wc = client._get_change_id('@')

        client.amend_commit_description(
            'Commit 1 new commit message',
            revisions={
                'base': f'{change}-',
                'tip': change,
            })

        changed_description = (
            run_process(['jj', 'log', '-T', 'description', '--no-graph', '-r',
                         change])
            .stdout
            .read()
        )

        self.assertEqual(changed_description, 'Commit 1 new commit message\n')

        unchanged_description = (
            run_process(['jj', 'log', '-T', 'description', '--no-graph', '-r',
                         wc])
            .stdout
            .read()
        )

        self.assertEqual(unchanged_description, 'Commit 2\n')

    def test_amend_commit_description_with_immutable_change(self) -> None:
        """Testing JujutsuClient.amend_commit_description with an immutable
        change
        """
        client = self.build_client()
        client.get_repository_info()

        change = client._get_change_id('@-')

        with self.assertRaises(AmendError):
            client.amend_commit_description(
                'New commit message',
                revisions={
                    'base': f'{change}-',
                    'tip': change,
                })

    def test_create_commit(self) -> None:
        """Testing JujutsuClient.create_commit"""
        client = self.build_client()
        client.get_repository_info()

        with open('foo.txt', 'wb') as f:
            f.write(FOO1)

        commit_message = 'summary\n\ndescription\ndescription 2'

        client.create_commit(
            message=commit_message,
            author=PatchAuthor(full_name='Test User',
                               email='test@example.com'),
            run_editor=False)

        status = (
            run_process(['jj', 'status'])
            .stdout
            .read()
        )
        self.assertIn('The working copy is clean', status)

        message = (
            run_process(['jj', 'log', '-r' '@-', '--no-graph', '-T',
                         'description'])
            .stdout
            .read()
            .strip()
        )
        self.assertEqual(message, commit_message)

        author = (
            run_process(['jj', 'log', '-r', '@-', '--no-graph', '-T',
                         'author'])
            .stdout
            .read()
            .strip()
        )
        self.assertEqual(author, 'Test User <test@example.com>')

    def test_merge_one_change(self) -> None:
        """Testing JujutsuClient.merge in merge mode with one change"""
        client = self.build_client()
        client.get_repository_info()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit to merge')

        upstream = client._get_change_id('master@origin')
        change_to_merge = client._get_change_id('@-')

        client.merge(
            target=change_to_merge,
            destination='master',
            message='Merged change',
            author=PatchAuthor(full_name='Joe User', email='joe@example.com'))

        tip = client._get_change_id('@')

        # Check that the tip is a new merge commit that has the destination
        # branch and target change as its parents.
        parents = set(
            run_process(['jj', 'log', '-T', 'parents.map(|c| c.change_id())',
                         '--no-graph', '-r', tip])
            .stdout
            .read()
            .strip()
            .split())

        self.assertEqual(parents, {upstream, change_to_merge})

        # Check that we updated the bookmark to point to the new merge commit.
        bookmark = client._get_change_id('master')
        self.assertEqual(bookmark, tip)

    def test_merge_multiple_changes(self) -> None:
        """Testing JujutsuClient.merge in merge mode with multiple changes"""
        client = self.build_client()
        client.get_repository_info()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='foo.txt', data=FOO2,
                               message='Commit 2')
        self._add_file_to_repo(filename='foo.txt', data=FOO3,
                               message='Commit to merge')

        upstream = client._get_change_id('master@origin')
        change_to_merge = client._get_change_id('@-')

        client.merge(
            target=change_to_merge,
            destination='master',
            message='Merged change',
            author=PatchAuthor(full_name='Joe User', email='joe@example.com'))

        tip = client._get_change_id('@')

        # Check that the tip is a new merge commit that has the destination
        # branch and target change as its parents.
        parents = set(
            run_process(['jj', 'log', '-T', 'parents.map(|c| c.change_id())',
                         '--no-graph', '-r', tip])
            .stdout
            .read()
            .strip()
            .split())

        self.assertEqual(parents, {upstream, change_to_merge})

        # Check that we updated the bookmark to point to the new merge commit.
        bookmark = client._get_change_id('master')
        self.assertEqual(bookmark, tip)

    def test_merge_squash_one_change(self) -> None:
        """Testing JujutsuClient.merge in squash mode with one change"""
        client = self.build_client()
        client.get_repository_info()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit to merge')

        upstream = client._get_change_id('master@origin')
        change_to_merge = client._get_change_id('@-')

        client.merge(
            target=change_to_merge,
            destination='master',
            message='Merged change',
            author=PatchAuthor(full_name='Joe User', email='joe@example.com'),
            squash=True)

        tip = client._get_change_id('@')

        # Check that the tip is a new commit that has only the destination
        # branch as its parent.
        parents = set(
            run_process(['jj', 'log', '-T', 'parents.map(|c| c.change_id())',
                         '--no-graph', '-r', tip])
            .stdout
            .read()
            .strip()
            .split())

        self.assertEqual(parents, {upstream})

        # Check that we updated the bookmark to point to the new merge commit.
        bookmark = client._get_change_id('master')
        self.assertEqual(bookmark, tip)

    def test_merge_squash_multiple_changes(self) -> None:
        """Testing JujutsuClient.merge in squash mode with multiple changes"""
        client = self.build_client()
        client.get_repository_info()

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit 1')
        self._add_file_to_repo(filename='foo.txt', data=FOO2,
                               message='Commit 2')
        self._add_file_to_repo(filename='foo.txt', data=FOO3,
                               message='Commit to merge')

        upstream = client._get_change_id('master@origin')
        change_to_merge = client._get_change_id('@-')

        client.merge(
            target=change_to_merge,
            destination='master',
            message='Merged change',
            author=PatchAuthor(full_name='Joe User', email='joe@example.com'),
            squash=True)

        tip = client._get_change_id('@')

        # Check that the tip is a new commit that has only the destination
        # branch as its parent.
        parents = set(
            run_process(['jj', 'log', '-T', 'parents.map(|c| c.change_id())',
                         '--no-graph', '-r', tip])
            .stdout
            .read()
            .strip()
            .split())

        self.assertEqual(parents, {upstream})

        # Check that we updated the bookmark to point to the new merge commit.
        bookmark = client._get_change_id('master')
        self.assertEqual(bookmark, tip)

    def test_push_upstream(self) -> None:
        """Testing JujutsuClient.push_upstream"""
        client = self.build_client()
        client.get_repository_info()

        # We need to make another copy of the git repo so we don't push into
        # our testdata repo.
        other_remote = make_tempdir()
        run_process(['git', 'clone', '--bare', self.git_upstream,
                     other_remote])
        run_process(['jj', 'git', 'remote', 'set-url', 'origin', other_remote])

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit', commit=False)
        run_process(['jj', 'bookmark', 'move', '--to', '@', 'master'])

        tip = client._get_change_id('@')

        client.push_upstream('master')

        self.assertEqual(client._get_change_id('master@origin'), tip)

    def test_push_upstream_invalid_bookmark(self) -> None:
        """Testing JujutsuClient.push_upstream with an invalid bookmark"""
        client = self.build_client()
        client.get_repository_info()

        # We need to make another copy of the git repo so we don't push into
        # our testdata repo.
        other_remote = make_tempdir()
        run_process(['git', 'clone', '--bare', self.git_upstream,
                     other_remote])
        run_process(['jj', 'git', 'remote', 'set-url', 'origin', other_remote])

        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Commit', commit=False)
        run_process(['jj', 'bookmark', 'move', '--to', '@', 'master'])

        with self.assertRaises(PushError):
            client.push_upstream('master2')

    def test_has_pending_changes(self) -> None:
        """Testing JujutsuClient.has_pending_changes"""
        client = self.build_client()

        self.assertFalse(client.has_pending_changes())

        # In Jujutsu, the "working copy" is a real commit, and we don't mind if
        # it has content because that doesn't block us from doing any
        # operations. Our implementation of patch/merge/etc. are designed to
        # not affect whatever is the current working copy.
        self._add_file_to_repo(filename='foo.txt', data=FOO1,
                               message='Working copy', commit=False)
        self.assertFalse(client.has_pending_changes())


class JujutsuPatcherTests(BaseJujutsuClientTests):
    """Unit tests for JujutsuPatcher.

    Version Added:
        6.0
    """

    def test_patch(self) -> None:
        """Testing JujutsuPatcher.patch"""
        client = self.build_client()

        old_tip = client._get_change_id('@')

        patcher = client.get_patcher(patches=[
            Patch(content=(
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
            )),
        ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO1)

        # The tip should still be the same.
        self.assertEqual(client._get_change_id('@'), old_tip)

    def test_patch_with_commit(self) -> None:
        """Testing JujutsuPatcher.patch with committing"""
        client = self.build_client()

        old_tip = client._get_change_id('@')

        patcher = client.get_patcher(patches=[
            Patch(content=(
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
            )),
        ])
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Test message')

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO1)

        new_parent = client._get_change_id('@-')

        # The new parent should be our original tip.
        self.assertEqual(new_parent, old_tip)

        self.assertEqual(self._get_description(new_parent), 'Test message')

    def test_patch_with_non_empty_wc(self) -> None:
        """Testing JujutsuPatcher.patch with a non-empty working copy commit"""
        client = self.build_client()

        old_tip = client._get_change_id('@')
        old_parent = client._get_change_id('@-')

        self._add_file_to_repo(filename='foo2.txt', data=FOO2,
                               message='WC commit', commit=False)

        patcher = client.get_patcher(patches=[
            Patch(
                content=(
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
                author=PatchAuthor(full_name='Test User',
                                   email='test@example.com'),
                message='Test message',
            ),
        ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO1)

        new_head = client._get_change_id('@')
        new_parent = client._get_change_id('@-')
        new_grandparent = client._get_change_id('@--')

        # The new parent should be our old WC.
        self.assertEqual(new_parent, old_tip)

        # The grandparent of the current WC should be our previous parent.
        self.assertEqual(new_grandparent, old_parent)

        # Because we didn't commit, this should be empty
        self.assertEqual(self._get_description(new_head), '')

    def test_patch_with_non_empty_wc_message_only(self) -> None:
        """Testing JujutsuPatcher.patch with a non-empty working copy commit
        (message only, no diff)
        """
        client = self.build_client()

        old_tip = client._get_change_id('@')
        parent = client._get_change_id('@-')

        run_process(['jj', 'describe', '-m', 'WC message'])

        patcher = client.get_patcher(patches=[
            Patch(
                content=(
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
                author=PatchAuthor(full_name='Test User',
                                   email='test@example.com'),
                message='Test message',
            ),
        ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO1)

        new_head = client._get_change_id('@')
        new_parent = client._get_change_id('@-')
        new_grandparent = client._get_change_id('@--')

        # The new parent should be our old WC.
        self.assertEqual(new_parent, old_tip)

        # The grandparent of the current WC should be our previous parent.
        self.assertEqual(new_grandparent, parent)

        # Because we didn't commit, this should be empty
        self.assertEqual(self._get_description(new_head), '')

    def test_patch_multiple_patches(self) -> None:
        """Testing JujutsuPatcher.patch with multiple patches"""
        client = self.build_client()

        old_tip = client._get_change_id('@')

        patcher = client.get_patcher(patches=[
            Patch(content=(
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
            )),
            Patch(content=(
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
            )),
        ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 2)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        result = results[1]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO2)

        # The tip should still be the same.
        self.assertEqual(client._get_change_id('@'), old_tip)

    def test_patch_with_multiple_patches_and_commit(self) -> None:
        """Testing JujutsuPatcher.patch with multiple patches and committing"""
        client = self.build_client()

        old_parent = client._get_change_id('@-')

        patcher = client.get_patcher(patches=[
            Patch(content=(
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
            )),
            Patch(content=(
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
            )),
        ])
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Test message')

        results = list(patcher.patch())
        self.assertEqual(len(results), 2)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        result = results[1]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        greatgrandparent = client._get_change_id('@---')
        grandparent = client._get_change_id('@--')
        parent = client._get_change_id('@-')

        self.assertEqual(greatgrandparent, old_parent)
        self.assertEqual(self._get_description(grandparent),
                         '[1/2] Test message')
        self.assertEqual(self._get_description(parent),
                         '[2/2] Test message')

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO2)

    def test_patch_with_multiple_patches_and_commit_with_messages(
        self,
    ) -> None:
        """Testing JujutsuPatcher.patch with multiple patches and committing
        with per-patch messages
        """
        client = self.build_client()

        old_parent = client._get_change_id('@-')

        patcher = client.get_patcher(patches=[
            Patch(
                content=(
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
                message='Commit message 1'),
            Patch(
                content=(
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
                message='Commit message 2'),
        ])
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Test message')

        results = list(patcher.patch())
        self.assertEqual(len(results), 2)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        result = results[1]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        greatgrandparent = client._get_change_id('@---')
        grandparent = client._get_change_id('@--')
        parent = client._get_change_id('@-')

        self.assertEqual(greatgrandparent, old_parent)
        self.assertEqual(self._get_description(grandparent),
                         'Commit message 1')
        self.assertEqual(self._get_description(parent),
                         'Commit message 2')

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO2)

    def test_patch_multiple_patches_squash(self) -> None:
        """Testing JujutsuPatcher.patch with multiple patches in squash mode
        """
        client = self.build_client()

        old_tip = client._get_change_id('@')

        patcher = client.get_patcher(
            patches=[
                Patch(content=(
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
                )),
                Patch(content=(
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
                )),
            ],
            squash=True)

        results = list(patcher.patch())
        self.assertEqual(len(results), 2)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        result = results[1]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO2)

        # We should have just applied the patches to the existing empty WC
        # commit.
        self.assertEqual(client._get_change_id('@'), old_tip)

    def test_patch_multiple_patches_squash_and_commit(self) -> None:
        """Testing JujutsuPatcher.patch with multiple patches in squash mode
        and committing
        """
        client = self.build_client()

        old_tip = client._get_change_id('@')

        patcher = client.get_patcher(
            patches=[
                Patch(
                    content=(
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
                    message='commit message'),
                Patch(
                    content=(
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
                    message='commit message 2'),
            ],
            squash=True)
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Test message')

        results = list(patcher.patch())
        self.assertEqual(len(results), 2)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        result = results[1]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(fp.read(), FOO2)

        # Our new parent commit should be our old tip commit.
        parent = client._get_change_id('@-')
        self.assertEqual(parent, old_tip)

        # We should use the default message (computed from the review request)
        # instead of the individual commit messages.
        self.assertEqual(self._get_description(parent), 'Test message')

    def test_patch_with_revert(self) -> None:
        """Testing JujutsuPatcher with revert"""
        client = self.build_client()

        old_tip = client._get_change_id('@')

        patcher = client.get_patcher(
            revert=True,
            patches=[
                Patch(content=(
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,4 +6,7 @@ multa quoque et bello passus, '
                    b'dum conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'+quidve dolens, regina deum tot volvere casus\n'
                    b'+insignem pietate virum, tot adire labores\n'
                    b'+impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                )),
            ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(
                fp.read(),
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'Italiam, fato profugus, Laviniaque venit\n'
                b'litora, multum ille et terris iactatus et alto\n'
                b'vi superum saevae memorem Iunonis ob iram;\n'
                b'multa quoque et bello passus, dum conderet urbem,\n'
                b'inferretque deos Latio, genus unde Latinum,\n'
                b'Albanique patres, atque altae moenia Romae.\n'
                b'Musa, mihi causas memora, quo numine laeso,\n\n')

        # The tip should still be the same.
        self.assertEqual(client._get_change_id('@'), old_tip)

    def test_patch_with_revert_and_commit(self) -> None:
        """Testing JujutsuPatcher with revert and commit"""
        client = self.build_client()

        old_tip = client._get_change_id('@')

        patcher = client.get_patcher(
            revert=True,
            patches=[
                Patch(content=(
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,4 +6,7 @@ multa quoque et bello passus, '
                    b'dum conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'+quidve dolens, regina deum tot volvere casus\n'
                    b'+insignem pietate virum, tot adire labores\n'
                    b'+impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                )),
            ])
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Test message')

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(
                fp.read(),
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'Italiam, fato profugus, Laviniaque venit\n'
                b'litora, multum ille et terris iactatus et alto\n'
                b'vi superum saevae memorem Iunonis ob iram;\n'
                b'multa quoque et bello passus, dum conderet urbem,\n'
                b'inferretque deos Latio, genus unde Latinum,\n'
                b'Albanique patres, atque altae moenia Romae.\n'
                b'Musa, mihi causas memora, quo numine laeso,\n\n')

        # The new parent should still be our old tip.
        parent = client._get_change_id('@-')
        self.assertEqual(parent, old_tip)

        self.assertEqual(self._get_description(parent),
                         '[Revert] Test message')

    def test_patch_with_multiple_patches_revert_and_commit(self) -> None:
        """Testing JujutsuPatcher with multiple patches, revert and commit"""
        client = self.build_client()

        old_parent = client._get_change_id('@-')

        patcher = client.get_patcher(
            revert=True,
            patches=[
                Patch(content=(
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,4 +6,7 @@ multa quoque et bello passus, '
                    b'dum conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'+quidve dolens, regina deum tot volvere casus\n'
                    b'+insignem pietate virum, tot adire labores\n'
                    b'+impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                )),
                Patch(content=(
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 5e98e9540e1b741b5be24fcb33c40c1c8069c1fb..'
                    b'e619c1387f5feb91f0ca83194650bfe4f6c2e347 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -1,6 +1,4 @@\n'
                    b' ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'-ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'-ARMA virumque cano, Troiae qui primus ab oris\n'
                    b' Italiam, fato profugus, Laviniaque venit\n'
                    b' litora, multum ille et terris iactatus et alto\n'
                    b' vi superum saevae memorem Iunonis ob iram;\n'
                )),
            ])
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Test message')

        results = list(patcher.patch())
        self.assertEqual(len(results), 2)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        result = results[1]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(
                fp.read(),
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'Italiam, fato profugus, Laviniaque venit\n'
                b'litora, multum ille et terris iactatus et alto\n'
                b'vi superum saevae memorem Iunonis ob iram;\n'
                b'multa quoque et bello passus, dum conderet urbem,\n'
                b'inferretque deos Latio, genus unde Latinum,\n'
                b'Albanique patres, atque altae moenia Romae.\n'
                b'Musa, mihi causas memora, quo numine laeso,\n'
                b'\n')

        greatgrandparent = client._get_change_id('@---')
        grandparent = client._get_change_id('@--')
        parent = client._get_change_id('@-')

        self.assertEqual(greatgrandparent, old_parent)
        self.assertEqual(self._get_description(grandparent),
                         '[Revert] [2/2] Test message')
        self.assertEqual(self._get_description(parent),
                         '[Revert] [1/2] Test message')

    def test_patch_with_multiple_patches_squash_revert_and_commit(
        self,
    ) -> None:
        """Testing JujutsuPatcher with multiple patches, squash, revert and
        commit
        """
        client = self.build_client()

        old_parent = client._get_change_id('@-')

        patcher = client.get_patcher(
            revert=True,
            squash=True,
            patches=[
                Patch(content=(
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -6,4 +6,7 @@ multa quoque et bello passus, '
                    b'dum conderet urbem,\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'+quidve dolens, regina deum tot volvere casus\n'
                    b'+insignem pietate virum, tot adire labores\n'
                    b'+impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                )),
                Patch(content=(
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'index 5e98e9540e1b741b5be24fcb33c40c1c8069c1fb..'
                    b'e619c1387f5feb91f0ca83194650bfe4f6c2e347 100644\n'
                    b'--- a/foo.txt\n'
                    b'+++ b/foo.txt\n'
                    b'@@ -1,6 +1,4 @@\n'
                    b' ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'-ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'-ARMA virumque cano, Troiae qui primus ab oris\n'
                    b' Italiam, fato profugus, Laviniaque venit\n'
                    b' litora, multum ille et terris iactatus et alto\n'
                    b' vi superum saevae memorem Iunonis ob iram;\n'
                )),
            ])
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Test message')

        results = list(patcher.patch())
        self.assertEqual(len(results), 2)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        result = results[1]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', 'rb') as fp:
            self.assertEqual(
                fp.read(),
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'Italiam, fato profugus, Laviniaque venit\n'
                b'litora, multum ille et terris iactatus et alto\n'
                b'vi superum saevae memorem Iunonis ob iram;\n'
                b'multa quoque et bello passus, dum conderet urbem,\n'
                b'inferretque deos Latio, genus unde Latinum,\n'
                b'Albanique patres, atque altae moenia Romae.\n'
                b'Musa, mihi causas memora, quo numine laeso,\n'
                b'\n')

        grandparent = client._get_change_id('@--')
        parent = client._get_change_id('@-')

        self.assertEqual(grandparent, old_parent)
        self.assertEqual(self._get_description(parent),
                         '[Revert] Test message')

    def _get_description(
        self,
        change: str,
    ) -> str:
        """Get the description for a given change.

        Args:
            change (str):
                The ID of the change (or a revset) to get the description for.

        Returns:
            str:
            The description of the change(s).
        """
        return (
            run_process(['jj', 'log', '-r', change, '--no-graph', '-T',
                         'description'])
            .stdout
            .read()
            .strip()
        )
