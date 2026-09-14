"""The rbt info command."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.box import SIMPLE
from rich.table import Table
from rich.markdown import Markdown
from rich.markup import escape

from rbtools.api.errors import APIError
from rbtools.commands.base import BaseCommand, CommandError
from rbtools.utils.users import get_user

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rbtools.api.resource import (
        DiffItemResource,
        DiffListResource,
        ReviewRequestDraftResource,
        ReviewRequestItemResource,
    )


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

        draft = self._get_draft(review_request)
        details = review_request if draft is None else draft

        n_diffs = 0
        diff = None
        commits = None

        if 'repository' in review_request.links is not None:
            try:
                diff_lists = [review_request.get_diffs()]

                if draft is not None:
                    # A draft diff is always the newest revision, so check it
                    # first.
                    diff_lists.insert(0, draft.get_draft_diffs())
            except APIError as e:
                raise CommandError(f'Error retrieving diffs: {e}')

            n_diffs = sum(
                diff_list.total_results or 0
                for diff_list in diff_lists
            )

            if diff_revision is None and n_diffs:
                diff_revision = n_diffs

            if diff_revision is not None:
                diff = self._get_diff(diff_lists, diff_revision)

            if diff is not None and getattr(diff, 'commit_count', 0) > 0:
                try:
                    if 'draft_commits' in diff.links:
                        commits = diff.get_draft_commits()
                    else:
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

        self.console.print(f'[rb.heading]{escape(details.summary)}')
        self.console.print()

        if draft is not None:
            self.console.print(
                '[rb.draft]Showing the unpublished draft of this review '
                'request.')
            self.console.print()

        self.console.print(f'[rb.muted]Submitter: {escape(submitter)}')
        self.console.print()

        if details.description_text_type == 'markdown':
            # Rendering this to markdown eliminates wrapping, which can make
            # things extremely unreadable in very wide terminals. Add some
            # default wrapping just because.
            description = Markdown(details.description)
            self.console.print(
                description,
                width=min(self.console.stdout_console.width, 120))
        else:
            self.console.print(escape(details.description))

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
            if n_diffs > 1:
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

    def _get_draft(
        self,
        review_request: ReviewRequestItemResource,
    ) -> ReviewRequestDraftResource | None:
        """Return the draft to show for a review request.

        Unpublished review requests only have content in their draft, so the
        draft is always used for them. Drafts of published review requests
        are only shown to the submitter.

        Version Added:
            7.0

        Args:
            review_request (rbtools.api.resource.ReviewRequestItemResource):
                The review request.

        Returns:
            rbtools.api.resource.ReviewRequestDraftResource:
            The draft, or ``None`` if there is no draft to show.
        """
        if review_request.public:
            assert self.api_client is not None
            assert self.api_root is not None

            user = get_user(self.api_client, self.api_root)

            if (user is None or
                user.username != review_request.submitter.username):
                return None

        try:
            return review_request.get_draft()
        except APIError:
            # There's no draft, or the user can't access it.
            return None

    def _get_diff(
        self,
        diff_lists: Sequence[DiffListResource],
        diff_revision: int,
    ) -> DiffItemResource:
        """Return the diff for a revision.

        Version Added:
            7.0

        Args:
            diff_lists (list of rbtools.api.resource.DiffListResource):
                The diff lists to look in, in order.

            diff_revision (int):
                The diff revision to fetch.

        Returns:
            rbtools.api.resource.DiffItemResource:
            The diff.

        Raises:
            rbtools.commands.CommandError:
                The diff revision does not exist.
        """
        for diff_list in diff_lists:
            if diff_list.total_results:
                try:
                    return cast('DiffItemResource',
                                diff_list.get_item(diff_revision))
                except APIError:
                    pass

        raise CommandError(f'Diff revision {diff_revision} does not exist.')
