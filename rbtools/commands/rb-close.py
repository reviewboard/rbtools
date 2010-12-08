import os
import sys

from rbtools.api.resource import Resource, RootResource, ReviewRequest
from rbtools.api.serverinterface import ServerInterface


def main():
    valid = False

    if len(sys.argv) > 2:
        cwd = os.getcwd()
        cookie = os.path.join(cwd, '.rb_cookie')
        server_url = 'http://demo.reviewboard.org/'
        resource_id = sys.argv[2]

        if resource_id.isdigit():
            if sys.argv[1] == '-s' or sys.argv[1] == '-d':
                valid = True
                server = ServerInterface(server_url, ".newstyle_cookie")
                root = RootResource(server, server_url + 'api/')
                review_requests = root.get('review_requests')
                review_request = \
                    ReviewRequest(review_requests.get(resource_id))

                if sys.argv[1] == '-s':
                    review_request.submit()
                else:
                    review_request.discard()

    if not valid:
        print "usage: rb close [-s|-d] <review_request_id>"

if __name__ == '__main__':
    main()
