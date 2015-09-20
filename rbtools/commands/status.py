from __future__ import print_function, unicode_literals

import logging

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
            max_status_length = max(d['status_len'] for d in request_stats)
            max_row_length = (max(d['summary_len'] for d in request_stats) +
                              self.PADDING + self.TAB_SIZE + max_status_length)
            white_space = max_status_length + self.TAB_SIZE
            border = '=' * max_row_length

            print(border)
            print('%s%s' % ('Status'.ljust(white_space), 'Review Request'))
            print(border)

            for request in request_stats:
                status = request['status'].ljust(white_space)
                print('%s%s' % (status, request['summary']))
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

        for request in requests.all_items:
            if request.draft:
                status = 'Draft'
            elif request.issue_open_count:
                status = 'Open Issues (%s)' % request.issue_open_count
            elif request.ship_it_count:
                status = 'Ship It! (%s)' % request.ship_it_count
            else:
                status = 'Pending'

            summary = 'r/%s - %s' % (request.id, request.summary)
            requests_stats.append({
                'status': status,
                'summary': summary,
                'status_len': len(status),
                'summary_len': len(summary),
            })

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
