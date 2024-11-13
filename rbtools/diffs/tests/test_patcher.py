"""Unit tests for rbtools.diffs.patcher.Patcher.

Version Added:
    5.1
"""

from __future__ import annotations

import os
from pathlib import Path

import kgb

from rbtools.api.resource import ReviewRequestResource
from rbtools.api.tests.base import MockTransport
from rbtools.clients.base.repository import RepositoryInfo
from rbtools.diffs.errors import ApplyPatchError
from rbtools.diffs.patcher import Patcher
from rbtools.diffs.patches import Patch, PatchAuthor, PatchResult
from rbtools.testing import TestCase
from rbtools.utils.filesystem import make_tempdir


class CommitPatcher(Patcher):
    can_commit = True

    ######################
    # Instance variables #
    ######################

    commits: list[PatchResult]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.commits = []

    def create_commit(
        self,
        *,
        patch_result: PatchResult,
        run_commit_editor: bool,
    ) -> None:
        self.commits.append(patch_result)


class EmptyFilesPatcher(Patcher):
    can_patch_empty_files = True

    EMPTY_FILE_DIFF = (
        b'--- test1.txt\n'
        b'+++ test1.txt\n'
    )

    def apply_patch_for_empty_files(
        self,
        patch: Patch,
    ) -> bool:
        return patch.content == self.EMPTY_FILE_DIFF


