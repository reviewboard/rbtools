import os
import sys
import urllib2

from rbtools.api.resource import Resource, RootResource
from rbtools.api.serverinterface import ServerInterface
from rbtools.clients.getclient import get_client


def main():
    valid = False

    if len(sys.argv) > 0:
        valid = True
        cwd = os.getcwd()
        cookie = os.path.join(cwd, '.rb_cookie')
        #server_url = 'http://0.0.0.0:8080/'
        server_url = 'http://demo.reviewboard.org/'
        client = get_client(server_url)
        diff, parent_diff = client.diff(None)
        diff_file = open('diff', 'w')
        diff_file.write(diff)
        diff_file.close()

        diff_data = {
            'filename': 'diff',
            'content': diff
        }
        parent_diff_data = None

        if parent_diff:
            parent_diff_data = {}
            parent_diff_file = open('parent_diff', 'w')
            parent_diff_file.write(parent_diff)
            parent_diff_file.close()
            parent_diff_path['filename'] = 'parent_diff'
            parent_diff_path['content'] = parent_diff

        server = ServerInterface(server_url, cookie)
        root = RootResource(server, server_url + 'api/')
        review_requests = root.get('review_requests')
        review_request = review_requests.create()
        review_request.update_field('submit_as', 'dionyses')
        review_request.update_field('repository', '2')
        review_request.save()

        print review_request
        diffs = review_request.get_or_create('diffs')
        print diffs
        resource_diff = diffs.create()
        #resource_diff.update_field('basedir', ' ')
        resource_diff.update_file('path', diff_data)

        #if parent_diff_data:
        #    diff.update_file('parent_diff_path', parent_diff_data)

        try:
            resource_diff.save()
            print diff
        except urllib2.HTTPError, e:
            print e.headers
            print e.code
            print e.msg
            print e.read()

    if not valid:
        print "usage: rb create ..."

if __name__ == '__main__':
    main()
