import os
import sys
import urllib2

from rbtools.api.resource import Resource, RootResource, ReviewRequest
from rbtools.api.serverinterface import ServerInterface
from rbtools.api.settings import Settings


SUBMITTED_OPTION = '-s'
DISCARDED_OPTION = '-d'
SUBMITTED = 'submitted'
DISCARDED = 'discarded'


def close_type(option_type):
    if option_type == SUBMITTED_OPTION:
        return SUBMITTED
    else:
        return DISCARDED


def main():
    valid = False

    if len(sys.argv) > 2:
        settings = Settings(config_file='rb_scripts.dat')
        cookie = settings.get_cookie_file()
        server_url = settings.get_server_url()
        resource_id = sys.argv[2]

        if resource_id.isdigit():
            if sys.argv[1] == SUBMITTED_OPTION \
                or sys.argv[1] == DISCARDED_OPTION:
                valid = True
                server = ServerInterface(server_url, cookie)

                try:
                    root = RootResource(server, server_url + 'api/')
                    review_requests = root.get('review_requests')
                    review_request = \
                        ReviewRequest(review_requests.get(resource_id))

                    if sys.argv[1] == SUBMITTED_OPTION:
                        review_request.submit()
                    else:
                        review_request.discard()

                    print 'Successfully %s review request #%s' % \
                        (close_type(sys.argv[1]), resource_id)
                except urllib2.HTTPError, e:
                    print 'Close failed..  Make sure the resource exists on ' \
                          'the server and try again.'

    if not valid:
        print "usage: rb close [-s|-d] <review_request_id>"


if __name__ == '__main__':
    main()
