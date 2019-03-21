"""The rbt patch command."""

from __future__ import print_function, unicode_literals

import logging
from gettext import gettext as _

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option
from rbtools.utils.commands import extract_commit_message
from rbtools.utils.filesystem import make_tempfile


logger = logging.getLogger(__name__)


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
        Option('--commit-id',
               dest='commit_id',
               default=None,
               help='The commit ID of the patch to apply.\n'
                    'This only applies to review requests created with commit '
                    'history.'),
        Command.server_options,
        Command.repository_options,
    ]

    def __init__(self):
        """Initialize the patch command."""
        super(Patch, self).__init__()

        self.tool = None

    def get_patch(self, tool, api_root, review_request_id, diff_revision=None,
                  commit_id=None):
        """Return the requested patch and its metadata.

        If a diff revision is not specified, then this will look at the most
        recent diff.

        Args:
            tool (rbtools.clients.SCMClient):
                The SCM tool for the current repository.

            api_root (rbtools.api.resource.RootResource):
                The root resource of the Review Board server.

            request_id (int):
                The ID of the review request.

            diff_revision (int, optional):
                The diff revision to apply.

                The latest revision will be used if not provided.

            commit_id (unicode, optional):
                The specific commit to apply.

                This argument is required if the review request was created
                with commit history.

        Returns:
            dict:
            A dictionary with the following keys:

            ``basedir`` (py:class:`unicode`):
                The base directory of the returned patch.

            ``diff`` (py:class:`bytes`):
                The actual patch contents.

            ``revision`` (py:class:`int`):
                The revision of the returned patch.

            ``commit_meta`` (:py:class:`dict`):
                Metadata about the requested commit if one was requested.
                Otherwise, this will be ``None``.

        Raises:
            rbtools.command.CommandError:
                One of the following occurred:

                * The patch could not be retrieved or does not exist
                * The review request was created with history support and
                  ``commit_id`` was not provided.
                * The review request was created without history support and
                  ``commit_id`` was provided.
                * The requested commit does not exist.
        """
        server_supports_history = tool.capabilities.has_capability(
            'review_requests', 'supports_history')

        if commit_id is not None and not server_supports_history:
            logger.warn('This server does not support review requests with '
                        'history; ignoring --commit-id=...')
            commit_id = None

        if diff_revision is None:
            try:
                diffs = api_root.get_diffs(review_request_id=review_request_id,
                                           only_fields='', only_links='')
            except APIError as e:
                raise CommandError('Error getting diffs: %s' % e)

            # Use the latest diff if a diff revision was not given.
            # Since diff revisions start a 1, increment by one, and
            # never skip a number, the latest diff revisions number
            # should be equal to the number of diffs.
            diff_revision = diffs.total_results

        result = {
            'revision': diff_revision,
        }

        if commit_id is None:
            try:
                diff = api_root.get_diff(review_request_id=review_request_id,
                                         diff_revision=diff_revision)
            except APIError:
                raise CommandError('The specified diff revision does not '
                                   'exist.')

            commit_count = getattr(diff, 'commit_count', 0)

            if commit_count > 0:
                raise CommandError('A commit ID is required.')

            patch_content = diff.get_patch().data
            commit_meta = None
            base_dir = getattr(diff, 'basedir', '')
        else:
            try:
                commit = api_root.get_commit(
                    review_request_id=review_request_id,
                    diff_revision=diff_revision,
                    commit_id=commit_id)
            except APIError:
                # Since we skipped fetching the diff resource earlier, we need
                # to see if the diff exists so we can report the correct error.
                try:
                    api_root.get_diff(review_request_id=review_request_id,
                                      diff_revision=diff_revision)
                except APIError:
                    raise CommandError('The specified diff revision does not '
                                       'exist.')
                else:
                    raise CommandError('The specified commit does not exist.')

            # DiffSets on review requests created with history support *always*
            # have an empty base dir.
            base_dir = ''
            commit_meta = {
                'author_date': commit.author_date,
                'author_email': commit.author_email,
                'author_name': commit.author_name,
                'committer_date': commit.committer_date,
                'commiter_email': commit.committer_email,
                'committer_name': commit.committer_name,
                'message': commit.commit_message,
            }
            patch_content = commit.get_patch().data

        result.update({
            'commit_meta': commit_meta,
            'diff': patch_content,
            'base_dir': base_dir,
        })

        return result

    def apply_patch(self, repository_info, tool, request_id, diff_revision,
                    diff_file_path, base_dir, revert=False, meta=None):
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

    def main(self, review_request_id):
        """Run the command.

        Args:
            review_request_id (int):
                The ID of the review request to patch from.

        Raises:
            rbtools.command.CommandError:
                Patching the tree has failed.
        """
        patch_stdout = self.options.patch_stdout
        revert = self.options.revert_patch

        if patch_stdout and revert:
            raise CommandError(_('--print and --revert cannot both be used.'))

        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type,
            require_repository_info=not patch_stdout)

        if revert and not tool.supports_patch_revert:
            raise CommandError(
                _('The %s backend does not support reverting patches.')
                % tool.name)

        server_url = self.get_server_url(repository_info, tool)

        api_client, api_root = self.get_api(server_url)
        self.setup_tool(tool, api_root=api_root)

        if not patch_stdout:
            # Check if the repository info on the Review Board server matches
            # the local checkout.
            repository_info = repository_info.find_server_repository_info(
                api_root)

        # Get the patch, the used patch ID and base dir for the diff
        patch_data = self.get_patch(
            tool,
            api_root,
            review_request_id,
            self.options.diff_revision,
            self.options.commit_id)

        diff_body = patch_data['diff']
        diff_revision = patch_data['revision']
        base_dir = patch_data['base_dir']

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

            success = self.apply_patch(
                repository_info, tool, review_request_id, diff_revision,
                tmp_patch_file, base_dir, revert=self.options.revert_patch)

            if not success:
                raise CommandError('Could not apply patch')

            if self.options.commit or self.options.commit_no_edit:
                if patch_data['commit_meta'] is not None:
                    # We are patching a commit so we already have the metadata
                    # required without making additional HTTP requests.
                    meta = patch_data['commit_meta']
                    message = meta['message']

                    # Fun fact: object does not have a __dict__ so you cannot
                    # call setattr() on them. We need this ability so we are
                    # creating a type that does.
                    author = type('Author', (object,), {})()
                    author.fullname = meta['author_name']
                    author.email = meta['author_email']

                else:
                    try:
                        review_request = api_root.get_review_request(
                            review_request_id=review_request_id,
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
