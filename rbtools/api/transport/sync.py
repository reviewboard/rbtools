import logging

from rbtools.api.decode import decode_response
from rbtools.api.factory import create_resource
from rbtools.api.request import HttpRequest, ReviewBoardServer
from rbtools.api.transport import Transport


class SyncTransport(Transport):
    """A synchronous transport layer for the API client.

    The file provided in cookie_file is used to store and retrieve
    the authentication cookies for the API.

    The optional agent parameter can be used to specify a custom
    User-Agent string for the API. If not provided, the default
    RBTools User-Agent will be used.

    The optional session can be used to specify an 'rbsessionid'
    to use when authenticating with reviewboard.
    """
    def __init__(self, url, cookie_file=None, username=None, password=None,
                 api_token=None, agent=None, session=None, disable_proxy=False,
                 auth_callback=None, otp_token_callback=None, verify=None,
                 *args, **kwargs):
        super(SyncTransport, self).__init__(url, *args, **kwargs)
        self.server = ReviewBoardServer(self.url,
                                        cookie_file=cookie_file,
                                        username=username,
                                        password=password,
                                        api_token=api_token,
                                        session=session,
                                        disable_proxy=disable_proxy,
                                        auth_callback=auth_callback,
                                        otp_token_callback=otp_token_callback,
                                        verify=verify)

    def get_root(self):
        return self._execute_request(HttpRequest(self.server.url))

    def get_path(self, path, *args, **kwargs):
        if not path.endswith('/'):
            path = path + '/'

        if path.startswith('/'):
            path = path[1:]

        return self._execute_request(
            HttpRequest(self.server.url + path, query_args=kwargs))

    def get_url(self, url, *args, **kwargs):
        if not url.endswith('/'):
            url = url + '/'

        return self._execute_request(HttpRequest(url, query_args=kwargs))

    def login(self, username, password):
        self.server.login(username, password)

    def execute_request_method(self, method, *args, **kwargs):
        request = method(*args, **kwargs)

        if isinstance(request, HttpRequest):
            return self._execute_request(request)

        return request

    def _execute_request(self, request):
        """Execute an HTTPRequest and construct a resource from the payload"""
        logging.debug('Making HTTP %s request to %s' % (request.method,
                                                        request.url))

        rsp = self.server.make_request(request)
        info = rsp.info()
        mime_type = info['Content-Type']
        item_content_type = info.get('Item-Content-Type', None)

        if request.method == 'DELETE':
            # DELETE calls don't return any data. Everything else should.
            return None
        else:
            payload = rsp.read()
            payload = decode_response(payload, mime_type)

            return create_resource(self, payload, request.url,
                                   mime_type=mime_type,
                                   item_mime_type=item_content_type)

    def __repr__(self):
        return '<%s(url=%r, cookie_file=%r, agent=%r)>' % (
            self.__class__.__name__,
            self.url,
            self.server.cookie_file,
            self.server.agent)
