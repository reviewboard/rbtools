"""Unit tests for rbtools.api.resource."""

from __future__ import unicode_literals

from six.moves import range

from rbtools.api.factory import create_resource
from rbtools.api.request import HttpRequest
from rbtools.api.resource import (CountResource,
                                  ItemResource,
                                  ListResource,
                                  RESOURCE_MAP,
                                  ResourceDictField,
                                  ResourceLinkField,
                                  ResourceListField,
                                  RootResource)
from rbtools.api.tests.base import TestWithPayloads


class ExpandedItemResource(ItemResource):
    pass


class ItemResourceTests(TestWithPayloads):
    """Unit tests for rbtools.api.resource.ItemResource."""

    expanded_item_payload = {
        'obj': {
            '_expanded': {
                'item1': {
                    'item_mimetype': 'application/vnd.test.item+json',
                },
                'other-item': {
                    'item_mimetype': 'application/vnd.test.other-item+json',
                },
            },
            'item1': {
                'links': {
                    'self': {
                        'href': 'http://localhost:8080/api/items/1/',
                        'method': 'GET',
                    },
                },
                'name': 'My Item 1',
            },
            'item2': {
                'links': {
                    'self': {
                        'href': 'http://localhost:8080/api/items/2/',
                        'method': 'GET',
                    },
                },
                'name': 'My Item 2',
            },
            'other-item': {
                'links': {
                    'self': {
                        'href': 'http://localhost:8080/api/other-items/2/',
                        'method': 'GET',
                    },
                },
                'name': 'Other Item',
            },
        },
        'stat': 'ok',
    }

    expanded_list_payload = {
        'obj': {
            '_expanded': {
                'list1': {
                    'list_mimetype': 'application/vnd.test.list+json',
                    'item_mimetype': 'application/vnd.test.item+json',
                    'list_url': 'http://localhost:8080/api/items/',
                },
                'other-list': {
                    'list_mimetype': 'application/vnd.test.other-list+json',
                    'item_mimetype': 'application/vnd.test.other-item+json',
                    'list_url': 'http://localhost:8080/api/other-items/',
                },
            },
            'list1': [
                {
                    'links': {
                        'self': {
                            'href': 'http://localhost:8080/api/items/1/',
                            'method': 'GET',
                        },
                    },
                    'name': 'My Item',
                },
            ],
            'list2': [
                {
                    'links': {
                        'self': {
                            'href': 'http://localhost:8080/api/items/1/',
                            'method': 'GET',
                        },
                    },
                    'name': 'My Item',
                },
            ],
            'other-list': [
                {
                    'links': {
                        'self': {
                            'href': 'http://localhost:8080/api/other-items/1/',
                            'method': 'GET',
                        },
                    },
                    'name': 'Other Item',
                },
            ],
        },
        'stat': 'ok',
    }

    def setUp(self):
        super(ItemResourceTests, self).setUp()

        RESOURCE_MAP['application/vnd.test.item'] = ExpandedItemResource

    def tearDown(self):
        super(ItemResourceTests, self).tearDown()

        RESOURCE_MAP.pop('application/vnd.test.item', None)

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

    def test_getattr_with_expanded_item_resource(self):
        """Testing ItemResource.__getattr__ with field as expanded item
        resource
        """
        r = create_resource(transport=self.transport,
                            payload=self.expanded_item_payload,
                            url='')

        self.assertIsInstance(r['item1'], ExpandedItemResource)
        self.assertIsInstance(r['item2'], ResourceDictField)
        self.assertIsInstance(r['other-item'], ResourceDictField)

    def test_getattr_with_expanded_list_resource(self):
        """Testing ItemResource.__getattr__ with field as expanded list
        resource
        """
        r = create_resource(transport=self.transport,
                            payload=self.expanded_list_payload,
                            url='')

        self.assertIsInstance(r['list1'], ResourceListField)
        self.assertIsInstance(r['list1'][0], ExpandedItemResource)
        self.assertIsInstance(r['list2'], ResourceListField)
        self.assertIsInstance(r['list2'][0], ResourceDictField)
        self.assertIsInstance(r['other-list'], ResourceListField)
        self.assertIsInstance(r['other-list'][0], ResourceDictField)

    def test_iteritems_with_expanded_item_resource(self):
        """Testing ItemResource.iteritems with field as expanded item resource
        """
        r = create_resource(transport=self.transport,
                            payload=self.expanded_item_payload,
                            url='')
        items = dict(r.iteritems())

        self.assertIsInstance(items['item1'], ExpandedItemResource)
        self.assertIsInstance(items['item2'], ResourceDictField)
        self.assertIsInstance(items['other-item'], ResourceDictField)

    def test_iteritems_with_expanded_list_resource(self):
        """Testing ItemResource.iteritems with field as expanded list resource
        """
        r = create_resource(transport=self.transport,
                            payload=self.expanded_list_payload,
                            url='')
        items = dict(r.iteritems())

        self.assertIsInstance(items['list1'], ResourceListField)
        self.assertIsInstance(items['list1'][0], ExpandedItemResource)
        self.assertIsInstance(items['list2'], ResourceListField)
        self.assertIsInstance(items['list2'][0], ResourceDictField)
        self.assertIsInstance(items['other-list'], ResourceListField)
        self.assertIsInstance(items['other-list'][0], ResourceDictField)

    def test_extra_data_rewriting_create(self):
        """Testing rewriting of extra_data__ parameters to create"""
        r = create_resource(self.transport, self.list_payload, '')
        request = r.create(extra_data__foo='bar')
        self.assertTrue(b'extra_data.foo' in request._fields)
        self.assertEqual(request._fields[b'extra_data.foo'], b'bar')

    def test_extra_data_rewriting_update(self):
        """Testing rewriting of exta_data__ parameters to update"""
        r = create_resource(self.transport, self.item_payload, '')
        request = r.update(extra_data__foo='bar')
        self.assertTrue(b'extra_data.foo' in request._fields)
        self.assertEqual(request._fields[b'extra_data.foo'], b'bar')


class ListResourceTests(TestWithPayloads):
    """Unit tests for rbtools.api.resource.ListResource."""

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
