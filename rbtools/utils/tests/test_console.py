"""Unit tests for rbtools.utils.console."""

from __future__ import unicode_literals

import os
import subprocess

from kgb import SpyAgency

from rbtools.testing import TestCase
from rbtools.utils.console import edit_file, edit_text
from rbtools.utils.errors import EditorError
from rbtools.utils.filesystem import make_tempfile


class ConsoleTests(SpyAgency, TestCase):
    """Unit tests for rbtools.utils.console."""

    def test_edit_file(self):
        """Testing edit_file"""
        result = edit_file(make_tempfile(b'Test content'))

        self.assertEqual(result, 'TEST CONTENT')

    def test_edit_file_with_invalid_filename(self):
        """Testing edit_file with invalid filename"""
        message = (
            'The file "blargh-bad-filename" does not exist or is not '
            'accessible.'
        )

        with self.assertRaisesMessage(EditorError, message):
            edit_file('blargh-bad-filename')

    def test_edit_file_with_invalid_editor(self):
        """Testing edit_file with invalid filename"""
        message = (
            'The editor "./bad-rbtools-editor" was not found or could not '
            'be run. Make sure the EDITOR environment variable is set '
            'to your preferred editor.'
        )

        os.environ[str('RBTOOLS_EDITOR')] = './bad-rbtools-editor'

        with self.assertRaisesMessage(EditorError, message):
            edit_file(make_tempfile(b'Test content'))

    def test_edit_file_with_file_deleted(self):
        """Testing edit_file with file deleted during edit"""
        def _subprocess_call(*args, **kwargs):
            os.unlink(filename)

        filename = make_tempfile(b'Test content')
        message = 'The edited file "%s" was deleted during edit.' % filename

        self.spy_on(subprocess.call, call_fake=_subprocess_call)

        with self.assertRaisesMessage(EditorError, message):
            edit_file(filename)

    def test_edit_file_with_editor_priority(self):
        """Testing edit_file editor priority"""
        self.spy_on(subprocess.call, call_original=False)

        # Save these so we can restore after the tests. We don't need to
        # save RBTOOLS_EDITOR, because this is taken care of in the base
        # TestCase class.
        old_visual = os.environ.get(str('VISUAL'))
        old_editor = os.environ.get(str('EDITOR'))

        filename = make_tempfile(b'Test content')

        try:
            os.environ[str('RBTOOLS_EDITOR')] = 'rbtools-editor'
            os.environ[str('VISUAL')] = 'visual'
            os.environ[str('EDITOR')] = 'editor'

            edit_file(filename)
            self.assertTrue(subprocess.call.last_called_with(
                ['rbtools-editor', filename]))

            os.environ[str('RBTOOLS_EDITOR')] = ''
            edit_file(filename)
            self.assertTrue(subprocess.call.last_called_with(
                ['visual', filename]))

            os.environ[str('VISUAL')] = ''
            edit_file(filename)
            self.assertTrue(subprocess.call.last_called_with(
                ['editor', filename]))

            os.environ[str('EDITOR')] = ''
            edit_file(filename)
            self.assertTrue(subprocess.call.last_called_with(
                ['vi', filename]))
        finally:
            if old_visual:
                os.environ[str('VISUAL')] = old_visual

            if old_editor:
                os.environ[str('EDITOR')] = old_editor

    def test_edit_text(self):
        """Testing edit_text"""
        result = edit_text('Test content')

        self.assertEqual(result, 'TEST CONTENT')

    def test_edit_text_with_filename(self):
        """Testing edit_text with custom filename"""
        self.spy_on(subprocess.call)

        result = edit_text('Test content',
                           filename='my-custom-filename')

        self.assertEqual(result, 'TEST CONTENT')
        self.assertEqual(
            os.path.basename(subprocess.call.last_call.args[0][-1]),
            'my-custom-filename')
