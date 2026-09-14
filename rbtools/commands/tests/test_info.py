"""Unit tests for the rbt info command.

Version Added:
    7.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.commands.info import Info
from rbtools.testing import CommandTestsMixin, TestCase

if TYPE_CHECKING:
    from rbtools.testing.api.transport import URLMapTransport


class InfoCommandTests(CommandTestsMixin[Info], TestCase):
    """Tests for the rbt info command.

    Version Added:
        7.0
    """

    command_cls = Info

    #: The API path for the review request.
    #: The API path for the review request's diffs.
    DIFFS_PATH = '/api/review-requests/1/diffs/'

    #: The API path for the review request draft.
    DRAFT_PATH = '/api/review-requests/1/draft/'

    #: The API path for the review request draft's diffs.
    DRAFT_DIFFS_PATH = '/api/review-requests/1/draft/draft-diffs/'

    def test_with_diffs(self) -> None:
        """Testing rbt info with published diffs"""
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport)
            self._add_diffs(transport, self.DIFFS_PATH, revisions=[1, 2])

        result = self.run_command(args=['1'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 0)

        stdout = result['stdout'].decode()
        self.assertIn('Test Summary', stdout)
        self.assertIn('https://reviews.example.com/r/1/diff/2/', stdout)
        self.assertIn('Diff revision 2 (of 2)', stdout)

    def test_with_no_published_diffs(self) -> None:
        """Testing rbt info with a repository but no published diffs"""
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport)
            self._add_diffs(transport, self.DIFFS_PATH, revisions=[])

        result = self.run_command(args=['1'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 0)

        stdout = result['stdout'].decode()
        self.assertIn('Test Summary', stdout)
        self.assertNotIn('Diff:', stdout)

    def test_with_invalid_diff_revision(self) -> None:
        """Testing rbt info with a diff revision that does not exist"""
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport)
            self._add_diffs(transport, self.DIFFS_PATH, revisions=[1])
            transport.add_error_url(url=f'{self.DIFFS_PATH}5/',
                                    error_code=100,
                                    error_message='Object does not exist',
                                    http_status=404)

        result = self.run_command(args=['1', '5'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 1)
        self.assertIn(b'Diff revision 5 does not exist.', result['stderr'])

    def test_with_non_numeric_diff_revision(self) -> None:
        """Testing rbt info with a non-numeric diff revision"""
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport)

        result = self.run_command(args=['1', 'abc'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 1)
        self.assertIn(b'"abc" is not a valid diff revision.',
                      result['stderr'])

    def test_with_unpublished_review_request(self) -> None:
        """Testing rbt info with an unpublished review request"""
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport,
                                     public=False,
                                     summary='')
            self._add_diffs(transport, self.DIFFS_PATH, revisions=[])
            transport.add_review_request_draft_url(draft_id=1,
                                                   review_request_id=1,
                                                   summary='Draft Summary')
            self._add_diffs(transport, self.DRAFT_DIFFS_PATH, revisions=[1],
                            with_commits=True)

        result = self.run_command(args=['1'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 0)

        stdout = result['stdout'].decode()
        self.assertIn('Draft Summary', stdout)
        self.assertIn('Showing the unpublished draft', stdout)
        self.assertIn('https://reviews.example.com/r/1/diff/1/', stdout)
        self.assertIn('Commit 1 message', stdout)

    def test_with_draft_as_submitter(self) -> None:
        """Testing rbt info with a published review request with a draft,
        as the submitter
        """
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport)
            self._add_diffs(transport, self.DIFFS_PATH, revisions=[1, 2])
            transport.add_review_request_draft_url(draft_id=1,
                                                   review_request_id=1,
                                                   summary='Draft Summary')
            self._add_diffs(transport, self.DRAFT_DIFFS_PATH, revisions=[3])

        result = self.run_command(args=['1'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 0)

        stdout = result['stdout'].decode()
        self.assertIn('Draft Summary', stdout)
        self.assertIn('Showing the unpublished draft', stdout)
        self.assertIn('https://reviews.example.com/r/1/diff/3/', stdout)
        self.assertIn('Diff revision 3 (of 3)', stdout)

    def test_with_draft_and_published_diff_revision(self) -> None:
        """Testing rbt info with a draft and an explicit published diff
        revision
        """
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport)
            self._add_diffs(transport, self.DIFFS_PATH, revisions=[1, 2])
            transport.add_review_request_draft_url(draft_id=1,
                                                   review_request_id=1,
                                                   summary='Draft Summary')
            self._add_diffs(transport, self.DRAFT_DIFFS_PATH, revisions=[3])
            transport.add_error_url(url=f'{self.DRAFT_DIFFS_PATH}1/',
                                    error_code=100,
                                    error_message='Object does not exist',
                                    http_status=404)

        result = self.run_command(args=['1', '1'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 0)

        stdout = result['stdout'].decode()
        self.assertIn('https://reviews.example.com/r/1/diff/1/', stdout)
        self.assertIn('Diff revision 1 (of 3)', stdout)

    def test_with_draft_as_other_user(self) -> None:
        """Testing rbt info with a published review request with a draft,
        as a user other than the submitter
        """
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport, username='other-user')
            self._add_diffs(transport, self.DIFFS_PATH, revisions=[1])
            transport.add_review_request_draft_url(draft_id=1,
                                                   review_request_id=1,
                                                   summary='Draft Summary')

        result = self.run_command(args=['1'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 0)

        stdout = result['stdout'].decode()
        self.assertIn('Test Summary', stdout)
        self.assertNotIn('Draft Summary', stdout)
        self.assertNotIn('Showing the unpublished draft', stdout)

    def test_with_no_draft_as_submitter(self) -> None:
        """Testing rbt info with a published review request without a
        draft, as the submitter
        """
        def setup_transport(
            transport: URLMapTransport,
        ) -> None:
            self._add_review_request(transport)
            self._add_diffs(transport, self.DIFFS_PATH, revisions=[1])

        result = self.run_command(args=['1'],
                                  setup_transport_func=setup_transport)

        self.assertEqual(result['exit_code'], 0)

        stdout = result['stdout'].decode()
        self.assertIn('Test Summary', stdout)
        self.assertNotIn('Showing the unpublished draft', stdout)
        self.assertIn('https://reviews.example.com/r/1/diff/1/', stdout)

    def _add_review_request(
        self,
        transport: URLMapTransport,
        username: str = 'test-user',
        **kwargs,
    ) -> None:
        """Add a review request with a repository to the transport.

        The review request is submitted by ``test-user``, and has no draft
        unless one is added afterward.

        Args:
            transport (rbtools.testing.api.transport.URLMapTransport):
                The transport to add URLs to.

            username (str, optional):
                The username of the logged-in user.

            **kwargs (dict):
                Additional keyword arguments for the review request payload.
        """
        transport.add_user_url(username='test-user')

        if username != 'test-user':
            transport.add_user_url(user_id=2, username=username)

        transport.add_session_url(username=username)
        transport.add_error_url(url=self.DRAFT_PATH,
                                error_code=100,
                                error_message='Object does not exist',
                                http_status=404)
        transport.add_review_request_url(review_request_id=1,
                                         repository_id=1,
                                         **kwargs)

    def _add_diffs(
        self,
        transport: URLMapTransport,
        list_path: str,
        revisions: list[int],
        with_commits: bool = False,
    ) -> None:
        """Add a diff list and its diffs to the transport.

        Args:
            transport (rbtools.testing.api.transport.URLMapTransport):
                The transport to add URLs to.

            list_path (str):
                The API path for the diff list resource.

            revisions (list of int):
                The revisions of the diffs to add.

            with_commits (bool, optional):
                Whether to add a commit to each diff. Draft diffs get a draft
                commit list.
        """
        payload_factory = transport.payload_factory

        transport.add_list_url(
            url=list_path,
            list_key='diffs',
            mimetype=payload_factory.make_mimetype('diffs'),
            item_mimetype=payload_factory.make_mimetype('diff'))

        if '/draft/' in list_path:
            commits_name = 'draft_commits'
            commit_resource_name = 'draft-commit'
        else:
            commits_name = 'commits'
            commit_resource_name = 'commit'

        for revision in revisions:
            url = f'{list_path}{revision}/'
            links = {
                'self': {
                    'href': url,
                    'method': 'GET',
                },
            }

            if with_commits:
                commits_path = f'{url}{commits_name.replace("_", "-")}/'
                links[commits_name] = {
                    'href': commits_path,
                    'method': 'GET',
                }

                transport.add_list_url(
                    url=commits_path,
                    list_key=commits_name,
                    mimetype=payload_factory.make_mimetype(
                        f'{commit_resource_name}s'),
                    item_mimetype=payload_factory.make_mimetype(
                        commit_resource_name))
                transport.add_item_url(
                    url=f'{commits_path}1/',
                    item_key=commits_name[:-1],
                    mimetype=payload_factory.make_mimetype(
                        commit_resource_name),
                    in_list_urls=[commits_path],
                    payload={
                        'author_name': 'Test User',
                        'commit_id': 'abc123',
                        'commit_message': f'Commit {revision} message',
                        'id': revision,
                        'links': {},
                    })

            transport.add_item_url(
                url=url,
                item_key='diff',
                mimetype=payload_factory.make_mimetype('diff'),
                in_list_urls=[list_path],
                payload={
                    'commit_count': 1 if with_commits else 0,
                    'id': revision,
                    'links': links,
                    'revision': revision,
                })
