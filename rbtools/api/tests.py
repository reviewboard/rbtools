from __future__ import unicode_literals

import datetime
import locale
import re

import six
from six.moves import range

from rbtools.api.cache import APICache, CacheEntry, CachedHTTPResponse
from rbtools.api.capabilities import Capabilities
from rbtools.api.factory import create_resource
from rbtools.api.request import HttpRequest, Request
from rbtools.api.resource import (CountResource,
                                  ItemResource,
                                  ListResource,
                                  ResourceDictField,
                                  ResourceLinkField,
                                  ReviewRequestResource,
                                  RootResource)
from rbtools.api.transport import Transport
from rbtools.testing import TestCase


class CapabilitiesTests(TestCase):
    """Tests for rbtools.api.capabilities.Capabilities"""
    def test_has_capability(self):
        """Testing Capabilities.has_capability with supported capability"""
        caps = Capabilities({
            'foo': {
                'bar': {
                    'value': True,
                }
            }
        })

        self.assertTrue(caps.has_capability('foo', 'bar', 'value'))

    def test_has_capability_with_unknown_capability(self):
        """Testing Capabilities.has_capability with unknown capability"""
        caps = Capabilities({})
        self.assertFalse(caps.has_capability('mycap'))

    def test_has_capability_with_partial_path(self):
        """Testing Capabilities.has_capability with partial capability path"""
        caps = Capabilities({
            'foo': {
                'bar': {
                    'value': True,
                }
            }
        })

        self.assertFalse(caps.has_capability('foo', 'bar'))


class MockTransport(Transport):
    """Mock transport which returns HttpRequests without executing them"""
    def __init__(self):
        pass


class TestWithPayloads(TestCase):
    transport = MockTransport()
    item_payload = {
        'resource_token': {
            'field1': 1,
            'field2': 2,
            'nested_field': {
                'nested1': 1,
                'nested2': 2,
            },
            'nested_list': [
                {
                    'href': 'http://localhost:8080/api/',
                    'method': 'GET',
                },
                {
                    'href': 'http://localhost:8080/api/',
                    'method': 'GET',
                },
            ],
            'link_field': {
                'href': 'http://localhost:8080/api/',
                'method': 'GET',
                'title': 'Link Field'
            },
        },
        'links': {
            'self': {
                'href': 'http://localhost:8080/api/',
                'method': 'GET',
            },
            'update': {
                'href': 'http://localhost:8080/api/',
                'method': 'PUT',
            },
            'delete': {
                'href': 'http://localhost:8080/api/',
                'method': 'DELETE',
            },
            'other_link': {
                'href': 'http://localhost:8080/api/',
                'method': 'GET',
            },
        },
        'stat': 'ok',
    }
    list_payload = {
        'resource_token': [
            {
                'field1': 1,
                'field2': 2,
                'links': {
                    'self': {
                        'href': 'http://localhost:8080/api/',
                        'method': 'GET',
                    },
                },
            },
            {
                'field1': 1,
                'field2': 2,
                'links': {
                    'self': {
                        'href': 'http://localhost:8080/api/',
                        'method': 'GET',
                    },
                },
            },
        ],
        'links': {
            'self': {
                'href': 'http://localhost:8080/api/',
                'method': 'GET',
            },
            'create': {
                'href': 'http://localhost:8080/api/',
                'method': 'POST',
            },
            'other_link': {
                'href': 'http://localhost:8080/api/',
                'method': 'GET',
            },
        },
        'total_results': 10,
        'stat': 'ok',
    }
    count_payload = {
        'count': 10,
        'stat': 'ok'
    }
    root_payload = {
        'uri_templates': {
            'reviews': ('http://localhost:8080/api/review-requests/'
                        '{review_request_id}/reviews/'),
        },
        'links': {
            'self': {
                'href': 'http://localhost:8080/api/',
                'method': 'GET',
            },
            'groups': {
                'href': 'http://localhost:8080/api/groups',
                'method': 'GET',
            },
        },
        'stat': 'ok',
    }


