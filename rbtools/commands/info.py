"""The rbt info command."""

from __future__ import unicode_literals

from texttable import Texttable
from backports.shutil_get_terminal_size import get_terminal_size

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError


class Info(Command):
    """Display information about a review request."""

    name = 'info'
    author = 'The Review Board Project'
    description = 'Display information about a review request.'

    needs_api = True

    args = '<review-request> [revision]'
    option_list = [
        Command.server_options,
        Command.repository_options,
    ]

    def main(self, review_request_id, diff_revision=None):
        try:
            review_request = self.api_root.get_review_request(
                review_request_id=review_request_id,
                expand='submitter')
        except APIError:
            raise CommandError('The review request does not exist.')

        diff = None
        commits = None

        if 'repository' in review_request.links is not None:
            try:
                diffs = review_request.get_diffs()
            except APIError as e:
                raise CommandError('Error retrieving diffs: %s' % e)

            if diff_revision is None:
                diff_revision = diffs.total_results

            diff = diffs.get_item(diff_revision)

            if getattr(diff, 'commit_count', 0) > 0:
                try:
                    commits = diff.get_commits()
                except APIError as e:
                    raise CommandError('Error retrieving commits: %s' % e)
        elif diff_revision is not None:
            raise CommandError('This review request does not have diffs '
                               'attached')

        self.stdout.write(review_request.summary)
        self.stdout.new_line()
        self.stdout.write('Submitter: %s'
                          % (review_request.submitter.fullname or
                             review_request.submitter.username))
        self.stdout.new_line()
        self.stdout.write(review_request.description)

        self.stdout.new_line()
        self.stdout.write('URL: %s' % review_request.absolute_url)

        if diff:
            self.stdout.write('Diff: %sdiff/%s/'
                              % (review_request.absolute_url, diff_revision))
            self.stdout.new_line()
            self.stdout.write('Revision: %s (of %d)'
                              % (diff_revision, diffs.total_results))

            if commits:
                self.stdout.new_line()
                self.stdout.write('Commits:')

                table = Texttable(get_terminal_size().columns)
                table.header(('ID', 'Summary', 'Author'))

                for commit in commits:
                    summary = commit.commit_message.split('\n', 1)[0].strip()

                    if len(summary) > 80:
                        summary = summary[:77] + '...'

                    table.add_row((commit.commit_id, summary,
                                   commit.author_name))

                self.stdout.write(table.draw())
