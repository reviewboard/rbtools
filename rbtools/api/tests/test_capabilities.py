"""Unit tests for rbtools.api.capabilities."""

from __future__ import annotations

from rbtools.api.capabilities import Capabilities
from rbtools.testing import TestCase


class CapabilitiesTests(TestCase):
    """Tests for rbtools.api.capabilities.Capabilities"""

    def test_has_capability(self) -> None:
        """Testing Capabilities.has_capability with supported capability"""
        caps = Capabilities({
            'foo': {
                'bar': {
                    'value': True,
                },
            },
        })

        self.assertTrue(caps.has_capability('foo', 'bar', 'value'))

    def test_has_capability_with_unknown_capability(self) -> None:
        """Testing Capabilities.has_capability with unknown capability"""
        caps = Capabilities({})
        self.assertFalse(caps.has_capability('mycap'))

    def test_has_capability_with_partial_path(self) -> None:
        """Testing Capabilities.has_capability with partial capability path"""
        caps = Capabilities({
            'foo': {
                'bar': {
                    'value': True,
                },
            },
        })

        self.assertFalse(caps.has_capability('foo', 'bar'))

    def test_get_capability(self) -> None:
        """Testing Capabilities.get_capability"""
        caps = Capabilities({
            'foo': {
                'bar': {
                    'value': True,
                },
                'baz': 123,
            },
        })

        self.assertEqual(caps.get_capability('foo', 'bar', 'value'), True)
        self.assertEqual(caps.get_capability('foo', 'bar'), {'value': True})
        self.assertEqual(caps.get_capability('foo', 'baz'), 123)

    def test_get_capability_with_unknown_capability(self) -> None:
        """Testing Capabilities.get_capability with unknown capability"""
        caps = Capabilities({})
        self.assertIsNone(caps.get_capability('mycap'))
