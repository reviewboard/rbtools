"""Unit tests for rbtools.api.resource."""

from __future__ import unicode_literals

import re

from rbtools.api.request import HttpRequest
from rbtools.testing import TestCase


class HttpRequestTests(TestCase):
    def setUp(self):
        self.request = HttpRequest('/')

    def test_default_values(self):
        """Testing the default values"""
        self.assertEqual(self.request.url, '/')
        self.assertEqual(self.request.method, 'GET')
        content_type, content = self.request.encode_multipart_formdata()
        self.assertTrue(content_type is None)
        self.assertTrue(content is None)

    def _get_fields_as_dict(self, ctype, content):
        """Extract the fields of a HTTP multipart request as a dictionary."""
        m = re.match('^multipart/form-data; boundary=(.*)$', ctype)
        self.assertFalse(m is None)
        boundary = b'--' + m.group(1).encode('utf-8')
        fields = [l.strip() for l in content.split(boundary)][1:-1]

        d = {}

        disposition_re = re.compile(
            b'Content-Disposition: form-data; name="(.*?)"$')

        for f in fields:
            lst = f.split(b'\r\n\r\n')
            self.assertEqual(len(lst), 2)
            k, v = lst

            m = disposition_re.match(k)
            self.assertFalse(m is None)
            d[m.group(1)] = v

        return d

    def test_post_form_data(self):
        """Testing the multipart form data generation"""
        request = HttpRequest('/', 'POST')
        request.add_field('foo', 'bar')
        request.add_field('bar', 42)
        request.add_field('err', 'must-be-deleted')
        request.add_field('name', 'somestring')
        request.del_field('err')

        ctype, content = request.encode_multipart_formdata()

        d = self._get_fields_as_dict(ctype, content)

        self.assertEqual(
            d, {b'foo': b'bar', b'bar': b'42', b'name': b'somestring'})

    def test_post_unicode_data(self):
        """Testing the encoding of multipart form data with unicode and binary
        field data
        """
        konnichiwa = '\u3053\u3093\u306b\u3061\u306f'

        request = HttpRequest('/', 'POST')
        request.add_field('foo', konnichiwa)
        request.add_field('bar', konnichiwa.encode('utf-8'))
        request.add_field('baz', b'\xff')

        ctype, content = request.encode_multipart_formdata()

        fields = self._get_fields_as_dict(ctype, content)

        self.assertTrue(b'foo' in fields)
        self.assertEqual(fields[b'foo'], konnichiwa.encode('utf-8'))
        self.assertEqual(fields[b'bar'], konnichiwa.encode('utf-8'))
        self.assertEqual(fields[b'baz'], b'\xff')
