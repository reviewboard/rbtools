"""Unit tests for rbtools.diffs.patches.Patch.

Version Added:
    5.1
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import kgb

from rbtools.api.resource import FileAttachmentItemResource
from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.diffs.patches import BinaryFilePatch, Patch, PatchAuthor
from rbtools.testing import TestCase
from rbtools.testing.api.transport import URLMapTransport
from rbtools.utils.filesystem import make_tempfile


class BinaryFilePatchTests(kgb.SpyAgency, TestCase):
    """Unit tests for BinaryFilePatch.

    Version Added:
        6.0
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        self.attachment = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 123,
                'absolute_url': 'https://reviews.example.com/r/1/file/123/'
                                'download/',
            },
            url=(
                'http://reviews.example.com/api/review-requests/1/'
                'file-attachments/123/'
            ),
        )

    def test_init(self) -> None:
        """Testing BinaryFilePatch.__init__"""
        binary_file = BinaryFilePatch(
            old_path='old/file.png',
            new_path='new/file.png',
            status='modified',
            file_attachment=self.attachment,
        )

        self.assertEqual(binary_file.old_path, 'old/file.png')
        self.assertEqual(binary_file.new_path, 'new/file.png')
        self.assertEqual(binary_file.status, 'modified')
        self.assertEqual(binary_file._attachment, self.attachment)
        self.assertIsNone(binary_file._content)
        self.assertIsNone(binary_file.download_error)
        self.assertFalse(binary_file._content_loaded)

    def test_path_property_with_new_path(self) -> None:
        """Testing BinaryFilePatch.path with new_path"""
        binary_file = BinaryFilePatch(
            old_path='old/file.png',
            new_path='new/file.png',
            status='modified',
            file_attachment=self.attachment,
        )

        self.assertEqual(binary_file.path, 'new/file.png')

    def test_path_property_with_only_old_path(self) -> None:
        """Testing BinaryFilePatch.path with only old_path (deleted file)"""
        binary_file = BinaryFilePatch(
            old_path='old/file.png',
            new_path=None,
            status='deleted',
            file_attachment=self.attachment,
        )

        self.assertEqual(binary_file.path, 'old/file.png')

    def test_content_lazy_loading_success(self) -> None:
        """Testing BinaryFilePatch.content lazy loading with successful
        download
        """
        test_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...'

        binary_file = BinaryFilePatch(
            old_path=None,
            new_path='file.png',
            status='added',
            file_attachment=self.attachment,
        )

        self.spy_on(urlopen, op=kgb.SpyOpReturn(BytesIO(test_content)))

        # First access should download content.
        content = binary_file.content
        self.assertEqual(content, test_content)
        self.assertTrue(binary_file._content_loaded)
        self.assertIsNone(binary_file.download_error)

        # Second access should return cached content without downloading again.
        content2 = binary_file.content
        self.assertEqual(content2, test_content)

    def test_content_lazy_loading_url_error(self) -> None:
        """Testing BinaryFilePatch.content lazy loading with URL error"""
        binary_file = BinaryFilePatch(
            old_path=None,
            new_path='file.png',
            status='added',
            file_attachment=self.attachment,
        )

        self.spy_on(urlopen, op=kgb.SpyOpRaise(URLError('Test URL error')))

        content = binary_file.content
        self.assertIsNone(content)
        self.assertTrue(binary_file._content_loaded)

        assert binary_file.download_error is not None
        self.assertIn('Test URL error', binary_file.download_error)

    def test_content_deleted_file(self) -> None:
        """Testing BinaryFilePatch.content for deleted files"""
        binary_file = BinaryFilePatch(
            old_path='file.png',
            new_path=None,
            status='deleted',
            file_attachment=self.attachment,
        )

        # Should not attempt to download for deleted files.
        content = binary_file.content
        self.assertIsNone(content)
        self.assertTrue(binary_file._content_loaded)
        self.assertIsNone(binary_file.download_error)

    def test_content_no_attachment(self) -> None:
        """Testing BinaryFilePatch.content with no attachment"""
        binary_file = BinaryFilePatch(
            old_path=None,
            new_path='file.png',
            status='added',
            file_attachment=None,
        )

        content = binary_file.content
        self.assertIsNone(content)
        self.assertTrue(binary_file._content_loaded)
        self.assertEqual(binary_file.download_error, 'No attachment available')


