import os
import re
import sys
import urllib2

from rbtools.api.resource import Resource, RootResource, ReviewRequestDraft
from rbtools.api.serverinterface import ServerInterface
from rbtools.clients.getclient import get_client


def main():
    valid = False

    if len(sys.argv) > 2:
        cwd = os.getcwd()
        cookie = os.path.join(cwd, '.rb_cookie')
        server_url = 'http://demo.reviewboard.org/'
        resource_id = sys.argv[2]

        if resource_id.isdigit():
            m = re.match('--screen-shot:', sys.argv[1])
            if m:
                file_name = re.split('--screen-shot:', sys.argv[1])[1]
                valid = True
                ss_file = open('%s' % file_name, 'r')
                ss_data = {
                    'filename': os.path.split(file_name)[1],
                    'content': ss_file.read()
                }

                try:
                    server = ServerInterface(server_url, cookie)
                    root = RootResource(server, server_url + 'api/')
                    review_requests = root.get('review_requests')
                    review_request = review_requests.get(resource_id)
                    sss = review_request.get_or_create('screenshots')
                    ss = sss.create()
                    ss.update_file('path', ss_data)

                    if len(sys.argv) > 3:
                        ss.update_field('caption', sys.argv[3])

                    ss.save()
                    review_request_draft = \
                        ReviewRequestDraft(
                        review_request.get_or_create('draft'))
                    review_request_draft.publish()
                    print "Request complete.  See: %s" % review_request.url
                except urllib2.HTTPError, e:
                    if e.code == 500:
                        print "There was an internal server error.  Please "
                        print "try your request again."
                    else:
                        print "The request failed for an unknown reason."

    if not valid:
        print "usage: rb upload ..."
        print ""
        print "Currently only supports uploading a screenshot to a review "
        print "request.  You may do this by following this format:"
        print ""
        print "rb upload --screen-shot:file_path_and_name review_request_id "
        print "          [caption]"

if __name__ == '__main__':
    main()
