"""The rbt info command."""

from __future__ import annotations

from rich.box import SIMPLE
from rich.table import Table
from rich.markdown import Markdown
from rich.markup import escape

from rbtools.api.errors import APIError
from rbtools.commands.base import BaseCommand, CommandError


class Info(BaseCommand):
    """Display information about a review request."""

    name = 'info'
    author = 'The Review Board Project'
    description = 'Display information about a review request.'

    needs_api = True

    args = '<review-request> [revision]'
    option_list = [
        BaseCommand.server_options,
        BaseCommand.repository_options,
    ]

    def main(self, review_request_id, diff_revision=None):
        if diff_revision is not None:
            try:
                diff_revision = int(diff_revision)
            except ValueError:
                raise CommandError(
                    f'"{diff_revision}" is not a valid diff revision.')

        try:
            review_request = self.api_root.get_review_request(
                review_request_id=review_request_id,
                expand='submitter')
        except APIError:
            raise CommandError('The review request does not exist.')

        diffs = None
        diff = None
        commits = None

        if 'repository' in review_request.links is not None:
            try:
                diffs = review_request.get_diffs()
            except APIError as e:
                raise CommandError(f'Error retrieving diffs: {e}')

            if diff_revision is None and diffs.total_results:
                diff_revision = diffs.total_results

            if diff_revision is not None:
                try:
                    diff = diffs.get_item(diff_revision)
                except APIError:
                    raise CommandError(
                        f'Diff revision {diff_revision} does not exist.')

            if getattr(diff, 'commit_count', 0) > 0:
                try:
                    commits = diff.get_commits()
                except APIError as e:
                    raise CommandError(f'Error retrieving commits: {e}')
        elif diff_revision is not None:
            raise CommandError('This review request does not have diffs '
                               'attached')

        submitter = (
            review_request.submitter.fullname or
            review_request.submitter.username
        )

        self.console.print(f'[rb.heading]{escape(review_request.summary)}')
        self.console.print()
        self.console.print(f'[rb.muted]Submitter: {escape(submitter)}')
        self.console.print()

        if review_request.description_text_type == 'markdown':
            # Rendering this to markdown eliminates wrapping, which can make
            # things extremely unreadable in very wide terminals. Add some
            # default wrapping just because.
            description = Markdown(review_request.description)
            self.console.print(
                description,
                width=min(self.console.stdout_console.width, 120))
        else:
            self.console.print(escape(review_request.description))

        self.console.print()

        grid = Table.grid()
        grid.add_column()
        grid.add_column()
        url = review_request.absolute_url
        grid.add_row('URL:  ', f'[rb.url]{url}')

        if diff:
            diff_url = f'{url}diff/{diff_revision}/'
            grid.add_row('Diff:  ', f'[rb.url]{diff_url}')

        self.console.print(grid)
        self.console.print()
        self.console.print()

        if diff:
            assert diffs is not None
            n_diffs = diffs.total_results

            if n_diffs and n_diffs > 1:
                self.console.print(
                    f'[rb.muted]Diff revision {diff_revision} (of {n_diffs})')

            if commits:
                table = Table(
                    title='Commits',
                    show_header=True,
                    box=SIMPLE,
                    header_style='rb.heading',
                )

                table.add_column('ID', style='rb.muted')
                table.add_column('Summary')
                table.add_column('Author')

                for commit in commits:
                    summary = commit.commit_message.split('\n', 1)[0].strip()

                    if len(summary) > 80:
                        summary = summary[:77] + '...'

                    table.add_row(
                        commit.commit_id,
                        summary,
                        commit.author_name,
                    )

                self.console.print(table)
