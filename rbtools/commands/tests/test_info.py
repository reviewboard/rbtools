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
    REVIEW_REQUEST_PATH = '/api/review-requests/1/'

    #: The API path for the review request's diffs.
    DIFFS_PATH = '/api/review-requests/1/diffs/'

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

    def _add_review_request(
        self,
        transport: URLMapTransport,
        **kwargs,
    ) -> None:
        """Add a review request with a repository to the transport.

        Args:
            transport (rbtools.testing.api.transport.URLMapTransport):
                The transport to add URLs to.

            **kwargs (dict):
                Additional keyword arguments for the review request payload.
        """
        transport.add_user_url(username='test-user')
        transport.add_review_request_url(review_request_id=1,
                                         repository_id=1,
                                         **kwargs)

    def _add_diffs(
        self,
        transport: URLMapTransport,
        list_path: str,
        revisions: list[int],
    ) -> None:
        """Add a diff list and its diffs to the transport.

        Args:
            transport (rbtools.testing.api.transport.URLMapTransport):
                The transport to add URLs to.

            list_path (str):
                The API path for the diff list resource.

            revisions (list of int):
                The revisions of the diffs to add.
        """
        payload_factory = transport.payload_factory

        transport.add_list_url(
            url=list_path,
            list_key='diffs',
            mimetype=payload_factory.make_mimetype('diffs'),
            item_mimetype=payload_factory.make_mimetype('diff'))

        for revision in revisions:
            url = f'{list_path}{revision}/'

            transport.add_item_url(
                url=url,
                item_key='diff',
                mimetype=payload_factory.make_mimetype('diff'),
                in_list_urls=[list_path],
                payload={
                    'commit_count': 0,
                    'id': revision,
                    'links': {
                        'self': {
                            'href': url,
                            'method': 'GET',
                        },
                    },
                    'revision': revision,
                })
