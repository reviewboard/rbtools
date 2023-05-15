"""Unit tests for rbtools.api.errors."""

from rbtools.api.errors import APIError, AuthorizationError, BadRequestError
from rbtools.testing import TestCase


class APIErrorTests(TestCase):
    """Unit tests for rbtools.api.errors.APIError."""

    def test_str_with_http_status(self):
        """Testing APIError.__str__ with http_status"""
        self.assertEqual(
            str(APIError(http_status=500)),
            'An error occurred when communicating with Review Board. '
            '(HTTP 500: Internal Server Error)')

    def test_str_with_http_status_unknown(self):
        """Testing APIError.__str__ with unknown http_status"""
        self.assertEqual(
            str(APIError(http_status=900)),
            'An error occurred when communicating with Review Board. '
            '(HTTP 900)')

    def test_str_with_error_code(self):
        """Testing APIError.__str__ with error_code"""
        self.assertEqual(
            str(APIError(error_code=105)),
            'An error occurred when communicating with Review Board. '
            '(API Error 105: Invalid Form Data)')

    def test_str_with_error_code_unknown(self):
        """Testing APIError.__str__ with unknown error_code"""
        self.assertEqual(
            str(APIError(error_code=12345)),
            'An error occurred when communicating with Review Board. '
            '(API Error 12345)')

    def test_str_with_http_status_and_error_code(self):
        """Testing APIError.__str__ with http_status and error_code"""
        self.assertEqual(
            str(APIError(http_status=400,
                                   error_code=106)),
            'An error occurred when communicating with Review Board. '
            '(API Error 106: Missing Attribute)')

    def test_str_with_rsp(self):
        """Testing APIError.__str__ with rsp error message"""
        self.assertEqual(
            str(APIError(rsp={
                'err': {
                    'msg': 'Bad things happened.',
                },
            })),
            'Bad things happened.')

    def test_str_with_rsp_and_error_code(self):
        """Testing APIError.__str__ with rsp error message and error_code"""
        self.assertEqual(
            str(APIError(
                http_status=400,
                error_code=106,
                rsp={
                    'err': {
                        'msg': 'Bad things happened.',
                    },
                })),
            'Bad things happened. (API Error 106: Missing Attribute)')

    def test_str_with_rsp_and_http_status(self):
        """Testing APIError.__str__ with rsp error message and http_status"""
        self.assertEqual(
            str(APIError(
                http_status=400,
                rsp={
                    'err': {
                        'msg': 'Bad things happened.',
                    },
                })),
            'Bad things happened. (HTTP 400: Bad Request)')

    def test_str_with_no_details(self):
        """Testing APIError.__str__ without any details"""
        self.assertEqual(
            str(APIError()),
            'An error occurred when communicating with Review Board.')


class AuthorizationErrorTests(TestCase):
    """Unit tests for rbtools.api.errors.AuthorizationError."""

    def test_str_with_message(self):
        """Testing AuthorizationError.__str__ with explicit error message"""
        self.assertEqual(
            str(AuthorizationError(message='Oh no.')),
            'Oh no.')

    def test_str_with_details(self):
        """Testing AuthorizationError.__str__ without explicit error message,
        with HTTP details
        """
        self.assertEqual(
            str(AuthorizationError(http_status=401,
                                   error_code=104)),
            'Error authenticating to Review Board. (API Error 104: '
            'Login Failed)')

    def test_str_without_message_or_details(self):
        """Testing AuthorizationError.__str__ without explicit error message
        or HTTP details
        """
        self.assertEqual(
            str(AuthorizationError()),
            'Error authenticating to Review Board.')


class BadRequestErrorTests(TestCase):
    """Unit tests for rbtools.api.errors.BadRequestError."""

    def test_str(self):
        """Testing BadRequestError.__str__"""
        self.assertEqual(
            str(BadRequestError()),
            'Missing or invalid data was sent to Review Board.')

    def test_str_with_error_code(self):
        """Testing BadRequestError.__str__"""
        self.assertEqual(
            str(BadRequestError(error_code=200)),
            'Missing or invalid data was sent to Review Board. '
            '(API Error 200: Unspecified Diff Revision)')

    def test_str_with_rsp_error_message(self):
        """Testing BadRequestError.__str__ with rsp error message"""
        self.assertEqual(
            str(BadRequestError(
                error_code=200,
                rsp={
                    'err': {
                        'msg': 'Diff revision not specified.',
                    },
                })),
            'Diff revision not specified. (API Error 200: Unspecified Diff '
            'Revision)')

    def test_str_with_message(self):
        """Testing BadRequestError.__str__ with message"""
        self.assertEqual(
            str(BadRequestError(
                error_code=200,
                message='Diff revision not specified.')),
            'Diff revision not specified. (API Error 200: Unspecified Diff '
            'Revision)')

    def test_str_with_message_with_fields(self):
        """Testing BadRequestError.__str__ with fields"""
        self.assertEqual(
            str(BadRequestError(
                error_code=105,
                rsp={
                    'err': {
                        'msg': 'One or more fields had errors',
                    },
                    'fields': {
                        'field1': ['This field was invalid'],
                        'field2': ['This one, too', 'So invalid'],
                    },
                })),
            'One or more fields had errors (API Error 105: Invalid Form '
            'Data)\n'
            '\n'
            '    field1: This field was invalid\n'
            '    field2: This one, too; So invalid')
