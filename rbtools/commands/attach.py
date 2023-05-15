"""Implementation of rbt attach."""

import os
from urllib.parse import urljoin

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option


class Attach(Command):
    """Attach a file to a review request."""

    name = 'attach'
    author = 'The Review Board Project'

    needs_api = True

    args = '<review-request-id> <file>'
    option_list = [
        Option('--filename',
               default=None,
               help='Custom filename for the file attachment.'),
        Option('--caption',
               default=None,
               help='Caption for the file attachment.'),
        Option('--attachment-history-id',
               default=None,
               metavar='ID',
               help='The ID of an existing file attachment history record '
                    'to append this attachment to. This will replace the '
                    'existing attachment, and enable diffing for files '
                    'that support it.',
               added_in='3.0'),
        Command.server_options,
        Command.repository_options,
    ]

    def main(self, review_request_id, path_to_file):
        try:
            review_request = self.api_root.get_review_request(
                review_request_id=review_request_id)
        except APIError as e:
            raise CommandError('Error getting review request %s: %s'
                               % (review_request_id, e))

        path_to_file = os.path.abspath(path_to_file)

        try:
            with open(path_to_file, 'rb') as f:
                content = f.read()
        except IOError:
            raise CommandError('%s is not a valid file.' % path_to_file)

        # Check if the user specified a custom filename, otherwise
        # use the original filename.
        filename = self.options.filename or os.path.basename(path_to_file)

        try:
            attachment = (
                review_request.get_file_attachments()
                .upload_attachment(
                    filename=filename,
                    content=content,
                    caption=self.options.caption,
                    attachment_history=self.options.attachment_history_id)
            )
        except APIError as e:
            raise CommandError('Error uploading file: %s' % e)

        self.stdout.write('Uploaded %s to review request %s.'
                          % (path_to_file, review_request_id))

        review_url = attachment.review_url

        if review_url.startswith('/'):
            review_url = urljoin(self.server_url, review_url)

        self.json.add('attached_file', path_to_file)
        self.json.add('attachment_history_id',
                      attachment.attachment_history_id)
        self.json.add('caption', attachment.caption)
        self.json.add('download_url', attachment.absolute_url)
        self.json.add('filename', attachment.filename)
        self.json.add('id', attachment.id)
        self.json.add('mimetype', attachment.mimetype)
        self.json.add('review_request_id', review_request_id)
        self.json.add('review_request_url', review_request.absolute_url)
        self.json.add('review_url', review_url)
        self.json.add('revision', attachment.revision)
