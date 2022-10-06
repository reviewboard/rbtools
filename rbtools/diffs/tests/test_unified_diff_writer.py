"""Unit tests for rbtools.diffs.writers.UnifiedDiffWriter.

Version Added:
    4.0
"""

import io

from rbtools.diffs.tools.base import DiffFileResult
from rbtools.diffs.writers import UnifiedDiffWriter
from rbtools.testing import TestCase


class UnifiedDiffWriterTests(TestCase):
    """Unit tests for rbtools.diffs.writers.UnifiedDiffWriter."""

    def test_write_orig_file_header_with_bytes(self):
        """Testing UnifiedDiffWriter.write_orig_file_header with byte strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_orig_file_header(b'path/to/f\xc3\xadle')

        self.assertEqual(stream.getvalue(),
                         b'--- path/to/f\xc3\xadle\n')

    def test_write_orig_file_header_with_str(self):
        """Testing UnifiedDiffWriter.write_orig_file_header with Unicode
        strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_orig_file_header('path/to/fíle')

        self.assertEqual(stream.getvalue(),
                         b'--- path/to/f\xc3\xadle\n')

    def test_write_orig_file_header_with_extra_bytes(self):
        """Testing UnifiedDiffWriter.write_orig_file_header with extra= and
        byte strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_orig_file_header('path/to/fíle',
                                      b'(r\xc3\xa9vision 123)')

        self.assertEqual(stream.getvalue(),
                         b'--- path/to/f\xc3\xadle\t(r\xc3\xa9vision 123)\n')

    def test_write_orig_file_header_with_extra_str(self):
        """Testing UnifiedDiffWriter.write_orig_file_header with extra= and
        Unicode strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_orig_file_header(b'path/to/f\xc3\xadle',
                                      '(révision 123)')

        self.assertEqual(stream.getvalue(),
                         b'--- path/to/f\xc3\xadle\t(r\xc3\xa9vision 123)\n')

    def test_write_orig_file_header_with_custom_newline(self):
        """Testing UnifiedDiffWriter.write_orig_file_header with custom
        newline on writer
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream,
                                   newline=b'\r\n')
        writer.write_orig_file_header('path/to/fíle',
                                      '(révision 123)')

        self.assertEqual(stream.getvalue(),
                         b'--- path/to/f\xc3\xadle\t(r\xc3\xa9vision 123)\r\n')

    def test_write_modified_file_header_with_bytes(self):
        """Testing UnifiedDiffWriter.write_modified_file_header with byte
        strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream=stream)
        writer.write_modified_file_header(b'path/to/f\xc3\xadle')

        self.assertEqual(stream.getvalue(),
                         b'+++ path/to/f\xc3\xadle\n')

    def test_write_modified_file_header_with_str(self):
        """Testing UnifiedDiffWriter.write_modified_file_header with Unicode
        strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream=stream)
        writer.write_modified_file_header('path/to/fíle')

        self.assertEqual(stream.getvalue(),
                         b'+++ path/to/f\xc3\xadle\n')

    def test_write_modified_file_header_with_extra_bytes(self):
        """Testing UnifiedDiffWriter.write_modified_file_header with extra=
        and byte strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream=stream)
        writer.write_modified_file_header('path/to/fíle',
                                          b'(r\xc3\xa9vision 123)')

        self.assertEqual(stream.getvalue(),
                         b'+++ path/to/f\xc3\xadle\t(r\xc3\xa9vision 123)\n')

    def test_write_modified_file_header_with_extra_str(self):
        """Testing UnifiedDiffWriter.write_modified_file_header with extra=
        and Unicode strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream=stream)
        writer.write_modified_file_header(b'path/to/f\xc3\xadle',
                                          '(révision 123)')

        self.assertEqual(stream.getvalue(),
                         b'+++ path/to/f\xc3\xadle\t(r\xc3\xa9vision 123)\n')

    def test_write_modified_file_header_with_custom_newline(self):
        """Testing UnifiedDiffWriter.write_modified_file_header with custom
        newline on writer
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream,
                                   newline=b'\r\n')
        writer.write_modified_file_header('path/to/fíle',
                                          '(révision 123)')

        self.assertEqual(
            stream.getvalue(),
            b'+++ path/to/f\xc3\xadle\t(r\xc3\xa9vision 123)\r\n')

    def test_write_file_headers_with_bytes(self):
        """Testing UnifiedDiffWriter.write_file_headers with byte strings"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_file_headers(
            orig_path=b'path/to/orig-f\xc3\xadle',
            modified_path=b'path/to/modified-f\xc3\xadle')

        self.assertEqual(
            stream.getvalue(),
            b'--- path/to/orig-f\xc3\xadle\n'
            b'+++ path/to/modified-f\xc3\xadle\n')

    def test_write_file_headers_with_str(self):
        """Testing UnifiedDiffWriter.write_file_headers with Unicode strings"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_file_headers(
            orig_path='path/to/orig-fíle',
            modified_path='path/to/modified-fíle')

        self.assertEqual(
            stream.getvalue(),
            b'--- path/to/orig-f\xc3\xadle\n'
            b'+++ path/to/modified-f\xc3\xadle\n')

    def test_write_file_headers_with_extra_bytes(self):
        """Testing UnifiedDiffWriter.write_file_headers with extra= and
        byte strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_file_headers(
            orig_path=b'path/to/orig-f\xc3\xadle',
            orig_extra=b'(r\xc3\xa9vision 123)',
            modified_path=b'path/to/modified-f\xc3\xadle',
            modified_extra=b'(r\xc3\xa9vision 456)')

        self.assertEqual(
            stream.getvalue(),
            b'--- path/to/orig-f\xc3\xadle\t(r\xc3\xa9vision 123)\n'
            b'+++ path/to/modified-f\xc3\xadle\t(r\xc3\xa9vision 456)\n')

    def test_write_file_headers_with_extra_str(self):
        """Testing UnifiedDiffWriter.write_file_headers with extra= and
        Unicode strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_file_headers(
            orig_path=b'path/to/orig-f\xc3\xadle',
            orig_extra='(révision 123)',
            modified_path=b'path/to/modified-f\xc3\xadle',
            modified_extra='(révision 456)')

        self.assertEqual(
            stream.getvalue(),
            b'--- path/to/orig-f\xc3\xadle\t(r\xc3\xa9vision 123)\n'
            b'+++ path/to/modified-f\xc3\xadle\t(r\xc3\xa9vision 456)\n')

    def test_write_index_with_bytes(self):
        """Testing UnifiedDiffWriter.write_index with byte string"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_index(b'foo.txt\t(some-t\xc3\xa1g)')

        self.assertEqual(
            stream.getvalue(),
            b'Index: foo.txt\t(some-t\xc3\xa1g)\n'
            b'============================================================'
            b'=======\n')

    def test_write_index_with_str(self):
        """Testing UnifiedDiffWriter.write_index with Unicode string"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_index('foo.txt\t(some-tág)')

        self.assertEqual(
            stream.getvalue(),
            b'Index: foo.txt\t(some-t\xc3\xa1g)\n'
            b'============================================================'
            b'=======\n')

    def test_write_hunks_with_bytes(self):
        """Testing UnifiedDiffWriter.write_hunks with byte string"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_hunks(
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')

        self.assertEqual(
            stream.getvalue(),
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')

    def test_write_hunks_with_bytes_no_trailing_newline(self):
        """Testing UnifiedDiffWriter.write_hunks with byte string without a
        trailing newline
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_hunks(
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar')

        self.assertEqual(
            stream.getvalue(),
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')

    def test_write_hunks_with_bytes_empty(self):
        """Testing UnifiedDiffWriter.write_hunks with empty byte string"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_hunks(b'')

        self.assertEqual(stream.getvalue(), b'')

    def test_write_hunks_with_iterable(self):
        """Testing UnifiedDiffWriter.write_hunks with iterable"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_hunks(iter([
            b'@@ -1 +1 @@',
            b'- foo',
            b'+ bar',
        ]))

        self.assertEqual(
            stream.getvalue(),
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')

    def test_write_hunks_with_iterable_and_custom_newline(self):
        """Testing UnifiedDiffWriter.write_hunks with iterable and custom
        newline on writer
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream,
                                   newline=b'\r\n')
        writer.write_hunks(iter([
            b'@@ -1 +1 @@',
            b'- foo',
            b'+ bar',
        ]))

        self.assertEqual(
            stream.getvalue(),
            b'@@ -1 +1 @@\r\n'
            b'- foo\r\n'
            b'+ bar\r\n')

    def write_binary_files_differ_with_bytes(self):
        """Testing UnifiedDiffWriter.write_binary_files_differ with byte
        strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_binary_files_differ(
            orig_path=b'orig-f\xc3\xafle',
            modified_path=b'modified-f\xc3\xafle')

        self.assertEqual(
            stream.getvalue(),
            b'Binary files orig-f\xc3\xafle and modified-f\xc3\xafle differ\n')

    def write_binary_files_differ_with_str(self):
        """Testing UnifiedDiffWriter.write_binary_files_differ with Unicode
        strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_binary_files_differ(
            orig_path='orig-fïle',
            modified_path='modified-fïle')

        self.assertEqual(
            stream.getvalue(),
            b'Binary files orig-f\xc3\xafle and modified-f\xc3\xafle differ\n')

    def test_write_diff_file_result_headers(self):
        """Testing UnifiedDiffWriter.write_diff_file_result_headers"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_diff_file_result_headers(DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\taaa bbb ccc\n'
                b'+++ modified-file\txxx yyy zzz\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            )))

        self.assertEqual(
            stream.getvalue(),
            b'--- orig-file\taaa bbb ccc\n'
            b'+++ modified-file\txxx yyy zzz\n')

    def test_write_diff_file_result_headers_no_extra(self):
        """Testing UnifiedDiffWriter.write_diff_file_result_headers with no
        extra details
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_diff_file_result_headers(DiffFileResult(
            orig_path='orig-file',
            modified_path='modified-file',
            diff=io.BytesIO(
                b'--- orig-file\n'
                b'+++ modified-file\n'
                b'@@ -1 +1 @@\n'
                b'- foo\n'
                b'+ bar\n'
            )))

        self.assertEqual(
            stream.getvalue(),
            b'--- orig-file\n'
            b'+++ modified-file\n')

    def test_write_diff_file_result_headers_with_custom_paths_bytes(self):
        """Testing UnifiedDiffWriter.write_diff_file_result_headers with
        custom paths as byte strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_diff_file_result_headers(
            DiffFileResult(
                orig_path='orig-file',
                modified_path='modified-file',
                diff=io.BytesIO(
                    b'--- orig-file\t\xc3\xa1aa bbb ccc\n'
                    b'+++ modified-file\txxx yyy zzz\n'
                    b'@@ -1 +1 @@\n'
                    b'- foo\n'
                    b'+ bar\n'
                )),
            orig_path=b'new-orig-f\xc3\xafle',
            modified_path=b'new-modified-f\xc3\xafle')

        self.assertEqual(
            stream.getvalue(),
            b'--- new-orig-f\xc3\xafle\t\xc3\xa1aa bbb ccc\n'
            b'+++ new-modified-f\xc3\xafle\txxx yyy zzz\n')

    def test_write_diff_file_result_headers_with_custom_paths_str(self):
        """Testing UnifiedDiffWriter.write_diff_file_result_headers with
        custom paths as Unicode strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_diff_file_result_headers(
            DiffFileResult(
                orig_path='orig-file',
                modified_path='modified-file',
                diff=io.BytesIO(
                    b'--- orig-file\t\xc3\xa1aa bbb ccc\n'
                    b'+++ modified-file\txxx yyy zzz\n'
                    b'@@ -1 +1 @@\n'
                    b'- foo\n'
                    b'+ bar\n'
                )),
            orig_path='new-orig-fïle',
            modified_path='new-modified-fïle')

        self.assertEqual(
            stream.getvalue(),
            b'--- new-orig-f\xc3\xafle\t\xc3\xa1aa bbb ccc\n'
            b'+++ new-modified-f\xc3\xafle\txxx yyy zzz\n')

    def test_write_diff_file_result_headers_with_custom_extra_bytes(self):
        """Testing UnifiedDiffWriter.write_diff_file_result_headers with
        custom extra details as byte strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_diff_file_result_headers(
            DiffFileResult(
                orig_path='orig-file',
                modified_path='modified-file',
                diff=io.BytesIO(
                    b'--- orig-file\taaa bbb ccc\n'
                    b'+++ modified-file\txxx yyy zzz\n'
                    b'@@ -1 +1 @@\n'
                    b'- foo\n'
                    b'+ bar\n'
                )),
            orig_extra=b'c\xc3\xbastom 1',
            modified_extra=b'c\xc3\xbastom 2')

        self.assertEqual(
            stream.getvalue(),
            b'--- orig-file\tc\xc3\xbastom 1\n'
            b'+++ modified-file\tc\xc3\xbastom 2\n')

    def test_write_diff_file_result_headers_with_custom_extra_str(self):
        """Testing UnifiedDiffWriter.write_diff_file_result_headers with
        custom extra details as Unicode strings
        """
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_diff_file_result_headers(
            DiffFileResult(
                orig_path='orig-file',
                modified_path='modified-file',
                diff=io.BytesIO(
                    b'--- orig-file\taaa bbb ccc\n'
                    b'+++ modified-file\txxx yyy zzz\n'
                    b'@@ -1 +1 @@\n'
                    b'- foo\n'
                    b'+ bar\n'
                )),
            orig_extra='cústom 1',
            modified_extra='cústom 2')

        self.assertEqual(
            stream.getvalue(),
            b'--- orig-file\tc\xc3\xbastom 1\n'
            b'+++ modified-file\tc\xc3\xbastom 2\n')

    def test_write_diff_file_result_hunks(self):
        """Testing UnifiedDiffWriter.diff_file_result_hunks"""
        stream = io.BytesIO()
        writer = UnifiedDiffWriter(stream)
        writer.write_diff_file_result_hunks(
            DiffFileResult(
                orig_path='orig-file',
                modified_path='modified-file',
                diff=io.BytesIO(
                    b'--- orig-file\taaa bbb ccc\n'
                    b'+++ modified-file\txxx yyy zzz\n'
                    b'@@ -1 +1 @@\n'
                    b'- foo\n'
                    b'+ bar\n'
                )))

        self.assertEqual(
            stream.getvalue(),
            b'@@ -1 +1 @@\n'
            b'- foo\n'
            b'+ bar\n')
