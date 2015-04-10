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
        Command.history_options,
    ]

    def get_patches(self, request_id, api_root, diff_revision=None,
                    with_history=False):
        """Return the set of patches for the corresponding review request.

        This function returns a tuple of the following:

         * a list of the history entry (diff, metadata) tuples;
         * the diff revision that was retrieved; and
         * the base directory of the diff.

        In the case of a review request with commit history, the metadata
        portion of each history entry is the ``DiffCommitResource`` instance.
        However, if the review request is a squashed review request or the
        ``with_history`` parameter is False, the metadata will be None.

        If a diff revision is not specified, then this will look at the most
        recent diff.
        """
        try:
            diffs = api_root.get_diffs(review_request_id=request_id)
        except APIError as e:
            raise CommandError('Error retrieving diffs: %s' % e)

        if diff_revision is None:
            diff_revision = diffs.total_results

        try:
            diff = diffs.get_item(diff_revision)
        except APIError:
            raise CommandError('The specified diff revision does not exist.')

        patches = None
        base_dir = getattr(diff, 'basedir', '')

        if with_history:
            try:
                commits = diff.get_diff_commits()
            except APIError as e:
                raise CommandError('Error retrieving commits: %s' % e)

            if commits.total_results == 0:
                # Even though we've determined we should fetch the history, it
                # may be the case that the diff revision we've fetched is
                # squashed.
                with_history = False
            else:
                try:
                    patches = [
                        (commit.get_patch().data, commit)
                        for commit in commits.all_items
                    ]
                except APIError as e:
                    raise CommandError('Error retrieving commits: %s' % e)

        if not with_history:
            try:
                patches = [(diff.get_patch().data, None)]
            except APIError as e:
                raise CommandError('Error retrieving patch: %s' % e)

        return patches, diff_revision, base_dir

    def apply_patch(self, repository_info, tool, request_id, diff_revision,
                    diff_file_path, base_dir, commit_id=None, revert=False):
        """Apply patch patch_file and display results to user."""
        if commit_id:
            commit_id = ' (commit %s)' % commit_id

        commit_id = commit_id or ''

        if revert:
            print('Patch is being reverted from request %s with diff revision '
                  '%s%s.' % (request_id, diff_revision, commit_id))
        else:
            print('Patch is being applied from request %s with diff revision '
                  '%s%s.' % (request_id, diff_revision, commit_id))

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
                print('Successfully reverted patch%s.' % commit_id)
            else:
                print('Successfully applied patch%s.' % commit_id)

            return True

    def main(self, request_id):
        """Run the command."""
        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)

        if self.options.revert_patch and not tool.supports_patch_revert:
            raise CommandError('The %s backend does not support reverting '
                               'patches.' % tool.name)

        if self.options.with_history and not tool.supports_history:
            raise CommandError('The %s backend does not support applying '
                               'patches with history.' % tool.name)

        if self.options.with_history and self.options.patch_revert:
            raise CommandError('The -R option cannot be used when using '
                               'commit histories. You can reverse this patch '
                               'by providing the -S option.')

        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(tool, api_root=api_root)

        # Check if repository info on reviewboard server match local ones.
        repository_info = repository_info.find_server_repository_info(api_root)

        should_commit = self.options.commit or self.options.commit_no_edit

        # When we are not committing our changes, we do can treat this is the
        # no history case. The end result will be the same if we apply all the
        # diffs in order, but this saves us a round trip from checking if the
        # server supports history and from fetching individual commits vs the
        # condensed diff.
        with_history = (should_commit and
                        self.should_use_history(tool, server_url))

        patches, diff_revision, base_dir = self.get_patches(
            request_id,
            api_root,
            self.options.diff_revision,
            with_history)

        if self.options.patch_stdout:
            for patch, _ in patches:
                print(patch)
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

            review_request = None

            if should_commit:
                try:
                    review_request = api_root.get_review_request(
                        review_request_id=request_id,
                        force_text_type='plain')
                except APIError as e:
                    raise CommandError('Error retrieving review request %s: %s'
                                       % (request_id, e))

            for diff_body, metadata in patches:
                tmp_patch_file = make_tempfile(diff_body)

                commit_id = None

                if metadata:
                    commit_id = metadata.commit_id

                success = self.apply_patch(repository_info, tool, request_id,
                                           diff_revision, tmp_patch_file,
                                           base_dir,
                                           revert=self.options.revert_patch,
                                           commit_id=commit_id)

                if not success:
                    raise CommandError('Could not apply all patches.')

                if should_commit:
                    if metadata:
                        author = metadata.author_name_and_email
                        message = metadata.get_commit_message(review_request)
                    else:
                        # We will only have to fetch this once because it is
                        # part of a squashed review request.
                        assert len(patches) == 1

                        try:
                            author = review_request.submitter_name_and_email
                        except APIError as e:
                            raise CommandError('Error retrieving review '
                                               'request %s submitter: %s'
                                               % (request_id, e))

                        message = extract_commit_message(review_request)

                    try:
                        tool.create_commit(message, author,
                                           not self.options.commit_no_edit)
                    except NotImplementedError:
                        raise CommandError('The --commit and --commit-no-edit '
                                           'options are not supported by the '
                                           '%s backend.'
                                           % tool.name)

            if should_commit:
                print('Changes committed to current branch.')
