from __future__ import unicode_literals

import os

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
               dest='filename',
               default=None,
               help='Custom filename for the file attachment.'),
        Option('--caption',
               dest='caption',
               default=None,
               help='Caption for the file attachment.'),
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

        try:
            with open(path_to_file, 'rb') as f:
                content = f.read()
        except IOError:
            raise CommandError('%s is not a valid file.' % path_to_file)

        # Check if the user specified a custom filename, otherwise
        # use the original filename.
        filename = self.options.filename or os.path.basename(path_to_file)

        try:
            review_request.get_file_attachments().upload_attachment(
                filename, content, self.options.caption)
        except APIError as e:
            raise CommandError('Error uploading file: %s' % e)

        self.stdout.write('Uploaded %s to review request %s.'
                          % (path_to_file, review_request_id))
