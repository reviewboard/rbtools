"""Unit tests for rbtools.api.request.HttpRequest."""

from __future__ import unicode_literals

import six
from six.moves.urllib.parse import parse_qsl, urlparse

from kgb import SpyAgency

from rbtools.api.request import HttpRequest
from rbtools.testing import TestCase


class HttpRequestTests(SpyAgency, TestCase):
    """Unit tests for rbtools.api.request.HttpRequest."""

    def test_defaults(self):
        """Testing HttpRequest default attribute values"""
        request = HttpRequest('/')
        self.assertEqual(request.url, '/')
        self.assertEqual(request.method, 'GET')

        content_type, content = request.encode_multipart_formdata()
        self.assertIsNone(content_type)
        self.assertIsNone(content)

    def test_url_includes_normalized_query_args(self):
        """Testing HttpRequest.url includes normalized query arguments"""
        request = HttpRequest(
            url='/',
            query_args={
                b'a_b': 'c',
                'd-e': b'f',
            })

        self.assertEqual(request.url, '/?a-b=c&d-e=f')

    def test_headers_normalized(self):
        """Testing HttpRequest.headers uses native string types"""
        request = HttpRequest(
            url='/',
            headers={
                b'a': 'b',
                'c': b'd',
            })

        keys = list(six.iterkeys(request.headers))
        self.assertIs(type(keys[0]), str)
        self.assertIs(type(keys[1]), str)
        self.assertIs(type(request.headers[keys[0]]), str)
        self.assertIs(type(request.headers[keys[1]]), str)

    def test_method_normalized(self):
        """Testing HttpRequest.method uses native string types"""
        request = HttpRequest(url='/')
        request.method = b'GET'
        self.assertIs(type(request.method), str)

        request.method = 'POST'
        self.assertIs(type(request.method), str)

    def test_encode_multipart_formdata(self):
        """Testing HttpRequest.encode_multipart_formdata"""
        request = HttpRequest(url='/',
                              method='POST')
        request.add_field('foo', 'bar')
        request.add_field('bar', 42)
        request.add_field('name', 'somestring')
        request.add_file(name='my-file',
                         filename='filename.txt',
                         content=b'This is a test.')

        self.spy_on(request._make_mime_boundary,
                    call_fake=lambda r: b'BOUNDARY')

        ctype, content = request.encode_multipart_formdata()

        self.assertEqual(ctype, 'multipart/form-data; boundary=BOUNDARY')
        self.assertEqual(
            content,
            b'--BOUNDARY\r\n'
            b'Content-Disposition: form-data; name="foo"\r\n'
            b'\r\n'
            b'bar'
            b'\r\n'
            b'--BOUNDARY\r\n'
            b'Content-Disposition: form-data; name="bar"\r\n'
            b'\r\n'
            b'42'
            b'\r\n'
            b'--BOUNDARY\r\n'
            b'Content-Disposition: form-data; name="name"\r\n'
            b'\r\n'
            b'somestring'
            b'\r\n'
            b'--BOUNDARY\r\n'
            b'Content-Disposition: form-data; name="my-file";'
            b' filename="filename.txt"\r\n'
            b'Content-Type: text/plain\r\n'
            b'\r\n'
            b'This is a test.'
            b'\r\n'
            b'--BOUNDARY--\r\n\r\n')

    def test_encode_multipart_formdata_normalizes_string_types(self):
        """Testing HttpRequest.encode_multipart_formdata normalizes
        Unicode and byte strings
        """
        konnichiwa = '\u3053\u3093\u306b\u3061\u306f'

        request = HttpRequest(url='/',
                              method='POST')
        request.add_field('foo', konnichiwa)
        request.add_field('bar', konnichiwa.encode('utf-8'))
        request.add_field('baz', b'\xff')

        self.spy_on(request._make_mime_boundary,
                    call_fake=lambda r: b'BOUNDARY')

        ctype, content = request.encode_multipart_formdata()

        self.assertEqual(ctype, 'multipart/form-data; boundary=BOUNDARY')
        self.assertEqual(
            content,
            b'--BOUNDARY\r\n'
            b'Content-Disposition: form-data; name="foo"\r\n'
            b'\r\n'
            b'\xe3\x81\x93\xe3\x82\x93\xe3\x81\xab\xe3\x81\xa1\xe3\x81\xaf'
            b'\r\n'
            b'--BOUNDARY\r\n'
            b'Content-Disposition: form-data; name="bar"\r\n'
            b'\r\n'
            b'\xe3\x81\x93\xe3\x82\x93\xe3\x81\xab\xe3\x81\xa1\xe3\x81\xaf'
            b'\r\n'
            b'--BOUNDARY\r\n'
            b'Content-Disposition: form-data; name="baz"\r\n'
            b'\r\n'
            b'\xff'
            b'\r\n'
            b'--BOUNDARY--\r\n\r\n')

    def test_encode_query_args(self):
        """Testing the encoding of query arguments"""
        request = HttpRequest(
            url='/',
            method='GET',
            query_args={
                'long_arg': 'long',
                'float': 1.2,
                'int': 5,
                'byte': b'binary',
                'true': True,
                'false': False,
            })

        query_args = dict(parse_qsl(urlparse(request.url).query))

        self.assertEqual(
            query_args,
            {
                'long-arg': 'long',
                'float': '1.2',
                'int': '5',
                'byte': 'binary',
                'true': '1',
                'false': '0',
            })

        for key, value in six.iteritems(query_args):
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)

    def test_encode_query_args_invalid(self):
        """Testing the encoding of query arguments with invalid keys and
        values
        """
        with self.assertRaises(ValueError):
            HttpRequest(
                url='/',
                method='GET',
                query_args={
                    1: 'value',
                })

        with self.assertRaises(ValueError):
            HttpRequest(
                url='/',
                method='GET',
                query_args={
                    1.2: 'value',
                })

        with self.assertRaises(ValueError):
            HttpRequest(
                url='/',
                method='GET',
                query_args={
                    True: 'value',
                })

        with self.assertRaises(ValueError):
            HttpRequest(
                url='/',
                method='GET',
                query_args={
                    'key': {'adsf': 'jkl;'},
                })

        with self.assertRaises(ValueError):
            HttpRequest(
                url='/',
                method='GET',
                query_args={
                    'key': ['a', 'b', 'c'],
                })
