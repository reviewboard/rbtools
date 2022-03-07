"""Unit tests for rbtools.utils.repository."""

from __future__ import unicode_literals

import json

import kgb
from six.moves.urllib.request import urlopen

from rbtools.api.client import RBClient
from rbtools.api.tests.base import MockResponse
from rbtools.testing import TestCase
from rbtools.utils.repository import get_repository_resource


_REPO1 = {
    'id': 1,
    'name': 'Git Repo 1',
    'path': 'git@example.com:test.git',
    'mirror_path': 'https://example.com/test3.git',
    'links': {
        'info': {
            'href': 'http://localhost:8080/api/repositories/1/info/',
            'method': 'GET',
        },
    },
}


_REPO2 = {
    'id': 2,
    'name': 'Git Repo 2',
    'path': 'https://git@example.com/test2.git',
    'mirror_path': 'git@example.com:test2.git',
    'links': {
        'info': {
            'href': 'http://localhost:8080/api/repositories/2/info/',
            'method': 'GET',
        },
    },
}

_REPO3 = {
    'id': 3,
    'name': 'Git Repo 3',
    'path': 'https://git@example.com/test3.git',
    'mirror_path': '',
    'links': {
        'info': {
            'href': 'http://localhost:8080/api/repositories/3/info/',
            'method': 'GET',
        },
    },
}


_MATCH_URL_BASE = (
    'http://localhost:8080/api/repositories/?'
    'only-fields=id%2Cname%2Cmirror_path%2Cpath&only-links=info'
)


class RepositoryMatchTests(kgb.SpyAgency, TestCase):
    """Unit tests for remote repository matching."""

    payloads = {
        'http://localhost:8080/api/': {
            'mimetype': 'application/vnd.reviewboard.org.root+json',
            'rsp': {
                'uri_templates': {},
                'links': {
                    'self': {
                        'href': 'http://localhost:8080/api/',
                        'method': 'GET',
                    },
                    'repositories': {
                        'href': 'http://localhost:8080/api/repositories/',
                        'method': 'GET',
                    },
                },
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE +
            '&path=git%40example.com%3Atest.git'): {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [_REPO1],
                'links': {},
                'total_results': 1,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE +
            '&path=git%40example.com%3Atest2.git'): {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [_REPO2],
                'links': {},
                'total_results': 1,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE +
            '&path=http%3A%2F%2Fexample.com%2Ftest3.git'): {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [_REPO1, _REPO3],
                'links': {},
                'total_results': 2,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE +
            '&path=git%40example.com%3Atest4.git'): {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [],
                'links': {},
                'total_results': 0,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE): {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [
                    _REPO1,
                    _REPO2,
                ],
                'links': {},
                'total_results': 2,
                'stat': 'ok',
            },
        },
    }

    def setUp(self):
        super(RepositoryMatchTests, self).setUp()

        @self.spy_for(urlopen)
        def _urlopen(url, **kwargs):
            url = url.get_full_url()

            try:
                payload = self.payloads[url]
            except KeyError:
                print('Test requested unexpected URL "%s"' % url)

                return MockResponse(404, {}, json.dumps({
                    'rsp': {
                        'stat': 'fail',
                        'err': {
                            'code': 100,
                            'msg': 'Object does not exist',
                        },
                    },
                }))

            return MockResponse(
                200,
                {
                    'Content-Type': payload['mimetype'],
                },
                json.dumps(payload['rsp']))

        self.api_client = RBClient('http://localhost:8080/')
        self.root_resource = self.api_client.get_root()

    def test_find_matching_server_repository_with_path_match(self):
        """Testing get_repository_resource with path match"""
        repository, info = get_repository_resource(
            self.root_resource,
            repository_paths='git@example.com:test.git')
        self.assertEqual(repository.id, 1)

    def test_find_matching_server_repository_with_mirror_path_match(self):
        """Testing get_repository_resource with mirror path match"""
        repository, info = get_repository_resource(
            self.root_resource,
            repository_paths='git@example.com:test2.git')
        self.assertEqual(repository.id, 2)

    def test_find_matching_server_repository_with_multiple_matches(self):
        """Testing get_repository_resource with multiple matching paths"""
        repository, info = get_repository_resource(
            self.root_resource,
            repository_paths='http://example.com/test3.git')
        self.assertEqual(repository.id, 1)

    def test_find_matching_server_repository_no_match(self):
        """Testing get_repository_resource with no match"""
        repository, info = get_repository_resource(
            self.root_resource,
            repository_paths='git@example.com:test4.git')
        self.assertIsNone(repository)
        self.assertIsNone(info)
