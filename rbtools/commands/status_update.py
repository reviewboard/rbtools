"""Implementation of rbt status-update."""

import json
import logging

from rbtools.api.errors import APIError
from rbtools.commands import (BaseMultiCommand,
                              BaseSubCommand,
                              Command,
                              CommandError,
                              CommandExit,
                              Option,
                              OptionGroup)


class BaseStatusUpdateSubCommand(BaseSubCommand):
    """Base class for all status update subcommands.

    This provides utilities for printing information or storing JSON data
    on status updates.

    Version Added:
        3.0
    """

    needs_api = True

    def print(self, response):
        """Print output in format specified by user.

        Args:
            response (list, dict):
                Response from API with list of status-updates or a single
                status-update.
        """
        self.json.add('status_updates', [])

        if isinstance(response, list):
            for status_update in response:
                self._print_status_update(status_update)
                self.json.append('status_updates',
                                 self._dict_status_update(status_update))
        else:
            self._print_status_update(response)
            self.json.append('status_updates',
                             self._dict_status_update(response))

    def _print_status_update(self, status_update):
        """Print status update in a human readable format.

        Args:
            status_update (rbtools.api.transport.Transport):
                Representation of status-update API for a review request.
        """
        if status_update.get('description'):
            description = ': %s' % status_update.get('description')
        else:
            description = ''

        self.stdout.write(' %d\t%s: <%s> %s%s'
                          % (status_update.get('id'),
                             status_update.get('service_id'),
                             status_update.get('state'),
                             status_update.get('summary'),
                             description))

    def _dict_status_update(self, status_update):
        """Create a dict for status update.

        Args:
            status_update (rbtools.api.transport.Transport):
                Representation of status-update API for a review request.

        Returns:
            dict:
            Description of status_update that was passed in.
        """
        keys = [
            'change',
            'description',
            'extra_data',
            'id',
            'review',
            'service_id',
            'state',
            'summary',
            'timeout',
            'url',
            'url_text',
        ]

        return {
            key: status_update.get(key)
            for key in keys
            if status_update.get(key)
        }


class GetStatusUpdateSubCommand(BaseStatusUpdateSubCommand):
    """Subcommand for displaying information on status updates.

    Version Added:
        3.0
    """

    name = 'get'

    option_list = [
        OptionGroup(
            name='Status Update Options',
            option_list=[
                Option('-s', '--status-update-id',
                       dest='sid',
                       metavar='ID',
                       type=int,
                       help='A specific status update to display.'),
            ]
        ),
    ]

    def main(self):
        """Handle getting status update information from Review Board.

        Raises:
            rbtools.commands.CommandError:
                Error with the execution of the command.

            rbtools.commands.CommandExit:
                Stop executing and return an exit status.
        """
        status_update_id = self.options.sid
        review_request_id = self.options.rid

        try:
            if status_update_id:
                self.print(
                    self.api_root.get_status_update(
                        review_request_id=review_request_id,
                        status_update_id=status_update_id)
                    .rsp.get('status_update'))
            else:
                self.print(
                    self.api_root.get_status_updates(
                        review_request_id=review_request_id)
                    .rsp.get('status_updates'))
        except APIError as e:
            if e.rsp:
                self.stdout.write(json.dumps(e.rsp, indent=2))
                raise CommandExit(1)
            else:
                raise CommandError('Could not retrieve the requested '
                                   'resource: %s' % e)


