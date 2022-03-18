from __future__ import unicode_literals

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
                                          guess_existing_review_request,
                                          parse_review_request_url)


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

    needs_api = True
    needs_scm_client = True
    needs_repository = True

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

    def patch(self, review_request_id, squash=False):
        """Patch a single review request's diff using rbt patch.

        Args:
            review_request_id (int):
                The ID of the review request to patch.

            squash (bool, optional):
                Whether to squash multiple commits into a single commit.

        Raises:
            rbtools.commands.CommandError:
                There was an error applying the patch.
        """
        patch_command = [RB_MAIN, 'patch']
        patch_command.extend(build_rbtools_cmd_argv(self.options))

        if self.options.edit:
            patch_command.append('-c')
        else:
            patch_command.append('-C')

        if squash:
            patch_command.append('--squash')

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
        """Land an individual review request.

        Args:
            destination_branch (unicode):
                The destination branch that the change will be committed or
                merged to.

            review_request (rbtools.api.resource.ReviewRequestResource):
                The review request containing the change to land.

            source_branch (unicode, optional):
                The source branch to land, if landing from a local branch.

            squash (bool, optional):
                Whether to squash the changes on the branch, for repositories
                that support it.

            edit (bool, optional):
                Whether to edit the commit message before landing.

            delete_branch (bool, optional):
                Whether to delete/close the branch, if landing from a local
                branch.

            dry_run (bool, optional):
                Whether to simulate landing without actually changing the
                repository.
        """
        json_data = {
            'review_request_id': review_request.id,
            'review_request_url': review_request.absolute_url,
            'destination_branch': destination_branch,
            'source_branch': None,
        }

        if source_branch:
            review_commit_message = extract_commit_message(review_request)
            author = review_request.get_submitter()

            json_data['source_branch'] = source_branch

            if squash:
                self.stdout.write('Squashing branch "%s" into "%s".'
                                  % (source_branch, destination_branch))
                json_data['type'] = 'squash'
            else:
                self.stdout.write('Merging branch "%s" into "%s".'
                                  % (source_branch, destination_branch))
                json_data['type'] = 'merge'

            if not dry_run:
                try:
                    self.tool.merge(target=source_branch,
                                    destination=destination_branch,
                                    message=review_commit_message,
                                    author=author,
                                    squash=squash,
                                    run_editor=edit,
                                    close_branch=delete_branch)
                except MergeError as e:
                    raise CommandError(six.text_type(e))
        else:
            self.stdout.write('Applying patch from review request %s.'
                              % review_request.id)

            json_data['type'] = 'patch'

            if not dry_run:
                self.patch(review_request.id,
                           squash=squash)

        self.stdout.write('Review request %s has landed on "%s".'
                          % (review_request.id,
                             self.options.destination_branch))
        self.json.append('landed_review_requests', json_data)

    def initialize(self):
        """Initialize the command.

        This overrides Command.initialize in order to handle full review
        request URLs on the command line. In this case, we want to parse that
        URL in order to pull the server name and review request ID out of it.

        Raises:
            rbtools.commands.CommandError:
                A review request URL passed in as the review request ID could
                not be parsed correctly or included a bad diff revision.
        """
        review_request_id = self.options.rid

        if review_request_id and review_request_id.startswith('http'):
            server_url, review_request_id, diff_revision = \
                parse_review_request_url(review_request_id)

            if diff_revision and '-' in diff_revision:
                raise CommandError('Interdiff patches are not supported: %s.'
                                   % diff_revision)

            if review_request_id is None:
                raise CommandError('The URL %s does not appear to be a '
                                   'review request.')

            self.options.server = server_url
            self.options.rid = review_request_id

        super(Land, self).initialize()

    def main(self, branch_name=None, *args):
        """Run the command."""
        self.cmd_args = list(args)

        if branch_name:
            self.cmd_args.insert(0, branch_name)

        if not self.tool.can_merge:
            raise CommandError('This command does not support %s repositories.'
                               % self.tool.name)

        if self.options.push and not self.tool.can_push_upstream:
            raise CommandError('--push is not supported for %s repositories.'
                               % self.tool.name)

        if self.tool.has_pending_changes():
            raise CommandError('Working directory is not clean.')

        if not self.options.destination_branch:
            raise CommandError('Please specify a destination branch.')

        if not self.tool.can_squash_merges:
            # If the client doesn't support squashing, then never squash.
            self.options.squash = False

        if self.options.rid:
            is_local = branch_name is not None
            review_request_id = self.options.rid
        else:
            try:
                review_request = guess_existing_review_request(
                    api_root=self.api_root,
                    api_client=self.api_client,
                    tool=self.tool,
                    revisions=get_revisions(self.tool, self.cmd_args),
                    guess_summary=False,
                    guess_description=False,
                    is_fuzzy_match_func=self._ask_review_request_match,
                    repository_id=self.repository.id)
            except ValueError as e:
                raise CommandError(six.text_type(e))

            if not review_request or not review_request.id:
                raise CommandError('Could not determine the existing review '
                                   'request URL to land.')

            review_request_id = review_request.id
            is_local = True

        try:
            review_request = self.api_root.get_review_request(
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
            self.json.add('is_approved', False)
            self.json.add('approval_failure', {
                'review_request_id': review_request.id,
                'review_request_url': review_request.absolute_url,
                'message': land_error,
            })

            raise CommandError('Cannot land review request %s: %s'
                               % (review_request_id, land_error))

        land_kwargs = {
            'delete_branch': self.options.delete_branch,
            'destination_branch': self.options.destination_branch,
            'dry_run': self.options.dry_run,
            'edit': self.options.edit,
            'squash': self.options.squash,
        }

        self.json.add('landed_review_requests', [])

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
                self.stdout.write('Recursively landing dependencies of '
                                  'review request %s.'
                                  % review_request_id)

                for dependency in dependencies:
                    land_error = self.can_land(dependency)

                    if land_error is not None:
                        self.json.add('is_approved', False)
                        self.json.add('approval_failure', {
                            'review_request_id': review_request.id,
                            'review_request_url': review_request.absolute_url,
                            'message': land_error,
                        })

                        raise CommandError(
                            'Aborting recursive land of review request %s.\n'
                            'Review request %s cannot be landed: %s'
                            % (review_request_id, dependency.id, land_error))

                for dependency in reversed(dependencies):
                    self.land(review_request=dependency, **land_kwargs)

        self.json.add('is_approved', True)

        self.land(review_request=review_request,
                  source_branch=branch_name,
                  **land_kwargs)

        if self.options.push:
            self.stdout.write('Pushing branch "%s" upstream'
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
