import unittest
import urllib2

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import json
except ImportError:
    import simplejson as json

from rbtools import postreview
from rbtools.api.errors import APIError
from rbtools.clients import RepositoryInfo
from rbtools.postreview import ReviewBoardServer


class MockHttpUnitTest(unittest.TestCase):
    deprecated_api = False

    def setUp(self):
        # Save the old http_get and http_post
        postreview.options = OptionsStub()

        self.saved_http_get = ReviewBoardServer.http_get
        self.saved_http_post = ReviewBoardServer.http_post

        self.server = ReviewBoardServer('http://localhost:8080/',
                                        RepositoryInfo(), None)
        ReviewBoardServer.http_get = self._http_method
        ReviewBoardServer.http_post = self._http_method

        self.server.deprecated_api = self.deprecated_api
        self.http_response = {}

    def tearDown(self):
        ReviewBoardServer.http_get = self.saved_http_get
        ReviewBoardServer.http_post = self.saved_http_post

    def _http_method(self, path, *args, **kwargs):
        if isinstance(self.http_response, dict):
            http_response = self.http_response[path]
        else:
            http_response = self.http_response

        if isinstance(http_response, Exception):
            raise http_response
        else:
            return http_response


class OptionsStub(object):
    def __init__(self):
        self.debug = True
        self.guess_summary = False
        self.guess_description = False
        self.tracking = None
        self.username = None
        self.password = None
        self.repository_url = None
        self.disable_proxy = False
        self.summary = None
        self.description = None


class ApiTests(MockHttpUnitTest):
    def setUp(self):
        super(ApiTests, self).setUp()

        self.http_response = {
            'api/': json.dumps({
                'stat': 'ok',
                'links': {
                    'info': {
                        'href': 'api/info/',
                        'method': 'GET',
                    },
                },
            }),
        }

    def test_check_api_version_1_5_2_higher(self):
        """Testing checking the API version compatibility (RB >= 1.5.2)"""
        self.http_response.update(self._build_info_resource('1.5.2'))
        self.server.check_api_version()
        self.assertFalse(self.server.deprecated_api)

        self.http_response.update(self._build_info_resource('1.5.3alpha0'))
        self.server.check_api_version()
        self.assertFalse(self.server.deprecated_api)

    def test_check_api_version_1_5_1_lower(self):
        """Testing checking the API version compatibility (RB < 1.5.2)"""
        self.http_response.update(self._build_info_resource('1.5.1'))
        self.server.check_api_version()
        self.assertTrue(self.server.deprecated_api)

    def test_check_api_version_old_api(self):
        """Testing checking the API version compatibility (RB < 1.5.0)"""
        self.http_response = {
            'api/': APIError(404, 0),
        }

        self.server.check_api_version()
        self.assertTrue(self.server.deprecated_api)

    def _build_info_resource(self, package_version):
        return {
            'api/info/': json.dumps({
                'stat': 'ok',
                'info': {
                    'product': {
                        'package_version': package_version,
                    },
                },
            }),
        }


class DeprecatedApiTests(MockHttpUnitTest):
    deprecated_api = True

    SAMPLE_ERROR_STR = json.dumps({
        'stat': 'fail',
        'err': {
            'code': 100,
            'msg': 'This is a test failure',
        }
    })

    def test_parse_get_error_http_200(self):
        self.http_response = self.SAMPLE_ERROR_STR

        try:
            self.server.api_get('/foo/')

            # Shouldn't be reached
            self._assert(False)
        except APIError, e:
            self.assertEqual(e.http_status, 200)
            self.assertEqual(e.error_code, 100)
            self.assertEqual(e.rsp['stat'], 'fail')
            self.assertEqual(
                str(e), 'This is a test failure (HTTP 200, API Error 100)')

    def test_parse_post_error_http_200(self):
        self.http_response = self.SAMPLE_ERROR_STR

        try:
            self.server.api_post('/foo/')

            # Shouldn't be reached
            self._assert(False)
        except APIError, e:
            self.assertEqual(e.http_status, 200)
            self.assertEqual(e.error_code, 100)
            self.assertEqual(e.rsp['stat'], 'fail')
            self.assertEqual(
                str(e), 'This is a test failure (HTTP 200, API Error 100)')

    def test_parse_get_error_http_400(self):
        self.http_response = self._make_http_error('/foo/', 400,
                                                   self.SAMPLE_ERROR_STR)

        try:
            self.server.api_get('/foo/')

            # Shouldn't be reached
            self._assert(False)
        except APIError, e:
            self.assertEqual(e.http_status, 400)
            self.assertEqual(e.error_code, 100)
            self.assertEqual(e.rsp['stat'], 'fail')
            self.assertEqual(
                str(e), 'This is a test failure (HTTP 400, API Error 100)')

    def test_parse_post_error_http_400(self):
        self.http_response = self._make_http_error('/foo/', 400,
                                                   self.SAMPLE_ERROR_STR)

        try:
            self.server.api_post('/foo/')

            # Shouldn't be reached
            self._assert(False)
        except APIError, e:
            self.assertEqual(e.http_status, 400)
            self.assertEqual(e.error_code, 100)
            self.assertEqual(e.rsp['stat'], 'fail')
            self.assertEqual(
                str(e), 'This is a test failure (HTTP 400, API Error 100)')

    def _make_http_error(self, url, code, body):
        return urllib2.HTTPError(url, code, body, {}, StringIO(body))
