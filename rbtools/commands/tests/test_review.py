"""Tests for the rbt review command.

Version Added:
    7.0
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import kgb

from rbtools.api.resource import (
    DiffItemResource,
    ReviewItemResource,
    RootResource,
)
from rbtools.api.resource.base import _create
from rbtools.commands.review import AddDiffComment
from rbtools.config import RBToolsConfig
from rbtools.testing import TestCase
from rbtools.testing.api.transport import URLMapTransport

if TYPE_CHECKING:
    from typelets.json import JSONDict


class AddDiffCommentTests(kgb.SpyAgency, TestCase):
    """Tests for the ``rbt review add-diff-comment`` subcommand.

    These focus on locating the file to comment on within a diff. The list of
    files in a diff is paginated by the Review Board API (25 files per page by
    default), so the command must walk *every* page when matching the requested
    filename.

    Version Added:
        7.0
    """

    #: Base URL for the test server.
    SERVER_URL = 'https://reviews.example.com/'

    #: The ID of the review request used in these tests.
    REVIEW_REQUEST_ID = 123

    #: The diff revision used in these tests.
    DIFF_REVISION = 1

    def _build_command(
        self,
        *,
        filename: str,
    ) -> AddDiffComment:
        """Return an ``add-diff-comment`` subcommand ready to run.

        Args:
            filename (str):
                The filename to search for in the diff.

        Returns:
            rbtools.commands.review.AddDiffComment:
            The configured subcommand instance.
        """
        options = argparse.Namespace(
            review_request_id=str(self.REVIEW_REQUEST_ID),
            diff_revision=self.DIFF_REVISION,
            filename=filename,
            line=42,
            num_lines=1,
            text='This needs a mutex.',
            open_issue=False,
            markdown=True)

        return AddDiffComment(options=options, config=RBToolsConfig())

    def _make_file_payload(
        self,
        file_id: int,
        dest_file: str,
    ) -> JSONDict:
        """Return an item payload for a single file in a diff.

        Args:
            file_id (int):
                The value of the file's ``id`` field. This is the
                ``filediff_id`` the comment should be posted against.

            dest_file (str):
                The destination path of the file.

        Returns:
            typelets.json.JSONDict:
            The file diff item payload.
        """
        file_url = (
            f'{self.SERVER_URL}api/review-requests/{self.REVIEW_REQUEST_ID}/'
            f'diffs/{self.DIFF_REVISION}/files/{file_id}/'
        )

        return {
            'id': file_id,
            'source_file': dest_file,
            'source_revision': 'abc123',
            'dest_file': dest_file,
            'dest_detail': '',
            'links': {
                'self': {
                    'href': file_url,
                    'method': 'GET',
                },
            },
        }

    def _make_paginated_files(
        self,
        *,
        page1_files: list[JSONDict],
        page2_files: list[JSONDict],
    ) -> tuple[str, URLMapTransport]:
        """Register a two-page file diff list resource in a fresh transport.

        The first page carries a ``next`` link pointing at the second page, so
        that walking the list with
        :py:attr:`~rbtools.api.resource.base.ListResource.all_items` will
        fetch the second page from the transport.

        Args:
            page1_files (list of typelets.json.JSONDict):
                The file item payloads for the first page.

            page2_files (list of typelets.json.JSONDict):
                The file item payloads for the second page.

        Returns:
            tuple:
            A 2-tuple of:

            Tuple:
                0 (str):
                    The path of the first page of the file diff list.

                1 (rbtools.testing.api.transport.URLMapTransport):
                    The transport with both pages registered.
        """
        files_url = (
            f'/api/review-requests/{self.REVIEW_REQUEST_ID}/'
            f'diffs/{self.DIFF_REVISION}/files/'
        )
        page1_url = f'{self.SERVER_URL}{files_url.lstrip("/")}'
        page2_path = f'{files_url}page2/'
        page2_url = f'{self.SERVER_URL}{page2_path.lstrip("/")}'

        list_mimetype = 'application/vnd.reviewboard.org.files+json'
        item_mimetype = 'application/vnd.reviewboard.org.file+json'

        transport = URLMapTransport(self.SERVER_URL)

        transport.add_url(
            url=files_url,
            mimetype=list_mimetype,
            headers={'Item-Content-Type': item_mimetype},
            payload={
                'files': page1_files,
                'links': {
                    'self': {
                        'href': page1_url,
                        'method': 'GET',
                    },
                    'next': {
                        'href': page2_url,
                        'method': 'GET',
                    },
                },
                'stat': 'ok',
                'total_results': len(page1_files) + len(page2_files),
            },
            extra_node_state={'list_key': 'files'})

        transport.add_url(
            url=page2_path,
            mimetype=list_mimetype,
            headers={'Item-Content-Type': item_mimetype},
            payload={
                'files': page2_files,
                'links': {
                    'self': {
                        'href': page2_url,
                        'method': 'GET',
                    },
                },
                'stat': 'ok',
                'total_results': len(page1_files) + len(page2_files),
            },
            extra_node_state={'list_key': 'files'})

        return files_url, transport

    def _run_add_comment(
        self,
        command: AddDiffComment,
        files_url: str,
        transport: URLMapTransport,
    ) -> None:
        """Run ``add_comment`` with a stubbed API root and review draft.

        The diff and review draft are real resources backed by ``transport``.
        The diff's ``files`` link points at ``files_url``, so walking the
        file list goes through the transport. The review draft's diff
        comments list is registered with a ``POST`` handler, and
        :py:func:`~rbtools.api.resource.base._create` is spied on so the
        posted fields can be checked.

        Args:
            command (rbtools.commands.review.AddDiffComment):
                The subcommand to run.

            files_url (str):
                The path of the first page of the file diff list.

            transport (rbtools.testing.api.transport.URLMapTransport):
                The transport with the file diff list pages registered.
        """
        api_url = f'{self.SERVER_URL}api/'
        diff_url = (
            f'{api_url}review-requests/{self.REVIEW_REQUEST_ID}/'
            f'diffs/{self.DIFF_REVISION}/'
        )
        review_url = (
            f'{api_url}review-requests/{self.REVIEW_REQUEST_ID}/reviews/1/'
        )
        diff_comments_path = (
            f'/api/review-requests/{self.REVIEW_REQUEST_ID}/'
            f'reviews/1/diff-comments/'
        )
        diff_comments_url = f'{self.SERVER_URL}{diff_comments_path[1:]}'
        comment_url = f'{diff_comments_url}4478196/'

        diff_comment_mimetype = \
            'application/vnd.reviewboard.org.review-diff-comment+json'

        transport.add_url(
            url=diff_comments_path,
            mimetype='application/vnd.reviewboard.org.review-diff-comments'
                     '+json',
            headers={'Item-Content-Type': diff_comment_mimetype},
            payload={
                'diff_comments': [],
                'links': {
                    'create': {
                        'href': diff_comments_url,
                        'method': 'POST',
                    },
                    'self': {
                        'href': diff_comments_url,
                        'method': 'GET',
                    },
                },
                'stat': 'ok',
                'total_results': 0,
            },
            extra_node_state={'list_key': 'diff_comments'})

        transport.add_url(
            url=diff_comments_path,
            method='POST',
            mimetype=diff_comment_mimetype,
            payload={
                'diff_comment': {
                    'id': 4478196,
                    'links': {
                        'self': {
                            'href': comment_url,
                            'method': 'GET',
                        },
                    },
                },
                'stat': 'ok',
            },
            extra_node_state={'item_key': 'diff_comment'})

        diffset = DiffItemResource(
            transport=transport,
            payload={
                'diff': {
                    'id': self.DIFF_REVISION,
                    'revision': self.DIFF_REVISION,
                    'links': {
                        'files': {
                            'href': f'{self.SERVER_URL}{files_url[1:]}',
                            'method': 'GET',
                        },
                        'self': {
                            'href': diff_url,
                            'method': 'GET',
                        },
                    },
                },
                'stat': 'ok',
            },
            url=diff_url,
            token='diff')

        review_draft = ReviewItemResource(
            transport=transport,
            payload={
                'review': {
                    'id': 1,
                    'links': {
                        'diff_comments': {
                            'href': diff_comments_url,
                            'method': 'GET',
                        },
                        'self': {
                            'href': review_url,
                            'method': 'GET',
                        },
                    },
                },
                'stat': 'ok',
            },
            url=review_url,
            token='review')

        api_root = transport.get_root()
        assert isinstance(api_root, RootResource)
        command.api_root = api_root

        self.spy_on(api_root.get_diff, op=kgb.SpyOpReturn(diffset))
        self.spy_on(command.get_review_draft,
                    op=kgb.SpyOpReturn(review_draft))
        self.spy_on(_create)

        command.add_comment('markdown')

    def test_add_comment_to_file_on_second_page(self) -> None:
        """Testing review add-diff-comment finds a file past the first page

        This is a regression test. The API returns diff files 25 at a time, and
        the command previously only searched the first page, so a comment could
        not be posted to any file beyond the 25th. Without the fix this raises
        ``CommandError: Could not find a file ...``.
        """
        page1_files = [
            self._make_file_payload(file_id=i, dest_file=f'src/file{i}.cpp')
            for i in range(1, 26)
        ]
        page2_files = [
            self._make_file_payload(file_id=26,
                                    dest_file='src/ThreadPool.cpp'),
        ]

        command = self._build_command(filename='ThreadPool.cpp')
        files_url, transport = self._make_paginated_files(
            page1_files=page1_files,
            page2_files=page2_files)

        self._run_add_comment(command, files_url, transport)

        self.assertSpyCalled(command.get_review_draft)
        self.assertSpyCallCount(_create, 1)
        self.assertSpyLastCalledWith(_create, filediff_id=26)

    def test_add_comment_to_file_on_first_page(self) -> None:
        """Testing review add-diff-comment finds a file on the first page"""
        page1_files = [
            self._make_file_payload(file_id=i, dest_file=f'src/file{i}.cpp')
            for i in range(1, 26)
        ]
        page2_files = [
            self._make_file_payload(file_id=26,
                                    dest_file='src/ThreadPool.cpp'),
        ]

        command = self._build_command(filename='file7.cpp')
        files_url, transport = self._make_paginated_files(
            page1_files=page1_files,
            page2_files=page2_files)

        self._run_add_comment(command, files_url, transport)

        self.assertSpyCallCount(_create, 1)
        self.assertSpyLastCalledWith(_create, filediff_id=7)
