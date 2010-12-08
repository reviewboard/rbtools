import os
import sys

from rbtools.api.resource import Resource, RootResource, ReviewRequestDraft
from rbtools.api.serverinterface import ServerInterface
from rbtools.api.settings import Settings


def main():
    valid = False

    if len(sys.argv) > 1:
        settings = Settings(config_file='rb_scripts.dat')
        cookie = settings.get_cookie_file()
        server_url = settings.get_server_url()
        resource_id = sys.argv[1]

        if resource_id.isdigit():
            valid = True
            server = ServerInterface(server_url, cookie)
            root = RootResource(server, server_url + 'api/')
            review_requests = root.get('review_requests')
            review_request = review_requests.get(resource_id)
            review_request_draft = \
                ReviewRequestDraft(review_request.get_or_create('draft'))
            review_request_draft.publish()

    if not valid:
        print "usage: rb publish <review_request_id>"


if __name__ == '__main__':
    main()
