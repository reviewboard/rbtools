from __future__ import print_function, unicode_literals

import logging

import six

from rbtools.api.errors import APIError
from rbtools.clients.errors import MergeError, PushError
from rbtools.commands import Command, CommandError, Option, RB_MAIN
from rbtools.utils.commands import (build_rbtools_cmd_argv,
                                    extract_commit_message)
from rbtools.utils.console import confirm
from rbtools.utils.graphs import toposort
from rbtools.utils.process import execute
from rbtools.utils.review_request import (get_draft_or_current_value,
                                          get_revisions,
                                          guess_existing_review_request)


class Land(Command):
    """Land changes from a review request onto the remote repository.

    This command takes a review request, applies it to a feature branch,
    merges it with the specified destination branch, and pushes the
    changes to an upstream repository.

    Notes:
        The review request needs to be approved first.

        ``--local`` option can be used to skip the patching step.
    """

    name = 'land'
    author = 'The Review Board Project'
    args = '[<branch-name>]'
    option_list = [
        Option('--dest',
               dest='destination_branch',
               default=None,
               config_key='LAND_DEST_BRANCH',
               help='Specifies the destination branch to land changes on.'),
        Option('-r', '--review-request-id',
               dest='rid',
               metavar='ID',
               default=None,
               help='Specifies the review request ID.'),
        Option('--local',
               dest='is_local',
               action='store_true',
               default=None,
               help='Forces the change to be merged without patching, if '
                    'merging a local branch. Defaults to true unless '
                    '--review-request-id is used.'),
        Option('-p', '--push',
               dest='push',
               action='store_true',
               default=False,
               config_key='LAND_PUSH',
               help='Pushes the branch after landing the change.'),
        Option('-n', '--no-push',
               dest='push',
               action='store_false',
               default=False,
               config_key='LAND_PUSH',
               help='Prevents pushing the branch after landing the change, '
                    'if pushing is enabled by default.'),
        Option('--squash',
               dest='squash',
               action='store_true',
               default=False,
               config_key='LAND_SQUASH',
               help='Squashes history into a single commit.'),
        Option('--no-squash',
               dest='squash',
               action='store_false',
               default=False,
               config_key='LAND_SQUASH',
               help='Disables squashing history into a single commit, '
                    'choosing instead to merge the branch, if squashing is '
                    'enabled by default.'),
        Option('-e', '--edit',
               dest='edit',
               action='store_true',
               default=False,
               help='Invokes the editor to edit the commit message before '
                    'landing the change.'),
        Option('--delete-branch',
               dest='delete_branch',
               action='store_true',
               config_key='LAND_DELETE_BRANCH',
               default=True,
               help="Deletes the local branch after it's landed. Only used if "
                    "landing a local branch. This is the default."),
        Option('--no-delete-branch',
               dest='delete_branch',
               action='store_false',
               config_key='LAND_DELETE_BRANCH',
               default=True,
               help="Prevents the local branch from being deleted after it's "
                    "landed."),
        Option('--dry-run',
               dest='dry_run',
               action='store_true',
               default=False,
               help='Simulates the landing of a change, without actually '
                    'making any changes to the tree.'),
        Option('--recursive',
               dest='recursive',
               action='store_true',
               default=False,
               help='Recursively fetch patches for review requests that the '
                    'specified review request depends on. This is equivalent '
                    'to calling "rbt patch" for each of those review '
                    'requests.',
               added_in='1.0'),
        Command.server_options,
        Command.repository_options,
        Command.branch_options,
    ]

    def patch(self, review_request_id):
        """Patch a single review request's diff using rbt patch."""
        patch_command = [RB_MAIN, 'patch']
        patch_command.extend(build_rbtools_cmd_argv(self.options))

        if self.options.edit:
            patch_command.append('-c')
        else:
            patch_command.append('-C')

        patch_command.append(six.text_type(review_request_id))

        rc, output = execute(patch_command, ignore_errors=True,
                             return_error_code=True)

        if rc:
            raise CommandError('Failed to execute "rbt patch":\n%s'
                               % output)

    def can_land(self, review_request):
        """Determine if the review request is land-able.

        A review request can be landed if it is approved or, if the Review
        Board server does not keep track of approval, if the review request
        has a ship-it count.

        This function returns the error with landing the review request or None
        if it can be landed.
        """
        try:
            is_rr_approved = review_request.approved
            approval_failure = review_request.approval_failure
        except AttributeError:
            # The Review Board server is an old version (pre-2.0) that
            # doesn't support the `approved` field. Determine it manually.
            if review_request.ship_it_count == 0:
                is_rr_approved = False
                approval_failure = \
                    'The review request has not been marked "Ship It!"'
            else:
                is_rr_approved = True
        except Exception as e:
            logging.exception(
                'Unexpected error while looking up review request '
                'approval state: %s',
                e)

            return ('An error was encountered while executing the land '
                    'command.')
        finally:
            if not is_rr_approved:
                return approval_failure

        return None

    def land(self, destination_branch, review_request, source_branch=None,
             squash=False, edit=False, delete_branch=True, dry_run=False):
        """Land an individual review request."""
        if source_branch:
            review_commit_message = extract_commit_message(review_request)
            author = review_request.get_submitter()

            if squash:
                print('Squashing branch "%s" into "%s".'
                      % (source_branch, destination_branch))
            else:
                print('Merging branch "%s" into "%s".'
                      % (source_branch, destination_branch))

            if not dry_run:
                try:
                    self.tool.merge(source_branch,
                                    destination_branch,
                                    review_commit_message,
                                    author,
                                    squash,
                                    edit)
                except MergeError as e:
                    raise CommandError(six.text_type(e))

            if delete_branch:
                print('Deleting merged branch "%s".' % source_branch)

                if not dry_run:
                    self.tool.delete_branch(source_branch, merged_only=False)
        else:
            print('Applying patch from review request %s.' % review_request.id)

            if not dry_run:
                self.patch(review_request.id)

        print('Review request %s has landed on "%s".' %
              (review_request.id, self.options.destination_branch))

    def main(self, branch_name=None, *args):
        """Run the command."""
        self.cmd_args = list(args)

        if branch_name:
            self.cmd_args.insert(0, branch_name)

        repository_info, self.tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, self.tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(self.tool, api_root=api_root)

        # Check if repository info on reviewboard server match local ones.
        repository_info = repository_info.find_server_repository_info(api_root)

        if (not self.tool.can_merge or
            not self.tool.can_push_upstream or
            not self.tool.can_delete_branch):
            raise CommandError('This command does not support %s repositories.'
                               % self.tool.name)

        if self.tool.has_pending_changes():
            raise CommandError('Working directory is not clean.')

        if not self.options.destination_branch:
            raise CommandError('Please specify a destination branch.')

        if self.options.rid:
            is_local = branch_name is not None
            review_request_id = self.options.rid
        else:
            try:
                review_request = guess_existing_review_request(
                    repository_info,
                    self.options.repository_name,
                    api_root,
                    api_client,
                    self.tool,
                    get_revisions(self.tool, self.cmd_args),
                    guess_summary=False,
                    guess_description=False,
                    is_fuzzy_match_func=self._ask_review_request_match)
            except ValueError as e:
                raise CommandError(six.text_type(e))

            if not review_request or not review_request.id:
                raise CommandError('Could not determine the existing review '
                                   'request URL to land.')

            review_request_id = review_request.id
            is_local = True

        try:
            review_request = api_root.get_review_request(
                review_request_id=review_request_id)
        except APIError as e:
            raise CommandError('Error getting review request %s: %s'
                               % (review_request_id, e))

        if self.options.is_local is not None:
            is_local = self.options.is_local

        if is_local:
            if branch_name is None:
                branch_name = self.tool.get_current_branch()

            if branch_name == self.options.destination_branch:
                raise CommandError('The local branch cannot be merged onto '
                                   'itself. Try a different local branch or '
                                   'destination branch.')
        else:
            branch_name = None

        land_error = self.can_land(review_request)

        if land_error is not None:
            raise CommandError('Cannot land review request %s: %s'
                               % (review_request_id, land_error))

        if self.options.recursive:
            # The dependency graph shows us which review requests depend on
            # which other ones. What we are actually after is the order to land
            # them in, which is the topological sorting order of the converse
            # graph. It just so happens that if we reverse the topological sort
            # of a graph, it is a valid topological sorting of the converse
            # graph, so we don't have to compute the converse graph.
            dependency_graph = review_request.build_dependency_graph()
            dependencies = toposort(dependency_graph)[1:]

            if dependencies:
                print('Recursively landing dependencies of review request %s.'
                      % review_request_id)

                for dependency in dependencies:
                    land_error = self.can_land(dependency)

                    if land_error is not None:
                        raise CommandError(
                            'Aborting recursive land of review request %s.\n'
                            'Review request %s cannot be landed: %s'
                            % (review_request_id, dependency.id, land_error))

                for dependency in reversed(dependencies):
                    self.land(self.options.destination_branch,
                              dependency,
                              None,
                              self.options.squash,
                              self.options.edit,
                              self.options.delete_branch,
                              self.options.dry_run)

        self.land(self.options.destination_branch,
                  review_request,
                  branch_name,
                  self.options.squash,
                  self.options.edit,
                  self.options.delete_branch,
                  self.options.dry_run)

        if self.options.push:
            print('Pushing branch "%s" upstream'
                  % self.options.destination_branch)

            if not self.options.dry_run:
                try:
                    self.tool.push_upstream(self.options.destination_branch)
                except PushError as e:
                    raise CommandError(six.text_type(e))

    def _ask_review_request_match(self, review_request):
        return confirm(
            'Land Review Request #%s: "%s"? '
            % (review_request.id,
               get_draft_or_current_value('summary', review_request)))
