from rbtools.commands import Command, CommandError, Option, OptionGroup
from rbtools.utils.commands import get_review_request
from rbtools.utils.console import confirm
from rbtools.utils.review_request import (get_raw_commit_message,
                                          get_draft_or_current_value,
                                          guess_existing_review_request_id)


class Stamp(Command):
    """Add the review request URL to the last commit message.

    Guesses the existing review request ID and stamp the review request URL
    to the last commit message. If a review request ID is specified by the
    user, use the specified review request URL instead of guessing.
    """
    name = 'stamp'
    author = 'The Review Board Project'

    option_list = [
        OptionGroup(
            name='Stamp Options',
            description='Controls the behavior of a stamp, including what '
                        'review request URL gets stamped.',
            option_list=[
                Option('-r', '--review-request-id',
                       dest='rid',
                       metavar='ID',
                       default=None,
                       help='Specifies the existing review request ID to '
                            'be stamped.'),
            ]
        ),
        Command.server_options,
        Command.repository_options,
        Command.diff_options,
    ]

    def no_commit_error(self):
        raise CommandError('No existing commit to stamp on.')

    def _ask_review_request_match(self, review_request):
        question = ("Stamp last commit with Review Request #%s: '%s'? "
                    % (review_request.id,
                       get_draft_or_current_value(
                           'summary', review_request)))

        return confirm(question)

    def main(self, *args):
        """Stamp the latest commit with corresponding review request URL"""
        self.cmd_args = list(args)

        repository_info, self.tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, self.tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(self.tool, api_root=api_root)

        if not self.tool.can_amend_commit:
            raise NotImplementedError('rbt stamp is not supported with %s.'
                                      % self.tool.name)

        commit_message = get_raw_commit_message(self.tool, self.cmd_args)

        if '\nReviewed at http' in commit_message:
            raise CommandError('This commit is already stamped.')

        if not self.options.rid:
            self.options.rid = guess_existing_review_request_id(
                repository_info, self.options.repository_name, api_root,
                api_client, self.tool, self.cmd_args, guess_summary=False,
                guess_description=False,
                is_fuzzy_match_func=self._ask_review_request_match,
                no_commit_error=self.no_commit_error)

            if not self.options.rid:
                raise CommandError('Could not determine the existing review '
                                   'request URL to stamp with.')

        review_request = get_review_request(self.options.rid, api_root)
        stamp_url = review_request.absolute_url
        commit_message += '\n\nReviewed at %s' % stamp_url

        self.tool.amend_commit(commit_message)
        print('Changes committed to current branch.')
