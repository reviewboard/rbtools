"""Unit tests for rbtools.ui.console.

Version Added:
    7.0
"""

from __future__ import annotations

import io
import logging
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
            self.assertFalse(live.transient)

            with console.pause():
                self.assertTrue(live.transient)
                self.assertFalse(live.is_started)

            self.assertTrue(live.is_started)

            # The display must go back to being non-transient, so that it's
            # still shown once the work completes.
            self.assertFalse(live.transient)

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
