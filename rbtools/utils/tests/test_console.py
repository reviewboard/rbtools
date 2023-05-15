"""Unit tests for rbtools.utils.console."""

import io
import os
import subprocess

import kgb

from rbtools.testing import TestCase
from rbtools.utils.console import (confirm,
                                   confirm_select,
                                   edit_file,
                                   edit_text,
                                   get_input,
                                   get_pass)
from rbtools.utils.errors import EditorError
from rbtools.utils.filesystem import make_tempfile


class StreamTestsMixin(object):
    """Mixin for console unit tests that require stream overrides.

    Version Added:
        3.1
    """

    def setUp(self):
        super(StreamTestsMixin, self).setUp()

        self.stdin = io.TextIOWrapper(io.BytesIO())
        self.stderr = io.TextIOWrapper(io.BytesIO())


class ConfirmTests(StreamTestsMixin, TestCase):
    """Unit tests for rbtools.utils.console.confirm."""

    def test_with_yes(self):
        """Testing confirm with "yes" response"""
        self._test_confirm(answer='yes',
                           expected_answer=True,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_y(self):
        """Testing confirm with "y" response"""
        self._test_confirm(answer='y',
                           expected_answer=True,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_true(self):
        """Testing confirm with "true" response"""
        self._test_confirm(answer='true',
                           expected_answer=True,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_t(self):
        """Testing confirm with "t" response"""
        self._test_confirm(answer='t',
                           expected_answer=True,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_on(self):
        """Testing confirm with "on" response"""
        self._test_confirm(answer='on',
                           expected_answer=True,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_1(self):
        """Testing confirm with "1" response"""
        self._test_confirm(answer='1',
                           expected_answer=True,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_no(self):
        """Testing confirm with "no" response"""
        self._test_confirm(answer='no',
                           expected_answer=False,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_n(self):
        """Testing confirm with "n" response"""
        self._test_confirm(answer='n',
                           expected_answer=False,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_false(self):
        """Testing confirm with "false" response"""
        self._test_confirm(answer='false',
                           expected_answer=False,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_f(self):
        """Testing confirm with "f" response"""
        self._test_confirm(answer='f',
                           expected_answer=False,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_off(self):
        """Testing confirm with "off" response"""
        self._test_confirm(answer='off',
                           expected_answer=False,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_0(self):
        """Testing confirm with "1" response"""
        self._test_confirm(answer='0',
                           expected_answer=False,
                           expected_stderr='My Prompt [Yes/No]: ')

    def test_with_repeated_asks(self):
        """Testing confirm repeatedly asks until an answer is given"""
        self._test_confirm(
            answer='\nfoo\ntrue',
            expected_answer=True,
            expected_stderr=(
                'My Prompt [Yes/No]: '
                '"" is not a valid answer.\n'
                'My Prompt [Yes/No]: '
                '"foo" is not a valid answer.\n'
                'My Prompt [Yes/No]: '
            ))

    def _test_confirm(self, answer, expected_answer, expected_stderr):
        """Convenience function for perform tests.

        This automates setting up the test, performing the call, and checking
        results.

        Args:
            answer (unicode):
                The answer(s) to give.

            expected_answer (bool):
                The expected final answer returned.

            expected_stderr (unicode):
                The expected stderr results.

        Raises:
            AssertionError:
                An assertion failed.
        """
        self.stdin.write('%s\n' % answer)
        self.stdin.seek(0)

        self.assertIs(confirm('My Prompt',
                              stderr=self.stderr,
                              stdin=self.stdin),
                      expected_answer)

        self.stderr.seek(0)
        self.assertEqual(self.stderr.read(), expected_stderr)


class ConfirmSelectTests(StreamTestsMixin, TestCase):
    """Unit tests for rbtools.utils.console.confirm_select."""

    def test_with_valid_response(self):
        """Testing confirm_select with valid response"""
        self._test_confirm_select(answer='2',
                                  expected_answer=2,
                                  expected_stderr='My Prompt [1-3]: ')

    def test_with_invalid_response(self):
        """Testing confirm_select with invalid response"""
        self._test_confirm_select(
            answer='\n0\n4\n1',
            expected_answer=1,
            expected_stderr=(
                'My Prompt [1-3]: '
                '"" is not a valid answer.\n'
                'My Prompt [1-3]: '
                '"0" is not a valid answer.\n'
                'My Prompt [1-3]: '
                '"4" is not a valid answer.\n'
                'My Prompt [1-3]: '
            ))

    def _test_confirm_select(self, answer, expected_answer, expected_stderr):
        """Convenience function for perform tests.

        This automates setting up the test, performing the call, and checking
        results.

        Args:
            answer (unicode):
                The answer(s) to give.

            expected_answer (bool):
                The expected final answer returned.

            expected_stderr (unicode):
                The expected stderr results.

        Raises:
            AssertionError:
                An assertion failed.
        """
        self.stdin.write('%s\n' % answer)
        self.stdin.seek(0)

        self.assertIs(confirm_select('My Prompt',
                                     options_length=3,
                                     stderr=self.stderr,
                                     stdin=self.stdin),
                      expected_answer)

        self.stderr.seek(0)
        self.assertEqual(self.stderr.read(), expected_stderr)


class EditFileTests(kgb.SpyAgency, TestCase):
    """Unit tests for rbtools.utils.console.edit_file."""

    def test_edit_file(self):
        """Testing edit_file"""
        result = edit_file(make_tempfile(content=b'Test content'))

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
            edit_file(make_tempfile(content=b'Test content'))

    def test_edit_file_with_file_deleted(self):
        """Testing edit_file with file deleted during edit"""
        def _subprocess_call(*args, **kwargs):
            os.unlink(filename)

        filename = make_tempfile(content=b'Test content')
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

        filename = make_tempfile(content=b'Test content')

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


class EditTextTests(kgb.SpyAgency, TestCase):
    """Unit tests for rbtools.utils.console.edit_text."""

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


class GetInputTests(StreamTestsMixin, TestCase):
    """Unit tests for rbtools.utils.console.get_input."""

    def test_with_require_false_and_value(self):
        """Testing get_input with require=False and value provided"""
        self._test_get_input(
            answer='my answer',
            require=False,
            expected_answer='my answer',
            expected_stderr='My Prompt: ')

    def test_with_require_false_and_blank_value(self):
        """Testing get_input with require=False and blank value provided"""
        self._test_get_input(
            answer='\n\nno answer',
            require=False,
            expected_answer='',
            expected_stderr='My Prompt: ')

    def test_with_require_false_and_no_value(self):
        """Testing get_input with require=False and no value provided"""
        self._test_get_input(
            answer='',
            require=False,
            expected_answer='',
            expected_stderr='My Prompt: ')

    def test_with_require_true_and_value(self):
        """Testing get_input with require=True and value provided"""
        self._test_get_input(
            answer='my answer',
            require=True,
            expected_answer='my answer',
            expected_stderr='My Prompt: ')

    def test_with_require_true_and_blank_value_initially_provided(self):
        """Testing get_input with require=True and blank values initially
        provided
        """
        self._test_get_input(
            answer='\n\nmy answer',
            require=True,
            expected_answer='my answer',
            expected_stderr=(
                'My Prompt: '
                'My Prompt: '
                'My Prompt: '
            ))

    def _test_get_input(self, answer, require, expected_answer,
                        expected_stderr):
        """Convenience function for perform tests.

        This automates setting up the test, performing the call, and checking
        results.

        Args:
            answer (unicode):
                The answer(s) to give.

            require (bool):
                The ``require=`` flag to pass.

            expected_answer (bool):
                The expected final answer returned.

            expected_stderr (unicode):
                The expected stderr results.

        Raises:
            AssertionError:
                An assertion failed.
        """
        self.stdin.write('%s\n' % answer)
        self.stdin.seek(0)

        self.assertEqual(
            get_input('My Prompt: ',
                      stderr=self.stderr,
                      stdin=self.stdin,
                      require=require),
            expected_answer)

        self.stderr.seek(0)
        self.assertEqual(self.stderr.read(), expected_stderr)


class GetPassTests(StreamTestsMixin, TestCase):
    """Unit tests for rbtools.utils.console.get_pass."""

    def test_with_require_false_and_value(self):
        """Testing get_pass with require=False and value provided"""
        self._test_get_pass(
            answer='my answer',
            require=False,
            expected_answer='my answer',
            expected_stderr='My Prompt: ')

    def test_with_require_false_and_blank_value(self):
        """Testing get_pass with require=False and blank value provided"""
        self._test_get_pass(
            answer='\n\nno answer',
            require=False,
            expected_answer='',
            expected_stderr='My Prompt: ')

    def test_with_require_false_and_no_value(self):
        """Testing get_pass with require=False and no value provided"""
        self._test_get_pass(
            answer='',
            require=False,
            expected_answer='',
            expected_stderr='My Prompt: ')

    def test_with_require_true_and_value(self):
        """Testing get_pass with require=True and value provided"""
        self._test_get_pass(
            answer='my answer',
            require=True,
            expected_answer='my answer',
            expected_stderr='My Prompt: ')

    def test_with_require_true_and_blank_value_initially_provided(self):
        """Testing get_pass with require=True and blank values initially
        provided
        """
        self._test_get_pass(
            answer='\n\nmy answer',
            require=True,
            expected_answer='my answer',
            expected_stderr=(
                'My Prompt: '
                'My Prompt: '
                'My Prompt: '
            ))

    def _test_get_pass(self, answer, require, expected_answer,
                       expected_stderr):
        """Convenience function for perform tests.

        This automates setting up the test, performing the call, and checking
        results.

        Args:
            answer (unicode):
                The answer(s) to give.

            require (bool):
                The ``require=`` flag to pass.

            expected_answer (bool):
                The expected final answer returned.

            expected_stderr (unicode):
                The expected stderr results.

        Raises:
            AssertionError:
                An assertion failed.
        """
        self.stdin.write('%s\n' % answer)
        self.stdin.seek(0)

        self.assertEqual(
            get_pass('My Prompt: ',
                     stderr=self.stderr,
                     stdin=self.stdin,
                     require=require),
            expected_answer)

        self.stderr.seek(0)
        self.assertEqual(self.stderr.read(), expected_stderr)
