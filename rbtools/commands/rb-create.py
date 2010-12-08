import os
import sys

from rbtools.api.resource import Resource, ResourceList
from rbtools.api.serverinterface import ServerInterface


def main(params):
    valid = False

    print "TO DO"
    """
    if len(sys.argv) > 1:
        cwd = os.getcwd()
        cookie = os.path.join(cwd, '.rb_cookie')
        server_url = 'http://demo.reviewboard.org/'
        resource_id = params[0]

        server = ServerInterface(server_url, cookie)

        if server.login():
            root = ResourceList(server, server_url + 'api/')
            review_requests = root.get('review_requests')
            review_request = review_requests.get(resource_id)
            review_request_draft = review_request.get_or_create('draft')
            review_request_draft.publish()
        else:
            print "Could not login"
    """

    if not valid:
        print "usage: rb create ..."

if __name__ == '__main__':
    main()
