"""Unit tests for rbtools.utils.filesystem."""

from __future__ import unicode_literals

import os
import shutil

from rbtools.testing import TestCase
from rbtools.utils import filesystem
from rbtools.utils.filesystem import (cleanup_tempfiles, make_empty_files,
                                      make_tempdir, make_tempfile)


class FilesystemTests(TestCase):
    """Unit tests for rbtools.utils.filesystem."""

    def test_make_tempfile(self):
        """Testing make_tempfile"""
        filename = make_tempfile()
        self.assertIn(filename, filesystem.tempfiles)

        self.assertTrue(os.path.isfile(filename))
        self.assertTrue(os.path.basename(filename).startswith('rbtools.'))
        self.assertEqual(os.stat(filename).st_uid, os.geteuid())
        self.assertTrue(os.access(filename, os.R_OK | os.W_OK))

    def test_make_tempfile_with_prefix(self):
        """Testing make_tempfile with prefix"""
        filename = make_tempfile(prefix='supertest-')

        self.assertIn(filename, filesystem.tempfiles)
        self.assertTrue(os.path.isfile(filename))
        self.assertTrue(os.path.basename(filename).startswith('supertest-'))
        self.assertEqual(os.stat(filename).st_uid, os.geteuid())
        self.assertTrue(os.access(filename, os.R_OK | os.W_OK))

    def test_make_tempfile_with_suffix(self):
        """Testing make_tempfile with suffix"""
        filename = make_tempfile(suffix='.xyz')

        self.assertIn(filename, filesystem.tempfiles)
        self.assertTrue(os.path.isfile(filename))
        self.assertTrue(os.path.basename(filename).startswith('rbtools.'))
        self.assertTrue(os.path.basename(filename).endswith('.xyz'))
        self.assertEqual(os.stat(filename).st_uid, os.geteuid())
        self.assertTrue(os.access(filename, os.R_OK | os.W_OK))

    def test_make_tempfile_with_filename(self):
        """Testing make_tempfile with filename"""
        filename = make_tempfile(filename='TEST123')

        self.assertIn(filename, filesystem.tempfiles)
        self.assertEqual(os.path.basename(filename), 'TEST123')
        self.assertTrue(os.path.isfile(filename))
        self.assertTrue(os.access(filename, os.R_OK | os.W_OK))
        self.assertEqual(os.stat(filename).st_uid, os.geteuid())

        parent_dir = os.path.dirname(filename)
        self.assertIn(parent_dir, filesystem.tempdirs)
        self.assertTrue(os.access(parent_dir, os.R_OK | os.W_OK | os.X_OK))
        self.assertEqual(os.stat(parent_dir).st_uid, os.geteuid())

    def test_make_empty_files(self):
        """Testing make_empty_files"""
        # Use make_tempdir to get a unique directory name
        tmpdir = make_tempdir()
        self.assertTrue(os.path.isdir(tmpdir))
        cleanup_tempfiles()

        fname = os.path.join(tmpdir, 'file')
        make_empty_files([fname])
        self.assertTrue(os.path.isdir(tmpdir))
        self.assertTrue(os.path.isfile(fname))
        self.assertEqual(os.stat(fname).st_uid, os.geteuid())
        self.assertTrue(os.access(fname, os.R_OK | os.W_OK))

        shutil.rmtree(tmpdir, ignore_errors=True)
