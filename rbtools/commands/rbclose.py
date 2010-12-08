import os

from rbtools.api.resource import Resource, ResourceList
from rbtools.api.serverinterface import ServerInterface


def main(params):
    if len(params) > 0:
        cwd = os.getcwd()
        cookie = os.path.join(cwd, '.rb_api_cookie')
        server_url = 'http://demo.reviewboard.org/'
        resource_id = params[0]

        server = ServerInterface(server_url, cookie)

        if server.login():
            root = ResourceList(server, server_url + 'api/')
            review_requests = root.get('review_requests')
            review_request = review_requests.get(resource_id)
            review_request.close()
        else:
            print "Could not login"
    else:
        print "Command requires a parameter"
