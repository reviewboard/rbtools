import re
import unittest

from rbtools.api.capabilities import Capabilities
from rbtools.api.factory import create_resource
from rbtools.api.request import HttpRequest
from rbtools.api.resource import CountResource, \
                                 ResourceItem, \
                                 ResourceList, \
                                 RootResource
from rbtools.api.transport.sync import ResourceListField, \
                                       ResourceDictField, \
                                       SyncTransport, \
                                       SyncTransportItemResource, \
                                       SyncTransportListResource, \
                                       SyncTransportMethod, \
                                       SyncTransportResourceLink


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


class TestWithPayloads(unittest.TestCase):
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
            'reviews': 'http://localhost:8080/api/review-requests/' +
                '{review_request_id}/reviews/',
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
        r = create_resource(self.item_payload, '')
        self.assertTrue('resource_token' not in r.fields)
        for field in self.item_payload['resource_token']:
            self.assertTrue(field in r.fields)

        r = create_resource(self.count_payload, '')
        self.assertTrue('count' in r.fields)

    def test_no_token_guessing(self):
        """Test constructing without guessing the resource token."""
        r = create_resource(self.item_payload, '', guess_token=False)
        self.assertTrue('resource_token' in r.fields)
        self.assertTrue('field1' not in r.fields)
        self.assertTrue('field1' in r.fields['resource_token'])

        r = create_resource(self.list_payload, '', guess_token=False)
        self.assertTrue('resource_token' in r.fields)

    def test_item_construction(self):
        """Test constructing an item resource."""
        r = create_resource(self.item_payload, '')
        self.assertTrue(isinstance(r, ResourceItem))
        self.assertEqual(r.fields['field1'],
                         self.item_payload['resource_token']['field1'])
        self.assertEqual(r.fields['field2'],
                         self.item_payload['resource_token']['field2'])

    def test_list_construction(self):
        """Test constructing a list resource."""
        r = create_resource(self.list_payload, '')
        self.assertTrue(isinstance(r, ResourceList))

    def test_count_construction(self):
        """Test constructing a count resource."""
        r = create_resource(self.count_payload, '')
        self.assertTrue(isinstance(r, CountResource))
        self.assertEqual(r.fields['count'], self.count_payload['count'])

    def test_resource_specific_base_class(self):
        """Test constructing a resource with a specific base class."""
        r = create_resource(self.root_payload, '')
        self.assertFalse(isinstance(r, RootResource))
        r = create_resource(
            self.root_payload,
            '',
            mime_type='application/vnd.reviewboard.org.root+json')
        self.assertTrue(isinstance(r, RootResource))


class ResourceTests(TestWithPayloads):
    def test_item_resource_fields(self):
        """Test item resource fields."""
        r = create_resource(self.item_payload, '')
        for field in self.item_payload['resource_token']:
            self.assertTrue(field in r.fields)

    def test_item_resource_links(self):
        """Test item resource link generation."""
        r = create_resource(self.item_payload, '')
        self.assertTrue(hasattr(r, 'get_self'))
        self.assertTrue(callable(r.get_self))
        self.assertTrue(isinstance(r.get_self(), HttpRequest))
        self.assertEqual(r.get_self().method, 'GET')

        self.assertTrue(hasattr(r, 'update'))
        self.assertTrue(callable(r.update))
        self.assertTrue(isinstance(r.update(), HttpRequest))
        self.assertEqual(r.update().method, 'PUT')

        self.assertTrue(hasattr(r, 'delete'))
        self.assertTrue(callable(r.delete))
        self.assertTrue(isinstance(r.delete(), HttpRequest))
        self.assertEqual(r.delete().method, 'DELETE')

        self.assertTrue(hasattr(r, 'get_other_link'))
        self.assertTrue(callable(r.get_other_link))
        self.assertTrue(isinstance(r.get_other_link(), HttpRequest))
        self.assertEqual(r.get_other_link().method, 'GET')

        self.assertFalse(hasattr(r, 'create'))

    def test_list_resource_list(self):
        """Test list resource lists."""
        r = create_resource(self.list_payload, '')
        self.assertEqual(r.num_items, len(self.list_payload['resource_token']))
        self.assertEqual(r.total_results, self.list_payload['total_results'])

        for index in range(r.num_items):
            for field in r[index]:
                self.assertEqual(
                    r[index][field],
                    self.list_payload['resource_token'][index][field])

    def test_list_resource_links(self):
        """Test link resource link generation."""
        r = create_resource(self.list_payload, '')
        self.assertTrue(hasattr(r, 'get_self'))
        self.assertTrue(callable(r.get_self))
        self.assertTrue(isinstance(r.get_self(), HttpRequest))
        self.assertEqual(r.get_self().method, 'GET')

        self.assertTrue(hasattr(r, 'create'))
        self.assertTrue(callable(r.create))
        self.assertTrue(isinstance(r.create(), HttpRequest))
        self.assertEqual(r.create().method, 'POST')

        self.assertTrue(hasattr(r, 'get_other_link'))
        self.assertTrue(callable(r.get_other_link))
        self.assertTrue(isinstance(r.get_other_link(), HttpRequest))
        self.assertEqual(r.get_other_link().method, 'GET')

        self.assertFalse(hasattr(r, 'update'))
        self.assertFalse(hasattr(r, 'delete'))

    def test_root_resource_templates(self):
        """Test generation of methods for the root resource uri templates."""
        r = create_resource(
            self.root_payload,
            '',
            mime_type='application/vnd.reviewboard.org.root+json')

        for template_name in self.root_payload['uri_templates']:
            method_name = "get_%s" % template_name
            self.assertTrue(hasattr(r, method_name))
            self.assertTrue(callable(getattr(r, method_name)))


