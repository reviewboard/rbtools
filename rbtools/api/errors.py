from __future__ import unicode_literals

import six

from rbtools.utils.encoding import force_unicode


HTTP_STATUS_CODES = {
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',
    103: 'Early Hints',
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi-Status',
    208: 'Already Reported',
    226: 'IM Used',
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    306: 'Switch Proxy',
    307: 'Temporary Redirect',
    308: 'Permanent Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    418: "I'm a teapot",
    421: 'Misdirected Request',
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    425: 'Unordered Collection',
    426: 'Upgrade Required',
    428: 'Precondition Required',
    429: 'Too Many Requests',
    431: 'Request Header Fields Too Large',
    444: 'No Response',
    449: 'Retry With',
    450: 'Blocked by Windows Parental Controls',
    451: 'Unavailable For Legal Reasons',
    499: 'Client Closed Request',
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    506: 'Variant Also Negotiates',
    507: 'Insufficient Storage',
    508: 'Loop Detected',
    509: 'Bandwidth Limit Exceeded',
    510: 'Not Extended',
    511: 'Network Authentication Required',
    598: 'Network Read Timeout Error',
    599: 'Network Connect Timeout Error',
}


API_ERROR_CODES = {
    0: 'No Error',
    1: 'Service Not Configured',
    100: 'Does Not Exist',
    101: 'Permission Denied',
    102: 'Invalid Attribute',
    103: 'Not Logged In',
    104: 'Login Failed',
    105: 'Invalid Form Data',
    106: 'Missing Attribute',
    107: 'Enable Extension Failed',
    108: 'Disable Extension Failed',
    109: 'Extension Already Installed',
    110: 'Extension Install Failed',
    111: 'Duplicate Item',
    112: 'OAuth Scope Missing',
    113: 'OAuth Token Access Denied',
    114: 'API Rate Limit Exceeded',
    200: 'Unspecified Diff Revision',
    201: 'Invalid Diff Revision',
    202: 'Invalid Action Specified',
    203: 'Invalid Commit ID',
    204: 'Commit ID In Use',
    205: 'Missing Repository',
    206: 'Invalid Repository',
    207: 'Repository File Not Found',
    208: 'Invalid User',
    209: 'Repository Operation Not Implemented',
    210: 'Repository Information Error',
    211: 'Nothing To Publish',
    212: 'Empty Changeset',
    213: 'Server Configuration Error',
    214: 'Bad Host Key',
    215: 'Unverified Host Key',
    216: 'Unverified Host Certificate',
    217: 'Missing User Key',
    218: 'Repository Authentication Failed',
    219: 'Empty Diff',
    220: 'Diff Too Big',
    221: 'File Retrieval Failed',
    222: 'Hosting Service Authentication Failed',
    223: 'Group Already Exists',
    224: 'Diff Parsing Failed',
    225: 'Publish Failed',
    226: 'User Query Failed',
    227: 'Commit ID Already Exists',
    228: 'API Token Generation Failed',
    229: 'Repository Already Exists',
    230: 'Close Review Request Failed',
    231: 'Reopen Review Request Failed',
    232: 'Revoke Ship-It Failed',
    233: 'Server Is Read Only',
}


class APIError(Exception):
    """An error communicating with the API.

    Attributes:
        error_code (int):
            The API error code. This may be ``None``.

        http_status (int):
            The HTTP status code.

        message (unicode):
            The error message from the API response. This may be ``None``.

            Version Added:
                3.1

        rsp (dict):
            The API response payload. This may be ``None``.
    """

    #: The default error message used if a specific error is not available.
    #:
    #: Version Added:
    #:     3.1
    #:
    #: Type:
    #:     unicode
    default_message = 'An error occurred when communicating with Review Board.'

    def __init__(self, http_status=None, error_code=None, rsp=None,
                 message=None, *args, **kwargs):
        """Initialize the error.

        Args:
            http_status (int, optional):
                The HTTP status code associated with this error.

                Version Changed:
                    3.1:
                    This is now optional.

            error_code (int, optional):
                The API error code associated with this error.

                Version Changed:
                    3.1:
                    This is now optional.

            rsp (dict, optional):
                The API response payload. This may be ``None`` for non-API
                Error payloads.

            message (unicode, optional):
                A specific error message to use. This will take precedence
                over any errors in ``rsp``.

                Version Added:
                    3.1

            *args (tuple):
                Extra positional arguments to pass to the base constructor.

            **kwargs (dict):
                Extra keyword arguments to pass to the base constructor.
        """
        Exception.__init__(self, *args, **kwargs)
        self.http_status = http_status
        self.error_code = error_code
        self.rsp = rsp

        if rsp and not message:
            try:
                message = rsp['err']['msg']
            except KeyError:
                message = None

        self.message = message or self.default_message

    def __str__(self):
        """Return a string representation of the error.

        The explicit :py:attr:`message` passed to the constructor will be
        used if provided. If not provided, this will fall back to the
        message in the :py:attr:`rsp` payload, or to
        :py:attr:`default_message`.

        If an API error code is available, it will be included in the message.
        If one is not provided, but an HTTP status is available, then it will
        be included instead.

        Returns:
            unicode:
            The error message.
        """
        http_status = self.http_status
        error_code = self.error_code

        details = None

        if self.error_code is not None:
            error_name = API_ERROR_CODES.get(error_code)
            details = 'API Error %s' % error_code

            if error_name:
                details = '%s: %s' % (details, error_name)
        elif http_status is not None:
            http_status_name = HTTP_STATUS_CODES.get(http_status)
            details = 'HTTP %s' % http_status

            if http_status_name:
                details = '%s: %s' % (details, http_status_name)

        message = self.message

        if details:
            message = '%s (%s)' % (message, details)

        return message


class AuthorizationError(APIError):
    """Authorization error when communicating with the API."""

    default_message = 'Error authenticating to Review Board.'


class BadRequestError(APIError):
    """Bad request data made to an API."""

    default_message = 'Missing or invalid data was sent to Review Board.'

    def __str__(self):
        """Return a string representation of the error.

        If the payload contains a list of fields, the error associated with
        each field will be included.

        Returns:
            unicode:
            The error message.
        """
        lines = [super(BadRequestError, self).__str__()]

        if self.rsp and 'fields' in self.rsp:
            lines.append('')

            for field, error in sorted(six.iteritems(self.rsp['fields']),
                                       key=lambda pair: pair[0]):
                lines.append('    %s: %s' % (field, '; '.join(error)))

        return '\n'.join(lines)


class CacheError(Exception):
    """An exception for caching errors."""


class ServerInterfaceError(Exception):
    def __init__(self, msg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.msg = msg

    def __str__(self):
        """Return the error message as a unicode string.

        Returns:
            unicode:
            The error message as a unicode string.
        """
        return force_unicode(self.msg)


API_ERROR_TYPE = {
    400: BadRequestError,
    401: AuthorizationError,
}


def create_api_error(http_status, *args, **kwargs):
    error_type = API_ERROR_TYPE.get(http_status, APIError)
    return error_type(http_status, *args, **kwargs)