class PatchTests(TestCase):
    """Unit tests for Patch.

    Version Added:
        5.1
    """

    def test_init_with_content(self) -> None:
        """Testing Patch.__init__ with content"""
        patch = Patch(author=PatchAuthor(full_name='Test User',
                                         email='test@example.com'),
                      base_dir='/base',
                      content=b'patch...',
                      message='This is a commit message.',
                      prefix_level=1)

        self.assertEqual(patch.base_dir, '/base')
        self.assertEqual(patch.message, 'This is a commit message.')
        self.assertEqual(patch.prefix_level, 1)
        self.assertEqual(patch._content, b'patch...')
        self.assertIsNone(patch._path)

        author = patch.author
        assert author is not None
        self.assertEqual(author.full_name, 'Test User')
        self.assertEqual(author.email, 'test@example.com')

    def test_init_with_path(self) -> None:
        """Testing Patch.__init__ with path"""
        patch = Patch(author=PatchAuthor(full_name='Test User',
                                         email='test@example.com'),
                      base_dir='/base',
                      path=Path('/path/to/patch'),
                      message='This is a commit message.',
                      prefix_level=1)

        self.assertEqual(patch.base_dir, '/base')
        self.assertEqual(patch.message, 'This is a commit message.')
        self.assertEqual(patch.prefix_level, 1)
        self.assertEqual(patch._path, Path('/path/to/patch'))
        self.assertIsNone(patch._content)

        author = patch.author
        assert author is not None
        self.assertEqual(author.full_name, 'Test User')
        self.assertEqual(author.email, 'test@example.com')

    def test_init_without_content_or_path(self) -> None:
        """Testing Patch.__init__ without content or path"""
        message = 'Either content= or path= must be provided.'

        with self.assertRaisesMessage(ValueError, message):
            Patch(author=PatchAuthor(full_name='Test User',
                                     email='test@example.com'),
                  base_dir='/base',
                  message='This is a commit message.',
                  prefix_level=1)

    def test_init_with_prefix_level_int_string(self) -> None:
        """Testing Patch.__init__ with prefix_level as string-encoded int"""
        message = re.escape(
            'prefix_level must be an integer, not a string. Support '
            'for string prefix levels will be removed in RBTools 7.'
        )

        with self.assertWarnsRegex(RemovedInRBTools70Warning, message):
            patch = Patch(author=PatchAuthor(full_name='Test User',
                                             email='test@example.com'),
                          content=b'XXX',
                          base_dir='/base',
                          message='This is a commit message.',
                          prefix_level='1')  # type: ignore

        self.assertEqual(patch.prefix_level, 1)

    def test_init_with_prefix_level_invalid_string(self) -> None:
        """Testing Patch.__init__ with prefix_level as string with non-int
        contents
        """
        error_message = "prefix_level must be an integer, not 'XXX'."
        warning_message = (
            'prefix_level must be an integer, not a string. Support for '
            'string prefix levels will be removed in RBTools 7.'
        )

        with self.assertRaisesMessage(ValueError,
                                      error_message), \
             self.assertWarns(RemovedInRBTools70Warning,
                              msg=warning_message):
            Patch(author=PatchAuthor(full_name='Test User',
                                     email='test@example.com'),
                  content=b'XXX',
                  base_dir='/base',
                  message='This is a commit message.',
                  prefix_level='XXX')  # type: ignore

    def test_content_with_content_set(self) -> None:
        """Testing Patch.content with content set"""
        patch = Patch(content=b'patch...')

        with patch.open():
            self.assertEqual(patch.content, b'patch...')

    def test_content_with_path_set(self) -> None:
        """Testing Patch.content with path set"""
        patch_file = Path(make_tempfile(content=b'patch from file...'))
        patch = Patch(path=patch_file)

        with patch.open():
            self.assertEqual(patch.content, b'patch from file...')

        self.assertTrue(patch_file.exists())

    def test_content_not_opened(self) -> None:
        """Testing Patch.content without patch opened"""
        patch = Patch(content=b'patch...')
        message = 'Patch objects must be opened before being read.'

        with self.assertRaisesMessage(IOError, message):
            patch.content

    def test_path_with_content_set(self) -> None:
        """Testing Patch.path with content set"""
        patch = Patch(content=b'patch...')

        with patch.open():
            patch_file = patch.path
            self.assertTrue(patch_file.exists())

            with open(patch_file, 'rb') as fp:
                self.assertEqual(fp.read(), b'patch...')

        self.assertFalse(patch_file.exists())

    def test_path_with_path_set(self) -> None:
        """Testing Patch.path with path set"""
        patch_file = Path(make_tempfile(content=b'patch from file...'))
        patch = Patch(path=patch_file)

        with patch.open():
            self.assertIs(patch.path, patch_file)
            self.assertTrue(patch_file.exists())

            with open(patch_file, 'rb') as fp:
                self.assertEqual(fp.read(), b'patch from file...')

        self.assertTrue(patch_file.exists())

    def test_path_not_opened(self) -> None:
        """Testing Patch.path without patch opened"""
        patch = Patch(content=b'patch...')
        message = 'Patch objects must be opened before being read.'

        with self.assertRaisesMessage(IOError, message):
            patch.path

    def test_init_with_binary_files(self) -> None:
        """Testing Patch.__init__ with binary_files"""
        attachment1 = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 123,
                'absolute_url': 'https://reviews.example.com/r/1/file/123/'
                                'download/',
            },
            url=(
                'http://reviews.example.com/api/review-requests/1/'
                'file-attachments/123/'
            ),
        )
        attachment2 = FileAttachmentItemResource(
            transport=URLMapTransport('https://reviews.example.com/'),
            payload={
                'id': 124,
                'absolute_url': 'https://reviews.example.com/r/1/file/124/'
                                'download/',
            },
            url=(
                'http://reviews.example.com/api/review-requests/1/'
                'file-attachments/124/'
            ),
        )

        binary_files = [
            BinaryFilePatch(
                old_path=None,
                new_path='images/file1.png',
                status='added',
                file_attachment=attachment1,
            ),
            BinaryFilePatch(
                old_path='images/old_file2.jpg',
                new_path='images/file2.jpg',
                status='modified',
                file_attachment=attachment2,
            ),
        ]

        patch = Patch(
            content=b'patch...',
            binary_files=binary_files,
        )

        self.assertEqual(len(patch.binary_files), 2)
        self.assertEqual(patch.binary_files[0].new_path, 'images/file1.png')
        self.assertEqual(patch.binary_files[0].status, 'added')
        self.assertEqual(patch.binary_files[1].old_path,
                         'images/old_file2.jpg')
        self.assertEqual(patch.binary_files[1].status, 'modified')


