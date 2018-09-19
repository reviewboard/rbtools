from __future__ import print_function, unicode_literals

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option
from rbtools.utils.commands import extract_commit_message
from rbtools.utils.filesystem import make_tempfile


class Patch(Command):
    """Applies a specific patch from a RB server.

    The patch file indicated by the request id is downloaded from the
    server and then applied locally."""

    name = 'patch'
    author = 'The Review Board Project'
    args = '<review-request-id>'
    option_list = [
        Option('-c', '--commit',
               dest='commit',
               action='store_true',
               default=False,
               help='Commits using information fetched '
                    'from the review request (Git/Mercurial only).',
               added_in='0.5.3'),
        Option('-C', '--commit-no-edit',
               dest='commit_no_edit',
               action='store_true',
               default=False,
               help='Commits using information fetched '
                    'from the review request (Git/Mercurial only). '
                    'This differs from --commit by not invoking the editor '
                    'to modify the commit message.'),
        Option('--diff-revision',
               dest='diff_revision',
               metavar='REVISION',
               default=None,
               help='The Review Board diff revision ID to use for the patch.'),
        Option('--px',
               dest='px',
               metavar='NUM',
               default=None,
               help="Strips the given number of paths from filenames in the "
                    "diff. Equivalent to patch's `-p` argument."),
        Option('--print',
               dest='patch_stdout',
               action='store_true',
               default=False,
               help='Prints the patch to standard output instead of applying '
                    'it to the tree.',
               added_in='0.5.3'),
        Option('-R', '--revert',
               dest='revert_patch',
               action='store_true',
               default=False,
               help='Revert the given patch instead of applying it.\n'
                    'This feature does not work with Bazaar or Mercurial '
                    'repositories.',
               added_in='0.7.3'),
        Command.server_options,
        Command.repository_options,
    ]

    def get_patch(self, request_id, api_root, diff_revision=None):
        """Return the diff as a string, the used diff revision and its basedir.

        If a diff revision is not specified, then this will look at the most
        recent diff.
        """
        try:
            diffs = api_root.get_diffs(review_request_id=request_id)
        except APIError as e:
            raise CommandError('Error getting diffs: %s' % e)

        # Use the latest diff if a diff revision was not given.
        # Since diff revisions start a 1, increment by one, and
        # never skip a number, the latest diff revisions number
        # should be equal to the number of diffs.
        if diff_revision is None:
            diff_revision = diffs.total_results

        try:
            diff = diffs.get_item(diff_revision)
            diff_body = diff.get_patch().data
            base_dir = getattr(diff, 'basedir', None) or ''
        except APIError:
            raise CommandError('The specified diff revision does not exist.')

        return diff_body, diff_revision, base_dir

    def apply_patch(self, repository_info, tool, request_id, diff_revision,
                    diff_file_path, base_dir, revert=False):
        """Apply patch patch_file and display results to user."""
        if revert:
            print('Patch is being reverted from request %s with diff revision '
                  '%s.' % (request_id, diff_revision))
        else:
            print('Patch is being applied from request %s with diff revision '
                  '%s.' % (request_id, diff_revision))

        result = tool.apply_patch(diff_file_path, repository_info.base_path,
                                  base_dir, self.options.px, revert=revert)

        if result.patch_output:
            print()
            print(result.patch_output.strip())
            print()

        if not result.applied:
            if revert:
                raise CommandError(
                    'Unable to revert the patch. The patch may be invalid, or '
                    'there may be conflicts that could not be resolved.')
            else:
                raise CommandError(
                    'Unable to apply the patch. The patch may be invalid, or '
                    'there may be conflicts that could not be resolved.')

        if result.has_conflicts:
            if result.conflicting_files:
                if revert:
                    print('The patch was partially reverted, but there were '
                          'conflicts in:')
                else:
                    print('The patch was partially applied, but there were '
                          'conflicts in:')

                print()

                for filename in result.conflicting_files:
                    print('    %s' % filename)

                print()
            elif revert:
                print('The patch was partially reverted, but there were '
                      'conflicts.')
            else:
                print('The patch was partially applied, but there were '
                      'conflicts.')

            return False
        else:
            if revert:
                print('Successfully reverted patch.')
            else:
                print('Successfully applied patch.')

            return True

    def main(self, request_id):
        """Run the command."""
        if self.options.patch_stdout and self.options.server:
            server_url = self.options.server
        else:
            repository_info, tool = self.initialize_scm_tool(
                client_name=self.options.repository_type)

            if self.options.revert_patch and not tool.supports_patch_revert:
                raise CommandError('The %s backend does not support reverting '
                                   'patches.' % tool.name)

            server_url = self.get_server_url(repository_info, tool)

        api_client, api_root = self.get_api(server_url)

        if not self.options.patch_stdout:
            self.setup_tool(tool, api_root=api_root)

            # Check if repository info on reviewboard server match local ones.
            repository_info = repository_info.find_server_repository_info(
                api_root)

        # Get the patch, the used patch ID and base dir for the diff
        diff_body, diff_revision, base_dir = self.get_patch(
            request_id,
            api_root,
            self.options.diff_revision)

        if self.options.patch_stdout:
            if isinstance(diff_body, bytes):
                print(diff_body.decode('utf-8'))
            else:
                print(diff_body)
        else:
            try:
                if tool.has_pending_changes():
                    message = 'Working directory is not clean.'

                    if not self.options.commit:
                        print('Warning: %s' % message)
                    else:
                        raise CommandError(message)
            except NotImplementedError:
                pass

            tmp_patch_file = make_tempfile(diff_body)

            success = self.apply_patch(repository_info, tool, request_id,
                                       diff_revision, tmp_patch_file, base_dir,
                                       revert=self.options.revert_patch)

            if not success:
                raise CommandError('Could not apply patch')

            if self.options.commit or self.options.commit_no_edit:
                try:
                    review_request = api_root.get_review_request(
                        review_request_id=request_id,
                        force_text_type='plain')
                except APIError as e:
                    raise CommandError('Error getting review request %s: %s'
                                       % (request_id, e))

                message = extract_commit_message(review_request)
                author = review_request.get_submitter()

                try:
                    tool.create_commit(message, author,
                                       not self.options.commit_no_edit)
                    print('Changes committed to current branch.')
                except NotImplementedError:
                    raise CommandError('--commit is not supported with %s'
                                       % tool.name)
