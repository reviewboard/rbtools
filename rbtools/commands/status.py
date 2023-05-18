"""Implementation of rbt status."""

import logging
import re
from shutil import get_terminal_size

import texttable as tt

from rbtools.commands import Command, Option
from rbtools.utils.users import get_username


class Status(Command):
    """Display review requests for the current repository."""

    name = 'status'
    author = 'The Review Board Project'
    description = 'Output a list of your pending review requests.'

    needs_api = True

    args = '[review-request [revision]]'
    option_list = [
        Option('--format',
               dest='format',
               default=None,
               help='Set the output format. The format is in the form of '
                    '`%%(field_name)s`, where `field_name` is one of: `id`, '
                    '`status`, `summary`, or `description`.\n'
                    'A character escape can be included via `\\xXX` where '
                    '`XX` the hex code of a character.\n'
                    'For example: --format="%%(id)s\\x09%%(summary)s"\n'
                    'This option will print out the ID and summary tab-'
                    'separated. This is incompatible with --json.'),
        Option('-z',
               dest='format_nul',
               default=False,
               action='store_true',
               help='Null-terminate each entry. Otherwise, the entries will '
                    'be newline-terminated. This is incompatible with '
                    '--json.'),
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

    _HEX_RE = re.compile(r'\\x([0-9a-fA-f]{2})')

    def tabulate(self, review_requests):
        """Print review request summary and status in a table.

        Args:
            review_requests (list of dict):
                A list that contains statistics about each review request.
        """
        self.json.add('review_requests', [])

        if len(review_requests):
            has_branches = False
            has_bookmarks = False

            table = tt.Texttable(get_terminal_size().columns)
            header = ['Status', 'Review Request']

            for info in review_requests:
                if 'branch' in info:
                    has_branches = True

                if 'bookmark' in info:
                    has_bookmarks = True

            if has_branches:
                header.append('Branch')

            if has_bookmarks:
                header.append('Bookmark')

            table.header(header)

            for info in review_requests:
                row = [
                    info['status'],
                    'r/%s - %s' % (info['id'], info['summary']),
                ]

                summary = {
                    'approval_failure': info['approval_failure'],
                    'approved': info['approved'],
                    'description': info['description'],
                    'has_draft': info['has_draft'],
                    'open_issue_count': info['open_issue_count'],
                    'review_request_id': info['id'],
                    'review_request_url': info['url'],
                    'shipit_count': info['shipit_count'],
                    'status': info['status'],
                    'summary': info['summary'],
                }

                if has_branches:
                    row.append(info.get('branch') or '')
                    summary['branch'] = row[-1]

                if has_bookmarks:
                    row.append(info.get('bookmark') or '')
                    summary['bookmark'] = row[-1]

                table.add_row(row)
                self.json.append('review_requests', summary)

            self.stdout.write(table.draw())
        else:
            self.stdout.write('No review requests found.')

        self.stdout.new_line()

    def get_data(self, review_requests):
        """Return current status and review summary for all review requests.

        Args:
            review_requests (ListResource):
                A ListResource that contains data on all open/draft
                review requests.

        Returns:
            list:
            A list whose elements are dicts of each review request's
            statistics.
        """
        review_requests_stats = []

        for review_request in review_requests.all_items:
            if review_request.draft:
                status = 'Draft'
            elif review_request.issue_open_count:
                status = 'Open Issues (%s)' % review_request.issue_open_count
            elif review_request.ship_it_count:
                status = 'Ship It! (%s)' % review_request.ship_it_count
            else:
                status = 'Pending'

            if review_request.draft:
                summary = review_request.draft[0]['summary']
            else:
                summary = review_request.summary

            info = {
                'approval_failure': review_request.approval_failure,
                'approved': review_request.approved,
                'description': review_request.description,
                'id':  review_request.id,
                'status': status,
                'summary': summary,
                'url': review_request.absolute_url,
                'shipit_count': review_request.ship_it_count,
                'open_issue_count': review_request.issue_open_count,
                'has_draft': review_request.draft is not None
            }

            if 'local_branch' in review_request.extra_data:
                info['branch'] = review_request.extra_data['local_branch']
            elif 'local_bookmark' in review_request.extra_data:
                info['bookmark'] = review_request.extra_data['local_bookmark']

            review_requests_stats.append(info)

        return review_requests_stats

    def initialize(self):
        """Initialize the command.

        This override of the base command initialize method exists so we can
        conditionally set whether the SCM Client is necessary. Without any
        options, this command will only print the status of review requests on
        the current repository, which requires the client. If --all is passed,
        this command only needs the API.
        """
        self.needs_repository = not self.options.all_repositories

        super(Status, self).initialize()

    def main(self):
        username = get_username(self.api_client, self.api_root,
                                auth_required=True)

        query_args = {
            'from_user': username,
            'status': 'pending',
            'expand': 'draft',
        }

        if not self.options.all_repositories:
            if self.repository:
                query_args['repository'] = self.repository.id
            else:
                logging.warning('The repository detected in the current '
                                'directory was not found on\n'
                                'the Review Board server. Displaying review '
                                'requests from all repositories.')

        review_requests = self.api_root.get_review_requests(**query_args)
        review_request_info = self.get_data(review_requests)

        if self.options.format:
            self.format_results(review_request_info)
        else:
            self.tabulate(review_request_info)

    def format_results(self, review_requests):
        """Print formatted information about the review requests.

        Args:
            review_requests (list of dict):
                The information about the review requests.
        """
        fmt = self._HEX_RE.sub(
            lambda m: chr(int(m.group(1), 16)),
            self.options.format,
        )

        if self.options.format_nul:
            end = '\x00'
        else:
            end = '\n'

        for info in review_requests:
            self.stdout.write(fmt % info, end=end)
