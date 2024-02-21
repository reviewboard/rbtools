"""Unit tests for rbtools.utils.mimetypes."""

from __future__ import annotations

from rbtools.testing import TestCase
from rbtools.utils.mimetypes import match_mimetype, parse_mimetype


class MIMETypeTests(TestCase):
    """Unit tests for rbtools.utils.mimetypes."""

    def test_parse(self) -> None:
        """Testing parse_mimetype"""
        self.assertEqual(
            parse_mimetype('application/octet-stream'),
            {
                'type': 'application/octet-stream',
                'main_type': 'application',
                'sub_type': 'octet-stream',
                'vendor': '',
                'format': 'octet-stream',
            })

    def test_parse_with_vendor(self) -> None:
        """Testing parse_mimetype with vendor"""
        self.assertEqual(
            parse_mimetype('application/vnd.reviewboard.org.test+json'),
            {
                'type': 'application/vnd.reviewboard.org.test+json',
                'main_type': 'application',
                'sub_type': 'vnd.reviewboard.org.test+json',
                'vendor': 'vnd.reviewboard.org.test',
                'format': 'json',
            })

    def test_parse_invalid(self) -> None:
        """Testing parse_mimetype with invalid format"""
        with self.assertRaises(ValueError):
            parse_mimetype('broken')

    def test_match_mimetype(self) -> None:
        """Testing match_mimetype"""
        mimetype = parse_mimetype('application/vnd.reviewboard.org.test+json')

        self.assertAlmostEqual(
            match_mimetype(mimetype, mimetype),
            2.0)

        self.assertAlmostEqual(
            match_mimetype(
                parse_mimetype('application/json'),
                mimetype),
            1.9)

        self.assertAlmostEqual(
            match_mimetype(
                parse_mimetype('application/*'),
                mimetype),
            1.8)

        self.assertAlmostEqual(
            match_mimetype(
                parse_mimetype('*/vnd.reviewboard.org.test+json'),
                mimetype),
            1.7)

        self.assertAlmostEqual(
            match_mimetype(
                parse_mimetype('*/json'),
                mimetype),
            1.6)

        self.assertAlmostEqual(
            match_mimetype(
                parse_mimetype('*/vnd.example.com+json'),
                mimetype),
            1.6)

        self.assertAlmostEqual(
            match_mimetype(
                parse_mimetype('*/*'),
                mimetype),
            1.5)

        self.assertEqual(
            match_mimetype(
                parse_mimetype('application/octet-stream'),
                mimetype),
            0)
