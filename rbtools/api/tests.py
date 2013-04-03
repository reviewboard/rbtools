import re
import unittest

from rbtools.api.capabilities import Capabilities
from rbtools.api.factory import create_resource
from rbtools.api.request import HttpRequest
from rbtools.api.resource import CountResource, \
                                 ItemResource, \
                                 ListResource, \
                                 ResourceDictField, \
                                 ResourceLinkField, \
                                 RootResource
from rbtools.api.transport import Transport


class CapabilitiesTests(unittest.TestCase):
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


class TestWithPayloads(unittest.TestCase):
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
        """Test guessing the resource's token."""
        r = create_resource(self.transport, self.item_payload, '')
        self.assertTrue('resource_token' not in r.fields)

        for field in self.item_payload['resource_token']:
            self.assertTrue(field in r)

        r = create_resource(self.transport, self.count_payload, '')
        self.assertTrue('count' in r)

    def test_no_token_guessing(self):
        """Test constructing without guessing the resource token."""
        r = create_resource(self.transport, self.item_payload, '',
                            guess_token=False)
        self.assertTrue('resource_token' in r)
        self.assertTrue('field1' not in r)
        self.assertTrue('field1' in r.resource_token)

        r = create_resource(self.transport, self.list_payload, '',
                            guess_token=False)
        self.assertTrue('resource_token' in r)

    def test_item_construction(self):
        """Test constructing an item resource."""
        r = create_resource(self.transport, self.item_payload, '')
        self.assertTrue(isinstance(r, ItemResource))
        self.assertEqual(r.field1,
                         self.item_payload['resource_token']['field1'])
        self.assertEqual(r.field2,
                         self.item_payload['resource_token']['field2'])

    def test_list_construction(self):
        """Test constructing a list resource."""
        r = create_resource(self.transport, self.list_payload, '')
        self.assertTrue(isinstance(r, ListResource))

    def test_count_construction(self):
        """Test constructing a count resource."""
        r = create_resource(self.transport, self.count_payload, '')
        self.assertTrue(isinstance(r, CountResource))
        self.assertEqual(r.count, self.count_payload['count'])

    def test_resource_specific_base_class(self):
        """Test constructing a resource with a specific base class."""
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
        """Test item resource fields."""
        r = create_resource(self.transport, self.item_payload, '')
        for field in self.item_payload['resource_token']:
            self.assertTrue(field in r)
            self.assertTrue(hasattr(r, field))

    def test_item_resource_links(self):
        """Test item resource link generation."""
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

    def test_list_resource_list(self):
        """Test list resource lists."""
        r = create_resource(self.transport, self.list_payload, '')
        self.assertEqual(r.num_items, len(self.list_payload['resource_token']))
        self.assertEqual(r.total_results, self.list_payload['total_results'])

        for index in range(r.num_items):
            for field in r[index].iterfields():
                self.assertEqual(
                    r[index][field],
                    self.list_payload['resource_token'][index][field])

    def test_list_resource_links(self):
        """Test link resource link generation."""
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
        """Test generation of methods for the root resource uri templates."""
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
        """Test access of a dictionary field."""
        r = create_resource(self.transport, self.item_payload, '')

        field = r.nested_field

        self.assertTrue(isinstance(field, ResourceDictField))
        self.assertEqual(
            field.nested1,
            self.item_payload['resource_token']['nested_field']['nested1'])

    def test_resource_dict_field_iteration(self):
        """Test iterating sub-fields of a dictionary field."""
        r = create_resource(self.transport, self.item_payload, '')

        field = r.nested_field
        iterated_fields = set(f for f in field.iterfields())
        nested_fields = set(
            f for f in self.item_payload['resource_token']['nested_field'])

        self.assertEqual(set(),
                         nested_fields.symmetric_difference(iterated_fields))

    def test_link_field(self):
        """Test access of a link field."""
        r = create_resource(self.transport, self.item_payload, '')

        field = r.link_field
        self.assertTrue(isinstance(field, ResourceLinkField))

        request = field.get()
        self.assertEqual(request.method, 'GET')
        self.assertEqual(
            request.url,
            self.item_payload['resource_token']['link_field']['href'])


class HttpRequestTests(unittest.TestCase):
    def setUp(self):
        self.request = HttpRequest('/')

    def test_default_values(self):
        """Test the default values."""
        self.assertEquals(self.request.url, '/')
        self.assertEquals(self.request.method, 'GET')
        content_type, content = self.request.encode_multipart_formdata()
        self.assertTrue(content_type is None)
        self.assertTrue(content is None)

    def test_post_form_data(self):
        """Test the multipart form data generation."""
        request = HttpRequest('/', 'POST')
        request.add_field('foo', 'bar')
        request.add_field('bar', 42)
        request.add_field('err', 'must-be-deleted')
        request.add_field('name', 'somestring')
        request.del_field('err')

        ctype, content = request.encode_multipart_formdata()
        m = re.match('^multipart/form-data; boundary=(.*)$', ctype)
        self.assertFalse(m is None)
        fields = [l.strip() for l in content.split('--' + m.group(1))][1:-1]

        d = {}

        for f in fields:
            lst = f.split('\r\n\r\n')
            self.assertEquals(len(lst), 2)
            k, v = lst

            m = re.match('Content-Disposition: form-data; name="(.*?)"$', k)
            self.assertFalse(m is None)
            d[m.group(1)] = v

        self.assertEquals(d, {'foo': 'bar', 'bar': '42', 'name': 'somestring'})
