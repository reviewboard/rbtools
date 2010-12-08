import os
import re
import sys
import urllib2

from rbtools.api.resource import Resource, RootResource, ReviewRequestDraft
from rbtools.api.serverinterface import ServerInterface
from rbtools.api.settings import Settings
from rbtools.clients.getclient import get_client


SCREENSHOT_OPTION = '-ss'
DIFF_OPTION = '-diff'
FILE_TYPES = [
    SCREENSHOT_OPTION,
    DIFF_OPTION,
]        

def main():
    valid = False

    if len(sys.argv) > 2:
        settings = Settings(config_file='rb_scripts.dat')
        cookie = settings.get_cookie_file()
        server_url = settings.get_server_url()
        resource_id = sys.argv[2]

        if resource_id.isdigit():
            split = re.split(':', sys.argv[1])
            file_type = split[0]
            file_name = split[1]

            if file_type and file_name:
                if file_type == SCREENSHOT_OPTION \
                    or file_type == DIFF_OPTION:
                    valid = True
                    server = ServerInterface(server_url, cookie)
                    root = RootResource(server, server_url + 'api/')
                    review_requests = root.get('review_requests')
                    review_request = review_requests.get(resource_id)
                    m = re.match(SCREENSHOT_OPTION, file_type)

                    try:
                        if m:
                            # Screenshot
                            ss_file = open('%s' % file_name, 'r')
                            ss_data = {
                                'filename': os.path.split(file_name)[1],
                                'content': ss_file.read()
                            }

                            sss = review_request.get_or_create('screenshots')
                            ss = sss.create()
                            ss.update_file('path', ss_data)

                            if len(sys.argv) > 3:
                                i = 3

                                while i < len(sys.argv):
                                    split = re.split(':', sys.argv[i])
                                    ss.update_field(split[0], split[1])
                                    i = i + 1

                            ss.save()
                        else:
                            # Diff
                            diff_file = open(file_name, 'r')
                            diff_data = {
                                'filename': file_name,
                                'content': diff_file.read()
                            }
                            diff_file.close()
                            diffs = review_request.get_or_create('diffs')
                            resource_diff = diffs.create()
                            resource_diff.update_file('path', diff_data)
                            resource_diff.save()

                        review_request_draft = \
                            ReviewRequestDraft(
                            review_request.get_or_create('draft'))
                        review_request_draft.publish()
                        print "Request complete.  See: %s" % review_request.url
                    except urllib2.HTTPError, e:
                        if e.code == 500:
                            print "There was an internal server error."
                            print "Please try your request again."
                        else:
                            print "The request failed."
                            print e.read()
                            raise e

    if not valid:
        print "usage: rb upload -file_type:file_name review_request_id " \
              "[field_name:field_value] .. [field_name:field_value]"
        print ""
        print "file_types:"
        for n in FILE_TYPES:
            print "    %s" % n


if __name__ == '__main__':
    main()
