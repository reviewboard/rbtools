from __future__ import print_function, unicode_literals

import logging

import six

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option, OptionGroup
from rbtools.utils.commands import stamp_commit_with_review_url
from rbtools.utils.console import confirm
from rbtools.utils.review_request import (find_review_request_by_change_id,
                                          get_draft_or_current_value,
                                          get_revisions,
                                          guess_existing_review_request)


class Stamp(Command):
    """Add the review request URL to the commit message.

    Stamps the review request URL onto the commit message of the revision
    specified. The revisions argument behaves like it does in rbt post, where
    it is required for some SCMs (e.g. Perforce) and unnecessary/ignored for
    others (e.g. Git).

    Normally, this command will guess the review request (based on the revision
    number if provided, and the commit summary and description otherwise).
    However, if a review request ID is specified by the user, it stamps the URL
    of that review request instead of guessing.
    """

    name = 'stamp'
    author = 'The Review Board Project'
    description = 'Adds the review request URL to the commit message.'
    args = '[revisions]'

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
        Command.branch_options,
        Command.perforce_options,
    ]

    def no_commit_error(self):
        raise CommandError('No existing commit to stamp on.')

    def _ask_review_request_match(self, review_request):
        question = ('Stamp with Review Request #%s: "%s"? '
                    % (review_request.id,
                       get_draft_or_current_value(
                           'summary', review_request)))

        return confirm(question)

    def determine_review_request(self, api_client, api_root, repository_info,
                                 repository_name, revisions):
        """Determine the correct review request for a commit.

        A tuple (review request ID, review request absolute URL) is returned.
        If no review request ID is found by any of the strategies,
        (None, None) is returned.
        """
        # First, try to match the changeset to a review request directly.
        if repository_info.supports_changesets:
            review_request = find_review_request_by_change_id(
                api_client, api_root, repository_info, repository_name,
                revisions)

            if review_request and review_request.id:
                return review_request.id, review_request.absolute_url

        # Fall back on guessing based on the description. This may return None
        # if no suitable review request is found.
        logging.debug('Attempting to guess review request based on '
                      'summary and description')

        try:
            review_request = guess_existing_review_request(
                repository_info, repository_name, api_root, api_client,
                self.tool, revisions, guess_summary=False,
                guess_description=False,
                is_fuzzy_match_func=self._ask_review_request_match,
                no_commit_error=self.no_commit_error)
        except ValueError as e:
            raise CommandError(six.text_type(e))

        if review_request:
            logging.debug('Found review request ID %d', review_request.id)
            return review_request.id, review_request.absolute_url
        else:
            logging.debug('Could not find a matching review request')
            return None, None

    def main(self, *args):
        """Add the review request URL to a commit message."""
        self.cmd_args = list(args)

        repository_info, self.tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, self.tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(self.tool, api_root=api_root)

        if not self.tool.can_amend_commit:
            raise NotImplementedError('rbt stamp is not supported with %s.'
                                      % self.tool.name)

        try:
            if self.tool.has_pending_changes():
                raise CommandError('Working directory is not clean.')
        except NotImplementedError:
            pass

        revisions = get_revisions(self.tool, self.cmd_args)

        # Use the ID from the command line options if present.
        if self.options.rid:
            review_request_id = self.options.rid

            try:
                review_request = api_root.get_review_request(
                    review_request_id=review_request_id)
            except APIError as e:
                raise CommandError('Error getting review request %s: %s'
                                   % (review_request_id, e))

            review_request_url = review_request.absolute_url
        else:
            review_request_id, review_request_url = \
                self. determine_review_request(
                    api_client, api_root, repository_info,
                    self.options.repository_name, revisions)

        if not review_request_url:
            raise CommandError('Could not determine the existing review '
                               'request URL to stamp with.')

        stamp_commit_with_review_url(revisions, review_request_url, self.tool)

        print('Successfully stamped change with the URL:')
        print(review_request_url)
