from __future__ import unicode_literals

import six


class APIError(Exception):
    def __init__(self, http_status, error_code, rsp=None, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.http_status = http_status
        self.error_code = error_code
        self.rsp = rsp

    def __str__(self):
        code_str = 'HTTP %d' % self.http_status

        if self.error_code:
            code_str += ', API Error %d' % self.error_code

        if self.rsp and 'err' in self.rsp:
            return '%s (%s)' % (self.rsp['err']['msg'], code_str)
        else:
            return code_str


class AuthorizationError(APIError):
    pass


class BadRequestError(APIError):
    def __str__(self):
        lines = [super(BadRequestError, self).__str__()]

        if self.rsp and 'fields' in self.rsp:
            lines.append('')

            for field, error in six.iteritems(self.rsp['fields']):
                lines.append('    %s: %s' % (field, '; '.join(error)))

        return '\n'.join(lines)


class CacheError(Exception):
    """An exception for caching errors."""


class ServerInterfaceError(Exception):
    def __init__(self, msg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.msg = msg

    def __str__(self):
        return self.msg


API_ERROR_TYPE = {
    400: BadRequestError,
    401: AuthorizationError,
}


def create_api_error(http_status, *args, **kwargs):
    error_type = API_ERROR_TYPE.get(http_status, APIError)
    return error_type(http_status, *args, **kwargs)
