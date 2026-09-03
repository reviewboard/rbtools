"""Unit tests for rbtools.utils.commit_messages.

Version Added:
    7.0
"""

from __future__ import annotations

from rbtools.api.resource import ReviewRequestItemResource
from rbtools.testing import TestCase
from rbtools.utils.commit_messages import (
    ParsedCommitMessage,
    format_commit_message,
    parse_commit_message,
)


class ParseCommitMessageTests(TestCase):
    """Unit tests for parse_commit_message.

    Version Added:
        7.0
    """

    def test_summary_only(self) -> None:
        """Testing parse_commit_message with summary only"""
        self.assertEqual(
            parse_commit_message('Fix the thing'),
            {
                'description': 'Fix the thing',
                'summary': 'Fix the thing',
            })

    def test_summary_and_description(self) -> None:
        """Testing parse_commit_message with summary and description"""
        self.assertEqual(
            parse_commit_message(
                'Fix the thing\n'
                '\n'
                'This fixes the thing by doing stuff.\n'
                'More details here.'
            ),
            {
                'description': ('This fixes the thing by doing stuff.\n'
                                'More details here.'),
                'summary': 'Fix the thing',
            })

    def test_full_message(self) -> None:
        """Testing parse_commit_message with all fields"""
        self.assertEqual(
            parse_commit_message(
                'Fix the thing\n'
                '\n'
                'This fixes the thing.\n'
                '\n'
                'Testing Done:\n'
                'Ran the unit tests.\n'
                '\n'
                'Bugs closed: 123, 456\n'
                '\n'
                'Reviewed at https://reviews.example.com/r/789/'
            ),
            {
                'bugs_closed': '123, 456',
                'description': 'This fixes the thing.',
                'summary': 'Fix the thing',
                'testing_done': 'Ran the unit tests.',
            })

    def test_testing_done_multiline(self) -> None:
        """Testing parse_commit_message with multiline Testing Done"""
        self.assertEqual(
            parse_commit_message(
                'Fix the thing\n'
                '\n'
                'Description here.\n'
                '\n'
                'Testing Done:\n'
                'Ran unit tests.\n'
                'Also ran integration tests.\n'
                '\n'
                'Bugs closed: 42'
            ),
            {
                'bugs_closed': '42',
                'description': 'Description here.',
                'summary': 'Fix the thing',
                'testing_done': ('Ran unit tests.\n'
                                 'Also ran integration tests.'),
            })

    def test_missing_testing_done(self) -> None:
        """Testing parse_commit_message with no Testing Done field"""
        self.assertEqual(
            parse_commit_message(
                'Fix the thing\n'
                '\n'
                'Description.\n'
                '\n'
                'Bugs closed: 123'
            ),
            {
                'bugs_closed': '123',
                'description': 'Description.',
                'summary': 'Fix the thing',
            })

    def test_missing_bugs_closed(self) -> None:
        """Testing parse_commit_message with no Bugs closed field"""
        self.assertEqual(
            parse_commit_message(
                'Fix the thing\n'
                '\n'
                'Description.\n'
                '\n'
                'Testing Done:\n'
                'Unit tests pass.'
            ),
            {
                'description': 'Description.',
                'summary': 'Fix the thing',
                'testing_done': 'Unit tests pass.',
            })

    def test_reviewed_at_stripped(self) -> None:
        """Testing parse_commit_message strips Reviewed at URL"""
        self.assertEqual(
            parse_commit_message(
                'Fix the thing\n'
                '\n'
                'Description.\n'
                '\n'
                'Reviewed at https://reviews.example.com/r/789/'
            ),
            {
                'description': 'Description.',
                'summary': 'Fix the thing',
            })

    def test_empty_message(self) -> None:
        """Testing parse_commit_message with empty message"""
        self.assertEqual(
            parse_commit_message(''),
            None)

    def test_custom_parser(self) -> None:
        """Testing parse_commit_message with custom_parser"""
        def my_parser(message: str) -> ParsedCommitMessage:
            return {
                'description': message,
                'summary': 'custom',
            }

        self.assertEqual(
            parse_commit_message('original', custom_parser=my_parser),
            {
                'description': 'original',
                'summary': 'custom',
            })

    def test_custom_parser_with_extra_keys(self) -> None:
        """Testing parse_commit_message with custom_parser returning extra
        keys
        """
        class MyParsedCommitMessage(ParsedCommitMessage, total=False):
            my_custom_field: str

        def my_parser(message: str) -> MyParsedCommitMessage:
            return {
                'my_custom_field': 'extra',
                'summary': 'custom',
            }

        self.assertEqual(
            parse_commit_message('original', custom_parser=my_parser),
            {
                'my_custom_field': 'extra',
                'summary': 'custom',
            })

    def test_roundtrip_with_format_commit_message(self) -> None:
        """Testing parse_commit_message with output from
        format_commit_message
        """
        client = self.create_rbclient()
        transport = self.get_rbclient_transport(client)

        url_info = transport.add_review_request_url(
            review_request_id=42,
            summary='Fix the widget',
            description='The widget was broken.',
            testing_done='Ran all tests.',
            bugs_closed=['101', '202'])

        review_request = client.get_url(url_info['url'])
        assert isinstance(review_request, ReviewRequestItemResource)

        self.assertEqual(
            parse_commit_message(format_commit_message(review_request)),
            {
                'summary': 'Fix the widget',
                'description': 'The widget was broken.',
                'testing_done': 'Ran all tests.',
                'bugs_closed': '101, 202',
            })