class ResourceFactoryTests(TestWithPayloads):
    def test_token_guessing(self):
        """Testing guessing the resource's token"""
        r = create_resource(self.transport, self.item_payload, '')
        self.assertTrue('resource_token' not in r._fields)

        for field in self.item_payload['resource_token']:
            self.assertTrue(field in r)

        r = create_resource(self.transport, self.count_payload, '')
        self.assertTrue('count' in r)

    def test_no_token_guessing(self):
        """Testing constructing without guessing the resource token"""
        r = create_resource(self.transport, self.item_payload, '',
                            guess_token=False)
        self.assertTrue('resource_token' in r)
        self.assertTrue('field1' not in r)
        self.assertTrue('field1' in r.resource_token)

        r = create_resource(self.transport, self.list_payload, '',
                            guess_token=False)
        self.assertTrue('resource_token' in r)

    def test_item_construction(self):
        """Testing constructing an item resource"""
        r = create_resource(self.transport, self.item_payload, '')
        self.assertTrue(isinstance(r, ItemResource))
        self.assertEqual(r.field1,
                         self.item_payload['resource_token']['field1'])
        self.assertEqual(r.field2,
                         self.item_payload['resource_token']['field2'])

    def test_list_construction(self):
        """Testing constructing a list resource"""
        r = create_resource(self.transport, self.list_payload, '')
        self.assertTrue(isinstance(r, ListResource))

    def test_count_construction(self):
        """Testing constructing a count resource"""
        r = create_resource(self.transport, self.count_payload, '')
        self.assertTrue(isinstance(r, CountResource))
        self.assertEqual(r.count, self.count_payload['count'])

    def test_resource_specific_base_class(self):
        """Testing constructing a resource with a specific base class"""
        r = create_resource(self.transport, self.root_payload, '')
        self.assertFalse(isinstance(r, RootResource))
        r = create_resource(
            self.transport,
            self.root_payload,
            '',
            mime_type='application/vnd.reviewboard.org.root+json')
        self.assertTrue(isinstance(r, RootResource))


