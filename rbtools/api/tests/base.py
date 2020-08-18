"""Base support for API unit tests."""

from __future__ import unicode_literals

from rbtools.api.transport import Transport
from rbtools.testing import TestCase


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
                'title': 'Link Field',
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
                'name': 'testname1',
                'path': 'testpath1',
                'tool': 'Git',
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
                'name': 'testname2',
                'path': 'testpath2',
                'tool': 'Git',
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

    list_payload_no_repos = {
        'resource_token': [],
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
        'stat': 'ok',
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
            'repositories': {
                'href': 'http://localhost:8080/api/repositories/',
                'method': 'GET',
            }
        },
        'stat': 'ok',
    }
