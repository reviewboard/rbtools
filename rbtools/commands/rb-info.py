import os
import re
import sys

from rbtools.api.resource import Resource, RootResource, ReviewRequest
from rbtools.api.serverinterface import ServerInterface

INFO = 'info'
USER = 'usr'
ROOT = 'root'
REPOSITORY = 'repo'
SESSION = 'sess'
GROUP = 'grp'
REVIEW_REQUEST = 'rr'
RESOURCE_NAMES = [INFO, USER, ROOT, REPOSITORY, SESSION, GROUP, REVIEW_REQUEST]


def main():
    valid = False
    resource_map = {}
    resource_map[INFO] = 'info'
    resource_map[USER] = 'users'
    resource_map[ROOT] = 'self'
    resource_map[REPOSITORY] = 'repositories'
    resource_map[SESSION] = 'session'
    resource_map[GROUP] = 'groups'
    resource_map[REVIEW_REQUEST] = 'review_requests'

    if len(sys.argv) > 1:
        cwd = os.getcwd()
        cookie = os.path.join(cwd, '.rb_cookie')
        #server_url = 'http://0.0.0.0:8080/'
        server_url = 'http://demo.reviewboard.org/'

        if re.match('-', sys.argv[1]):
            valid = True
            resource_name = re.split('-', sys.argv[1])[1]
            server = ServerInterface(server_url, cookie)
            root = RootResource(server, server_url + 'api/')
            resource_list = root.get(resource_map[resource_name])

            if len(sys.argv) > 2 and sys.argv[2]:
                resource_id = sys.argv[2]
                resource = resource_list.get(resource_id)
                print resource
            else:
                print resource_list

    if not valid:
        print "usage: rb info -resource_name [resource_id]"
        print ""
        print "resource_names:"
        for n in RESOURCE_NAMES:
            print "     %s" % n

if __name__ == '__main__':
    main()
