"""Unit tests for rbtools.diffs.tools.backends.gnu.AppleDiffTool.

Version Added:
    4.0
"""

import os
import time

import kgb

from rbtools.diffs.tools.base import DiffFileResult
from rbtools.diffs.tools.backends.apple import AppleDiffTool
from rbtools.testing import TestCase
from rbtools.utils.filesystem import (_iter_exes_in_path_cache,
                                      iter_exes_in_path)
from rbtools.utils.process import RunProcessError, run_process_exec


class AppleDiffToolTests(kgb.SpyAgency, TestCase):
    """Unit tests for rbtools.diffs.tools.backends.gnu.AppleDiffTool."""

    def tearDown(self):
        super().tearDown()

        _iter_exes_in_path_cache.clear()

    def test_get_install_instructions(self):
        """Testing AppleDiffTool.get_install_instructions"""
        self.assertEqual(AppleDiffTool.get_install_instructions(), '')

    def test_check_available_with_found(self):
        """Testing AppleDiffTool.check_available with diff found"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': (['/path1/bin/diff', '--version'],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'diff (GNU diffutils) 2.8.1\n',
                        b'',
                    )),
                },
                {
                    'args': (['/path2/bin/diff', '--version'],),
                    'op': kgb.SpyOpReturn((
                        1,
                        b'',
                        b'Some error.',
                    )),
                },
                {
                    'args': (['/path3/bin/diff', '--version'],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'Apple diff (based on FreeBSD diff)\n',
                        b'',
                    )),
                },
            ]))

        self.spy_on(
            iter_exes_in_path,
            op=kgb.SpyOpReturn([
                '/path1/bin/diff',
                '/path2/bin/diff',
                '/path3/bin/diff',
            ]))

        diff_tool = AppleDiffTool()
        available = diff_tool.check_available()

        self.assertTrue(available)
        self.assertEqual(diff_tool.exe_path, '/path3/bin/diff')
        self.assertEqual(diff_tool.version_info,
                         'Apple diff (based on FreeBSD diff)')

    def test_check_available_with_not_found(self):
        """Testing AppleDiffTool.check_available with diff not found"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': (['/path1/bin/diff', '--version'],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'diff (GNU diffutils) 2.8.1\n',
                        b'',
                    )),
                },
                {
                    'args': (['/path2/bin/diff', '--version'],),
                    'op': kgb.SpyOpReturn((
                        1,
                        b'',
                        b'Some error.',
                    )),
                },
            ]))

        self.spy_on(
            iter_exes_in_path,
            op=kgb.SpyOpReturn([
                '/path1/bin/diff',
                '/path2/bin/diff',
            ]))

        diff_tool = AppleDiffTool()
        available = diff_tool.check_available()

        self.assertFalse(available)
        self.assertIsNone(diff_tool.exe_path)
        self.assertIsNone(diff_tool.version_info)

    def test_run_diff_file_with_no_differences(self):
        """Testing AppleDiffTool.run_diff_file with no differences"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        '/path/to/diff', '-uN', '/path1.txt', '/path2.txt',
                    ],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'',
                        b'',
                    )),
                },
            ]))

        diff_tool = AppleDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        result = diff_tool.run_diff_file(
            orig_path='/path1.txt',
            modified_path='/path2.txt')

        self.assertIsInstance(result, DiffFileResult)
        self.assertFalse(result.is_binary)
        self.assertFalse(result.has_text_differences)
        self.assertFalse(result.has_differences)
        self.assertEqual(result.diff.read(), b'')

    def test_run_diff_file_with_text_differences(self):
        """Testing AppleDiffTool.run_diff_file with text differences"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        '/path/to/diff', '-uN', '/path1.txt', '/path2.txt',
                    ],),
                    'op': kgb.SpyOpReturn((
                        1,
                        (b'--- /path1.txt\t2022-09-25 01:02:03\n'
                         b'+++ /path2.txt\t2022-09-26 10:20:30\n'
                         b'@@ -1 +1 @@\n'
                         b'- foo\n'
                         b'+ bar\n'),
                        b'',
                    )),
                },
            ]))

        diff_tool = AppleDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        # US/Arizona does not have DST. So it'll no doubt find another
        # way to eventually bite us.
        old_tz = os.environ.get('TZ', '')
        os.environ['TZ'] = 'US/Arizona'

        try:
            time.tzset()

            result = diff_tool.run_diff_file(
                orig_path='/path1.txt',
                modified_path='/path2.txt')
        finally:
            os.environ['TZ'] = old_tz
            time.tzset()

        self.assertIsInstance(result, DiffFileResult)
        self.assertFalse(result.is_binary)
        self.assertTrue(result.has_text_differences)
        self.assertTrue(result.has_differences)
        self.assertEqual(
            result.diff.read(),
            b'--- /path1.txt\t2022-09-25 01:02:03.000000000 -0700\n'
            b'+++ /path2.txt\t2022-09-26 10:20:30.000000000 -0700\n'
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')

    def test_run_diff_file_with_binary_differences(self):
        """Testing AppleDiffTool.run_diff_file with binary differences"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        '/path/to/diff', '-uN', '/path1.bin', '/path2.bin',
                    ],),
                    'op': kgb.SpyOpReturn((
                        2,
                        b'Binary files /path1.bin and /path2.bin differ\n',
                        b'',
                    )),
                },
            ]))

        diff_tool = AppleDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        result = diff_tool.run_diff_file(
            orig_path='/path1.bin',
            modified_path='/path2.bin')

        self.assertIsInstance(result, DiffFileResult)
        self.assertTrue(result.is_binary)
        self.assertFalse(result.has_text_differences)
        self.assertTrue(result.has_differences)
        self.assertEqual(
            result.diff.read(),
            b'Binary files /path1.bin and /path2.bin differ\n')

    def test_run_diff_file_with_trouble_result(self):
        """Testing AppleDiffTool.run_diff_file with "trouble" result"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        '/path/to/diff', '-uN', '/path1.txt', '/path2.txt',
                    ],),
                    'op': kgb.SpyOpReturn((
                        2,
                        b'',
                        b'Something bad happened.\n',
                    )),
                },
            ]))

        diff_tool = AppleDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        with self.assertRaises(RunProcessError) as ctx:
            diff_tool.run_diff_file(
                orig_path='/path1.txt',
                modified_path='/path2.txt')

        e = ctx.exception
        self.assertIsInstance(e, RunProcessError)
        self.assertEqual(e.result.stderr_bytes.read(),
                         b'Something bad happened.\n')

    def test_run_diff_file_with_show_hunk_context_true(self):
        """Testing AppleDiffTool.run_diff_file with show_hunk_context=True"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        '/path/to/diff', '-uNp', '/path1.txt', '/path2.txt',
                    ],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'',
                        b'',
                    )),
                },
            ]))

        diff_tool = AppleDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        diff_tool.run_diff_file(
            orig_path='/path1.txt',
            modified_path='/path2.txt',
            show_hunk_context=True)

        self.assertSpyCalled(run_process_exec)

    def test_run_diff_file_with_treat_missing_as_empty_false(self):
        """Testing AppleDiffTool.run_diff_file with
        treat_missing_as_empty=False
        """
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        '/path/to/diff', '-u', '/path1.txt', '/path2.txt',
                    ],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'',
                        b'',
                    )),
                },
            ]))

        diff_tool = AppleDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        diff_tool.run_diff_file(
            orig_path='/path1.txt',
            modified_path='/path2.txt',
            treat_missing_as_empty=False)

        self.assertSpyCalled(run_process_exec)
