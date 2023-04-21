"""Unit tests for rbtools.diffs.tools.backends.gnu.GNUDiffTool.

Version Added:
    4.0
"""

import platform

import kgb

from rbtools.diffs.tools.base import DiffFileResult
from rbtools.diffs.tools.backends.gnu import GNUDiffTool
from rbtools.testing import TestCase
from rbtools.utils.filesystem import (_iter_exes_in_path_cache,
                                      iter_exes_in_path)
from rbtools.utils.process import RunProcessError, run_process_exec


class GNUDiffToolTests(kgb.SpyAgency, TestCase):
    """Unit tests for rbtools.diffs.tools.backends.gnu.GNUDiffTool."""

    def tearDown(self):
        super().tearDown()

        _iter_exes_in_path_cache.clear()

    def test_get_install_instructions_on_linux(self):
        """Testing GNUDiffTool.get_install_instructions on Linux"""
        self.spy_on(platform.system,
                    op=kgb.SpyOpReturn('Linux'))

        self.assertEqual(
            GNUDiffTool.get_install_instructions(),
            'On Linux, GNU Diff can be installed using your system package '
            'manager.')

    def test_get_install_instructions_on_macos(self):
        """Testing GNUDiffTool.get_install_instructions on macOS"""
        self.spy_on(platform.system,
                    op=kgb.SpyOpReturn('Darwin'))

        self.assertEqual(GNUDiffTool.get_install_instructions(), '')

    def test_get_install_instructions_on_windows(self):
        """Testing GNUDiffTool.get_install_instructions on Windows"""
        self.spy_on(platform.system,
                    op=kgb.SpyOpReturn('Windows'))

        self.assertEqual(
            GNUDiffTool.get_install_instructions(),
            "On Windows, if you're not using our RBTools for Windows "
            "installer, you can manually download our version of diff.exe "
            "(http://downloads.reviewboard.org/ports/gnu-diffutils/) and "
            "place the bin/ directory in your system path. Alternatively, "
            "install Git for Windows (https://git-scm.com/download/win) and "
            "place it in your system path, as this version will also be "
            "compatible.")

    def test_check_available_with_found(self):
        """Testing GNUDiffTool.check_available with diff found"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': (['/path1/bin/diff', '--version'],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'Some Other Diff v1.2.3\n',
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
                        (b'diff (GNU diffutils) 2.8.1\n'
                         b'Copyright (C) 2002 Free Software Foundation, Inc.\n'
                         b'\n'
                         b'This program comes with NO WARRANTY, to the extent '
                         b'permitted by law.\n'
                         b'You may redistribute copies of this program under '
                         b'the terms of the GNU General Public License.\n'
                         b'For more information about these matters, see '
                         b'the file named COPYING.\n'
                         b'\n'
                         b'Written by Paul Eggert, Mike Haertel, David '
                         b'Hayes, Richard Stallman, and Len Tower.\n'),
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

        diff_tool = GNUDiffTool()
        available = diff_tool.check_available()

        self.assertTrue(available)
        self.assertEqual(diff_tool.exe_path, '/path3/bin/diff')
        self.assertEqual(diff_tool.version_info,
                         'diff (GNU diffutils) 2.8.1')

    def test_check_available_with_not_found(self):
        """Testing GNUDiffTool.check_available with diff not found"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': (['/path1/bin/diff', '--version'],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'Some Other Diff v1.2.3\n',
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

        diff_tool = GNUDiffTool()
        available = diff_tool.check_available()

        self.assertFalse(available)
        self.assertIsNone(diff_tool.exe_path)
        self.assertIsNone(diff_tool.version_info)

    def test_check_available_with_not_found_on_windows(self):
        """Testing GNUDiffTool.check_available with diff not found on
        Windows
        """
        self.spy_on(platform.system,
                    op=kgb.SpyOpReturn('Windows'))

        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        r'C:\Program Files\RBTools\bin\diff.exe',
                        '--version',
                    ],),
                    'op': kgb.SpyOpReturn((
                        0,
                        b'Some Other Diff v1.2.3\n',
                        b'',
                    )),
                },
                {
                    'args': ([
                        r'C:\Program Files\Git\bin\git.exe',
                        '--version',
                    ],),
                    'op': kgb.SpyOpReturn((
                        1,
                        b'',
                        b'Some error.',
                    )),
                },
                {
                    'args': ([
                        r'C:\Program Files\Unity\Editor\Data\Tools\diff.exe',
                        '--version',
                    ],),
                    'op': kgb.SpyOpReturn((
                        1,
                        b'',
                        b'Some error.',
                    )),
                },
                {
                    'args': ([
                        r'C:\Program Files\FooApp\gdiff.exe',
                        '--version',
                    ],),
                    'op': kgb.SpyOpReturn((
                        1,
                        b'',
                        b'Some error.',
                    )),
                },
                {
                    'args': ([
                        r'C:\Program Files\BarApp\gdiff.exe',
                        '--version',
                    ],),
                    'op': kgb.SpyOpReturn((
                        1,
                        b'',
                        b'Some error.',
                    )),
                },
                {
                    'args': ([
                        r'C:\Program Files\OtherApp\diff.exe',
                        '--version',
                    ],),
                    'op': kgb.SpyOpReturn((
                        1,
                        b'',
                        b'Some error.',
                    )),
                },
            ]))

        self.spy_on(
            iter_exes_in_path,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ('rbt',),
                    'op': kgb.SpyOpReturn([
                        r'C:\Program Files\RBTools\bin\rbt.cmd',
                    ]),
                },
                {
                    'args': ('git',),
                    'op': kgb.SpyOpReturn([
                        r'C:\Program Files\Git\bin\git.exe',
                    ]),
                },
                {
                    'args': ('gdiff',),
                    'op': kgb.SpyOpReturn([
                        r'C:\Program Files\FooApp\gdiff.exe',
                        r'C:\Program Files\BarApp\gdiff.exe',
                    ]),
                },
                {
                    'args': ('diff',),
                    'op': kgb.SpyOpReturn([
                        r'C:\Program Files\OtherApp\diff.exe',
                    ]),
                },
            ]))

        diff_tool = GNUDiffTool()
        available = diff_tool.check_available()

        self.assertFalse(available)
        self.assertIsNone(diff_tool.exe_path)
        self.assertIsNone(diff_tool.version_info)

    def test_run_diff_file_with_no_differences(self):
        """Testing GNUDiffTool.run_diff_file with no differences"""
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

        diff_tool = GNUDiffTool()
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
        """Testing GNUDiffTool.run_diff_file with text differences"""
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        '/path/to/diff', '-uN', '/path1.txt', '/path2.txt',
                    ],),
                    'op': kgb.SpyOpReturn((
                        1,
                        (b'--- /path1.txt\t2022-09-25 01:02:03.123456789 '
                         b'-0700\n'
                         b'+++ /path2.txt\t2022-09-26 10:20:30.987654321 '
                         b'-0700\n'
                         b'@@ -1 +1 @@\n'
                         b'- foo\n'
                         b'+ bar\n'),
                        b'',
                    )),
                },
            ]))

        diff_tool = GNUDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        result = diff_tool.run_diff_file(
            orig_path='/path1.txt',
            modified_path='/path2.txt')

        self.assertIsInstance(result, DiffFileResult)
        self.assertFalse(result.is_binary)
        self.assertTrue(result.has_text_differences)
        self.assertTrue(result.has_differences)
        self.assertEqual(
            result.diff.read(),
            b'--- /path1.txt\t2022-09-25 01:02:03.123456789 -0700\n'
            b'+++ /path2.txt\t2022-09-26 10:20:30.987654321 -0700\n'
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')

    def test_run_diff_file_with_binary_differences(self):
        """Testing GNUDiffTool.run_diff_file with binary differences"""
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

        diff_tool = GNUDiffTool()
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

    def test_run_diff_file_with_binary_differences_2(self):
        """Testing GNUDiffTool.run_diff_file with binary differences (older
        variant)
        """
        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        '/path/to/diff', '-uN', '/path1.bin', '/path2.bin',
                    ],),
                    'op': kgb.SpyOpReturn((
                        2,
                        b'Files /path1.bin and /path2.bin differ\n',
                        b'',
                    )),
                },
            ]))

        diff_tool = GNUDiffTool()
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
        """Testing GNUDiffTool.run_diff_file with "trouble" result"""
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

        diff_tool = GNUDiffTool()
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
        """Testing GNUDiffTool.run_diff_file with show_hunk_context=True"""
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

        diff_tool = GNUDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        diff_tool.run_diff_file(
            orig_path='/path1.txt',
            modified_path='/path2.txt',
            show_hunk_context=True)

        self.assertSpyCalled(run_process_exec)

    def test_run_diff_file_with_treat_missing_as_empty_false(self):
        """Testing GNUDiffTool.run_diff_file with treat_missing_as_empty=False
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

        diff_tool = GNUDiffTool()
        diff_tool.available = True
        diff_tool.exe_path = '/path/to/diff'

        diff_tool.run_diff_file(
            orig_path='/path1.txt',
            modified_path='/path2.txt',
            treat_missing_as_empty=False)

        self.assertSpyCalled(run_process_exec)
