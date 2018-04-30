from __future__ import print_function, unicode_literals

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option


SUBMITTED = 'submitted'
DISCARDED = 'discarded'


class Close(Command):
    """Close a specific review request as discarded or submitted.

    By default, the command will change the status to submitted. The
    user can provide an optional description for this action.
    """

    name = 'close'
    author = 'The Review Board Project'
    args = '<review-request-id>'
    option_list = [
        Option('--close-type',
               dest='close_type',
               default=SUBMITTED,
               help='Either `submitted` or `discarded`.'),
        Option('--description',
               dest='description',
               default=None,
               help='An optional description accompanying the change.'),
        Command.server_options,
        Command.repository_options,
    ]

    def check_valid_type(self, close_type):
        """Check if the user specificed a proper type.

        Type must either be 'discarded' or 'submitted'. If the type
        is wrong, the command will stop and alert the user.
        """
        if close_type not in (SUBMITTED, DISCARDED):
            raise CommandError('%s is not valid type. Try "%s" or "%s"' % (
                self.options.close_type, SUBMITTED, DISCARDED))

    def main(self, review_request_id):
        """Run the command."""
        close_type = self.options.close_type
        self.check_valid_type(close_type)
        if self.options.server:
            # Bypass getting the scm_tool to discover the server since it was
            # specified with --server or in .reviewboardrc
            repository_info, tool = None, None
        else:
            repository_info, tool = self.initialize_scm_tool(
                client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)

        try:
            review_request = api_root.get_review_request(
                review_request_id=review_request_id)
        except APIError as e:
            raise CommandError('Error getting review request %s: %s'
                               % (review_request_id, e))

        if review_request.status == close_type:
            raise CommandError('Review request #%s is already %s.' % (
                review_request_id, close_type))

        if self.options.description:
            review_request = review_request.update(
                status=close_type,
                description=self.options.description)
        else:
            review_request = review_request.update(status=close_type)

        print('Review request #%s is set to %s.' %
              (review_request_id, review_request.status))
