"""Unit tests for rbtools.commands.base.output.

Version Added:
    5.0
"""

from __future__ import annotations

import io

from rbtools.commands.base.output import JSONOutput
from rbtools.testing import TestCase


class JSONOutputTests(TestCase):
    """Unit tests for JSONOutput.

    Version Added:
        5.0
    """

    def test_add(self) -> None:
        """Testing JSONOutput.add"""
        output = JSONOutput(io.StringIO())
        output.add('key1', 'value')
        output.add('key2', 123)
        output.add('key3', {
            'subkey': 'value!',
        })

        self.assertEqual(output._output, {
            'key1': 'value',
            'key2': 123,
            'key3': {
                'subkey': 'value!',
            },
        })

    def test_append(self) -> None:
        """Testing JSONOutput.append"""
        output = JSONOutput(io.StringIO())
        output.add('key1', [])
        output.append('key1', 1)
        output.append('key1', True)
        output.append('key1', 'XYZ')

        self.assertEqual(output._output, {
            'key1': [1, True, 'XYZ'],
        })

    def test_append_with_invalid_key(self) -> None:
        """Testing JSONOutput.append with invalid key"""
        output = JSONOutput(io.StringIO())

        with self.assertRaisesMessage(KeyError, 'key1'):
            output.append('key1', 1)

        self.assertEqual(output._output, {})

    def test_append_with_non_list(self) -> None:
        """Testing JSONOutput.append with non-list"""
        output = JSONOutput(io.StringIO())
        output.add('key1', 'str')

        message = (
            'Expected "key1" to be a list, but it is a <class \'str\'>.'
        )

        with self.assertRaisesMessage(TypeError, message):
            output.append('key1', 1)

        self.assertEqual(output._output, {
            'key1': 'str',
        })

    def test_add_error(self) -> None:
        """Testing JSONOutput.add_error"""
        output = JSONOutput(io.StringIO())
        output.add_error('Error 1')
        output.add_error('Error 2')

        self.assertEqual(output._output, {
            'errors': ['Error 1', 'Error 2'],
        })

    def test_add_warning(self) -> None:
        """Testing JSONOutput.add_warning"""
        output = JSONOutput(io.StringIO())
        output.add_warning('Warning 1')
        output.add_warning('Warning 2')

        self.assertEqual(output._output, {
            'warnings': ['Warning 1', 'Warning 2'],
        })

    def test_print_to_stream(self) -> None:
        """Testing JSONOutput.print_to_stream"""
        buf = io.StringIO()
        output = JSONOutput(buf)

        output.add('key1', 'value1')
        output.add('key3', [])
        output.add('key2', {
            'a': 'b',
            'c': 'd',
        })
        output.append('key3', 1)
        output.append('key3', 2)
        output.append('key3', 3)
        output.add_warning('Warning!')
        output.add_error('Error!')

        output.print_to_stream()

        value = buf.getvalue()
        buf.close()

        self.assertEqual(
            value,
            '{\n'
            '    "errors": [\n'
            '        "Error!"\n'
            '    ],\n'
            '    "key1": "value1",\n'
            '    "key2": {\n'
            '        "a": "b",\n'
            '        "c": "d"\n'
            '    },\n'
            '    "key3": [\n'
            '        1,\n'
            '        2,\n'
            '        3\n'
            '    ],\n'
            '    "warnings": [\n'
            '        "Warning!"\n'
            '    ]\n'
            '}\n')