class SetStatusUpdateSubCommand(BaseStatusUpdateSubCommand):
    """Subcommand for creating or modifying status updates.

    Version Added:
        3.0
    """

    name = 'set'

    option_list = [
        OptionGroup(
            name='Status Update Options',
            option_list=[
                Option('-s', '--status-update-id',
                       dest='sid',
                       metavar='ID',
                       type=int,
                       help='Specifies which status update from the review '
                            'request.'),
                Option('--review',
                       dest='review',
                       metavar='FILE_PATH',
                       default=None,
                       help='JSON formatted file defining details of '
                            'review(s) to add to status update.'),
                Option('--change-id',
                       dest='change_id',
                       metavar='ID',
                       type=int,
                       help='The change to a review request which this status '
                            'update applies to. When not specified, the '
                            'status update is for the review request as '
                            'initially published.'),
                Option('--description',
                       dest='description',
                       metavar='TEXT',
                       default=None,
                       help='A user-visible description of the status '
                            'update.'),
                Option('--service-id',
                       dest='service_id',
                       metavar='SERVICE_ID',
                       default=None,
                       help='A unique identifier for the service providing '
                            'the status update.'),
                Option('--state',
                       dest='state',
                       metavar='STATE',
                       default=None,
                       choices=(
                           'pending',
                           'done-failure',
                           'done-success',
                           'error',
                       ),
                       help='The current state of the status update.'),
                Option('--summary',
                       dest='summary',
                       metavar='TEXT',
                       default=None,
                       help='A user-visible short summary of the status '
                            'update.'),
                Option('--timeout',
                       dest='timeout',
                       metavar='TIMEOUT',
                       type=int,
                       help='Timeout for pending status updates, measured in '
                            'seconds.'),
                Option('--url',
                       dest='url',
                       metavar='URL',
                       default=None,
                       help='URL to link to for more details about the status '
                            'update.'),
                Option('--url-text',
                       dest='url_text',
                       metavar='URL_TEXT',
                       default=None,
                       help='The text to use for the --url link.'),
            ]
        ),
    ]

    def main(self):
        """Handle setting status update information on Review Board.

        Raises:
            rbtools.commands.CommandError:
                Error with the execution of the command.

            rbtools.commands.CommandExit:
                Stop executing and return an exit status.
        """
        # If a review file is specified, create review.
        new_review_draft = None
        review_draft_id = None

        if self.options.review:
            new_review_draft = self.add_review()
            review_draft_id = new_review_draft.id

        # Build query args.
        request_parameters = ['change_id', 'description', 'service_id',
                              'state', 'summary', 'timeout', 'url',
                              'url_text']

        options = vars(self.options)

        query_args = {
            parameter: options.get(parameter)
            for parameter in iter(request_parameters)
            if options.get(parameter) is not None
        }

        # Attach review to status-update.
        if review_draft_id:
            query_args['review_id'] = review_draft_id

        try:
            if self.options.sid:
                status_update = self.api_root.get_status_update(
                    review_request_id=self.options.rid,
                    status_update_id=self.options.sid)

                status_update = status_update.update(**query_args)
            else:
                if not self.options.service_id or not self.options.summary:
                    raise CommandError('--service-id and --summary are '
                                       'required input for creating a new '
                                       'status update')

                status_update = self.api_root.get_status_updates(
                    review_request_id=self.options.rid)

                status_update = status_update.create(**query_args)

            # Make review public.
            if new_review_draft:
                new_review_draft.update(public=True)

            self.print(status_update.rsp.get('status_update'))
        except APIError as e:
            if e.rsp:
                self.stdout.write(json.dumps(e.rsp, indent=2))
                raise CommandExit(1)
            else:
                raise CommandError('Could not set the requested '
                                   'resource: %s' % e)

    def add_review(self):
        """Handle adding a review to a review request from a json file.

        Looks for ``reviews``, ``diff_comments``, and ``general_comments`` keys
        in the json file contents and populates the review accordingly.

        To find appropriate inputs for each key:

        ``reviews``:
            Look at Web API documentation for POST on the Review List resource
            for available fields.

        ``diff_comments``:
            Look at Web API documentation for POST on the Review Diff Comment
            List resource for available fields. All diff comments require
            ``first_line``, ``filediff_id``, ``num_lines``, and ``text`` field
            to be specified.

        ``general_comments``:
            Look at Web API documentation for POST on the Review General
            Comment List resource for available fields. All general comments
            require ``text`` field to be specified.

        Example file contents::

            {
                "review": {
                    "body_top": "Header comment"
                },
                "diff_comments": [
                    {
                        "filediff_id": 10,
                        "first_line": 729,
                        "issue_opened": true,
                        "num_lines": 1,
                        "text": "Adding a comment on a diff line",
                        "text_type": "markdown"
                    }
                ],
                "general_comments": [
                    {
                        "text": "Adding a general comment",
                        "text_type": "markdown"
                    }
                ]
            }

        Raises:
            rbtools.commands.CommandError:
                Error with the execution of the command.
        """
        with open(self.options.review) as f:
            file_contents = json.loads(f.read())

        review_draft = self.api_root.get_reviews(
            review_request_id=self.options.rid)

        if ('reviews' not in file_contents and
            'diff_comments' not in file_contents and
            'general_comments' not in file_contents):
            raise CommandError('No information in review file, this will '
                               'create an empty review.')

        if 'reviews' in file_contents:
            # Make sure public is false so that comments can be added.
            file_contents['reviews']['public'] = False

            new_review_draft = review_draft.create(**file_contents['reviews'])
        else:
            new_review_draft = review_draft.create()

        if 'diff_comments' in file_contents:
            diff_comments = new_review_draft.get_diff_comments()

            for comment in file_contents['diff_comments']:
                try:
                    diff_comments.create(**comment)
                except APIError as e:
                    logging.warning('Failed to create diff comment: %s\n'
                                    'APIError: %s',
                                    json.dumps(comment),
                                    e)

        if 'general_comments' in file_contents:
            general_comments = new_review_draft.get_general_comments()

            for comment in file_contents['general_comments']:
                try:
                    general_comments.create(**comment)
                except APIError as e:
                    logging.warning('Failed to create general comment: %s\n'
                                    'APIError: %s',
                                    json.dumps(comment),
                                    e)

        return new_review_draft