class ResourceTests(TestWithPayloads):
    def test_item_resource_fields(self):
        """Testing item resource fields"""
        r = create_resource(self.transport, self.item_payload, '')
        for field in self.item_payload['resource_token']:
            self.assertTrue(field in r)
            self.assertTrue(hasattr(r, field))

    def test_item_resource_links(self):
        """Testing item resource link generation"""
        r = create_resource(self.transport, self.item_payload, '')

        self.assertTrue(hasattr(r, 'get_self'))
        self.assertTrue(callable(r.get_self))
        request = r.get_self()
        self.assertTrue(isinstance(request, HttpRequest))
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.url,
                         self.item_payload['links']['self']['href'])

        self.assertTrue(hasattr(r, 'update'))
        self.assertTrue(callable(r.update))
        request = r.update()
        self.assertTrue(isinstance(request, HttpRequest))
        self.assertEqual(request.method, 'PUT')
        self.assertEqual(request.url,
                         self.item_payload['links']['update']['href'])

        self.assertTrue(hasattr(r, 'delete'))
        self.assertTrue(callable(r.delete))
        request = r.delete()
        self.assertTrue(isinstance(request, HttpRequest))
        self.assertEqual(request.method, 'DELETE')
        self.assertEqual(request.url,
                         self.item_payload['links']['delete']['href'])

        self.assertTrue(hasattr(r, 'get_other_link'))
        self.assertTrue(callable(r.get_other_link))
        request = r.get_other_link()
        self.assertTrue(isinstance(request, HttpRequest))
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.url,
                         self.item_payload['links']['other_link']['href'])

        self.assertFalse(hasattr(r, 'create'))

    def test_extra_data_rewriting_create(self):
        """Testing rewriting of extra_data__ parameters to create"""
        r = create_resource(self.transport, self.list_payload, '')
        request = r.create(extra_data__foo='bar')
        self.assertTrue('extra_data.foo' in request._fields)
        self.assertEqual(request._fields['extra_data.foo'], 'bar')

    def test_extra_data_rewriting_update(self):
        """Testing rewriting of exta_data__ parameters to update"""
        r = create_resource(self.transport, self.item_payload, '')
        request = r.update(extra_data__foo='bar')
        self.assertTrue('extra_data.foo' in request._fields)
        self.assertEqual(request._fields['extra_data.foo'], 'bar')

    def test_list_resource_list(self):
        """Testing list resource lists"""
        r = create_resource(self.transport, self.list_payload, '')
        self.assertEqual(r.num_items, len(self.list_payload['resource_token']))
        self.assertEqual(r.total_results, self.list_payload['total_results'])

        for index in range(r.num_items):
            for field in r[index].iterfields():
                self.assertEqual(
                    r[index][field],
                    self.list_payload['resource_token'][index][field])

    def test_list_resource_links(self):
        """Testing link resource link generation"""
        r = create_resource(self.transport, self.list_payload, '')

        self.assertTrue(hasattr(r, 'get_self'))
        self.assertTrue(callable(r.get_self))
        request = r.get_self()
        self.assertTrue(isinstance(request, HttpRequest))
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.url,
                         self.list_payload['links']['self']['href'])

        self.assertTrue(hasattr(r, 'create'))
        self.assertTrue(callable(r.create))
        request = r.create()
        self.assertTrue(isinstance(request, HttpRequest))
        self.assertEqual(request.method, 'POST')
        self.assertEqual(request.url,
                         self.list_payload['links']['create']['href'])

        self.assertTrue(hasattr(r, 'get_other_link'))
        self.assertTrue(callable(r.get_other_link))
        request = r.get_other_link()
        self.assertTrue(isinstance(request, HttpRequest))
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.url,
                         self.list_payload['links']['other_link']['href'])

        self.assertFalse(hasattr(r, 'update'))
        self.assertFalse(hasattr(r, 'delete'))

    def test_root_resource_templates(self):
        """Testing generation of methods for the root resource uri templates"""
        r = create_resource(
            self.transport,
            self.root_payload,
            '',
            mime_type='application/vnd.reviewboard.org.root+json')

        for template_name in self.root_payload['uri_templates']:
            method_name = "get_%s" % template_name
            self.assertTrue(hasattr(r, method_name))
            self.assertTrue(callable(getattr(r, method_name)))

    def test_resource_dict_field(self):
        """Testing access of a dictionary field"""
        r = create_resource(self.transport, self.item_payload, '')

        field = r.nested_field

        self.assertTrue(isinstance(field, ResourceDictField))
        self.assertEqual(
            field.nested1,
            self.item_payload['resource_token']['nested_field']['nested1'])

    def test_resource_dict_field_iteration(self):
        """Testing iterating sub-fields of a dictionary field"""
        r = create_resource(self.transport, self.item_payload, '')

        field = r.nested_field
        iterated_fields = set(f for f in field.iterfields())
        nested_fields = set(
            f for f in self.item_payload['resource_token']['nested_field'])

        self.assertEqual(set(),
                         nested_fields.symmetric_difference(iterated_fields))

    def test_link_field(self):
        """Testing access of a link field"""
        r = create_resource(self.transport, self.item_payload, '')

        field = r.link_field
        self.assertTrue(isinstance(field, ResourceLinkField))

        request = field.get()
        self.assertEqual(request.method, 'GET')
        self.assertEqual(
            request.url,
            self.item_payload['resource_token']['link_field']['href'])


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


