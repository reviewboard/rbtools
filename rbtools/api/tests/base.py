"""Base support for API unit tests."""

from __future__ import annotations

from typing import Dict, Optional, Union

from rbtools.api.transport import Transport
from rbtools.testing import TestCase


class MockResponse(object):
    """A mock up for a response from urllib2."""

    def __init__(
        self,
        code: int,
        headers: Dict[str, str],
        body: Union[bytes, str],
    ) -> None:
        """Create a new MockResponse."""
        if isinstance(body, str):
            body = body.encode('utf-8')

        self.code = code
        self.headers = headers
        self.body = body

        if self.body:
            self.headers['Content-Length'] = str(len(body))

            if 'Content-Type' not in self.headers:
                self.headers['Content-Type'] = 'text/plain'

    def info(self) -> Dict[str, str]:
        """Return the HTTP response headers."""
        return self.headers

    def read(self) -> bytes:
        """Return the HTTP response body."""
        return self.body

    def getcode(self) -> int:
        """Return the HTTP response code."""
        return self.code

    @property
    def status(self) -> int:
        """Return the HTTP response code."""
        return self.code


class MockTransport(Transport):
    """Mock transport which returns HttpRequests without executing them"""

    def __init__(self):
        pass

    def enable_cache(
        self,
        cache_location: Optional[str] = None,
        in_memory: bool = False,
    ) -> None:
        """Enable caching for all future HTTP requests.

        The cache will be created at the default location if none is provided.

        If the in_memory parameter is True, the cache will be created in memory
        instead of on disk. This overrides the cache_location parameter.

        Args:
            cache_location (str, optional):
                The filename to store the cache in, if using a persistent
                cache.

            in_memory (bool, optional):
                Whether to keep the cache data in memory rather than persisting
                to a file.
        """
        self.cache_enabled = True

    def disable_cache(self) -> None:
        """Disable the HTTP cache.

        Version Added:
            5.0
        """
        self.cache_enabled = False


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
            'extra_data': {
                'key1': 'value1',
                'key2': [1, 2, 3],
                'key3': {
                    'subkey': True,
                },
                'links': {
                    'test': {
                        'href': 'https://example.com/',
                        'method': 'POST',
                    },
                },
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
