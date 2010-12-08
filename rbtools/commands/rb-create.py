import os
import sys
import urllib2

from rbtools.api.resource import Resource, RootResource
from rbtools.api.resource import RepositoryList, ReviewRequestDraft
from rbtools.api.serverinterface import ServerInterface
from rbtools.api.settings import Settings
from rbtools.clients.getclient import get_client


def main():
    valid = True

    if len(sys.argv) > 0:
        settings = Settings(config_file='rb_scripts.dat')
        cookie = settings.get_cookie_file()
        server_url = settings.get_server_url()
        client = get_client(server_url)
        server_repo = client.get_info()
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
        repositories = RepositoryList(root.get('repositories'))
        repo_id = repositories.get_repository_id(server_repo.path)

        if repo_id:
            try:
                review_requests = root.get('review_requests')
                review_request = review_requests.create()
                review_request.update_field('submit_as',
                                            settings.get_setting('user_name'))
                review_request.update_field('repository', str(repo_id))
                review_request.save()
                diffs = review_request.get_or_create('diffs')
                resource_diff = diffs.create()
                resource_diff.update_file('path', diff_data)

                if server_repo.base_path:
                    resource_diff.update_field('basedir',
                                               server_repo.base_path)

                if parent_diff_data:
                    diff.update_file('parent_diff_path', parent_diff_data)

                resource_diff.save()
                review_request_draft = ReviewRequestDraft(
                    review_request.get_or_create('draft'))
                review_request_draft.publish()
                print "Review request created at: %s\n" % review_request.url
                print "To view the review request in a browser go to: " \
                    "%sr/%s/" % (server_url, review_request.get_field('id'))
            except Error, e:
                raise e
        else:
            print "The repository could not be found on the server."

    if not valid:
        print "usage: rb create"


if __name__ == '__main__':
    main()