class ReviewRequestResourceTests(TestCase):
    def setUp(self):
        self.transport = MockTransport()

    def test_absolute_url_with_absolute_url_field(self):
        """Testing ReviewRequestResource.absolute_url with 'absolute_url'
        field
        """
        payload = {
            'review_request': {
                'id': 123,
                'absolute_url': 'https://example.com/r/123/',
            },
            'stat': 'ok',
        }

        r = create_resource(
            transport=self.transport,
            payload=payload,
            url='https://api.example.com/',
            mime_type='application/vnd.reviewboard.org.review-request')
        self.assertTrue(isinstance(r, ReviewRequestResource))
        self.assertEqual(r.absolute_url, 'https://example.com/r/123/')

    def test_absolute_url_with_url_field(self):
        """Testing ReviewRequestResource.absolute_url with 'url' field"""
        payload = {
            'review_request': {
                'id': 123,
                'url': '/r/123/',
            },
            'stat': 'ok',
        }

        r = create_resource(
            transport=self.transport,
            payload=payload,
            url='https://example.com/',
            mime_type='application/vnd.reviewboard.org.review-request')
        self.assertTrue(isinstance(r, ReviewRequestResource))
        self.assertEqual(r.absolute_url, 'https://example.com/r/123/')

    def test_absolute_url_with_fallback(self):
        """Testing ReviewRequestResource.absolute_url with
        generated fallback URL
        """
        payload = {
            'review_request': {
                'id': 123,
            },
            'stat': 'ok',
        }

        r = create_resource(
            transport=self.transport,
            payload=payload,
            url='https://example.com/',
            mime_type='application/vnd.reviewboard.org.review-request')
        self.assertTrue(isinstance(r, ReviewRequestResource))
        self.assertEqual(r.absolute_url, 'https://example.com/r/123/')


class MockResponse(object):
    """A mock up for a response from urllib2."""

    def __init__(self, code, headers, body):
        """Create a new MockResponse."""
        self.code = code
        self.headers = headers
        self.body = body

        if self.body:
            self.headers['Content-Length'] = len(body)

            if 'Content-Type' not in self.headers:
                self.headers['Content-Type'] = 'text/plain'

    def info(self):
        """Get the response headers."""
        return self.headers

    def read(self):
        """Get the response body."""
        return self.body

    def getcode(self):
        """Get the response code."""
        return self.code


class MockUrlOpener(object):
    """A mock url opener that records the number of hits it gets to URL."""

    CONTENT = b'foobar'

    def __init__(self, endpoints):
        """Create a new MockUrlOpener given the endpoints: headers mapping."""
        self.endpoints = {}
        for url, headers in six.iteritems(endpoints):
            self.endpoints[url] = {
                'hit_count': 0,
                'headers': headers
            }

    def __call__(self, request):
        """Call the URL opener to return a MockResponse for the URL."""
        url = request.get_full_url()

        self.endpoints[url]['hit_count'] += 1

        headers = self.endpoints[url]['headers'].copy()
        headers['Date'] = datetime.datetime.utcnow().strftime(
            '%a, %d %b %Y %H:%M:%S GMT')

        if 'If-none-match' in request.headers and 'ETag' in headers:
            # If the request includes an If-None-Match header, we should check
            # if the ETag in our headers matches.
            if headers.get('ETag') == request.headers['If-none-match']:
                resp = MockResponse(304, headers, None)
            else:
                resp = MockResponse(200, headers, self.CONTENT)
        elif 'If-modified-since' in request.headers:
            if 'max-age=0' in headers.get('Cache-Control', ''):
                # We are only testing the case for when max-age is 0 and when
                # max-age is very large because it is impractical to require
                # the tests to sleep().
                resp = MockResponse(200, headers, self.CONTENT)
            else:
                request_datetime = datetime.datetime.strptime(
                    request.headers['If-modified-since'],
                    CacheEntry.DATE_FORMAT)

                header_datetime = datetime.datetime.strptime(
                    headers['Last-Modified'],
                    CacheEntry.DATE_FORMAT)

                if request_datetime < header_datetime:
                    # The content has been modified
                    resp = MockResponse(200, headers, self.CONTENT)
                else:
                    resp = MockResponse(304, headers, None)
        else:
            resp = MockResponse(200, headers, self.CONTENT)

        return resp

    def get_hit_count(self, url):
        return self.endpoints[url]['hit_count']


