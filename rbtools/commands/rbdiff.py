import os
import re
import string
import sys
from urllib2 import HTTPError

from rbtools.api.settings import Settings
from rbtools.api.resource import Resource, \
                                RootResource, \
                                ReviewRequest, \
                                ResourceList, \
                                DiffResource
from rbtools.api.serverinterface import ServerInterface
from rbtools.clients.getclient import get_client


FILE_OPTION = '--file'
MAKE = 'make'
GET = 'get'
REQUEST_TYPES = [MAKE, GET]


def main():
    diff(sys.argv[1:])


def diff(args):
    valid = False
    settings = Settings(config_file='rb_scripts.dat')

    if len(args) > 0:  # command given
        cookie = settings.get_cookie_file()
        server_url = settings.get_server_url()
        command = args[0]

        if command[0] == '-':
            command = command[1:]

        if REQUEST_TYPES.count(command) == 1:
            valid = True
            diff_file_name = 'diff'

            if command == MAKE:
                """builds a local diff

                builds a diff of the local repository. call is:
                rb diff -make [--file:<diff_file>] [args]

                    diff_file: optional, the name of the file to write to
                    args: arguments required for build a diff. Unneaded for
                          most clients, but some (e.g. Perforce require it)
                """
                if len(args) > 1:
                    m = re.match(FILE_OPTION, args[1])

                    if m:
                        diff_file_name = string.split(args[1], ':', 1)[1]
                    else:
                        valid = False

                client = get_client(server_url)

                if client == None:
                    print 'could not find the source control manager'
                    exit()

                diff_args = None
                # diff_args is only used for certain clients
                # (e.g. Perforce)
                if len(args) > 2 and client.client_type == 'perforce':
                    diff_args = args[2]

                diff, parent_diff = client.diff(diff_args)
                diff_file = open(diff_file_name, 'w')

                if diff_file < 0:
                    print 'could not open the file ' + \
                          diff_file_name + ' to write the diff.'

                diff_file.write(diff)
                diff_file.close()
            else:
                """ gets diff(s) from a review_request on the server

                call structure:
                    rb diff -GET [--file:<diff_file>] <review_request_id>
                            [diff_revision]

                (currently text/x-patch, it is defined in config.dat).
                """
                server = ServerInterface(server_url, cookie)
                root = RootResource(server, server_url + 'api/')
                diff_id = None

                if len(args) > 1:
                    m = re.match(FILE_OPTION, args[1])

                    if m:
                        if len(args) > 2:
                            diff_file_name = string.split(args[1], ':', 1)[1]
                            review_request_id = args[2]
                            valid = True

                            if len(args) > 3:
                                diff_id = args[3]
                    else:
                        review_request_id = args[1]
                        valid = True

                        if len(args) > 2:
                            diff_id = args[2]

                    if valid:
                        review_requests = root.get('review_requests')
                        request = ReviewRequest( \
                                    review_requests.get(review_request_id))
                        diffs = request.get_or_create('diffs')
                        num_revisions = len(diffs)

                        """find out which diff is required

                        find the required diff. If no preference is given the
                        most recent one will be used.  If diff_revision of
                        'all' is requested, the operation will be run on each
                        diff, one at a time. In this case, diff files will be
                        prefixed with <revision_num>_.
                        """
                        if not diff_id:
                            diff_id = num_revisions

                        diff_id = str(diff_id)

                        if diff_id.isdigit():
                            #single diff
                            try:
                                diff = DiffResource(diffs.get(diff_id))
                            except urllib2.HTTPError, e:
                                if e.code == 404:
                                    print 'The specified diff revision ' \
                                          'does not exist.'
                                    exit()
                                else:
                                    raise e

                            server_diff = diff.get_diff()

                            diff_file = open(diff_file_name, 'w')

                            if diff_file < 0:
                                print 'could not open "' + \
                                      diff_file_name + '" for writing.'
                                exit()

                            diff_file.write(server_diff)
                            diff_file.close()
                        elif diff_id == 'all':
                            #deal with each dif, one at a time
                            diff_id = 1

                            while diff_id <= num_revisions:
                                diff = DiffResource(diffs.get(diff_id))
                                server_diff = diff.get_diff()

                                diff_file = open('%d_%s' % \
                                                 (diff_id, diff_file_name),
                                                 'w')

                                if diff_file < 0:
                                    print 'could not open "' + \
                                          diff_id + '_' + diff_file_name + \
                                          '" for writing.'
                                    exit()

                                diff_file.write(server_diff)
                                diff_file.close()
                                diff_id = diff_id + 1

    if not valid:
        print 'usage: rb diff -type [--file:<file_name>] ' \
              '<review_request_id> [revision_id]'
        print ''
        print 'types:'

        for n in REQUEST_TYPES:
            print '    %s' % n

        print ''
        print 'If TYPE is MAKE the options <review_request_id> and ' \
              '[revision_id] are ignored.'
        print 'If TYPE is GET, an unspecified [revision_id] will get ' \
              'the most recent revision''s diff.  [revision_id] may ' \
              'be set to ''all'' to iteratively get every revision.'


if __name__ == '__main__':
    main()