class PatcherTests(kgb.SpyAgency, TestCase):
    """Unit tests for Patcher.

    Version Added:
        5.1
    """

    def test_get_default_prefix_level(self) -> None:
        """Testing Patcher.get_default_prefix_level"""
        patch = Patch(content=b'patch',
                      base_dir='/src')

        patcher = Patcher(patches=[])

        self.assertIsNone(patcher.get_default_prefix_level(patch=patch))

    def test_get_default_prefix_level_with_base_dir_equal(self) -> None:
        """Testing Patcher.get_default_prefix_level with
        RepositoryInfo.base_dir equal to Patch.base_dir
        """
        patch = Patch(content=b'patch',
                      base_dir='/src')

        patcher = Patcher(
            patches=[],
            repository_info=RepositoryInfo(base_path='/src/'))

        self.assertIsNone(patcher.get_default_prefix_level(patch=patch))

    def test_get_default_prefix_level_with_base_dir_subdir(self) -> None:
        """Testing Patcher.get_default_prefix_level with
        RepositoryInfo.base_dir subdirectory of Patch.base_dir
        """
        patch = Patch(content=b'patch',
                      base_dir='/src/')

        patcher = Patcher(
            patches=[],
            repository_info=RepositoryInfo(base_path='/src/test'))

        self.assertIsNone(patcher.get_default_prefix_level(patch=patch))

    def test_get_default_prefix_level_with_base_dir_parent(self) -> None:
        """Testing Patcher.get_default_prefix_level with
        RepositoryInfo.base_dir parent of Patch.base_dir
        """
        patch = Patch(content=b'patch',
                      base_dir='/src/test')

        patcher = Patcher(
            patches=[],
            repository_info=RepositoryInfo(base_path='/src'))

        self.assertEqual(patcher.get_default_prefix_level(patch=patch), 2)

    def test_prepare_for_commit_with_author_message(self) -> None:
        """Testing Patcher.prepare_for_commit with default_author= and
        default_message=
        """
        patch2_author = PatchAuthor(full_name='Test User 1',
                                    email='test1@example.com')
        patch2_message = 'Commit message for patch 2.'

        patch3_author = PatchAuthor(full_name='Test User 2',
                                    email='test1@example.com')

        patch4_message = 'Commit message for patch 4.'

        default_author = PatchAuthor(full_name='Default Author',
                                     email='default@example.com')
        default_message = 'Default message.'

        patcher = CommitPatcher(patches=[
            Patch(content=b'patch1'),
            Patch(content=b'patch2',
                  author=patch2_author,
                  message=patch2_message),
            Patch(content=b'patch3',
                  author=patch3_author),
            Patch(content=b'patch4',
                  message=patch4_message),
            Patch(content=b'patch5'),
        ])

        patcher.prepare_for_commit(default_author=default_author,
                                   default_message=default_message)

        self.assertTrue(patcher.commit)
        self.assertFalse(patcher.run_commit_editor)

        patch = patcher.patches[0]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[1/5] {default_message}')

        patch = patcher.patches[1]
        self.assertEqual(patch.author, patch2_author)
        self.assertEqual(patch.message, patch2_message)

        patch = patcher.patches[2]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[3/5] {default_message}')

        patch = patcher.patches[3]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[4/5] {default_message}')

        patch = patcher.patches[4]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[5/5] {default_message}')

    def test_prepare_for_commit_with_review_request(self) -> None:
        """Testing Patcher.prepare_for_commit with review_request="""
        review_request = ReviewRequestResource(
            transport=MockTransport(),
            payload={
                'id': 123,
                'summary': 'Default summary.',
                'description': 'Default description.',
                'testing_done': 'Default testing.',
                'bugs_closed': ['123', '456'],
                'submitter': {
                    'email': 'default@example.com',
                    'fullname': 'Default Author',
                },
            },
            url='https://reviews.example.com/api/review-requests/123/')

        patch2_author = PatchAuthor(full_name='Test User 1',
                                    email='test1@example.com')
        patch2_message = 'Commit message for patch 2.'

        patch3_author = PatchAuthor(full_name='Test User 2',
                                    email='test1@example.com')

        patch4_message = 'Commit message for patch 4.'

        default_author = PatchAuthor(full_name='Default Author',
                                     email='default@example.com')
        default_message = (
            'Default summary.\n'
            '\n'
            'Default description.\n'
            '\n'
            'Testing Done:\n'
            'Default testing.\n'
            '\n'
            'Bugs closed: 123, 456\n'
            '\n'
            'Reviewed at https://reviews.example.com/r/123/'
        )

        patcher = CommitPatcher(patches=[
            Patch(content=b'patch1'),
            Patch(content=b'patch2',
                  author=patch2_author,
                  message=patch2_message),
            Patch(content=b'patch3',
                  author=patch3_author),
            Patch(content=b'patch4',
                  message=patch4_message),
            Patch(content=b'patch5'),
        ])

        patcher.prepare_for_commit(review_request=review_request)

        self.assertTrue(patcher.commit)
        self.assertFalse(patcher.run_commit_editor)

        patch = patcher.patches[0]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[1/5] {default_message}')

        patch = patcher.patches[1]
        self.assertEqual(patch.author, patch2_author)
        self.assertEqual(patch.message, patch2_message)

        patch = patcher.patches[2]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[3/5] {default_message}')

        patch = patcher.patches[3]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[4/5] {default_message}')

        patch = patcher.patches[4]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[5/5] {default_message}')

    def test_prepare_for_commit_with_review_request_expanded(self) -> None:
        """Testing Patcher.prepare_for_commit with review_request= and
        submitter expanded
        """
        review_request = ReviewRequestResource(
            transport=MockTransport(),
            payload={
                'id': 123,
                'summary': 'Default summary.',
                'description': 'Default description.',
                'testing_done': 'Default testing.',
                'bugs_closed': ['123', '456'],
                'submitter': {
                    'email': 'default@example.com',
                    'fullname': 'Default Author',
                },
            },
            url='https://reviews.example.com/api/review-requests/123/')

        patch2_author = PatchAuthor(full_name='Test User 1',
                                    email='test1@example.com')
        patch2_message = 'Commit message for patch 2.'

        patch3_author = PatchAuthor(full_name='Test User 2',
                                    email='test1@example.com')

        patch4_message = 'Commit message for patch 4.'

        default_author = PatchAuthor(full_name='Default Author',
                                     email='default@example.com')
        default_message = (
            'Default summary.\n'
            '\n'
            'Default description.\n'
            '\n'
            'Testing Done:\n'
            'Default testing.\n'
            '\n'
            'Bugs closed: 123, 456\n'
            '\n'
            'Reviewed at https://reviews.example.com/r/123/'
        )

        patcher = CommitPatcher(patches=[
            Patch(content=b'patch1'),
            Patch(content=b'patch2',
                  author=patch2_author,
                  message=patch2_message),
            Patch(content=b'patch3',
                  author=patch3_author),
            Patch(content=b'patch4',
                  message=patch4_message),
            Patch(content=b'patch5'),
        ])

        patcher.prepare_for_commit(review_request=review_request)

        self.assertTrue(patcher.commit)
        self.assertFalse(patcher.run_commit_editor)

        patch = patcher.patches[0]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[1/5] {default_message}')

        patch = patcher.patches[1]
        self.assertEqual(patch.author, patch2_author)
        self.assertEqual(patch.message, patch2_message)

        patch = patcher.patches[2]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[3/5] {default_message}')

        patch = patcher.patches[3]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[4/5] {default_message}')

        patch = patcher.patches[4]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[5/5] {default_message}')

    def test_prepare_for_commit_one_patch_needing_defaults(self) -> None:
        """Testing Patcher.prepare_for_commit with one patch needing defaults
        """
        default_author = PatchAuthor(full_name='Default Author',
                                     email='default@example.com')
        default_message = 'Default commit message.'

        patcher = CommitPatcher(patches=[
            Patch(content=b'patch1'),
        ])

        patcher.prepare_for_commit(default_author=default_author,
                                   default_message=default_message)

        self.assertTrue(patcher.commit)
        self.assertFalse(patcher.run_commit_editor)

        patch = patcher.patches[0]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, default_message)

    def test_prepare_for_commit_one_patch_no_defaults_needed(self) -> None:
        """Testing Patcher.prepare_for_commit with one patch and not needing
        defaults
        """
        default_author = PatchAuthor(full_name='Default Author',
                                     email='default@example.com')
        default_message = 'Default commit message.'

        patcher = CommitPatcher(patches=[
            Patch(content=b'patch1',
                  author=PatchAuthor(full_name='Test User 1',
                                     email='test1@example.com'),
                  message='Commit message for patch 1.'),
        ])

        patcher.prepare_for_commit(default_author=default_author,
                                   default_message=default_message)

        self.assertTrue(patcher.commit)
        self.assertFalse(patcher.run_commit_editor)

        patch = patcher.patches[0]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, default_message)

    def test_prepare_for_commit_with_squash(self) -> None:
        """Testing Patcher.prepare_for_commit with squash=True"""
        default_author = PatchAuthor(full_name='Default Author',
                                     email='default@example.com')
        default_message = 'Default message.'

        patcher = CommitPatcher(
            patches=[
                Patch(content=b'patch1'),
                Patch(content=b'patch2',
                      author=PatchAuthor(full_name='Test User 1',
                                         email='test1@example.com'),
                      message='Commit message for patch 2.'),
                Patch(content=b'patch3',
                      author=PatchAuthor(full_name='Test User 2',
                                         email='test1@example.com')),
                Patch(content=b'patch4',
                      message='Commit message for patch 4.'),
                Patch(content=b'patch5'),
            ],
            squash=True)

        patcher.prepare_for_commit(default_author=default_author,
                                   default_message=default_message)

        self.assertTrue(patcher.commit)
        self.assertFalse(patcher.run_commit_editor)

        patch = patcher.patches[0]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[1/5] {default_message}')

        patch = patcher.patches[1]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[2/5] {default_message}')

        patch = patcher.patches[2]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[3/5] {default_message}')

        patch = patcher.patches[3]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[4/5] {default_message}')

        patch = patcher.patches[4]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[5/5] {default_message}')

    def test_prepare_for_commit_with_revert(self) -> None:
        """Testing Patcher.prepare_for_commit with revert=True"""
        default_author = PatchAuthor(full_name='Test User 1',
                                     email='test1@example.com')
        author2 = PatchAuthor(full_name='Test User 2',
                              email='test2@example.com')
        author3 = PatchAuthor(full_name='Test User 3',
                              email='test3@example.com')
        author4 = PatchAuthor(full_name='Test User 4',
                              email='test4@example.com')

        default_message = 'Default message.'

        patcher = CommitPatcher(
            patches=[
                Patch(content=b'patch1',
                      message='Commit message for patch 1.'),
                Patch(content=b'patch2',
                      author=author2,
                      message='Commit message for patch 2.'),
                Patch(content=b'patch3',
                      author=author3),
                Patch(content=b'patch4',
                      message='Commit message for patch 4.'),
                Patch(content=b'patch5',
                      author=author4),
            ],
            revert=True)

        patcher.prepare_for_commit(default_author=default_author,
                                   default_message=default_message)

        self.assertTrue(patcher.commit)
        self.assertFalse(patcher.run_commit_editor)

        patch = patcher.patches[0]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[Revert] [1/5] {default_message}')

        # This is the only commit with no missing metadata (it has both an
        # author and a message), so it gets to retain its information.
        patch = patcher.patches[1]
        self.assertEqual(patch.author, author2)
        self.assertEqual(patch.message,
                         '[Revert] Commit message for patch 2.')

        patch = patcher.patches[2]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[Revert] [3/5] {default_message}')

        patch = patcher.patches[3]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[Revert] [4/5] {default_message}')

        patch = patcher.patches[4]
        self.assertEqual(patch.author, default_author)
        self.assertEqual(patch.message, f'[Revert] [5/5] {default_message}')

    def test_prepare_for_commit_without_defaults(self) -> None:
        """Testing Patcher.prepare_for_commit without default_*= or
        review_request=
        """
        patcher = CommitPatcher(patches=[
            Patch(content=b'patch1'),
        ])

        message = (
            'Patches cannot be prepared to be committed without a '
            'review_request= argument or both default_author= and '
            'default_message=.'
        )

        with self.assertRaisesMessage(ValueError, message):
            patcher.prepare_for_commit()

    def test_prepare_for_commit_without_can_commit(self) -> None:
        """Testing Patcher.prepare_for_commit without can_commit"""
        patcher = Patcher(patches=[
            Patch(content=b'patch1'),
        ])

        message = 'This patcher does not support committing applied patches.'

        with self.assertRaisesMessage(NotImplementedError, message):
            patcher.prepare_for_commit()

    def test_patch_with_one_patch(self) -> None:
        """Testing Patcher.patch with one patch"""
        tmpdir = Path(make_tempdir())
        test_file = tmpdir / 'test.txt'

        with open(test_file, 'w') as fp:
            fp.write('1\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                )),
            ])

        patch_results = list(patcher.patch())

        self.assertEqual(len(patch_results), 1)

        patch_result = patch_results[0]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[0])
        self.assertEqual(patch_result.patch_range, (1, 1))

        with open(test_file, 'r') as fp:
            self.assertEqual(fp.read(), '2\n')

    def test_patch_with_multiple_patches(self) -> None:
        """Testing Patcher.patch with multiple patches"""
        tmpdir = Path(make_tempdir())
        test_file = tmpdir / 'test.txt'

        with open(test_file, 'w') as fp:
            fp.write('1\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                )),
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-2\n'
                    b'+3\n'
                )),
            ])

        patch_results = list(patcher.patch())

        self.assertEqual(len(patch_results), 2)

        patch_result = patch_results[0]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[0])
        self.assertEqual(patch_result.patch_range, (1, 1))

        patch_result = patch_results[1]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[1])
        self.assertEqual(patch_result.patch_range, (2, 2))

        with open(test_file, 'r') as fp:
            self.assertEqual(fp.read(), '3\n')

    def test_patch_with_commit(self) -> None:
        """Testing Patcher.patch with commiting"""
        tmpdir = Path(make_tempdir())
        test_file = tmpdir / 'test.txt'

        with open(test_file, 'w') as fp:
            fp.write('1\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                )),
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-2\n'
                    b'+3\n'
                )),
            ])
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Commit message')

        patch_results = list(patcher.patch())

        self.assertEqual(len(patch_results), 2)
        self.assertEqual(len(patcher.commits), 2)
        self.assertEqual(patcher.commits, patch_results)

        patch_result = patcher.commits[0]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[0])
        self.assertEqual(patch_result.patch_range, (1, 1))

        patch_result = patcher.commits[1]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[1])
        self.assertEqual(patch_result.patch_range, (2, 2))

        with open(test_file, 'r') as fp:
            self.assertEqual(fp.read(), '3\n')

    def test_patch_with_commit_squash(self) -> None:
        """Testing Patcher.patch with commiting and squashing"""
        tmpdir = Path(make_tempdir())
        test_file = tmpdir / 'test.txt'

        with open(test_file, 'w') as fp:
            fp.write('1\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                )),
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-2\n'
                    b'+3\n'
                )),
            ],
            squash=True)
        patcher.prepare_for_commit(
            default_author=PatchAuthor(full_name='Test User',
                                       email='test@example.com'),
            default_message='Commit message')

        patch_results = list(patcher.patch())

        self.assertEqual(len(patch_results), 2)
        self.assertEqual(len(patcher.commits), 1)

        patch_result = patcher.commits[0]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[1])
        self.assertEqual(patch_result.patch_range, (2, 2))

        with open(test_file, 'r') as fp:
            self.assertEqual(fp.read(), '3\n')

    def test_patch_with_revert(self) -> None:
        """Testing Patcher.patch with revert"""
        tmpdir = Path(make_tempdir())
        test_file = tmpdir / 'test.txt'

        with open(test_file, 'w') as fp:
            fp.write('3\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                )),
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-2\n'
                    b'+3\n'
                )),
            ],
            revert=True)

        patch_results = list(patcher.patch())

        self.assertEqual(len(patch_results), 2)

        patch_result = patch_results[0]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[1])
        self.assertEqual(patch_result.patch_range, (1, 1))

        patch_result = patch_results[1]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[0])
        self.assertEqual(patch_result.patch_range, (2, 2))

        with open(test_file, 'r') as fp:
            self.assertEqual(fp.read(), '1\n')

    def test_patch_with_patch_error(self) -> None:
        """Testing Patcher.patch with patch error"""
        tmpdir = Path(make_tempdir())
        test_file = tmpdir / 'test.txt'

        with open(test_file, 'w') as fp:
            fp.write('1\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                )),
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+3\n'
                )),
            ])

        message = (
            'Could not apply patch 2 of 2. The patch may be invalid, or '
            'there may be conflicts that could not be resolved.'
        )

        with self.assertRaisesMessage(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertFalse(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, ['test.txt'])
        self.assertTrue(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (2, 2))
        self.assertIs(patch_result.patch, patcher.patches[1])

        patch_results = patcher.applied_patch_results
        self.assertEqual(len(patch_results), 1)

        patch_result = patch_results[0]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[0])

        with open(test_file, 'r') as fp:
            self.assertEqual(fp.read(), '2\n')

    def test_patch_with_patch_error_conflicts(self) -> None:
        """Testing Patcher.patch with patch error and conflicts"""
        tmpdir = Path(make_tempdir())
        test_file1 = tmpdir / 'test1.txt'
        test_file2 = tmpdir / 'test2.txt'

        with open(test_file1, 'w') as fp:
            fp.write('1\n')

        with open(test_file2, 'w') as fp:
            fp.write('a\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test1.txt\n'
                    b'+++ test1.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-x\n'
                    b'+2\n'
                    b'--- test2.txt\n'
                    b'+++ test2.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-a\n'
                    b'+b\n'
                )),
                Patch(content=(
                    b'--- test1.txt\n'
                    b'+++ test1.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-2\n'
                    b'+3\n'
                    b'--- test2.txt\n'
                    b'+++ test2.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-b\n'
                    b'+c\n'
                )),
            ])

        message = (
            'Partially applied patch 1 of 2, but there were conflicts.'
        )

        with self.assertRaisesMessage(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertTrue(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, ['test1.txt'])
        self.assertTrue(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[0])

        self.assertEqual(len(patcher.applied_patch_results), 0)

        with open(test_file1, 'r') as fp:
            self.assertEqual(fp.read(), '1\n')

        with open(test_file2, 'r') as fp:
            self.assertEqual(fp.read(), 'b\n')

    def test_patch_with_patch_error_conflicts_some_hunks(self) -> None:
        """Testing Patcher.patch with patch error and some hunks with
        conflicts
        """
        tmpdir = Path(make_tempdir())
        test_file1 = tmpdir / 'test1.txt'
        test_file2 = tmpdir / 'test2.txt'

        with open(test_file1, 'w') as fp:
            fp.write(
                '1\n'
                '\n'
                '\n'
                '\n'
                '\n'
                '--\n'
                '\n'
                '\n'
                '\n'
                '\n'
                '2\n'
            )

        with open(test_file2, 'w') as fp:
            fp.write('a\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test1.txt\n'
                    b'+++ test1.txt\n'
                    b'@@ -1,4 +1,4 @@\n'
                    b'-1\n'
                    b'+2\n'
                    b'\n'
                    b'\n'
                    b'\n'
                    b'@@ -8,4 +8,4 @@\n'
                    b'\n'
                    b'\n'
                    b'\n'
                    b'-x\n'
                    b'+3\n'
                    b'--- test2.txt\n'
                    b'+++ test2.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-a\n'
                    b'+b\n'
                )),
                Patch(content=(
                    b'--- test1.txt\n'
                    b'+++ test1.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-2\n'
                    b'+3\n'
                    b'--- test2.txt\n'
                    b'+++ test2.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-b\n'
                    b'+c\n'
                )),
            ])

        message = (
            'Partially applied patch 1 of 2, but there were conflicts.'
        )

        with self.assertRaisesMessage(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertTrue(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, ['test1.txt'])
        self.assertTrue(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[0])

        self.assertEqual(len(patcher.applied_patch_results), 0)

        with open(test_file1, 'r') as fp:
            self.assertEqual(
                fp.read(),
                '2\n'
                '\n'
                '\n'
                '\n'
                '\n'
                '--\n'
                '\n'
                '\n'
                '\n'
                '\n'
                '2\n')

        with open(test_file2, 'r') as fp:
            self.assertEqual(fp.read(), 'b\n')

    def test_patch_with_patch_revert_error(self) -> None:
        """Testing Patcher.patch with patch revert error"""
        tmpdir = Path(make_tempdir())
        test_file = tmpdir / 'test.txt'

        with open(test_file, 'w') as fp:
            fp.write('1\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                )),
                Patch(content=(
                    b'--- test.txt\n'
                    b'+++ test.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+3\n'
                )),
            ],
            revert=True)

        message = (
            'Could not revert patch 1 of 2. The patch may be invalid, or '
            'there may be conflicts that could not be resolved.'
        )

        with self.assertRaisesMessage(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertFalse(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, ['test.txt'])
        self.assertTrue(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[1])

        self.assertEqual(len(patcher.applied_patch_results), 0)

        with open(test_file, 'r') as fp:
            self.assertEqual(fp.read(), '1\n')

    def test_patch_with_patch_revert_error_conflicts(self) -> None:
        """Testing Patcher.patch with patch revert error and conflicts"""
        tmpdir = Path(make_tempdir())
        test_file1 = tmpdir / 'test1.txt'
        test_file2 = tmpdir / 'test2.txt'

        with open(test_file1, 'w') as fp:
            fp.write('3\n')

        with open(test_file2, 'w') as fp:
            fp.write('c\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test1.txt\n'
                    b'+++ test1.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                    b'--- test2.txt\n'
                    b'+++ test2.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-a\n'
                    b'+b\n'
                )),
                Patch(content=(
                    b'--- test1.txt\n'
                    b'+++ test1.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-2\n'
                    b'+3\n'
                    b'--- test2.txt\n'
                    b'+++ test2.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-b\n'
                    b'+x\n'
                )),
            ],
            revert=True)

        message = (
            'Partially reverted patch 1 of 2, but there were conflicts.'
        )

        with self.assertRaisesMessage(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertTrue(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, ['test2.txt'])
        self.assertTrue(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[1])

        self.assertEqual(len(patcher.applied_patch_results), 0)

        with open(test_file1, 'r') as fp:
            self.assertEqual(fp.read(), '2\n')

        with open(test_file2, 'r') as fp:
            self.assertEqual(fp.read(), 'c\n')

    def test_patch_with_bad_patch(self) -> None:
        """Testing Patcher.patch with bad patch"""
        tmpdir = Path(make_tempdir())
        test_file1 = tmpdir / 'test1.txt'

        with open(test_file1, 'w') as fp:
            fp.write('3\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=b'XXX'),
            ])

        message = (
            'Could not apply patch 1 of 1. The patch may be invalid, or '
            'there may be conflicts that could not be resolved.'
        )

        message = (
            r"("

            # GNU Diff
            r"There was an error applying patch 1 of 1: patch unexpectedly "
            r"ends in middle of line"
            r"|"

            # Apple Diff
            r"I can't seem to find a patch in there anywhere."
            r")"
        )

        with self.assertRaisesRegex(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertFalse(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[0])

        self.assertEqual(len(patcher.applied_patch_results), 0)

        with open(test_file1, 'r') as fp:
            self.assertEqual(fp.read(), '3\n')

    def test_patch_with_bad_filename(self) -> None:
        """Testing Patcher.patch with bad filename in patch"""
        tmpdir = Path(make_tempdir())
        test_file1 = tmpdir / 'test1.txt'

        with open(test_file1, 'w') as fp:
            fp.write('3\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- xxx.txt\n'
                    b'+++ xxx.txt\n'
                    b'@@ -1,1 +1,1 @@\n'
                    b'-1\n'
                    b'+2\n'
                )),
            ])

        message = (
            'Could not apply patch 1 of 1. The patch may be invalid, or '
            'there may be conflicts that could not be resolved.'
        )

        with self.assertRaisesMessage(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertFalse(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[0])

        self.assertEqual(len(patcher.applied_patch_results), 0)

        with open(test_file1, 'r') as fp:
            self.assertEqual(fp.read(), '3\n')

    def test_patch_with_malformed_patch(self) -> None:
        """Testing Patcher.patch with malformed patch"""
        tmpdir = Path(make_tempdir())
        test_file1 = tmpdir / 'test1.txt'

        with open(test_file1, 'w') as fp:
            fp.write('3\n')

        patcher = CommitPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=(
                    b'--- test1.txt\n'
                    b'+++ test1.txt\n'
                    b'@@ -1,1 +1,1\n'
                    b'-1\n'
                    b'+2\n'
                )),
            ])

        patch_command = os.environ.get('RBTOOLS_PATCH_COMMAND', 'patch')

        message = (
            f'There was an error applying patch 1 of 1: '
            f'patching file test1.txt\n'
            f'{patch_command}: **** malformed patch at line 3: @@ -1,1 +1,1'
        )

        with self.assertRaisesMessage(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertFalse(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[0])

        self.assertEqual(len(patcher.applied_patch_results), 0)

        with open(test_file1, 'r') as fp:
            self.assertEqual(fp.read(), '3\n')

    def test_patch_with_empty_files(self) -> None:
        """Testing Patcher.patch with empty files"""
        tmpdir = Path(make_tempdir())
        test_file1 = tmpdir / 'test1.txt'

        with open(test_file1, 'w') as fp:
            fp.write('3\n')

        patcher = EmptyFilesPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=EmptyFilesPatcher.EMPTY_FILE_DIFF),
            ])

        list(patcher.patch())

        patch_results = patcher.applied_patch_results

        self.assertEqual(len(patch_results), 1)

        patch_result = patch_results[0]
        self.assertTrue(patch_result.applied)
        self.assertTrue(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertIs(patch_result.patch, patcher.patches[0])
        self.assertEqual(patch_result.patch_range, (1, 1))

        with open(test_file1, 'r') as fp:
            self.assertEqual(fp.read(), '3\n')

    def test_patch_with_empty_files_and_garbage(self) -> None:
        """Testing Patcher.patch with empty files and garbage"""
        tmpdir = Path(make_tempdir())
        test_file1 = tmpdir / 'test1.txt'

        with open(test_file1, 'w') as fp:
            fp.write('3\n')

        patcher = EmptyFilesPatcher(
            dest_path=tmpdir,
            patches=[
                Patch(content=b'XXX'),
            ])

        message = (
            'There was an error applying patch 1 of 1: '
        )

        with self.assertRaisesMessage(ApplyPatchError, message) as ctx:
            list(patcher.patch())

        patch_result = ctx.exception.failed_patch_result
        assert patch_result
        self.assertFalse(patch_result.applied)
        self.assertFalse(patch_result.success)
        self.assertEqual(patch_result.conflicting_files, [])
        self.assertFalse(patch_result.has_conflicts)
        self.assertEqual(patch_result.patch_range, (1, 1))
        self.assertIs(patch_result.patch, patcher.patches[0])

        self.assertEqual(len(patcher.applied_patch_results), 0)

        with open(test_file1, 'r') as fp:
            self.assertEqual(fp.read(), '3\n')

    def test_parse_patch_output_with_empty(self) -> None:
        """Testing Patcher.parse_patch_output with empty output"""
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(b''),
            {
                'conflicting_files': [],
                'fatal_error': None,
                'has_empty_files': False,
                'has_partial_applied_files': False,
                'patched_files': [],
            })

    def test_parse_patch_output_with_success(self) -> None:
        """Testing Patcher.parse_patch_output with successful patches"""
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b'patching file foo.c\n'
                b'patching file subdir/bar.txt\n'
            ),
            {
                'conflicting_files': [],
                'fatal_error': None,
                'has_empty_files': False,
                'has_partial_applied_files': False,
                'patched_files': [
                    'foo.c',
                    'subdir/bar.txt',
                ],
            })

    def test_parse_patch_output_gnu_with_fatal_error(self) -> None:
        """Testing Patcher.parse_patch_output with GNU patch and fatal error"""
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b'patch: **** something bad happened\n'
                b'oh no.\n'
            ),
            {
                'conflicting_files': [],
                'fatal_error': (
                    'patch: **** something bad happened\n'
                    'oh no.'
                ),
                'has_empty_files': False,
                'has_partial_applied_files': False,
                'patched_files': [],
            })

    def test_parse_patch_output_bsd_with_fatal_error(self) -> None:
        """Testing Patcher.parse_patch_output with BSD patch and fatal error"""
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b"I can't seem to find a patch in there anywhere.\n"
                b"oh no.\n"
            ),
            {
                'conflicting_files': [],
                'fatal_error': (
                    "I can't seem to find a patch in there anywhere.\n"
                    "oh no."
                ),
                'has_empty_files': True,
                'has_partial_applied_files': False,
                'patched_files': [],
            })

    def test_parse_patch_output_gnu_with_empty_files(self) -> None:
        """Testing Patcher.parse_patch_output with GNU patch and possible
        empty files
        """
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b'patch: **** Only garbage was found in the patch input.'
            ),
            {
                'conflicting_files': [],
                'fatal_error': (
                    'patch: **** Only garbage was found in the patch input.'
                ),
                'has_empty_files': True,
                'has_partial_applied_files': False,
                'patched_files': [],
            })

    def test_parse_patch_output_bsd_with_empty_files(self) -> None:
        """Testing Patcher.parse_patch_output with BSD patch and possible
        empty files
        """
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b"I can't seem to find a patch in there anywhere."
            ),
            {
                'conflicting_files': [],
                'fatal_error': (
                    "I can't seem to find a patch in there anywhere."
                ),
                'has_empty_files': True,
                'has_partial_applied_files': False,
                'patched_files': [],
            })

    def test_parse_patch_output_gnu_with_conflicts(self) -> None:
        """Testing Patcher.parse_patch_output with GNU patch and conflicts"""
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b'patching file subdir/bar.txt\n'
                b'2 out of 2 hunks failed--saving rejects to'
                b' subdir/bar.txt.rej\n'
            ),
            {
                'conflicting_files': [
                    'subdir/bar.txt',
                ],
                'fatal_error': None,
                'has_empty_files': False,
                'has_partial_applied_files': False,
                'patched_files': [
                    'subdir/bar.txt',
                ],
            })

    def test_parse_patch_output_bsd_with_conflicts(self) -> None:
        """Testing Patcher.parse_patch_output with BSD patch and conflicts"""
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b'patching file subdir/bar.txt\n'
                b'2 out of 2 hunks FAILED -- saving rejects to file'
                b' subdir/bar.txt.rej\n'
            ),
            {
                'conflicting_files': [
                    'subdir/bar.txt',
                ],
                'fatal_error': None,
                'has_empty_files': False,
                'has_partial_applied_files': False,
                'patched_files': [
                    'subdir/bar.txt',
                ],
            })

    def test_parse_patch_output_gnu_with_conflicts_partial(self) -> None:
        """Testing Patcher.parse_patch_output with GNU patch and conflicts
        and patches partially applied
        """
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b'patching file subdir/bar.txt\n'
                b'1 out of 2 hunks failed--saving rejects to'
                b' subdir/bar.txt.rej\n'
            ),
            {
                'conflicting_files': [
                    'subdir/bar.txt',
                ],
                'fatal_error': None,
                'has_empty_files': False,
                'has_partial_applied_files': True,
                'patched_files': [
                    'subdir/bar.txt',
                ],
            })

    def test_parse_patch_output_bsd_with_conflicts_partial(self) -> None:
        """Testing Patcher.parse_patch_output with BSD patch and conflicts
        and patches partially applied
        """
        patcher = Patcher(patches=[])

        self.assertEqual(
            patcher.parse_patch_output(
                b'patching file subdir/bar.txt\n'
                b'1 out of 2 hunks FAILED -- saving rejects to file'
                b' subdir/bar.txt.rej\n'
            ),
            {
                'conflicting_files': [
                    'subdir/bar.txt',
                ],
                'fatal_error': None,
                'has_empty_files': False,
                'has_partial_applied_files': True,
                'patched_files': [
                    'subdir/bar.txt',
                ],
            })
