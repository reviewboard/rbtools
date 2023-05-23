"""Unit tests for rbtools.api.errors."""

from __future__ import annotations

import os
import ssl
import sys
from ssl import SSLCertVerificationError, SSLContext, SSLError
from typing import Optional

import kgb

from rbtools.api.errors import (APIError,
                                AuthorizationError,
                                BadRequestError,
                                ServerInterfaceSSLError)
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


class ServerInterfaceSSLErrorTests(kgb.SpyAgency, TestCase):
    """Unit tests for ServerInterfaceSSLError.

    Version Added:
        4.1
    """

    ######################
    # Instance variables #
    ######################

    ssl_context: Optional[SSLContext]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ssl_context = ssl.create_default_context()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.ssl_context = None

        super().tearDownClass()

    def test_with_generic_ssl_error(self) -> None:
        """Testing ServerInterfaceSSLError with generic SSLError"""
        self._test_ssl_error(
            host='example.com',
            reason='SOME_REASON',
            error_message='something went wrong',
            expected_message=(
                'An expected SSL error occurred when communicating with '
                '"example.com": [SSL: SOME_REASON] something went wrong '
                '(_ssl.c:123)'
            ))

    def test_with_handshake_failure(self) -> None:
        """Testing ServerInterfaceSSLError with SSL handshake failure"""
        self._test_ssl_error(
            host='tls-v1-0.badssl.com',
            port=1010,
            reason='SSLV3_ALERT_HANDSHAKE_FAILURE',
            error_message='sslv3 alert handshake failure',
            expected_message=(
                'The server on "tls-v1-0.badssl.com" is using a TLS '
                'protocol or cipher suite that your version of Python does '
                'not support. You may need to upgrade Python, or contact '
                'your Review Board administrator for further assistance.'
            ))

    def test_with_expired_or_revoked_cert(self) -> None:
        """Testing ServerInterfaceSSLError with expired or revoked cert"""
        self._test_cert_error(
            host='expired.badssl.com',
            verify_code=10,
            verify_message='certificate has expired',
            expected_message=(
                'The SSL certificate used for "expired.badssl.com" has '
                'expired or has been revoked. Contact your Review Board '
                'administrator for further assistance.'
            ))

    def test_with_self_signed_cert(self) -> None:
        """Testing ServerInterfaceSSLError with self-signed cert"""
        self._test_cert_error(
            host='self-signed.badssl.com',
            verify_code=18,
            verify_message='self-signed certificate',
            shows_cert_paths=True,
            expected_message=(
                'The SSL certificate used for "self-signed.badssl.com" is '
                'self-signed and cannot currently be verified by RBTools.\n'
                '\n'
                'Make sure any necessary certificates in the chain are '
                'placed in one of the following locations:\n'
                '\n'
                '    * /path/to/cafile.pem\n'
                '    * /path/to/capath\n'
                '    * /path/to/env/cafile.pem\n'
                '    * /path/to/env/capath\n'
                '    * /path/to/openssl/cafile.pem\n'
                '    * /path/to/openssl/capath\n'
                '\n'
                'You may need to update your root SSL certificates for '
                'RBTools by running:\n'
                '\n'
                '    %s -m pip install -U certifi'
                % sys.executable
            ))

    def test_with_untrusted_root_cert(self) -> None:
        """Testing ServerInterfaceSSLError with untrusted root cert"""
        self._test_cert_error(
            host='untrusted-root.badssl.com',
            verify_code=19,
            verify_message='self-signed certificate in certificate chain',
            shows_cert_paths=True,
            expected_message=(
                'The SSL certificate used for "untrusted-root.badssl.com" has '
                'an untrusted or self-signed root certificate that cannot '
                'currently be verified by RBTools.\n'
                '\n'
                'Make sure any necessary certificates in the chain are '
                'placed in one of the following locations:\n'
                '\n'
                '    * /path/to/cafile.pem\n'
                '    * /path/to/capath\n'
                '    * /path/to/env/cafile.pem\n'
                '    * /path/to/env/capath\n'
                '    * /path/to/openssl/cafile.pem\n'
                '    * /path/to/openssl/capath\n'
                '\n'
                'You may need to update your root SSL certificates for '
                'RBTools by running:\n'
                '\n'
                '    %s -m pip install -U certifi'
                % sys.executable
            ))

    def test_with_no_local_issue_cert(self) -> None:
        """Testing ServerInterfaceSSLError without local issue cert"""
        self._test_cert_error(
            host='incomplete-chain.badssl.com',
            verify_code=20,
            verify_message='unable to get local issuer certificate',
            shows_cert_paths=True,
            expected_message=(
                'The SSL certificate used for "incomplete-chain.badssl.com" '
                'has an untrusted or self-signed certificate in the chain '
                'that cannot currently be verified by RBTools.\n'
                '\n'
                'Make sure any necessary certificates in the chain are '
                'placed in one of the following locations:\n'
                '\n'
                '    * /path/to/cafile.pem\n'
                '    * /path/to/capath\n'
                '    * /path/to/env/cafile.pem\n'
                '    * /path/to/env/capath\n'
                '    * /path/to/openssl/cafile.pem\n'
                '    * /path/to/openssl/capath\n'
                '\n'
                'You may need to update your root SSL certificates for '
                'RBTools by running:\n'
                '\n'
                '    %s -m pip install -U certifi'
                % sys.executable
            ))

    def test_with_hostname_mismatch(self) -> None:
        """Testing ServerInterfaceSSLError with hostname mismatch"""
        self._test_cert_error(
            host='wrong.host.badssl.com',
            verify_code=62,
            verify_message=(
                "Hostname mismatch, certificate is not valid for "
                "'wrong.host.badssl.com'."
            ),
            shows_cert_paths=True,
            expected_message=(
                'The SSL certificate is not valid for '
                '"wrong.host.badssl.com". Make sure you are connecting to '
                'the correct host. Contact your Review Board administrator '
                'for further assistance.'
            ))

    def _test_ssl_error(
        self,
        *,
        host: str,
        reason: str,
        error_message: str,
        expected_message: str,
        port: int = 443,
    ) -> None:
        """Test the SSL error for the given criteria.

        Args:
            host (str):
                The host the test will connect to, or simulate connecting to.

            port (int, optional):
                The port to connect to.

            reason (str):
                The reason value for the error.

            error_message (str):
                The error message to show after the reason code.

            expected_message (str):
                The expected error message from the exception.

        Raises:
            AssertionError:
                One of the expectations failed.
        """
        assert self.ssl_context

        e = SSLError(
            1,
            f'[SSL: {reason}] {error_message} (_ssl.c:123)')
        e.reason = reason

        error = ServerInterfaceSSLError(
            host=host,
            port=port,
            ssl_error=e,
            ssl_context=self.ssl_context)

        self.assertEqual(str(error), expected_message)

    def _test_cert_error(
        self,
        *,
        host: str,
        verify_code: int,
        verify_message: str,
        expected_message: str,
        shows_cert_paths: bool = False,
    ) -> None:
        """Test the SSL certificate error for the given criteria.

        Args:
            host (str):
                The host the test will connect to, or simulate connecting to.

            verify_code (int):
                The value to set for the ``verify_code`` state on the SSL
                error.

            verify_message (str):
                The value to set for the ``verify_message`` state on the SSL
                error.

            expected_message (str):
                The expected error message from the exception.

            shows_cert_paths (bool):
                Whether the error message is expected to list SSL certificate
                paths.

        Raises:
            AssertionError:
                One of the expectations failed.
        """
        assert self.ssl_context

        if shows_cert_paths:
            self.spy_on(ssl.get_default_verify_paths, op=kgb.SpyOpReturn(
                ssl.DefaultVerifyPaths(
                    cafile='/path/to/cafile.pem',
                    capath='/path/to/capath',
                    openssl_cafile_env='SSL_CERT_FILE',
                    openssl_cafile='/path/to/openssl/cafile.pem',
                    openssl_capath_env='SSL_CERT_PATH',
                    openssl_capath='/path/to/openssl/capath')))

        old_cert_file_env = os.environ.get('SSL_CERT_FILE')
        old_cert_path_env = os.environ.get('SSL_CERT_PATH')

        os.environ['SSL_CERT_FILE'] = '/path/to/env/cafile.pem'
        os.environ['SSL_CERT_PATH'] = '/path/to/env/capath'

        try:
            e = SSLCertVerificationError(
                1,
                f'[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: '
                f'{verify_message} (_ssl.c:123)')
            e.verify_code = verify_code
            e.verify_message = verify_message

            error = ServerInterfaceSSLError(
                host=host,
                port=443,
                ssl_error=e,
                ssl_context=self.ssl_context)

            self.assertEqual(str(error), expected_message)
        finally:
            if old_cert_file_env:
                os.environ['SSL_CERT_FILE'] = old_cert_file_env
            else:
                del os.environ['SSL_CERT_FILE']

            if old_cert_path_env:
                os.environ['SSL_CERT_PATH'] = old_cert_path_env
            else:
                del os.environ['SSL_CERT_PATH']
