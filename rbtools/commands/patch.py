"""The rbt patch command."""

from __future__ import unicode_literals

import logging
import os
import re
from gettext import gettext as _, ngettext

import six
from rbtools.api.errors import APIError
from rbtools.clients import PatchAuthor
from rbtools.clients.errors import CreateCommitError
from rbtools.commands import Command, CommandError, Option
from rbtools.utils.commands import extract_commit_message
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.review_request import parse_review_request_url


logger = logging.getLogger(__name__)


COMMIT_ID_SPLIT_RE = re.compile(r'\s*,\s*')


class Patch(Command):
    """Applies a specific patch from a RB server.

    The patch file indicated by the request id is downloaded from the
    server and then applied locally."""

    name = 'patch'
    author = 'The Review Board Project'

    needs_api = True
    needs_scm_client = True

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
        Option('--write',
               dest='patch_outfile',
               default=None,
               help='Write the patch to a given file instead of applying '
                    'it to the tree.',
               added_in='2.0.1'),
        Option('--commit-ids',
               dest='commit_ids',
               default=None,
               help='Comma-separated list of commit IDs to apply.\n'
                    'This only applies to review requests created with commit '
                    'history.',
               added_in='2.0'),
        Option('--squash',
               dest='squash',
               action='store_true',
               default=False,
               help='Squash all patches into one commit. This is only used if '
                    'also using -c/--commit or -C/--commit-no-edit.',
               added_in='2.0'),
        Command.server_options,
        Command.repository_options,
    ]

    def get_patches(self, diff_revision=None, commit_ids=None, squashed=False,
                    reverted=False):
        """Return the requested patches and their metadata.

        If a diff revision is not specified, then this will look at the most
        recent diff.

        Args:
            diff_revision (int, optional):
                The diff revision to apply.

                The latest revision will be used if not provided.

            commit_ids (list of unicode, optional):
                The specific commit IDs to apply.

                If not specified, the squashed version of any commits
                (or the sole diff, in a non-multi-commit review request)
                will be applied.

            squashed (bool, optional):
                Whether to return a squashed version of the commits, if
                using a multi-commit review request.

            reverted (bool, optional):
                Return patches in the order needed to revert them.

        Returns:
            list of dict:
            A list of dictionaries with the following keys:

            ``basedir`` (:py:class:`unicode`):
                The base directory of the returned patch.

            ``diff`` (:py:class:`bytes`):
                The actual patch contents.

            ``patch_num`` (:py:class:`int`):
                The application number for the patch. This is 1-based.

            ``revision`` (:py:class:`int`):
                The revision of the returned patch.

            ``commit_meta`` (:py:class:`dict`):
                Metadata about the requested commit if one was requested.
                Otherwise, this will be ``None``.

        Raises:
            rbtools.command.CommandError:
                One of the following occurred:

                * The patch could not be retrieved or does not exist
                * The review request was created without history support and
                  ``commit_ids`` was provided.
                * One or more requested commit IDs could not be found.
        """
        if commit_ids is not None:
            commit_ids = set(commit_ids)

        # Sanity-check the arguments, making sure that the options provided
        # are compatible with each other and with the Review Board server.
        server_supports_history = self.capabilities.has_capability(
            'review_requests', 'supports_history')

        if server_supports_history:
            if squashed and commit_ids:
                logger.warning(
                    '--squash is not compatible with --commit-ids; '
                    'ignoring --squash')
                squashed = False
        else:
            squashed = True

            if commit_ids:
                logger.warning('This server does not support review requests '
                               'with history; ignoring --commit-ids=...')
                commit_ids = None

        # If a diff revision is not specified, we'll need to get the latest
        # revision through the API.
        if diff_revision is None:
            try:
                diffs = self.api_root.get_diffs(
                    review_request_id=self._review_request_id,
                    only_fields='',
                    only_links='')
            except APIError as e:
                raise CommandError('Error getting diffs: %s' % e)

            # Use the latest diff if a diff revision was not given.
            # Since diff revisions start a 1, increment by one, and
            # never skip a number, the latest diff revisions number
            # should be equal to the number of diffs.
            diff_revision = diffs.total_results

        try:
            # Fetch the main diff and (unless we're squashing) any commits within.
            if squashed:
                diff = self.api_root.get_diff(
                    review_request_id=self._review_request_id,
                    diff_revision=diff_revision)
            else:
                diff = self.api_root.get_diff(
                    review_request_id=self._review_request_id,
                    diff_revision=diff_revision,
                    expand='commits')
        except APIError:
            raise CommandError('The specified diff revision does not '
                               'exist.')

        # Begin to gather results.
        patches = []

        if squashed or len(diff.commits) == 0:
            # Either this was a review request created before we had
            # multi-commit, or the user requested to squash everything. Return
            # a single patch.

            try:
                diff_content = diff.get_patch().data
            except APIError:
                raise CommandError(
                    _('Unable to retrieve the diff content for revision %s')
                    % diff_revision)

            # We only have one patch to apply, containing a squashed version
            # of all commits.
            patches.append({
                'base_dir': getattr(diff, 'basedir', ''),
                'commit_meta': None,
                'diff': diff_content,
                'patch_num': 1,
                'revision': diff_revision,
            })
        else:
            # We'll be returning one patch per commit. This may be the
            # entire list of the review request, or a filtered list.
            commits = diff.commits

            if commit_ids:
                # Filter the commits down by the specified list of IDs.
                commit_ids = set(commit_ids)
                commits = [
                    commit
                    for commit in commits
                    if commit['commit_id'] in commit_ids
                ]

                # Make sure we're not missing any.
                if len(commits) != len(commit_ids):
                    found_commit_ids = set(
                        commit['commit_id']
                        for commit in commits
                    )

                    raise CommandError(
                        _('The following commit IDs could not be found: %s')
                        % ', '.join(sorted(commit_ids - found_commit_ids)))

            for patch_num, commit in enumerate(commits, start=1):
                try:
                    diff_content = commit.get_patch().data
                except APIError:
                    raise CommandError(
                        _('Unable to retrieve the diff content for '
                          'revision %(diff_revision)d, commit %(commit_id)s')
                        % {
                            'diff_revision': diff_revision,
                            'commit_id': commit['commit_id'],
                        })

                assert isinstance(diff_content, bytes)

                patches.append({
                    # DiffSets on review requests created with history
                    # support *always* have an empty base dir.
                    'base_dir': '',

                    'commit_meta': {
                        'author': PatchAuthor(full_name=commit.author_name,
                                              email=commit.author_email),
                        'author_date': commit.author_date,
                        'committer_date': commit.committer_date,
                        'committer_email': commit.committer_email,
                        'committer_name': commit.committer_name,
                        'message': commit.commit_message,
                    },
                    'diff': diff_content,
                    'patch_num': patch_num,
                    'revision': diff_revision,
                })

        if reverted:
            patches = list(reversed(patches))

        return patches

    def apply_patch(self, diff_file_path, base_dir, patch_num, total_patches,
                    revert=False):
        """Apply a patch to the tree.

        Args:
            diff_file_path (unicode):
                The file path of the diff being applied.

            base_dir (unicode):
                The base directory within which to apply the patch.

            patch_num (int):
                The 1-based index of the patch being applied.

            total_patches (int):
                The total number of patches being applied.

            revert (bool, optional):
                Whether the patch is being reverted.

        Returns:
            bool:
            ``True`` if the patch was applied/reverted successfully.
            ``False`` if the patch was partially applied/reverted but there
            were conflicts.

        Raises:
            rbtools.command.CommandError:
                There was an error applying or reverting the patch.
        """
        # If we're working with more than one patch, show the patch number
        # we're applying or reverting. If we're only working with one, the
        # previous log from _apply_patches() will suffice.
        if total_patches > 1:
            if revert:
                msg = _('Reverting patch %(num)d/%(total)d...')
            else:
                msg = _('Applying patch %(num)d/%(total)d...')

            logger.info(
                msg,
                {
                    'num': patch_num,
                    'total': total_patches,
                })

        result = self.tool.apply_patch(
            patch_file=diff_file_path,
            base_path=self.repository_info.base_path,
            base_dir=base_dir,
            p=self.options.px,
            revert=revert)

        if result.patch_output:
            self.stdout.new_line()

            patch_output = result.patch_output.strip()

            if six.PY2:
                self.stdout.write(patch_output)
            else:
                self.stdout_bytes.write(patch_output)
                self.stdout.new_line()

            self.stdout.new_line()

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
                    self.stdout.write('The patch was partially reverted, but '
                                      'there were conflicts in:')
                    self.json.add_error('The patch was partially reverted, '
                                        'but there were conflicts.')
                else:
                    self.stdout.write('The patch was partially applied, but '
                                      'there were conflicts in:')
                    self.json.add_error('The patch was partially applied, '
                                        'but there were conflicts.')

                self.stdout.new_line()

                self.json.add('conflicting_files', [])

                for filename in result.conflicting_files:
                    self.stdout.write('    %s' % filename)
                    self.json.append('conflicting_files',
                                     filename.decode('utf-8'))

                self.stdout.new_line()
            elif revert:
                err = ('The patch was partially reverted, but there were '
                       'conflicts.')
                self.stdout.write(err)
                self.json.add_error(err)
            else:
                err = ('The patch was partially applied, but there were '
                       'conflicts.')
                self.stdout.write(err)
                self.json.add_error('The patch was partially applied, but '
                                    'there were conflicts.')

            return False

        return True

    def initialize(self):
        """Initialize the command.

        This overrides Command.initialize in order to handle full review
        request URLs on the command line. In this case, we want to parse that
        URL in order to pull the server name and diff revision out of it.

        Raises:
            rbtools.commands.CommandError:
                A review request URL passed in as the review request ID could
                not be parsed correctly or included a bad diff revision.
        """
        review_request_id = self.options.args[0]

        if review_request_id.startswith('http'):
            server_url, review_request_id, diff_revision = \
                parse_review_request_url(review_request_id)

            if diff_revision and '-' in diff_revision:
                raise CommandError('Interdiff patches are not supported: %s.'
                                   % diff_revision)

            if review_request_id is None:
                raise CommandError('The URL %s does not appear to be a '
                                   'review request.')

            self.options.server = server_url
            self.options.diff_revision = diff_revision
            self.options.args[0] = review_request_id

        self.needs_scm_client = (not self.options.patch_stdout and
                                 not self.options.patch_outfile)
        self.needs_repository = self.needs_scm_client

        super(Patch, self).initialize()

    def main(self, review_request_id):
        """Run the command.

        Args:
            review_request_id (int):
                The ID of the review request to patch from.

        Raises:
            rbtools.command.CommandError:
                Patching the tree has failed.
        """
        self._review_request_id = review_request_id
        patch_stdout = self.options.patch_stdout
        patch_outfile = self.options.patch_outfile
        revert = self.options.revert_patch
        tool = self.tool

        if revert:
            if patch_stdout:
                raise CommandError(
                    _('--print and --revert cannot both be used.'))

            if patch_outfile and revert:
                raise CommandError(
                    _('--write and --revert cannot both be used.'))

        if patch_stdout and patch_outfile:
            raise CommandError(
                _('--print and --write cannot both be used.'))

        if patch_stdout and self.options.json_output:
            raise CommandError(
                _('--print and --json cannot both be used.'))

        if revert and not tool.supports_patch_revert:
            raise CommandError(
                _('The %s backend does not support reverting patches.')
                % tool.name)

        if not patch_stdout and not patch_outfile:
            # Check if the working directory is clean.
            try:
                if tool.has_pending_changes():
                    message = 'Working directory is not clean.'

                    if self.options.commit:
                        raise CommandError(message)
                    else:
                        logger.warning(message)
                        self.json.add_warning(message)
            except NotImplementedError:
                pass

        if self.options.commit_ids:
            # Do our best to normalize what gets passed in, so that we don't
            # end up with any blank entries.
            commit_ids = [
                commit_id
                for commit_id in COMMIT_ID_SPLIT_RE.split(
                    self.options.commit_ids.trim())
                if commit_id
            ]
        else:
            commit_ids = None

        # Fetch the patches from the review request, based on the requested
        # options.
        patches = self.get_patches(
            diff_revision=self.options.diff_revision,
            commit_ids=commit_ids,
            squashed=self.options.squash,
            reverted=revert)

        if patch_stdout:
            self._output_patches(patches, self.stdout_bytes)
        elif patch_outfile:
            try:
                with open(patch_outfile, 'wb') as fp:
                    self._output_patches(patches, fp)
            except IOError as e:
                raise CommandError(_('Unable to write patch to %s: %s')
                                   % (patch_outfile, e))
        else:
            self._apply_patches(patches)

    def _output_patches(self, patches, fp):
        """Output the contents of the patches to the console.

        Args:
            patches (list of dict):
                The list of patches that would be applied.

            fp (file or io.BufferedIOBase):
                The file pointer or stream to write the patch content to.
                This must accept byte strings.
        """
        for patch_data in patches:
            fp.write(patch_data['diff'])
            fp.write(b'\n')

    def _apply_patches(self, patches):
        """Apply a list of patches to the tree.

        Args:
            patches (list of dict):
                The list of patches to apply.

        Raises:
            rbtools.command.CommandError:
                Patching the tree has failed.
        """
        squash = self.options.squash
        revert = self.options.revert_patch
        commit_no_edit = self.options.commit_no_edit
        will_commit = self.options.commit or commit_no_edit
        total_patches = len(patches)

        # Check if we're planning to commit and have any patch without
        # metadata, in which case we'll need to fetch metadata from the
        # review request so we can generate a commit message.
        needs_review_request_metadata = will_commit and (
            squash or total_patches == 1 or
            any(patch_data['commit_meta'] is None for patch_data in patches)
        )

        # Fetch the review request to use as a description and for URLs in
        # JSON metadata. We only want to fetch this once.
        try:
            review_request = self.api_root.get_review_request(
                review_request_id=self._review_request_id,
                force_text_type='plain')
        except APIError as e:
            raise CommandError(
                _('Error getting review request %(review_request_id)d: '
                  '%(error)s')
                % {
                    'review_request_id': self._review_request_id,
                    'error': e,
                })

        if needs_review_request_metadata:
            default_author = review_request.get_submitter()
            default_commit_message = extract_commit_message(review_request)
        else:
            default_author = None
            default_commit_message = None

        # Display a summary of what's about to be applied.
        diff_revision = patches[0]['revision']

        if revert:
            summary = ngettext(
                ('Reverting 1 patch from review request '
                 '%(review_request_id)s (diff revision %(diff_revision)s)'),
                ('Reverting %(num)d patches from review request '
                 '%(review_request_id)s (diff revision %(diff_revision)s)'),
                total_patches)
        else:
            summary = ngettext(
                ('Applying 1 patch from review request '
                 '%(review_request_id)s (diff revision %(diff_revision)s)'),
                ('Applying %(num)d patches from review request '
                 '%(review_request_id)s (diff revision %(diff_revision)s)'),
                total_patches)

        logger.info(
            summary,
            {
                'num': total_patches,
                'review_request_id': self._review_request_id,
                'diff_revision': diff_revision,
            })
        self.json.add('review_request_id', review_request.id)
        self.json.add('review_request_url', review_request.absolute_url)
        self.json.add('diff_revision', diff_revision)
        self.json.add('total_patches', total_patches)

        # Start applying all the patches.
        for patch_data in patches:
            patch_num = patch_data['patch_num']
            tmp_patch_file = make_tempfile(patch_data['diff'])

            success = self.apply_patch(
                diff_file_path=tmp_patch_file,
                base_dir=patch_data['base_dir'],
                patch_num=patch_num,
                total_patches=total_patches,
                revert=revert)

            os.unlink(tmp_patch_file)

            if not success:
                if revert:
                    error = _('Could not apply patch %(num)d of %(total)d')
                else:
                    error = _('Could not revert patch %(num)d of %(total)d')

                self.json.add('failed_patch_num', patch_num)

                raise CommandError(error % {
                    'num': patch_num,
                    'total': total_patches,
                })

            # If the user wants to commit, then we'll be committing every
            # patch individually, unless the user wants to squash commits in
            # which case we'll only do this on the final commit.
            if will_commit and (not squash or patch_num == total_patches):
                meta = patch_data.get('commit_meta')

                if meta is not None and not squash and total_patches > 1:
                    # We are patching a commit so we already have the metadata
                    # required without making additional HTTP requests.
                    message = meta['message']
                    author = meta['author']
                else:
                    # We'll build this based on the summary/description from
                    # the review request and the patch number.
                    message = default_commit_message
                    author = default_author

                    assert message is not None
                    assert author is not None

                    if total_patches > 1:
                        # Record the patch number to help differentiate, in
                        # case we only have review request information and
                        # not commit messages. In practice, this shouldn't
                        # happen, as we should always have commit messages,
                        # but it's a decent safeguard.
                        message = '[%s/%s] %s' % (patch_num,
                                                  total_patches,
                                                  message)

                if revert:
                    # Make it clear that this commit is reverting a prior
                    # patch, so it's easy to identify.
                    message = '[Revert] %s' % message

                try:
                    self.tool.create_commit(
                        message=message,
                        author=author,
                        run_editor=not commit_no_edit)
                except CreateCommitError as e:
                    raise CommandError(six.text_type(e))
                except NotImplementedError:
                    raise CommandError('--commit is not supported with %s'
                                       % self.tool.name)
