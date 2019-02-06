from __future__ import print_function, unicode_literals

import logging

import texttable as tt
try:
    from backports.shutil_get_terminal_size import get_terminal_size
except ImportError:
    from shutil import get_terminal_size

from rbtools.commands import Command, Option
from rbtools.utils.repository import get_repository_id
from rbtools.utils.users import get_username


class Status(Command):
    """Display review requests for the current repository."""

    name = 'status'
    author = 'The Review Board Project'
    description = 'Output a list of your pending review requests.'
    args = ''
    option_list = [
        Option('--all',
               dest='all_repositories',
               action='store_true',
               default=False,
               help='Shows review requests for all repositories instead '
                    'of just the detected repository.'),
        Command.server_options,
        Command.repository_options,
        Command.perforce_options,
        Command.tfs_options,
    ]
    # The number of spaces between the request's status and the request's id
    # and summary.
    TAB_SIZE = 3
    # The number of spaces after the end of the request's summary.
    PADDING = 5

    def tabulate(self, request_stats):
        """Print review request summary and status in a table.

        Args:
            request_stats (dict):
                A dict that contains statistics about each review request.
        """
        if len(request_stats):
            has_branches = False
            has_bookmarks = False

            table = tt.Texttable(get_terminal_size().columns)
            header = ['Status', 'Review Request']

            for request in request_stats:
                if 'branch' in request:
                    has_branches = True

                if 'bookmark' in request:
                    has_bookmarks = True

            if has_branches:
                header.append('Branch')

            if has_bookmarks:
                header.append('Bookmark')

            table.header(header)

            for request in request_stats:
                row = [request['status'], request['summary']]

                if has_branches:
                    row.append(request.get('branch') or '')

                if has_bookmarks:
                    row.append(request.get('bookmark') or '')

                table.add_row(row)

            print(table.draw())
        else:
            print('No review requests found.')

        print()

    def get_data(self, requests):
        """Return current status and review summary for all reviews.

        Args:
            requests (ListResource):
                A ListResource that contains data on all open/draft requests.

        Returns:
            list: A list whose elements are dicts of each request's statistics.
        """
        requests_stats = []
        request_stats = {}

        for request in requests.all_items:
            if request.draft:
                status = 'Draft'
            elif request.issue_open_count:
                status = 'Open Issues (%s)' % request.issue_open_count
            elif request.ship_it_count:
                status = 'Ship It! (%s)' % request.ship_it_count
            else:
                status = 'Pending'

            request_stats = {
                'status': status,
                'summary': 'r/%s - %s' % (request.id, request.summary)
            }

            if 'local_branch' in request.extra_data:
                request_stats['branch'] = \
                    request.extra_data['local_branch']
            elif 'local_bookmark' in request.extra_data:
                request_stats['bookmark'] = \
                    request.extra_data['local_bookmark']

            requests_stats.append(request_stats)

        return requests_stats

    def main(self):
        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(tool, api_root=api_root)
        username = get_username(api_client, api_root, auth_required=True)

        # Check if repository info on reviewboard server match local ones.
        repository_info = repository_info.find_server_repository_info(api_root)

        query_args = {
            'from_user': username,
            'status': 'pending',
            'expand': 'draft',
        }

        if not self.options.all_repositories:
            repo_id = get_repository_id(
                repository_info,
                api_root,
                repository_name=self.options.repository_name)

            if repo_id:
                query_args['repository'] = repo_id
            else:
                logging.warning('The repository detected in the current '
                                'directory was not found on\n'
                                'the Review Board server. Displaying review '
                                'requests from all repositories.')

        requests = api_root.get_review_requests(**query_args)
        request_stats = self.get_data(requests)
        self.tabulate(request_stats)