class PatchResultTests(TestCase):
    """Unit tests for PatchResult.

    Version Added:
        6.0
    """

    def test_init_with_binary_results(self) -> None:
        """Testing PatchResult.__init__ with binary file results"""
        from rbtools.diffs.patches import PatchResult

        binary_applied = ['file1.png', 'file2.jpg']
        binary_failed = {'file3.gif': 'Download failed'}

        result = PatchResult(
            applied=True,
            binary_applied=binary_applied,
            binary_failed=binary_failed,
        )

        self.assertTrue(result.applied)
        self.assertEqual(list(result.binary_applied), binary_applied)
        self.assertEqual(dict(result.binary_failed), binary_failed)

        # Should fail due to binary_failed.
        self.assertFalse(result.success)

    def test_init_without_binary_results(self) -> None:
        """Testing PatchResult.__init__ without binary file results"""
        from rbtools.diffs.patches import PatchResult

        result = PatchResult(applied=True)

        self.assertTrue(result.applied)
        self.assertEqual(len(result.binary_applied), 0)
        self.assertEqual(len(result.binary_failed), 0)
        self.assertTrue(result.success)

    def test_success_with_binary_failures(self) -> None:
        """Testing PatchResult.success with binary file failures"""
        from rbtools.diffs.patches import PatchResult

        result = PatchResult(
            applied=True,
            has_conflicts=False,
            binary_applied=['file1.png'],
            binary_failed={'file2.jpg': 'Network error'},
        )

        # Should be False because binary files failed.
        self.assertFalse(result.success)

    def test_success_with_conflicts_and_binary_success(self) -> None:
        """Testing PatchResult.success with conflicts but binary success"""
        from rbtools.diffs.patches import PatchResult

        result = PatchResult(
            applied=True,
            has_conflicts=True,
            binary_applied=['file1.png'],
            binary_failed={},
        )

        # Should be False because of conflicts.
        self.assertFalse(result.success)

    def test_success_with_all_success(self) -> None:
        """Testing PatchResult.success with all operations successful"""
        from rbtools.diffs.patches import PatchResult

        result = PatchResult(
            applied=True,
            has_conflicts=False,
            binary_applied=['file1.png', 'file2.jpg'],
            binary_failed={},
        )

        # Should be True - all operations successful.
        self.assertTrue(result.success)
