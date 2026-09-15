"""Unit tests for rbtools.ui.console.

Version Added:
    7.0
"""

from __future__ import annotations

import io
import logging
from contextlib import ExitStack
from typing import TYPE_CHECKING

import kgb

from rbtools.testing import TestCase
from rbtools.ui.console import RBToolsConsole, write_passthrough

if TYPE_CHECKING:
    from rbtools.ui.console import ColorMode


class RBToolsConsoleTests(kgb.SpyAgency, TestCase):
    """Unit tests for RBToolsConsole.

    Version Added:
        7.0
    """

    def setUp(self) -> None:
        """Set up the test case."""
        super().setUp()

        # Rich disables color and live displays when TERM is "dumb", which
        # is what the CI image sets. Pin it so these tests don't depend on
        # the environment.
        stack = ExitStack()
        stack.enter_context(self.env({'TERM': 'xterm'}))
        self.addCleanup(stack.close)

    def test_enabled_for_color_mode(self) -> None:
        """Testing RBToolsConsole.enabled for each color mode"""
        console, _stdout, _stderr = self._make_console(color_mode='always')
        self.assertTrue(console.enabled)

        console, _stdout, _stderr = self._make_console(color_mode='never')
        self.assertFalse(console.enabled)

    def test_write_passthrough(self) -> None:
        """Testing write_passthrough writes text verbatim"""
        console, stdout_buffer, _stderr = self._make_console()

        write_passthrough(console.stdout_console, 'foo   bar\n')
        write_passthrough(console.stdout_console, 'x' * 200)

        self.assertEqual(self._read(console, stdout_buffer),
                         b'foo   bar\n' + b'x' * 200)

    def test_print_disabled_is_plain(self) -> None:
        """Testing RBToolsConsole.print with color disabled writes plain text
        """
        console, stdout_buffer, _stderr = self._make_console()

        console.print('Hello world', style='rb.heading')

        self.assertEqual(self._read(console, stdout_buffer),
                         b'Hello world\n')

    def test_print_enabled_emits_color(self) -> None:
        """Testing RBToolsConsole.print_success with color enabled emits
        ANSI codes
        """
        console, stdout_buffer, _stderr = \
            self._make_console(color_mode='always')

        console.print_success('Done.')

        output = self._read(console, stdout_buffer)
        self.assertIn(b'\x1b[', output)
        self.assertIn(b'Done.', output)

    def test_suppress(self) -> None:
        """Testing RBToolsConsole.suppress discards all output"""
        console, stdout_buffer, stderr_buffer = self._make_console()

        console.suppress()
        console.print('should not appear')
        console.print_success('nor this')
        console.print_warning('nor this warning')

        self.assertEqual(self._read(console, stdout_buffer), b'')
        self.assertEqual(self._read(console, stderr_buffer, err=True), b'')

    def test_print_json(self) -> None:
        """Testing RBToolsConsole.print_json renders JSON to stdout"""
        console, stdout_buffer, _stderr = self._make_console()

        console.print_json({'b': 2, 'a': 1})

        self.assertEqual(
            self._read(console, stdout_buffer),
            b'{\n    "a": 1,\n    "b": 2\n}\n')

    def test_print_json_lifts_suppression(self) -> None:
        """Testing RBToolsConsole.print_json emits after suppress"""
        console, stdout_buffer, _stderr = self._make_console()

        console.suppress()
        console.print('should not appear')
        console.print_json({'a': 1})

        self.assertEqual(
            self._read(console, stdout_buffer),
            b'{\n    "a": 1\n}\n')

    def test_track_disabled_returns_iterable(self) -> None:
        """Testing RBToolsConsole.track with color disabled returns the
        iterable unchanged
        """
        console, _stdout, _stderr = self._make_console()

        items = [1, 2, 3]
        self.assertIs(console.track(items, 'Working'), items)

    def test_track_enabled_yields_all_items(self) -> None:
        """Testing RBToolsConsole.track with color enabled yields all items"""
        console, _, _ = self._make_console(color_mode='always')

        self.assertEqual(list(console.track([1, 2, 3], 'Working')), [1, 2, 3])

    def test_progress_bar_disabled(self) -> None:
        """Testing RBToolsConsole.progress_bar with color disabled yields a
        no-op controller
        """
        console, stdout_buffer, _stderr = self._make_console()

        with console.progress_bar('Downloading', total=10) as bar:
            bar.advance(5)
            bar.update('Still downloading')

        self.assertEqual(self._read(console, stdout_buffer), b'')

    def test_progress_bar_with_multiple_steps(self) -> None:
        """Testing RBToolsConsole.progress_bar with multiple steps shows a
        bar
        """
        console, stdout_buffer, _stderr = \
            self._make_console(color_mode='always')

        with console.progress_bar('Downloading', total=10) as bar:
            bar.advance(5)

        output = self._read(console, stdout_buffer)

        self.assertIn('━'.encode('utf-8'), output)
        self.assertIn(b'5/10', output)

    def test_progress_bar_with_single_step(self) -> None:
        """Testing RBToolsConsole.progress_bar with a single step shows only
        a spinner
        """
        console, stdout_buffer, _stderr = \
            self._make_console(color_mode='always')

        with console.progress_bar('Downloading', total=1) as bar:
            bar.advance()

        output = self._read(console, stdout_buffer)

        self.assertIn(b'Downloading', output)
        self.assertNotIn('━'.encode('utf-8'), output)
        self.assertNotIn(b'1/1', output)

    def test_progress_bar_is_transient(self) -> None:
        """Testing RBToolsConsole.progress_bar erases the display when done"""
        console, stdout_buffer, _stderr = \
            self._make_console(color_mode='always')

        with console.progress_bar('Downloading', total=10) as bar:
            bar.advance(5)

        console.print('Done.')

        output = self._read(console, stdout_buffer)

        # The display is erased by moving up a line and clearing it, just
        # before the next thing is written.
        self.assertIn(b'\x1b[1A\x1b[2KDone.\n', output)

    def test_progress_bar_non_transient(self) -> None:
        """Testing RBToolsConsole.progress_bar with transient=False leaves the
        display on screen
        """
        console, stdout_buffer, _stderr = \
            self._make_console(color_mode='always')

        with console.progress_bar('Downloading', total=10,
                                  transient=False) as bar:
            bar.advance(10)

        console.print('Done.')

        output = self._read(console, stdout_buffer)

        self.assertNotIn(b'\x1b[1A\x1b[2KDone.\n', output)
        self.assertIn(b'10/10', output)

    def test_progress_bar_nested(self) -> None:
        """Testing RBToolsConsole.progress_bar nested inside another shares
        the display
        """
        console, stdout_buffer, _stderr = \
            self._make_console(color_mode='always')

        with console.progress_bar('Posting') as outer:
            live = console._live

            with console.progress_bar('validating', total=3) as inner:
                # The inner block takes over the same display, rather than
                # starting a new one.
                self.assertIs(console._live, live)
                inner.advance()

            outer.advance()

        output = self._read(console, stdout_buffer)

        self.assertIn(b'Posting', output)
        self.assertIn(b'Posting: validating', output)
        self.assertIn(b'/3', output)

        # Only the outermost block writes the cursor show/hide sequences that
        # bracket a live display.
        self.assertEqual(output.count(b'\x1b[?25l'), 1)

    def test_progress_bar_nested_update(self) -> None:
        """Testing RBToolsConsole.progress_bar nested inside another keeps
        the outer description when updated
        """
        console, _stdout, _stderr = self._make_console(color_mode='always')

        with (console.progress_bar('Posting'),
              console.progress_bar('uploading') as inner):
            inner.update('publishing')

            progress = console._progress
            assert progress is not None

            self.assertEqual(
                [task.description for task in progress.tasks],
                ['Posting', 'Posting: publishing'])

    def test_pause_with_no_live_display(self) -> None:
        """Testing RBToolsConsole.pause with no active live display"""
        console, stdout_buffer, _ = self._make_console()

        with console.pause():
            console.print('Hello world')

        self.assertEqual(self._read(console, stdout_buffer),
                         b'Hello world\n')

    def test_pause_with_progress_bar(self) -> None:
        """Testing RBToolsConsole.pause stops and restarts a progress bar"""
        console, _, _ = self._make_console(color_mode='always')

        with console.progress_bar('Downloading', total=10):
            live = console._live
            assert live is not None

            self.assertTrue(live.is_started)

            with console.pause():
                self.assertFalse(live.is_started)

            self.assertTrue(live.is_started)

    def test_log_handler_pauses_progress_bar(self) -> None:
        """Testing the Rich log handler pauses an active progress bar"""
        console, _, _ = self._make_console(color_mode='always')
        handler = console.get_rich_log_handler()
        record = logging.LogRecord(name='test', level=logging.INFO,
                                   pathname=__file__, lineno=1,
                                   msg='Please log in.', args=(),
                                   exc_info=None)

        with console.progress_bar('Downloading', total=10):
            live = console._live
            assert live is not None

            self.spy_on(live.stop)
            handler.emit(record)

            self.assertSpyCalled(live.stop)
            self.assertTrue(live.is_started)

    def _make_console(
        self,
        color_mode: ColorMode = 'never',
    ) -> tuple[RBToolsConsole, io.BytesIO, io.BytesIO]:
        """Return a console writing to in-memory streams.

        Args:
            color_mode (str, optional):
                The color mode to use.

        Returns:
            tuple:
            A 3-tuple of the console, the stdout buffer, and the stderr
            buffer.
        """
        stdout_buffer = io.BytesIO()
        stderr_buffer = io.BytesIO()

        console = RBToolsConsole(
            stdout=io.TextIOWrapper(stdout_buffer, encoding='utf-8'),
            stderr=io.TextIOWrapper(stderr_buffer, encoding='utf-8'),
            color_mode=color_mode)

        return console, stdout_buffer, stderr_buffer

    def _read(
        self,
        console: RBToolsConsole,
        buffer: io.BytesIO,
        *,
        err: bool = False,
    ) -> bytes:
        """Flush the console and return the captured bytes.

        Args:
            console (RBToolsConsole):
                The console to flush.

            buffer (io.BytesIO):
                The buffer to read.

            err (bool, optional):
                Whether to flush the stderr console.

        Returns:
            bytes:
            The captured output.
        """
        if err:
            console.stderr_console.file.flush()
        else:
            console.stdout_console.file.flush()

        return buffer.getvalue()
