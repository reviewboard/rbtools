"""Unit tests for rbtools.api.factory."""

from __future__ import annotations

from rbtools.api.factory import create_resource
from rbtools.api.resource import (CountResource,
                                  ItemResource,
                                  ListResource,
                                  RootResource)
from rbtools.api.tests.base import TestWithPayloads


class ResourceFactoryTests(TestWithPayloads):
    """Unit tests for the resource factory."""

    def test_token_guessing(self) -> None:
        """Testing guessing the resource's token"""
        r = create_resource(
            transport=self.transport,
            payload=self.item_payload,
            url='')
        self.assertTrue('resource_token' not in r._fields)

        for field in self.item_payload['resource_token']:
            self.assertTrue(field in r)

        r = create_resource(
            transport=self.transport,
            payload=self.count_payload,
            url='')
        self.assertTrue('count' in r)

    def test_no_token_guessing(self) -> None:
        """Testing constructing without guessing the resource token"""
        r = create_resource(
            transport=self.transport,
            payload=self.item_payload,
            url='',
            guess_token=False)
        self.assertTrue('resource_token' in r)
        self.assertTrue('field1' not in r)
        self.assertTrue('field1' in r.resource_token)

        r = create_resource(
            transport=self.transport,
            payload=self.list_payload,
            url='',
            guess_token=False)
        self.assertTrue('resource_token' in r)

    def test_item_construction(self) -> None:
        """Testing constructing an item resource"""
        r = create_resource(
            transport=self.transport,
            payload=self.item_payload,
            url='')
        self.assertTrue(isinstance(r, ItemResource))
        self.assertEqual(r.field1,
                         self.item_payload['resource_token']['field1'])
        self.assertEqual(r.field2,
                         self.item_payload['resource_token']['field2'])

    def test_list_construction(self) -> None:
        """Testing constructing a list resource"""
        r = create_resource(
            transport=self.transport,
            payload=self.list_payload,
            url='')
        self.assertTrue(isinstance(r, ListResource))

    def test_count_construction(self) -> None:
        """Testing constructing a count resource"""
        r = create_resource(
            transport=self.transport,
            payload=self.count_payload,
            url='')
        self.assertTrue(isinstance(r, CountResource))
        self.assertEqual(r.count, self.count_payload['count'])

    def test_resource_specific_base_class(self) -> None:
        """Testing constructing a resource with a specific base class"""
        r = create_resource(
            transport=self.transport,
            payload=self.root_payload,
            url='')
        self.assertFalse(isinstance(r, RootResource))

        r = create_resource(
            transport=self.transport,
            payload=self.root_payload,
            url='',
            mime_type='application/vnd.reviewboard.org.root+json')
        self.assertTrue(isinstance(r, RootResource))
