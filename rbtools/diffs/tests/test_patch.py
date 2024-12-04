"""Unit tests for rbtools.diffs.patches.Patch.

Version Added:
    5.1
"""

from __future__ import annotations

import re
from pathlib import Path

from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.diffs.patches import Patch, PatchAuthor
from rbtools.testing import TestCase
from rbtools.utils.filesystem import make_tempfile


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
        self.assertEqual(author.fullname, 'Test User')
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
        self.assertEqual(author.fullname, 'Test User')
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
        message = "prefix_level must be an integer, not 'XXX'."

        with self.assertRaisesMessage(ValueError, message):
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