class MockSyncTransport(SyncTransport):
    """Sync Transport without initialization of ReviewBoardServer"""
    def __init__(self):
        self.server = None


class SyncTransportTests(TestWithPayloads):
    def setUp(self):
        self.transport = MockSyncTransport()
        self.item_resource = create_resource(self.item_payload, '')
        self.item = SyncTransportItemResource(self.transport,
                                              self.item_resource)

        self.list_resource = create_resource(self.list_payload, '')
        self.list = SyncTransportListResource(self.transport,
                                              self.list_resource)

    def test_item_attributes(self):
        """Test item resource attributes."""
        for field, value in self.item_payload['resource_token'].iteritems():
            self.assertTrue(hasattr(self.item, field))
            attr = getattr(self.item, field)

            if isinstance(value, list):
                # Test list wrapping.
                self.assertTrue(isinstance(attr, ResourceListField))
            elif isinstance(value, dict):
                # Test dict wrapping and link detection.
                self.assertTrue(isinstance(attr, ResourceDictField) or
                                isinstance(attr, SyncTransportResourceLink))

                if isinstance(attr, SyncTransportResourceLink):
                    self.assertEqual(attr.href, value['href'])
                    self.assertEqual(attr.method, value.get('method', 'GET'))
                    self.assertEqual(attr.title, value.get('title', None))
            else:
                self.assertEquals(attr, value)

    def test_item_links(self):
        """Test item resource links."""
        self.assertTrue(hasattr(self.item, 'get_self'))
        self.assertTrue(callable(self.item.get_self))
        self.assertTrue(isinstance(self.item.get_self, SyncTransportMethod))

        self.assertTrue(hasattr(self.item, 'update'))
        self.assertTrue(callable(self.item.update))
        self.assertTrue(isinstance(self.item.update, SyncTransportMethod))

        self.assertTrue(hasattr(self.item, 'delete'))
        self.assertTrue(callable(self.item.delete))
        self.assertTrue(isinstance(self.item.delete, SyncTransportMethod))

        self.assertTrue(hasattr(self.item, 'get_other_link'))
        self.assertTrue(callable(self.item.get_other_link))
        self.assertTrue(
            isinstance(self.item.get_other_link, SyncTransportMethod))

        self.assertFalse(hasattr(self.item, 'create'))

    def test_list_items(self):
        """Test items of a list resource."""
        self.assertTrue(hasattr(self.list, 'num_items'))
        self.assertTrue(hasattr(self.list, 'total_results'))
        for index in range(self.list.num_items):
            self.assertTrue(
                isinstance(self.list[index], SyncTransportItemResource))

            for field in self.list_payload['resource_token'][index]:
                if field != 'links':
                    self.assertTrue(hasattr(self.list[index], field))


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