class DeleteStatusUpdateSubCommand(BaseStatusUpdateSubCommand):
    """Subcommand for deleting status updates.

    Version Added:
        3.0
    """

    name = 'delete'

    option_list = [
        OptionGroup(
            name='Status Update Options',
            option_list=[
                Option('-s', '--status-update-id',
                       dest='sid',
                       metavar='ID',
                       type=int,
                       required=True,
                       help='Specifies which status update from the review '
                            'request.'),
            ]
        ),
    ]

    def main(self):
        """Handle deleting status updates on Review Board.

        Raises:
            rbtools.commands.CommandError:
                Error with the execution of the command.
        """
        status_update_id = self.options.sid
        review_request_id = self.options.rid

        try:
            status_update = self.api_root.get_status_update(
                review_request_id=review_request_id,
                status_update_id=status_update_id)

            status_update.delete()
        except APIError as e:
            raise CommandError('Could not delete the requested resource: '
                               '%s' % e)

        self.stdout.write('Status update %s has been deleted.'
                          % status_update_id)


class StatusUpdate(BaseMultiCommand):
    """Interact with review request status updates on Review Board.

    This command allows setting, getting and deleting status updates for review
    requests.

    A status update is a way for a third-party service or extension to mark
    some kind of status on a review request.
    """

    name = 'status-update'
    author = 'The Review Board Project'

    description = ('Interact with review request status updates on Review '
                   'Board.')

    subcommands = [
        GetStatusUpdateSubCommand,
        SetStatusUpdateSubCommand,
        DeleteStatusUpdateSubCommand,
    ]

    common_subcommand_option_list = [
        OptionGroup(
            name='Status Update Options',
            description='Controls the behavior of a status-update, including '
                        'what review request the status update is attached '
                        'to.',
            option_list=[
                Option('-r', '--review-request-id',
                       dest='rid',
                       metavar='ID',
                       type=int,
                       required=True,
                       help='Specifies which review request.'),
            ]
        ),
        Command.server_options,
    ]

    def run_from_argv(self, argv):
        """Execute the command using the provided arguments.

        This will first check if the command is being called in the legacy
        (pre-RBTools 3) style, with the subcommand name as the last argument.
        If so, a warning will be logged and the order of arguments will be
        corrected.

        Args:
            argv (list of unicode):
                The list of command line arguments.
        """
        if argv[-1] in ('delete', 'get', 'set') and argv[-2] != self.name:
            subcommand_name = argv[-1]

            # This is an old-style invocation.
            logging.warning(
                'rbt status-update is being run with "%s" as the last '
                'argument. This is deprecated as of RBTools 3.0, and will '
                'be removed in 4.0. Please update your script to call '
                '`rbt status-update %s ...` instead.',
                subcommand_name, subcommand_name)

            # Rework this to have the command first. Just to be on the safe
            # side, we won't assume anything about where this should be
            # inserted.
            #
            # If we can't find this, then there's something special going on
            # and we'll just let it fail normally.
            i = argv.index(self.name)

            if i != -1:
                argv = argv[:i + 1] + [subcommand_name] + argv[i + 1:-1]

        return super(StatusUpdate, self).run_from_argv(argv)
