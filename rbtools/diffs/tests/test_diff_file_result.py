"""Unit tests for rbtools.diffs.tools.base.diff_file_result.DiffFileResult.

Version Added:
    4.0
"""

import inspect
import io

from rbtools.testing import TestCase
from rbtools.diffs.tools.base.diff_file_result import DiffFileResult


class DiffFileResultTests(TestCase):
    """Unit tests for DiffFileResult."""

    def test_has_differences_with_text_changes(self):
        """Testing DiffFileResult.has_differences with text diff and
        changes
        """
        diff_result = DiffFileResult(orig_path='orig-file',
                                     modified_path='modified-file',
                                     diff=io.BytesIO(b'...'),
                                     has_text_differences=True)

        self.assertTrue(diff_result.has_differences)

    def test_has_differences_with_text_no_changes(self):
        """Testing DiffFileResult.has_differences with text diff and no
        changes
        """
        diff_result = DiffFileResult(orig_path='orig-file',
                                     modified_path='modified-file',
                                     diff=io.BytesIO(b''),
                                     has_text_differences=False)

        self.assertFalse(diff_result.has_differences)

    def test_has_differences_with_binary(self):
        """Testing DiffFileResult.has_differences with binary diff"""
        diff_result = DiffFileResult(orig_path='orig-file',
                                     modified_path='modified-file',
                                     diff=io.BytesIO(b''),
                                     is_binary=True,
                                     has_text_differences=False)

        self.assertTrue(diff_result.has_differences)

    def test_orig_file_header(self):
        """Testing DiffFileResult.orig_file_header"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\n'
                b'+++ modified-file\txxx\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.orig_file_header,
                         b'--- orig-file\txxx\n')
        self.assertEqual(diff_result.diff.tell(), 18)
        self.assertEqual(diff_result._line_offset_cache, [(0, 18)])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(diff_result.orig_file_header,
                         b'--- orig-file\txxx\n')
        self.assertEqual(diff_result.diff.tell(), 18)
        self.assertEqual(diff_result._line_offset_cache, [(0, 18)])

    def test_orig_file_header_with_crlf(self):
        """Testing DiffFileResult.orig_file_header with CRLF"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified=file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\n'
                b'+++ modified-file\txxx\r\n'
                b'@@ -1 +1 @@\r\n'
                b'- foo\r\n'
                b'+ bar\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.orig_file_header,
                         b'--- orig-file\txxx\r\n')
        self.assertEqual(diff_result.diff.tell(), 19)
        self.assertEqual(diff_result._line_offset_cache, [(0, 19)])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(diff_result.orig_file_header,
                         b'--- orig-file\txxx\r\n')
        self.assertEqual(diff_result.diff.tell(), 19)
        self.assertEqual(diff_result._line_offset_cache, [(0, 19)])

    def test_orig_file_header_with_crcrlf(self):
        """Testing DiffFileResult.orig_file_header with CRCRLF"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\r\n'
                b'+++ modified-file\txxx\r\r\n'
                b'@@ -1 +1 @@\r\n'
                b'- foo\r\r\n'
                b'+ bar\r\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.orig_file_header,
                         b'--- orig-file\txxx\r\r\n')
        self.assertEqual(diff_result.diff.tell(), 20)
        self.assertEqual(diff_result._line_offset_cache, [(0, 20)])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(diff_result.orig_file_header,
                         b'--- orig-file\txxx\r\r\n')
        self.assertEqual(diff_result.diff.tell(), 20)
        self.assertEqual(diff_result._line_offset_cache, [(0, 20)])

    def test_orig_file_header_with_no_text_diff(self):
        """Testing DiffFileResult.orig_file_header with no text differences"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            has_text_differences=False,
            is_binary=True,
            diff=io.BytesIO(
                b'Binary files orig-file and modified-file differ\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.orig_file_header, b'')
        self.assertEqual(diff_result.diff.tell(), 0)
        self.assertEqual(diff_result._line_offset_cache, [])

    def test_orig_file_header_with_no_header(self):
        """Testing DiffFileResult.orig_file_header with no '---' header"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            has_text_differences=True,
            diff=io.BytesIO(
                b'Something else\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.orig_file_header, b'')
        self.assertEqual(diff_result.diff.tell(), 15)
        self.assertEqual(diff_result._line_offset_cache, [(0, 15)])

    def test_orig_file_header_with_out_of_bounds(self):
        """Testing DiffFileResult.orig_file_header with out-of-bounds line"""
        diff_result = DiffFileResult(orig_path='orig-file',
                                     modified_path='modified-file',
                                     diff=io.BytesIO())

        self.assertEqual(diff_result.orig_file_header, b'')
        self.assertEqual(diff_result.diff.tell(), 0)

    def test_parsed_orig_file_header_with_tab(self):
        """Testing DiffFileResult.parsed_orig_file_header with tab separator"""
        diff_result = DiffFileResult(
            orig_path='orig file',
            modified_path='modified file',
            diff=io.BytesIO(
                b'--- orig file\txxx yyy zzz\n'
                b'+++ modified file\txxx yyy zzz\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.parsed_orig_file_header,
            {
                'extra': b'xxx yyy zzz',
                'marker': b'---',
                'path': b'orig file',
            })

        self.assertEqual(diff_result.diff.tell(), 26)
        self.assertEqual(diff_result._line_offset_cache, [(0, 26)])

    def test_parsed_orig_file_header_with_spaces(self):
        """Testing DiffFileResult.parsed_orig_file_header with two-space
        separator
        """
        diff_result = DiffFileResult(
            orig_path='orig file',
            modified_path='modified file',
            diff=io.BytesIO(
                b'--- orig file  xxx yyy zzz\n'
                b'+++ modified file  xxx yyy zzz\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.parsed_orig_file_header,
            {
                'extra': b'xxx yyy zzz',
                'marker': b'---',
                'path': b'orig file',
            })

        self.assertEqual(diff_result.diff.tell(), 27)
        self.assertEqual(diff_result._line_offset_cache, [(0, 27)])

    def test_parsed_orig_file_header_with_no_separator(self):
        """Testing DiffFileResult.parsed_orig_file_header with no
        distinguishable separator
        """
        diff_result = DiffFileResult(
            orig_path='orig file',
            modified_path='modified file',
            diff=io.BytesIO(
                b'--- orig file xxx yyy zzz\n'
                b'+++ modified file xxx yyy zzz\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.parsed_orig_file_header,
            {
                'extra': b'',
                'marker': b'---',
                'path': b'orig file xxx yyy zzz',
            })

        self.assertEqual(diff_result.diff.tell(), 26)
        self.assertEqual(diff_result._line_offset_cache, [(0, 26)])

    def test_modified_file_header(self):
        """Testing DiffFileResult.modified_file_header"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\n'
                b'+++ modified-file\txxx\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\n')
        self.assertEqual(diff_result.diff.tell(), 40)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\n')
        self.assertEqual(diff_result.diff.tell(), 40)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
        ])

    def test_modified_file_header_with_crlf(self):
        """Testing DiffFileResult.modified_file_header with CRLF"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\n'
                b'+++ modified-file\txxx\r\n'
                b'@@ -1 +1 @@\r\n'
                b'- foo\r\n'
                b'+ bar\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\r\n')
        self.assertEqual(diff_result.diff.tell(), 42)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 19),
            (19, 23),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\r\n')
        self.assertEqual(diff_result.diff.tell(), 42)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 19),
            (19, 23),
        ])

    def test_modified_file_header_with_crcrlf(self):
        """Testing DiffFileResult.modified_file_header with CRCRLF"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\r\n'
                b'+++ modified-file\txxx\r\r\n'
                b'@@ -1 +1 @@\r\n'
                b'- foo\r\r\n'
                b'+ bar\r\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\r\r\n')
        self.assertEqual(diff_result.diff.tell(), 44)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 20),
            (20, 24),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\r\r\n')
        self.assertEqual(diff_result.diff.tell(), 44)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 20),
            (20, 24),
        ])

    def test_modified_file_header_with_no_text_diff(self):
        """Testing DiffFileResult.modified_file_header with no text
        differences
        """
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            has_text_differences=False,
            is_binary=True,
            diff=io.BytesIO(
                b'Binary files orig-file and modified-file differ\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.modified_file_header, b'')
        self.assertEqual(diff_result.diff.tell(), 0)
        self.assertEqual(diff_result._line_offset_cache, [])

    def test_modified_file_header_with_no_header(self):
        """Testing DiffFileResult.modified_file_header with no '+++' header"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            has_text_differences=True,
            diff=io.BytesIO(
                b'--- file1\txxx\n'
                b'Something else\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(diff_result.modified_file_header, b'')
        self.assertEqual(diff_result.diff.tell(), 29)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 14),
            (14, 15),
        ])

    def test_modified_file_header_with_out_of_bounds(self):
        """Testing DiffFileResult.modified_file_header with out-of-bounds
        line
        """
        diff_result = DiffFileResult(orig_path='orig-file',
                                     modified_path='modified-file',
                                     diff=io.BytesIO())

        self.assertEqual(diff_result.modified_file_header, b'')
        self.assertEqual(diff_result.diff.tell(), 0)

    def test_modified_file_header_after_orig_header(self):
        """Testing DiffFileResult.modified_file_header after orig_file_header
        """
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\n'
                b'+++ modified-file\txxx\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        # Start by fetching the first header.
        self.assertEqual(diff_result.orig_file_header,
                         b'--- orig-file\txxx\n')

        self.assertEqual(diff_result.diff.tell(), 18)

        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\n')
        self.assertEqual(diff_result.diff.tell(), 40)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\n')
        self.assertEqual(diff_result.diff.tell(), 40)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
        ])

    def test_parsed_modified_file_header_with_tab(self):
        """Testing DiffFileResult.parsed_modified_file_header with tab
        separator
        """
        diff_result = DiffFileResult(
            orig_path='orig file',
            modified_path='modified file',
            diff=io.BytesIO(
                b'--- orig file\txxx yyy zzz\n'
                b'+++ modified file\txxx yyy zzz\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.parsed_modified_file_header,
            {
                'extra': b'xxx yyy zzz',
                'marker': b'+++',
                'path': b'modified file',
            })

        self.assertEqual(diff_result.diff.tell(), 56)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 26),
            (26, 30),
        ])

    def test_parsed_modified_file_header_with_spaces(self):
        """Testing DiffFileResult.parsed_modified_file_header with two-space
        separator
        """
        diff_result = DiffFileResult(
            orig_path='orig file',
            modified_path='modified file',
            diff=io.BytesIO(
                b'--- orig file  xxx yyy zzz\n'
                b'+++ modified file  xxx yyy zzz\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.parsed_modified_file_header,
            {
                'extra': b'xxx yyy zzz',
                'marker': b'+++',
                'path': b'modified file',
            })

        self.assertEqual(diff_result.diff.tell(), 58)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 27),
            (27, 31),
        ])

    def test_parsed_modified_file_header_with_no_separator(self):
        """Testing DiffFileResult.parsed_modified_file_header with no
        distinguishable separator
        """
        diff_result = DiffFileResult(
            orig_path='orig file',
            modified_path='modified file',
            diff=io.BytesIO(
                b'--- orig file xxx yyy zzz\n'
                b'+++ modified file xxx yyy zzz\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.parsed_modified_file_header,
            {
                'extra': b'',
                'marker': b'+++',
                'path': b'modified file xxx yyy zzz',
            })

        self.assertEqual(diff_result.diff.tell(), 56)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 26),
            (26, 30),
        ])

    def test_hunks(self):
        """Testing DiffFileResult.hunks"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\n'
                b'+++ modified-file\txxx\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.hunks,
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            diff_result.hunks,
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

    def test_hunks_with_crlf(self):
        """Testing DiffFileResult.hunks with CRLF"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\n'
                b'+++ modified-file\txxx\r\n'
                b'@@ -1 +1 @@\r\n'
                b'- foo\r\n'
                b'+ bar\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.hunks,
            b'@@ -1 +1 @@\r\n'
            b'- foo\r\n'
            b'+ bar\r\n')
        self.assertEqual(diff_result.diff.tell(), 69)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 19),
            (19, 23),
            (42, 13),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            diff_result.hunks,
            b'@@ -1 +1 @@\r\n'
            b'- foo\r\n'
            b'+ bar\r\n')
        self.assertEqual(diff_result.diff.tell(), 69)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 19),
            (19, 23),
            (42, 13),
        ])

    def test_hunks_with_crcrlf(self):
        """Testing DiffFileResult.hunks with CRCRLF"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\r\n'
                b'+++ modified-file\txxx\r\r\n'
                b'@@ -1 +1 @@\r\r\n'
                b'- foo\r\r\n'
                b'+ bar\r\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.hunks,
            b'@@ -1 +1 @@\r\r\n'
            b'- foo\r\r\n'
            b'+ bar\r\r\n')
        self.assertEqual(diff_result.diff.tell(), 74)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 20),
            (20, 24),
            (44, 14),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            diff_result.hunks,
            b'@@ -1 +1 @@\r\r\n'
            b'- foo\r\r\n'
            b'+ bar\r\r\n')
        self.assertEqual(diff_result.diff.tell(), 74)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 20),
            (20, 24),
            (44, 14),
        ])

    def test_hunks_with_no_text_diff(self):
        """Testing DiffFileResult.hunks with no text diff"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            has_text_differences=False,
            is_binary=True,
            diff=io.BytesIO(
                b'Binary files orig-file and modified-file differ\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            diff_result.hunks,
            b'Binary files orig-file and modified-file differ\n')
        self.assertEqual(diff_result.diff.tell(), 48)
        self.assertEqual(diff_result._line_offset_cache, [])

    def test_hunks_with_out_of_bounds(self):
        """Testing DiffFileResult.hunks with out-of-bounds
        line
        """
        diff_result = DiffFileResult(orig_path='orig-file',
                                     modified_path='modified-file',
                                     diff=io.BytesIO())

        self.assertEqual(diff_result.hunks, b'')
        self.assertEqual(diff_result.diff.tell(), 0)

    def test_hunks_after_orig_header(self):
        """Testing DiffFileResult.hunks after orig_file_header
        """
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\n'
                b'+++ modified-file\txxx\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        # Start by fetching the first header.
        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\n')

        self.assertEqual(diff_result.diff.tell(), 40)

        self.assertEqual(
            diff_result.hunks,
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            diff_result.hunks,
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

    def test_iter_hunk_lines(self):
        """Testing DiffFileResult.iter_hunk_lines"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\n'
                b'+++ modified-file\txxx\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)
        lines = diff_result.iter_hunk_lines()

        self.assertTrue(inspect.isgenerator(lines))
        self.assertEqual(
            list(lines),
            [
                b'@@ -1 +1 @@',
                b'- foo',
                b'+ bar',
            ])
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            list(diff_result.iter_hunk_lines()),
            [
                b'@@ -1 +1 @@',
                b'- foo',
                b'+ bar',
            ])
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

    def test_iter_hunk_lines_with_keep_newlines(self):
        """Testing DiffFileResult.iter_hunk_lines with keep_newlines=True"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\n'
                b'+++ modified-file\txxx\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)
        lines = diff_result.iter_hunk_lines(keep_newlines=True)

        self.assertTrue(inspect.isgenerator(lines))
        self.assertEqual(
            list(lines),
            [
                b'@@ -1 +1 @@\n',
                b'- foo\n',
                b'+ bar\n',
            ])
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            list(diff_result.iter_hunk_lines(keep_newlines=True)),
            [
                b'@@ -1 +1 @@\n',
                b'- foo\n',
                b'+ bar\n',
            ])
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

    def test_iter_hunk_lines_with_crlf(self):
        """Testing DiffFileResult.iter_hunk_lines with CRLF"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\n'
                b'+++ modified-file\txxx\r\n'
                b'@@ -1 +1 @@\r\n'
                b'- foo\r\n'
                b'+ bar\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            list(diff_result.iter_hunk_lines()),
            [
                b'@@ -1 +1 @@',
                b'- foo',
                b'+ bar',
            ])
        self.assertEqual(diff_result.diff.tell(), 69)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 19),
            (19, 23),
            (42, 13),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            list(diff_result.iter_hunk_lines()),
            [
                b'@@ -1 +1 @@',
                b'- foo',
                b'+ bar',
            ])
        self.assertEqual(diff_result.diff.tell(), 69)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 19),
            (19, 23),
            (42, 13),
        ])

    def test_iter_hunk_lines_with_crlf_and_keep_newlines(self):
        """Testing DiffFileResult.iter_hunk_lines with CRLF and
        keep_newlines=True
        """
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\n'
                b'+++ modified-file\txxx\r\n'
                b'@@ -1 +1 @@\r\n'
                b'- foo\r\n'
                b'+ bar\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            list(diff_result.iter_hunk_lines(keep_newlines=True)),
            [
                b'@@ -1 +1 @@\r\n',
                b'- foo\r\n',
                b'+ bar\r\n',
            ])
        self.assertEqual(diff_result.diff.tell(), 69)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 19),
            (19, 23),
            (42, 13),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            list(diff_result.iter_hunk_lines(keep_newlines=True)),
            [
                b'@@ -1 +1 @@\r\n',
                b'- foo\r\n',
                b'+ bar\r\n',
            ])
        self.assertEqual(diff_result.diff.tell(), 69)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 19),
            (19, 23),
            (42, 13),
        ])

    def test_iter_hunk_lines_with_crcrlf(self):
        """Testing DiffFileResult.iter_hunk_lines with CRCRLF"""
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\r\n'
                b'+++ modified-file\txxx\r\r\n'
                b'@@ -1 +1 @@\r\r\n'
                b'- foo\r\r\n'
                b'+ bar\r\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            list(diff_result.iter_hunk_lines()),
            [
                b'@@ -1 +1 @@',
                b'- foo',
                b'+ bar',
            ])
        self.assertEqual(diff_result.diff.tell(), 74)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 20),
            (20, 24),
            (44, 14),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            list(diff_result.iter_hunk_lines()),
            [
                b'@@ -1 +1 @@',
                b'- foo',
                b'+ bar',
            ])
        self.assertEqual(diff_result.diff.tell(), 74)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 20),
            (20, 24),
            (44, 14),
        ])

    def test_iter_hunk_lines_with_crcrlf_and_keep_newlines(self):
        """Testing DiffFileResult.iter_hunk_lines with CRCRLF and
        keep_newlines=True
        """
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\r\r\n'
                b'+++ modified-file\txxx\r\r\n'
                b'@@ -1 +1 @@\r\r\n'
                b'- foo\r\r\n'
                b'+ bar\r\r\n'
            ))

        self.assertEqual(diff_result.diff.tell(), 0)

        self.assertEqual(
            list(diff_result.iter_hunk_lines(keep_newlines=True)),
            [
                b'@@ -1 +1 @@\r\n',
                b'- foo\r\n',
                b'+ bar\r\n',
            ])
        self.assertEqual(diff_result.diff.tell(), 74)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 20),
            (20, 24),
            (44, 14),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            list(diff_result.iter_hunk_lines(keep_newlines=True)),
            [
                b'@@ -1 +1 @@\r\n',
                b'- foo\r\n',
                b'+ bar\r\n',
            ])
        self.assertEqual(diff_result.diff.tell(), 74)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 20),
            (20, 24),
            (44, 14),
        ])

    def test_iter_hunk_lines_with_out_of_bounds(self):
        """Testing DiffFileResult.iter_hunk_lines with out-of-bounds
        line
        """
        diff_result = DiffFileResult(orig_path='orig-file',
                                     modified_path='modified-file',
                                     diff=io.BytesIO())

        self.assertEqual(list(diff_result.iter_hunk_lines()), [])
        self.assertEqual(diff_result.diff.tell(), 0)

    def test_iter_hunk_lines_after_orig_header(self):
        """Testing DiffFileResult.iter_hunk_lines after orig_file_header
        """
        diff_result = DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\txxx\n'
                b'+++ modified-file\txxx\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            ))

        # Start by fetching the first header.
        self.assertEqual(diff_result.modified_file_header,
                         b'+++ modified-file\txxx\n')

        self.assertEqual(diff_result.diff.tell(), 40)

        self.assertEqual(
            list(diff_result.iter_hunk_lines()),
            [
                b'@@ -1 +1 @@',
                b'- foo',
                b'+ bar',
            ])
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])

        # Since we're seeking, reading, and caching, check again.
        self.assertEqual(
            list(diff_result.iter_hunk_lines()),
            [
                b'@@ -1 +1 @@',
                b'- foo',
                b'+ bar',
            ])
        self.assertEqual(diff_result.diff.tell(), 64)
        self.assertEqual(diff_result._line_offset_cache, [
            (0, 18),
            (18, 22),
            (40, 12),
        ])
