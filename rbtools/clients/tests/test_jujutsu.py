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
from rbtools.api.resource import FileAttachmentItemResource
from rbtools.diffs.patches import BinaryFilePatch, Patch, PatchAuthor
from rbtools.testing.api.transport import URLMapTransport
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import make_tempdir
from rbtools.utils.process import run_process


class BaseJujutsuClientTests(SCMClientTestCase[JujutsuClient]):
    """Base class for unit tests for JujutsuClient.

    Version Added:
        6.0
    """

    default_scmclient_caps = {
        'scmtools': {
            'git': {
                'empty_files': True,
            },
        },
    }

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
            client.parse_revision_spec([]),
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
            client.parse_revision_spec([]),
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
            client.diff(revisions,
                        exclude_patterns=['exclude.txt']),
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
            client.diff(revisions,
                        exclude_patterns=['exclude.txt']),
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

    def test_diff_with_deleted_files(self) -> None:
        """Testing JujutsuClient.diff with deleted files"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        base_commit_id = client._get_change_id('@-')

        # Delete the file from working copy
        os.unlink('foo.txt')
        commit_id = client._get_change_id('@')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'base_commit_id': base_commit_id,
                'commit_id': commit_id,
                'diff': (
                    b'diff --git a/foo.txt b/foo.txt\n'
                    b'deleted file mode 100644\n'
                    b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
                    b'0000000000000000000000000000000000000000\n\n'
                    b'--- a/foo.txt\n'
                    b'+++ /dev/null\n'
                    b'@@ -1,12 +0,0 @@\n'
                    b'-ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'-Italiam, fato profugus, Laviniaque venit\n'
                    b'-litora, multum ille et terris iactatus et alto\n'
                    b'-vi superum saevae memorem Iunonis ob iram;\n'
                    b'-multa quoque et bello passus, dum conderet urbem,\n'
                    b'-inferretque deos Latio, genus unde Latinum,\n'
                    b'-Albanique patres, atque altae moenia Romae.\n'
                    b'-Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b'-\n'
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
        self.assertIn('The working copy has no changes', status)

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

    def test_binary_file_add(self) -> None:
        """Testing JujutsuPatcher with an added binary file"""
        client = self.build_client()

        test_content = b'Binary file content'
        test_path = 'new_binary_file.bin'

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 123,
                'absolute_url': 'https://example.com/r/1/file/123/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/123/'
        )

        binary_file = self.make_binary_file_patch(
            old_path=None,
            new_path=test_path,
            status='added',
            file_attachment=attachment,
            content=test_content,
        )

        patch_content = (
            b'diff --git a/new_binary_file.bin b/new_binary_file.bin\n'
            b'new file mode 100644\n'
            b'index 0000000..e69de29 100644\n'
            b'Binary files /dev/null and b/new_binary_file.bin differ\n'
        )
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], test_path)

        self.assertTrue(os.path.exists(test_path))

        with open(test_path, 'rb') as f:
            self.assertEqual(f.read(), test_content)

    def test_binary_file_add_in_subdirectory(self) -> None:
        """Testing JujutsuPatcher with an added binary file in a subdirectory
        """
        client = self.build_client()

        test_content = b'Binary file content in subdirectory'
        test_path = 'subdir/new_binary_file.bin'

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 123,
                'absolute_url': 'https://example.com/r/1/file/123/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/123/'
        )

        binary_file = self.make_binary_file_patch(
            old_path=None,
            new_path=test_path,
            status='added',
            file_attachment=attachment,
            content=test_content,
        )

        patch_content = (
            b'diff --git a/subdir/new_binary_file.bin '
            b'b/subdir/new_binary_file.bin\n'
            b'new file mode 100644\n'
            b'index 0000000000000000000000000000000000000000..'
            b'e619c1387f5feb91f0ca83194650bfe4f6c2e347\n'
            b'Binary files /dev/null and b/subdir/new_binary_file.bin differ\n'
        )
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], test_path)

        self.assertTrue(os.path.exists(test_path))

        with open(test_path, 'rb') as f:
            self.assertEqual(f.read(), test_content)

    def test_binary_file_move(self) -> None:
        """Testing JujutsuPatcher with a moved binary file"""
        client = self.build_client()

        old_path = 'old_binary.bin'
        new_path = 'new_binary.bin'
        test_content = b'Moved binary file content'

        # Create the original file
        with open(old_path, 'wb') as f:
            f.write(test_content)

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 123,
                'absolute_url': 'https://example.com/r/1/file/123/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/123/'
        )

        binary_file = self.make_binary_file_patch(
            old_path=old_path,
            new_path=new_path,
            status='moved',
            file_attachment=attachment,
            content=test_content,
        )

        patch_content = (
            b'diff --git a/old_binary.bin b/new_binary.bin\n'
            b'similarity index 100%\n'
            b'rename from old_binary.bin\n'
            b'rename to new_binary.bin\n'
        )
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], new_path)

        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(new_path))

        with open(new_path, 'rb') as f:
            self.assertEqual(f.read(), test_content)

    def test_binary_file_remove(self) -> None:
        """Testing JujutsuPatcher with a removed binary file"""
        client = self.build_client()

        test_path = 'to_remove.bin'

        # Create the file to be removed
        with open(test_path, 'wb') as f:
            f.write(b'File to be removed')

        binary_file = BinaryFilePatch(
            old_path=test_path,
            new_path=None,
            status='deleted',
            file_attachment=None,
        )

        patch_content = (
            b'diff --git a/to_remove.bin b/to_remove.bin\n'
            b'deleted file mode 100644\n'
            b'index e69de29..0000000 100644\n'
            b'Binary files a/to_remove.bin and /dev/null differ\n'
        )
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], test_path)

        self.assertFalse(os.path.exists(test_path))

    def test_binary_file_modified(self) -> None:
        """Testing JujutsuPatcher with a modified binary file"""
        client = self.build_client()

        test_path = 'modified_binary.bin'
        original_content = b'Original binary content'
        new_content = b'Modified binary content'

        # Create the original file
        with open(test_path, 'wb') as f:
            f.write(original_content)

        attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 123,
                'absolute_url': 'https://example.com/r/1/file/123/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/123/'
        )

        binary_file = self.make_binary_file_patch(
            old_path=test_path,
            new_path=test_path,
            status='modified',
            file_attachment=attachment,
            content=new_content,
        )

        patch_content = (
            b'diff --git a/modified_binary.bin b/modified_binary.bin\n'
            b'index e69de29..f572d396 100644\n'
            b'Binary files a/modified_binary.bin and b/modified_binary.bin '
            b'differ\n'
        )
        patch = Patch(content=patch_content, binary_files=[binary_file])
        patcher = client.get_patcher(patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 1)
        self.assertEqual(result.binary_applied[0], test_path)

        self.assertTrue(os.path.exists(test_path))

        with open(test_path, 'rb') as f:
            self.assertEqual(f.read(), new_content)

    def test_patch_with_regular_and_binary_files(self) -> None:
        """Testing JujutsuPatcher.patch with regular and binary files"""
        client = self.build_client()

        test_content1 = b'Binary file content 1'
        test_content2 = b'Binary file content 2'

        attachment1 = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 201,
                'absolute_url': 'https://example.com/r/1/file/201/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/201/'
        )

        attachment2 = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 202,
                'absolute_url': 'https://example.com/r/1/file/202/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/202/'
        )

        binary_file1 = self.make_binary_file_patch(
            old_path=None,
            new_path='new_binary.bin',
            status='added',
            file_attachment=attachment1,
            content=test_content1,
        )

        binary_file2 = self.make_binary_file_patch(
            old_path='bar.txt',
            new_path='bar.txt',
            status='modified',
            file_attachment=attachment2,
            content=test_content2,
        )

        with open('bar.txt', 'wb') as f:
            f.write(b'old binary content')

        patch_content = (
            b'diff --git a/foo.txt b/foo.txt\n'
            b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
            b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
            b'--- a/foo.txt\n'
            b'+++ b/foo.txt\n'
            b'@@ -6,7 +6,8 @@ multa quoque et bello passus, '
            b'dum conderet urbem,\n'
            b' inferretque deos Latio, genus unde Latinum,\n'
            b' Albanique patres, atque altae moenia Romae.\n'
            b' Musa, mihi causas memora, quo numine laeso,\n'
            b'+New line added\n'
            b' quidve dolens, regina deum tot volvere casus\n'
            b' insignem pietate virum, tot adire labores\n'
            b' impulerit. Tantaene animis caelestibus irae?\n'
            b' \n'
            b'diff --git a/new_binary.bin b/new_binary.bin\n'
            b'new file mode 100644\n'
            b'index 0000000..e69de29 100644\n'
            b'Binary files /dev/null and b/new_binary.bin differ\n'
            b'diff --git a/bar.txt b/bar.txt\n'
            b'index 0000000..e69de29 100644\n'
            b'Binary files a/bar.txt and b/bar.txt differ\n'
        )

        patch = Patch(content=patch_content,
                      binary_files=[binary_file1, binary_file2])
        patcher = client.get_patcher(patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 2)

        with open('foo.txt', 'rb') as fp:
            content = fp.read()
            self.assertIn(b'New line added', content)

        self.assertTrue(os.path.exists('new_binary.bin'))
        self.assertTrue(os.path.exists('bar.txt'))

        with open('new_binary.bin', 'rb') as f:
            self.assertEqual(f.read(), test_content1)

        with open('bar.txt', 'rb') as f:
            self.assertEqual(f.read(), test_content2)

    def test_patch_with_multiple_binary_files(self) -> None:
        """Testing JujutsuPatcher.patch with multiple binary files"""
        client = self.build_client()

        test_content1 = b'Binary file content 1'
        test_content2 = b'Binary file content 2'

        attachment1 = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 301,
                'absolute_url': 'https://example.com/r/1/file/301/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/301/'
        )

        attachment2 = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 302,
                'absolute_url': 'https://example.com/r/1/file/302/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/302/'
        )

        binary_file1 = self.make_binary_file_patch(
            old_path=None,
            new_path='new_binary1.bin',
            status='added',
            file_attachment=attachment1,
            content=test_content1,
        )

        binary_file2 = self.make_binary_file_patch(
            old_path=None,
            new_path='new_binary2.bin',
            status='added',
            file_attachment=attachment2,
            content=test_content2,
        )

        patch_content = (
            b'diff --git a/new_binary1.bin b/new_binary1.bin\n'
            b'new file mode 100644\n'
            b'index 0000000..e69de29 100644\n'
            b'Binary files /dev/null and b/new_binary1.bin differ\n'
            b'diff --git a/new_binary2.bin b/new_binary2.bin\n'
            b'new file mode 100644\n'
            b'index 0000000..e69de29 100644\n'
            b'Binary files /dev/null and b/new_binary2.bin differ\n'
        )

        patch = Patch(content=patch_content,
                      binary_files=[binary_file1, binary_file2])
        patcher = client.get_patcher(patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 2)

        self.assertTrue(os.path.exists('new_binary1.bin'))
        self.assertTrue(os.path.exists('new_binary2.bin'))

        with open('new_binary1.bin', 'rb') as f:
            self.assertEqual(f.read(), test_content1)

        with open('new_binary2.bin', 'rb') as f:
            self.assertEqual(f.read(), test_content2)

    def test_patch_with_mixed_file_types(self) -> None:
        """Testing JujutsuPatcher.patch with regular and multiple binary files
        """
        client = self.build_client()

        test_content1 = b'New binary content'
        test_content2 = b'Modified binary content'

        attachment1 = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 401,
                'absolute_url': 'https://example.com/r/1/file/401/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/401/'
        )

        attachment2 = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 402,
                'absolute_url': 'https://example.com/r/1/file/402/download/',
            },
            url='https://reviews.example.com/api/review-requests/1/'
                'file-attachments/402/'
        )

        binary_file1 = self.make_binary_file_patch(
            old_path=None,
            new_path='new_binary.bin',
            status='added',
            file_attachment=attachment1,
            content=test_content1,
        )

        binary_file2 = self.make_binary_file_patch(
            old_path='bar.txt',
            new_path='bar.txt',
            status='modified',
            file_attachment=attachment2,
            content=test_content2,
        )

        with open('bar.txt', 'wb') as f:
            f.write(b'old binary content')

        patch_content = (
            b'diff --git a/foo.txt b/foo.txt\n'
            b'index 634b3e8ff85bada6f928841a9f2c505560840b3a..'
            b'5e98e9540e1b741b5be24fcb33c40c1c8069c1fb 100644\n'
            b'--- a/foo.txt\n'
            b'+++ b/foo.txt\n'
            b'@@ -6,7 +6,8 @@ multa quoque et bello passus, '
            b'dum conderet urbem,\n'
            b' inferretque deos Latio, genus unde Latinum,\n'
            b' Albanique patres, atque altae moenia Romae.\n'
            b' Musa, mihi causas memora, quo numine laeso,\n'
            b'+New line added\n'
            b' quidve dolens, regina deum tot volvere casus\n'
            b' insignem pietate virum, tot adire labores\n'
            b' impulerit. Tantaene animis caelestibus irae?\n'
            b' \n'
            b'diff --git a/new_binary.bin b/new_binary.bin\n'
            b'new file mode 100644\n'
            b'index 0000000..e69de29 100644\n'
            b'Binary files /dev/null and b/new_binary.bin differ\n'
            b'diff --git a/bar.txt b/bar.txt\n'
            b'index 0000000..e69de29 100644\n'
            b'Binary files a/bar.txt and b/bar.txt differ\n'
        )

        patch = Patch(content=patch_content,
                      binary_files=[binary_file1, binary_file2])
        patcher = client.get_patcher(patches=[patch])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertEqual(len(result.binary_applied), 2)

        with open('foo.txt', 'rb') as fp:
            content = fp.read()
            self.assertIn(b'New line added', content)

        self.assertTrue(os.path.exists('new_binary.bin'))
        self.assertTrue(os.path.exists('bar.txt'))

        with open('new_binary.bin', 'rb') as f:
            self.assertEqual(f.read(), test_content1)

        with open('bar.txt', 'rb') as f:
            self.assertEqual(f.read(), test_content2)

    def test_patch_with_empty_files(self) -> None:
        """Testing JujutsuPatcher.patch with empty files"""
        client = self.build_client()

        empty_to_delete = 'empty_delete.txt'

        with open(empty_to_delete, mode='w', encoding='utf-8') as f:
            pass

        self._add_file_to_repo(filename='empty_delete.txt',
                               data=b'',
                               message='Add empty file')

        empty_to_add = 'empty_add.txt'

        patch_content = (
            b'diff --git a/empty_add.txt b/empty_add.txt\n'
            b'new file mode 100644\n'
            b'index 0000000..e69de29\n'
            b'--- /dev/null\n'
            b'+++ b/empty_add.txt\n'
            b'diff --git a/empty_delete.txt b/empty_delete.txt\n'
            b'deleted file mode 100644\n'
            b'index e69de29..0000000\n'
            b'--- a/empty_delete.txt\n'
            b'+++ /dev/null\n'
        )

        patcher = client.get_patcher(patches=[
            Patch(content=patch_content),
        ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        self.assertTrue(os.path.exists(empty_to_add))

        with open(empty_to_add, mode='rb') as f:
            self.assertEqual(f.read(), b'')

        self.assertFalse(os.path.exists(empty_to_delete))

    def test_patch_with_regular_and_empty_files(self) -> None:
        """Testing JujutsuPatcher.patch with regular and empty files"""
        client = self.build_client()

        empty_to_delete = 'empty_delete.txt'

        with open(empty_to_delete, mode='w', encoding='utf-8') as f:
            pass

        self._add_file_to_repo(filename='empty_delete.txt',
                               data=b'',
                               message='Add empty file')

        empty_to_add = 'empty_add.txt'

        patch_content = (
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
            b'diff --git a/empty_add.txt b/empty_add.txt\n'
            b'new file mode 100644\n'
            b'index 0000000..e69de29\n'
            b'--- /dev/null\n'
            b'+++ b/empty_add.txt\n'
            b'diff --git a/empty_delete.txt b/empty_delete.txt\n'
            b'deleted file mode 100644\n'
            b'index e69de29..0000000\n'
            b'--- a/empty_delete.txt\n'
            b'+++ /dev/null\n'
        )

        patcher = client.get_patcher(patches=[
            Patch(content=patch_content),
        ])

        results = list(patcher.patch())
        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertTrue(result.success)
        self.assertIsNotNone(result.patch)

        with open('foo.txt', mode='rb') as fp:
            self.assertEqual(fp.read(), FOO1)

        self.assertTrue(os.path.exists(empty_to_add))

        with open(empty_to_add, mode='rb') as f:
            self.assertEqual(f.read(), b'')

        self.assertFalse(os.path.exists(empty_to_delete))

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
