"""Tests for rbt patch command.

Version Added:
    6.0.1
"""

from __future__ import annotations

from rbtools.api.resource import FileDiffItemResource
from rbtools.commands.patch import PatchCommand
from rbtools.testing import CommandTestsMixin, TestCase
from rbtools.testing.api.transport import URLMapTransport


class GetBinaryFileFromFileDiffTests(CommandTestsMixin[PatchCommand],
                                     TestCase):
    """Tests for PatchCommand._get_binary_file_from_filediff.

    Version Added:
        6.0.1
    """

    command_cls = PatchCommand

    #: Base URL for the test server.
    SERVER_URL = 'https://reviews.example.com/'

    #: Base URL for file diff API endpoints.
    FILE_DIFF_URL = (
        'https://reviews.example.com/api/review-requests/1/diffs/1/files/1/'
    )

    #: URL for the dest attachment link.
    DEST_ATTACHMENT_URL = (
        'https://reviews.example.com/api/review-requests/1/diffs/1/files/1/'
        'dest-attachment/'
    )

    #: URL for the source attachment link.
    SOURCE_ATTACHMENT_URL = (
        'https://reviews.example.com/api/review-requests/1/diffs/1/files/1/'
        'source-attachment/'
    )

    #: Mimetype for file attachment responses.
    FILE_ATTACHMENT_MIMETYPE = (
        'application/vnd.reviewboard.org.file-attachment'
    )

    def _create_file_diff(
        self,
        *,
        source_file: str = 'old.png',
        dest_file: str = 'new.png',
        source_revision: str = 'abc123',
        status: str = 'modified',
        has_dest_attachment: bool = True,
        has_source_attachment: bool = True,
    ) -> FileDiffItemResource:
        """Create a FileDiffItemResource for testing.

        Args:
            source_file (str, optional):
                The source file path.

            dest_file (str, optional):
                The destination file path.

            source_revision (str, optional):
                The source revision.

            status (str, optional):
                The file status.

            has_dest_attachment (bool, optional):
                Whether to include a dest_attachment link.

            has_source_attachment (bool, optional):
                Whether to include a source_attachment link.

        Returns:
            rbtools.api.resource.FileDiffItemResource:
            The constructed file diff resource.
        """
        links = {
            'self': {
                'href': self.FILE_DIFF_URL,
                'method': 'GET',
            },
        }

        transport = URLMapTransport(self.SERVER_URL)

        if has_dest_attachment:
            links['dest_attachment'] = {
                'href': self.DEST_ATTACHMENT_URL,
                'method': 'GET',
            }
            transport.add_url(
                url=self.DEST_ATTACHMENT_URL,
                mimetype=self.FILE_ATTACHMENT_MIMETYPE,
                payload={
                    'stat': 'ok',
                    'file_attachment': {
                        'id': 10,
                        'absolute_url': (
                            'https://reviews.example.com/r/1/file/10/'
                            'download/'
                        ),
                        'links': {
                            'self': {
                                'href': self.DEST_ATTACHMENT_URL,
                                'method': 'GET',
                            },
                        },
                    },
                })

        if has_source_attachment:
            links['source_attachment'] = {
                'href': self.SOURCE_ATTACHMENT_URL,
                'method': 'GET',
            }
            transport.add_url(
                url=self.SOURCE_ATTACHMENT_URL,
                mimetype=self.FILE_ATTACHMENT_MIMETYPE,
                payload={
                    'stat': 'ok',
                    'file_attachment': {
                        'id': 11,
                        'absolute_url': (
                            'https://reviews.example.com/r/1/file/11/'
                            'download/'
                        ),
                        'links': {
                            'self': {
                                'href': self.SOURCE_ATTACHMENT_URL,
                                'method': 'GET',
                            },
                        },
                    },
                })

        return FileDiffItemResource(
            transport=transport,
            payload={
                'stat': 'ok',
                'file': {
                    'id': 1,
                    'binary': True,
                    'dest_detail': '',
                    'dest_file': dest_file,
                    'encoding': '',
                    'extra_data': {},
                    'source_file': source_file,
                    'source_revision': source_revision,
                    'status': status,
                    'links': links,
                },
            },
            url=self.FILE_DIFF_URL,
            token='file',
        )

    def test_with_modified_file(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with modified
        file
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(status='modified')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=False)

        self.assertEqual(result.old_path, 'old.png')
        self.assertEqual(result.new_path, 'new.png')
        self.assertEqual(result.status, 'modified')
        self.assertIsNotNone(result._attachment)

    def test_with_added_file(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with added
        file
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(
            source_revision='PRE-CREATION',
            status='modified')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=False)

        self.assertEqual(result.old_path, 'old.png')
        self.assertEqual(result.new_path, 'new.png')
        self.assertEqual(result.status, 'added')
        self.assertIsNotNone(result._attachment)

    def test_with_deleted_file(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with deleted
        file
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(status='deleted')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=False)

        self.assertEqual(result.old_path, 'old.png')
        self.assertEqual(result.new_path, 'new.png')
        self.assertEqual(result.status, 'deleted')
        self.assertIsNone(result._attachment)

    def test_with_moved_file(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with moved
        file
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(status='moved')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=False)

        self.assertEqual(result.old_path, 'old.png')
        self.assertEqual(result.new_path, 'new.png')
        self.assertEqual(result.status, 'moved')
        self.assertIsNotNone(result._attachment)

    def test_with_reverted_modified_file(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with reverted
        modified file
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(status='modified')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=True)

        self.assertEqual(result.old_path, 'new.png')
        self.assertEqual(result.new_path, 'old.png')
        self.assertEqual(result.status, 'modified')
        self.assertIsNotNone(result._attachment)

    def test_with_reverted_added_file(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with reverted
        added file (becomes deleted)
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(
            source_revision='PRE-CREATION',
            status='modified')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=True)

        self.assertEqual(result.old_path, 'new.png')
        self.assertEqual(result.new_path, 'old.png')
        self.assertEqual(result.status, 'deleted')
        self.assertIsNotNone(result._attachment)

    def test_with_reverted_deleted_file(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with reverted
        deleted file (becomes added)
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(status='deleted')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=True)

        self.assertEqual(result.old_path, 'new.png')
        self.assertEqual(result.new_path, 'old.png')
        self.assertEqual(result.status, 'added')
        self.assertIsNone(result._attachment)

    def test_with_no_dest_attachment_link(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with no
        dest_attachment link
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(
            has_dest_attachment=False,
            status='modified')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=False)

        self.assertEqual(result.old_path, 'old.png')
        self.assertEqual(result.new_path, 'new.png')
        self.assertEqual(result.status, 'modified')
        self.assertIsNone(result._attachment)

    def test_with_no_source_attachment_link_reverted(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with no
        source_attachment link and reverted
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(
            has_source_attachment=False,
            status='modified')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=True)

        self.assertEqual(result.old_path, 'new.png')
        self.assertEqual(result.new_path, 'old.png')
        self.assertEqual(result.status, 'modified')
        self.assertIsNone(result._attachment)

    def test_with_no_attachment_links(self) -> None:
        """Testing PatchCommand._get_binary_file_from_filediff with no
        attachment links
        """
        command = self.create_command(args=['1'])
        file_diff = self._create_file_diff(
            has_dest_attachment=False,
            has_source_attachment=False,
            source_revision='PRE-CREATION',
            status='modified')

        result = command._get_binary_file_from_filediff(
            file_diff, reverted=False)

        self.assertEqual(result.old_path, 'old.png')
        self.assertEqual(result.new_path, 'new.png')
        self.assertEqual(result.status, 'added')
        self.assertIsNone(result._attachment)