class APICacheTests(TestCase):
    """Test cases for the APICache class."""

    content = b'foobar'
    request_headers = {
        'http://high_max_age': {
            'Cache-Control': 'max-age=10000'
        },
        'http://zero_max_age': {
            'Cache-Control': 'max-age=0',
        },
        'http://no_cache_etag': {
            'Cache-Control': 'no-cache',
            'ETag': 'etag',
        },
        'http://no_cache': {
            'Cache-Control': 'no-cache',
        },
        'http://no_cache_date': {
            'Cache-Control': 'no-cache',
            'Last-Modified': '1999-12-31T00:00:00',
        },
        'http://no_store': {
            'Cache-Control': 'no-store',
        },
        'http://must_revalidate': {
            'Cache-Control': 'must-revalidate',
            'ETag': 'etag'
        },
        'http://vary': {
            'Cache-control': 'max-age=1000',
            'Vary': 'User-agent'
        },
        'http://pragma': {
            'Pragma': 'no-cache'
        },
        'http://expired': {
            'Expires': 'Thu, 01 Dec 1983 20:00:00 GMT',
        },
        'http://expires_override': {
            'Expires': 'Thu, 01 Dec 1983 20:00:00 GMT',
            'Cache-Control': 'max-age=10000',
        },
    }

    def setUp(self):
        """Create a MockUrlOpener and an instance of the APICache using it."""
        self.urlopener = MockUrlOpener(self.request_headers)
        self.cache = APICache(create_db_in_memory=True, urlopen=self.urlopener)

    def test_cache_control_header_max_age_high(self):
        """Testing the cache with a high max-age value"""
        request = Request('http://high_max_age', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(
            self.urlopener.get_hit_count('http://high_max_age'),
            1)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(second_resp, CachedHTTPResponse))

    def test_cache_control_header_max_age_zero(self):
        """Testing the cache with a zero max-age value"""
        request = Request('http://zero_max_age', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://zero_max_age'),
                         2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertFalse(isinstance(second_resp, CachedHTTPResponse))

    def test_cache_control_header_nocache(self):
        """Testing the cache with the no-cache control"""
        request = Request('http://no_cache', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://no_cache'), 2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertFalse(isinstance(second_resp, CachedHTTPResponse))

    def test_cache_control_header_nocache_with_etag(self):
        """Testing the cache with the no-cache control and a specified ETag"""
        request = Request('http://no_cache_etag', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://no_cache_etag'),
                         2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(second_resp, CachedHTTPResponse))

    def test_cache_control_header_nocache_with_etag_updated(self):
        """Testing the cache with the no-cache control and an updated ETag"""
        request = Request('http://no_cache_etag', method='GET')
        first_resp = self.cache.make_request(request)

        # Pretend the end point has been updated since the last request.
        self.urlopener.endpoints['http://no_cache_etag']['headers']['ETag'] = (
            'new-etag')

        second_resp = self.cache.make_request(request)
        third_resp = self.cache.make_request(request)

        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertFalse(isinstance(second_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(third_resp, CachedHTTPResponse))

        self.assertEqual(self.urlopener.get_hit_count('http://no_cache_etag'),
                         3)

    def test_cache_control_header_nocache_with_last_modfied(self):
        """Testing the cache with the no-cache control"""
        request = Request('http://no_cache_date', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://no_cache_date'),
                         2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(second_resp, CachedHTTPResponse))

    def test_cache_control_header_nocache_with_last_modified_updated(self):
        """Testing the cache with the no-cache control and an updated
        Last-Modified header
        """
        endpoint = 'http://no_cache_lastmodified_updated'
        future_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)

        self.urlopener.endpoints[endpoint] = {
            'hit_count': 0,
            'headers': {
                'Cache-Control': 'no-cache',
                'Last-Modified': '1999-12-31T00:00:00'
            },
        }

        request = Request(endpoint, method='GET')
        first_resp = self.cache.make_request(request)

        self.urlopener.endpoints[endpoint]['headers']['Last-Modified'] = (
            future_date.strftime(CacheEntry.DATE_FORMAT))

        second_resp = self.cache.make_request(request)
        third_resp = self.cache.make_request(request)

        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertFalse(isinstance(second_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(third_resp, CachedHTTPResponse))
        self.assertEqual(self.urlopener.get_hit_count(endpoint), 3)

    def test_cache_control_header_no_store(self):
        """Testing the cache with the no-store control"""
        request = Request('http://no_store', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://no_store'), 2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertFalse(isinstance(second_resp, CachedHTTPResponse))

    def test_cache_control_header_must_revalidate(self):
        """Testing the cache with the must-revalidate control"""
        request = Request('http://must_revalidate', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(
            self.urlopener.get_hit_count('http://must_revalidate'),
            2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(second_resp, CachedHTTPResponse))

    def test_vary_header(self):
        """Testing the cache with the Vary header"""
        request = Request('http://vary', headers={'User-agent': 'foo'},
                          method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://vary'), 1)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(second_resp, CachedHTTPResponse))

    def test_vary_header_different_requests(self):
        """Testing the cache with the Vary header and different requests"""
        first_request = Request('http://vary', headers={'User-agent': 'foo'},
                                method='GET')
        second_request = Request('http://vary', headers={'User-agent': 'bar'},
                                 method='GET')

        first_resp = self.cache.make_request(first_request)
        second_resp = self.cache.make_request(second_request)

        self.assertEqual(self.urlopener.get_hit_count('http://vary'), 2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertFalse(isinstance(second_resp, CachedHTTPResponse))

    def test_pragma_header(self):
        """Testing the cache with the Pragma: no-cache header"""
        request = Request('http://pragma', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://pragma'), 2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertFalse(isinstance(second_resp, CachedHTTPResponse))

    def test_expires_header_expired(self):
        """Testing the cache with the Expires header in the past"""
        request = Request('http://expired', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://expired'), 2)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertFalse(isinstance(second_resp, CachedHTTPResponse))

    def test_expires_header_future(self):
        """Testing the cache with the Expires header in the future"""

        # We generate the future date in the C locale so that it is properly
        # formatted.
        locale.setlocale(locale.LC_TIME, str('C'))
        future_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        future_date = future_date.strftime(APICache.EXPIRES_FORMAT) + 'UTC'
        locale.resetlocale(locale.LC_TIME)

        self.urlopener.endpoints['http://expires_future'] = {
            'hit_count': 0,
            'headers': {
                'Expires': future_date,
            },
        }

        request = Request('http://expires_future', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(self.urlopener.get_hit_count('http://expires_future'),
                         1)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(second_resp, CachedHTTPResponse))

    def test_expires_header_overriden_by_max_age(self):
        """Testing the cache with an Expires header that is overridden"""
        request = Request('http://expires_override', method='GET')
        first_resp = self.cache.make_request(request)
        second_resp = self.cache.make_request(request)

        self.assertEqual(
            self.urlopener.get_hit_count('http://expires_override'),
            1)
        self.assertFalse(isinstance(first_resp, CachedHTTPResponse))
        self.assertTrue(isinstance(second_resp, CachedHTTPResponse))

    def test_saving_non_ascii_data(self):
        """Testing writing to the cache with non-ASCII data"""
        # "Hello world" in Japanese as unicode characters.
        hello_world = '\u3053\u3093\u306b\u3061\u306f\u4e16\u754c'

        entry = CacheEntry(
            url='http://unicode-example',
            vary_headers={},
            max_age=0,
            etag='etag',
            local_date=datetime.datetime.now(),
            last_modified='Sat, 21 Mar 2015 05:33:22 GMT',
            mime_type='text/plain',
            item_mime_type=None,
            response_body=hello_world.encode('utf-8'))

        try:
            self.cache._save_entry(entry)
        except Exception:
            self.fail('Could not write binary data to the API cache.')

        try:
            self.cache._save_entry(entry)
        except Exception:
            self.fail('Could not update binary data in the API cache.')
