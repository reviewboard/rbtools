from __future__ import print_function, unicode_literals

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option
from rbtools.utils.commands import get_review_request


class Publish(Command):
    """Publish a specific review request from a draft."""
    name = 'publish'
    author = 'The Review Board Project'
    args = '<review-request-id>'
    option_list = [
        Command.server_options,
        Command.repository_options,
        Option('-t', '--trivial',
               dest='trivial_publish',
               action='store_true',
               default=False,
               help='Mark this publish as trivial. E-mails are not sent for '
                    'trivial publishes.',
               added_in='0.8.0')
    ]

    def main(self, request_id):
        """Run the command."""
        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)

        request = get_review_request(request_id, api_root)

        self.setup_tool(tool, api_root)

        update_fields = {
            'public': True,
        }

        if (self.options.trivial_publish and
            tool.capabilities.has_capability('review_requests',
                                             'trivial_publish')):
            update_fields['trivial'] = True

        try:
            draft = request.get_draft()
            draft.update(**update_fields)
        except APIError as e:
            raise CommandError('Error publishing review request (it may '
                               'already be published): %s' % e)

        print('Review request #%s is published.' % request_id)
