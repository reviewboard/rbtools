"""Implementation of rbt patch."""

from __future__ import annotations

import re
from gettext import gettext as _, ngettext
from typing import TYPE_CHECKING

from typing_extensions import TypedDict

from rbtools.api.errors import APIError
from rbtools.commands.base import BaseCommand, CommandError, Option
from rbtools.diffs.errors import ApplyPatchError
from rbtools.diffs.patches import BinaryFilePatch, Patch, PatchAuthor
from rbtools.utils.encoding import force_unicode
from rbtools.utils.review_request import parse_review_request_url

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any, BinaryIO

    from rbtools.api.resource import (
        DiffCommitItemResource,
        DiffItemResource,
        FileDiffItemResource,
    )
    from rbtools.commands.base.output import OutputWrapper


COMMIT_ID_SPLIT_RE = re.compile(r'\s*,\s*')


class PendingPatchInfo(TypedDict):
    """Information on a pending patch to apply.

    Version Added:
        5.1
    """

    #: The diff revision from the review request.
    diff_revision: int | None

    #: Whether this patch contains scanned metadata.
    #:
    #: This is ``True`` when an author and commit message could be determined.
    has_metadata: bool

    #: The patch to apply.
    patch: Patch


class PatchCommand(BaseCommand):
    """Applies a specific patch from a RB server.

    The patch file indicated by the request id is downloaded from the
    server and then applied locally.
    """

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
               type=int,
               help='The Review Board diff revision ID to use for the patch.'),
        Option('--px',
               dest='px',
               metavar='NUM',
               default=None,
               type=int,
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
        Option('--no-binary',
               dest='no_binary',
               action='store_true',
               default=False,
               help='Skip binary files during patch application.',
               added_in='6.0'),
        BaseCommand.server_options,
        BaseCommand.repository_options,
    ]

    def get_patches(
        self,
        *,
        diff_revision: (int | None) = None,
        commit_ids: (set[str] | None) = None,
        squashed: bool = False,
        reverted: bool = False,
        include_binary: bool = True,
    ) -> Sequence[PendingPatchInfo]:
        """Return the requested patches and their metadata.

        If a diff revision is not specified, then this will look at the most
        recent diff.

        Args:
            diff_revision (int, optional):
                The diff revision to apply.

                The latest revision will be used if not provided.

            commit_ids (list of str, optional):
                The specific commit IDs to apply.

                If not specified, the squashed version of any commits
                (or the sole diff, in a non-multi-commit review request)
                will be applied.

            squashed (bool, optional):
                Whether to return a squashed version of the commits, if
                using a multi-commit review request.

            reverted (bool, optional):
                Return patches in the order needed to revert them.

            include_binary (bool, optional):
                Whether to include binary files in the patches.

                Version Added:
                    6.0

        Returns:
            list of PendingPatchInfo:
            A list of dictionaries with patch information.

        Raises:
            rbtools.command.CommandError:
                One of the following occurred:

                * The patch could not be retrieved or does not exist
                * The review request was created without history support and
                  ``commit_ids`` was provided.
                * One or more requested commit IDs could not be found.
        """
        patch_prefix_level: (int | None) = self.options.px

        assert (patch_prefix_level is None or
                isinstance(patch_prefix_level, int))

        # Sanity-check the arguments, making sure that the options provided
        # are compatible with each other and with the Review Board server.
        capabilities = self.capabilities
        assert capabilities

        server_supports_history = capabilities.has_capability(
            'review_requests', 'supports_history')

        if server_supports_history:
            if squashed and commit_ids:
                self.log.warning(
                    '--squash is not compatible with --commit-ids; '
                    'ignoring --squash')
                squashed = False
        else:
            squashed = True

            if commit_ids:
                self.log.warning(
                    'This server does not support review requests with '
                    'history; ignoring --commit-ids=...')
                commit_ids = None

        diff = self._get_diff(diff_revision=diff_revision,
                              squashed=squashed)

        if diff is None:
            raise CommandError(
                _('The specified diff revision does not exist.'))

        diff_revision = diff.revision

        # Begin to gather results.
        patches: list[PendingPatchInfo] = []

        if hasattr(diff, 'draft_commits'):
            commits = diff.draft_commits
        elif hasattr(diff, 'commits'):
            commits = diff.commits
        else:
            commits = []

        if squashed or len(commits) == 0:
            # Either this was a review request created before we had
            # multi-commit, or the user requested to squash everything. Return
            # a single patch.

            try:
                diff_content = diff.get_patch().data
            except APIError:
                raise CommandError(
                    _('Unable to retrieve the diff content for revision %s')
                    % diff_revision)

            if include_binary:
                binary_files = self._get_binary_files_for_diff(
                    diff, reverted=reverted)
            else:
                binary_files = None

            # We only have one patch to apply, containing a squashed version
            # of all commits.
            patches.append({
                'diff_revision': diff_revision,
                'has_metadata': False,
                'patch': Patch(base_dir=getattr(diff, 'basedir', None),
                               content=diff_content,
                               prefix_level=patch_prefix_level,
                               binary_files=binary_files),
            })
        else:
            # We'll be returning one patch per commit. This may be the
            # entire list of the review request, or a filtered list.
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
                    found_commit_ids = {
                        commit['commit_id']
                        for commit in commits
                    }

                    raise CommandError(
                        _('The following commit IDs could not be found: %s')
                        % ', '.join(sorted(commit_ids - found_commit_ids)))

            for commit in commits:
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

                if include_binary:
                    binary_files = self._get_binary_files_for_commit(
                        commit, reverted=reverted)
                else:
                    binary_files = None

                patches.append({
                    'diff_revision': diff_revision,
                    'has_metadata': True,

                    # Note that DiffSets on review requests created with
                    # history support *always* have an empty base dir, so
                    # we don't pass base_dir= here.
                    'patch': Patch(
                        author=PatchAuthor(full_name=commit.author_name,
                                           email=commit.author_email),
                        content=diff_content,
                        prefix_level=patch_prefix_level,
                        message=commit.commit_message,
                        binary_files=binary_files),
                })

        if reverted:
            patches = list(reversed(patches))

        return patches

    def _get_binary_files_for_diff(
        self,
        diff: DiffItemResource,
        *,
        reverted: bool,
    ) -> Sequence[BinaryFilePatch]:
        """Get binary files for a diff resource.

        Version Added:
            6.0

        Args:
            diff (rbtools.api.resource.DiffItemResource):
                The diff resource to get binary files from.

            reverted (bool):
                Return binary files to revert the changes.

        Returns:
            list of rbtools.diffs.patches.BinaryFilePatch:
            List of binary files found in the diff.
        """
        if 'draft_files' in diff.links:
            files = diff.get_draft_files(binary=True)
        else:
            files = diff.get_files(binary=True)

        return [
            self._get_binary_file_from_filediff(file_diff, reverted=reverted)
            for file_diff in files.all_items
        ]

    def _get_binary_files_for_commit(
        self,
        commit: DiffCommitItemResource,
        *,
        reverted: bool,
    ) -> Sequence[BinaryFilePatch]:
        """Get binary files for a commit resource.

        Version Added:
            6.0

        Args:
            commit:
                The commit resource to get binary files from.

            reverted (bool):
                Return binary files to revert the changes.

        Returns:
            list of rbtools.diffs.patches.BinaryFilePatch:
            List of binary files found in the commit.
        """
        if 'draft_files' in commit.links:
            files = commit.get_draft_files(binary=True)
        else:
            files = commit.get_files(binary=True)

        return [
            self._get_binary_file_from_filediff(file_diff, reverted=reverted)
            for file_diff in files.all_items
        ]

    def _get_binary_file_from_filediff(
        self,
        file_diff: FileDiffItemResource,
        *,
        reverted: bool,
    ) -> BinaryFilePatch:
        """Return a binary file patch for a FileDiff.

        Version Added:
            6.0

        Args:
            file_diff (rbtools.api.resource.FileDiffItemResource):
                The file diff resource.

            reverted (bool):
                Whether the patch is being reverted.

        Returns:
            rbtools.diffs.patches.BinaryFilePatch:
            The binary file patch object.
        """
        status: (str | None) = None

        if reverted:
            if file_diff.source_revision == 'PRE-CREATION':
                status = 'deleted'
            elif file_diff.status == 'deleted':
                status = 'added'

            old_path = file_diff.dest_file
            new_path = file_diff.source_file

            if status != 'added':
                attachment = file_diff.get_source_attachment()
            else:
                attachment = None
        else:
            if file_diff.source_revision == 'PRE-CREATION':
                status = 'added'
            elif file_diff.status == 'deleted':
                status = 'deleted'

            old_path = file_diff.source_file
            new_path = file_diff.dest_file

            if status != 'deleted':
                attachment = file_diff.get_dest_attachment()
            else:
                attachment = None

        if status is None:
            if file_diff.status == 'moved':
                status = 'moved'
            else:
                status = 'modified'

        return BinaryFilePatch(
            old_path=old_path,
            new_path=new_path,
            status=status,
            file_attachment=attachment,
        )

    def initialize(self) -> None:
        """Initialize the command.

        This overrides :py:meth:`BaseCommand.initialize
        <rbtools.commands.base.commands.BaseCommand.initialize>` in order to
        handle full review request URLs on the command line. In this case, we
        want to parse that URL in order to pull the server name and diff
        revision out of it.

        Raises:
            rbtools.commands.CommandError:
                A review request URL passed in as the review request ID could
                not be parsed correctly or included a bad diff revision.
        """
        options = self.options
        review_request_id = options.args[0]

        if review_request_id.startswith('http'):
            server_url, review_request_id, diff_revision = \
                parse_review_request_url(review_request_id)

            if diff_revision and '-' in diff_revision:
                raise CommandError(
                    f'Interdiff patches are not supported: {diff_revision}.')

            if review_request_id is None:
                raise CommandError(
                    f'The URL {options.args[0]} does not appear to be a '
                    f'review request.')

            options.server = server_url
            options.diff_revision = diff_revision
            options.args[0] = review_request_id

        self.needs_scm_client = (not options.patch_stdout and
                                 not options.patch_outfile)
        self.needs_repository = self.needs_scm_client

        super().initialize()

    def main(
        self,
        review_request_id: int,
    ) -> int:
        """Run the command.

        Args:
            review_request_id (int):
                The ID of the review request to patch from.

        Returns:
            int:
            The resulting exit code.

        Raises:
            rbtools.command.CommandError:
                Patching the tree has failed.
        """
        options = self.options
        self._review_request_id = review_request_id
        patch_stdout = options.patch_stdout
        patch_outfile = options.patch_outfile
        revert = options.revert_patch
        diff_revision = options.diff_revision
        tool = self.tool

        if revert:
            if patch_stdout:
                raise CommandError(
                    _('--print and --revert cannot both be used.'))

            if patch_outfile and revert:
                raise CommandError(
                    _('--write and --revert cannot both be used.'))

            assert tool is not None

            if not tool.supports_patch_revert:
                raise CommandError(
                    _('The %s backend does not support reverting patches.')
                    % tool.name)

        if patch_stdout and patch_outfile:
            raise CommandError(
                _('--print and --write cannot both be used.'))

        if patch_stdout and self.options.json_output:
            raise CommandError(
                _('--print and --json cannot both be used.'))

        if not patch_stdout and not patch_outfile:
            # Check if the working directory is clean.
            assert tool is not None

            try:
                if tool.has_pending_changes():
                    message = 'Working directory is not clean.'

                    if options.commit:
                        raise CommandError(message)
                    else:
                        self.log.warning(message)
                        self.json.add_warning(message)
            except NotImplementedError:
                pass

        commit_ids: set[str] | None

        if options.commit_ids:
            # Do our best to normalize what gets passed in, so that we don't
            # end up with any blank entries.
            commit_ids = {
                commit_id
                for commit_id in COMMIT_ID_SPLIT_RE.split(
                    options.commit_ids.trim())
                if commit_id
            }
        else:
            commit_ids = None

        # Fetch the patches from the review request, based on the requested
        # options.
        patches = self.get_patches(
            diff_revision=diff_revision,
            commit_ids=commit_ids,
            squashed=options.squash,
            reverted=revert,
            include_binary=not options.no_binary)

        if patch_stdout:
            self._output_patches(patches, self.stdout_bytes)
        elif patch_outfile:
            try:
                with open(patch_outfile, 'wb') as fp:
                    self._output_patches(patches, fp)
            except OSError as e:
                raise CommandError(_('Unable to write patch to %s: %s')
                                   % (patch_outfile, e))
        else:
            self._apply_patches(patches)

        return 0

    def _get_draft_diff(
        self,
        **query_kwargs,
    ) -> DiffItemResource | None:
        """Return the latest draft diff for the review request.

        Args:
            **query_kwargs (dict):
                Keyword arguments to pass when querying the diff resource

        Returns:
            rbtools.api.resource.DiffItemResource:
            The draft diff resource if found, or ``None``.
        """
        try:
            assert self.api_root is not None
            draft = self.api_root.get_draft(
                review_request_id=self._review_request_id)

            return draft.get_draft_diffs(**query_kwargs)[0]
        except (APIError, IndexError):
            return None

    def _get_diff(
        self,
        *,
        diff_revision: int | None,
        squashed: bool,
    ) -> DiffItemResource | None:
        """Retrieve the latest diff for a review request.

        This will attempt to retrieve the diff for the given diff revision,
        or the latest available diff if a revision is not specified.

        If a revision is specified, both published and draft diffs (in that
        order) will be considered.

        If a revision is not specified, this will return a draft diff if
        available, or the latest published diff if not.

        Note that support for draft diffs were introduced in RBTools 4.2.

        Args:
            diff_revision (int):
                An explicit diff revision to return.

            squashed (bool):
                Whether the resulting diff is intended to be squashed.

        Returns:
            rbtools.api.resource.DiffItemResource:
            The resulting diff/draft diff resource, or ``None`` if a diff
            was not found.

        Raises:
            rbtools.commands.CommandError:
                There was an error fetching required information from the API.
        """
        diff: (DiffItemResource | None) = None
        draft_diff: (DiffItemResource | None) = None
        review_request_id = self._review_request_id
        use_latest_diff = diff_revision is None

        api_root = self.api_root
        assert api_root is not None

        # Set default arguments for all our diff fetch requests.
        get_diff_kwargs: dict[str, Any] = {}
        get_draft_diff_kwargs: dict[str, Any] = {}

        if not squashed:
            get_diff_kwargs['expand'] = 'commits'
            get_draft_diff_kwargs['expand'] = 'draft_commits'

        # If a diff revision is not specified, we'll need to get the latest
        # revision through the API.
        if use_latest_diff:
            # A draft diff may very well be the latest diff available. If we
            # find one, then we'll return this.
            draft_diff = self._get_draft_diff(**get_draft_diff_kwargs)

            if draft_diff is not None:
                # We found a draft diff. Consider this the latest.
                diff = draft_diff
            else:
                # We didn't find a draft diff, so instead, find the latest
                # published diff. Diff revisions are numeric, starting with 1,
                # so we can base it on the total count.
                try:
                    diffs = api_root.get_diffs(
                        review_request_id=review_request_id,
                        only_fields='',
                        only_links='')
                except APIError as e:
                    # Something went wrong, so we have to report it.
                    raise CommandError(
                        _('Error retrieving a list of diffs for review '
                          'request %(review_request_id)s: %(error)s')
                        % {
                            'error': e,
                            'review_request_id': review_request_id,
                        })

                diff_revision = diffs.total_results

        if diff is None:
            # Either the user specified --diff-revision, or we didn't find a
            # suitable diff yet (on draft diff).
            try:
                # Fetch the main diff and (unless we're squashing) any commits
                # within.
                assert diff_revision is not None
                diff = api_root.get_diff(review_request_id=review_request_id,
                                         diff_revision=diff_revision,
                                         **get_diff_kwargs)
            except APIError:
                # We didn't find a diff. If we haven't yet fetched the draft
                # diff, then do so now.
                if not use_latest_diff:
                    draft_diff = self._get_draft_diff(**get_draft_diff_kwargs)

                    if draft_diff and draft_diff.revision == diff_revision:
                        # This is only valid if it matches the diff revision
                        # we're fetching. Note that we're only here if a diff
                        # revision was explicitly specified.
                        diff = draft_diff

        return diff

    def _output_patches(
        self,
        patches: Sequence[PendingPatchInfo],
        fp: BinaryIO | OutputWrapper[bytes],
    ) -> None:
        """Output the contents of the patches to the console.

        Args:
            patches (list of dict):
                The list of patches that would be applied.

            fp (rbtools.commands.base.output.OutputWrapper):
                The file pointer or stream to write the patch content to.
                This must accept byte strings.
        """
        for pending_patch in patches:
            patch = pending_patch['patch']

            with patch.open():
                content = patch.content
                fp.write(content)

                if not content.endswith(b'\n'):
                    fp.write(b'\n')

    def _apply_patches(
        self,
        pending_patches: Sequence[PendingPatchInfo],
    ) -> None:
        """Apply a list of patches to the tree.

        Args:
            pending_patches (list of PendingPatchInfo):
                The list of pending patches to apply.

        Raises:
            rbtools.command.CommandError:
                Patching the tree has failed.
        """
        tool = self.tool
        assert tool

        options = self.options
        squash = options.squash
        revert = options.revert_patch
        commit_no_edit = options.commit_no_edit
        total_patches = len(pending_patches)

        # Fetch the review request to use as a description and for URLs in
        # JSON metadata. We only want to fetch this once.
        try:
            assert self.api_root is not None
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

        # Display a summary of what's about to be applied.
        diff_revision = pending_patches[0]['diff_revision']

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

        self.stdout.write(summary % {
            'num': total_patches,
            'review_request_id': self._review_request_id,
            'diff_revision': diff_revision,
        })
        self.json.add('review_request_id', review_request.id)
        self.json.add('review_request_url', review_request.absolute_url)
        self.json.add('diff_revision', diff_revision)
        self.json.add('total_patches', total_patches)

        patch_num: int = 0

        patcher = tool.get_patcher(
            patches=[
                pending_patch['patch']
                for pending_patch in pending_patches
            ],
            repository_info=self.repository_info,
            revert=revert,
            squash=squash)

        try:
            if (options.commit or commit_no_edit) and patcher.can_commit:
                patcher.prepare_for_commit(
                    review_request=review_request,
                    run_commit_editor=not commit_no_edit)

            # Start applying all the patches.
            for patch_result in patcher.patch():
                patch_range = patch_result.patch_range

                if patch_range is not None:
                    patch_num = patch_range[0]
                else:
                    # This is an older implementation. We'll have to assume
                    # 1 higher than the previous patch.
                    #
                    # TODO [DEPRECATED]: This can go away with RBTools 7.
                    patch_num += 1

                if patch_result.patch_output:
                    self.stdout.new_line()

                    patch_output = patch_result.patch_output.strip()
                    self.stdout_bytes.write(patch_output)
                    self.stdout.new_line()
                    self.stdout.new_line()

                if revert:
                    self.stdout.write(
                        _('Reverted patch {patch_num} / {total_patches}')
                        .format(patch_num=patch_num,
                                total_patches=total_patches))
                else:
                    self.stdout.write(
                        _('Applied patch {patch_num} / {total_patches}')
                        .format(patch_num=patch_num,
                                total_patches=total_patches))

                # Report binary file results.
                if patch_result.binary_applied:
                    n = len(patch_result.binary_applied)

                    self.stdout.write(
                        ngettext(
                            'Applied {n} binary file.',
                            'Applied {n} binary files.',
                            n)
                        .format(n=n))

                    self.json.add('binary_files_applied',
                                  patch_result.binary_applied)

                if patch_result.binary_failed:
                    n = len(patch_result.binary_failed)

                    self.stdout.write(
                        ngettext(
                            'Failed to apply {n} binary file.',
                            'Failed to apply {n} binary files.',
                            n)
                        .format(n=n))

                    failed_json = []

                    for filename, reason in patch_result.binary_failed.items():
                        self.stdout.write(f'  {filename}: {reason}')
                        failed_json.append({
                            'filename': filename,
                            'reason': reason
                        })

                    self.json.add('binary_files_failed', failed_json)
        except ApplyPatchError as e:
            failed_patch_result = e.failed_patch_result

            self.stdout.write(str(e))
            self.json.add('failed_patch_num', patch_num)

            if failed_patch_result is None:
                # We'll claim this is the first patch, for compatibility.
                self.json.add_error(str(e))
            else:
                patch_range = failed_patch_result.patch_range

                if patch_range is not None:
                    patch_num = patch_range[0]
                else:
                    # This is an older implementation. We'll have to assume
                    # 1 higher than the previous patch.
                    #
                    # TODO [DEPRECATED]: This can go away with RBTools 7.
                    patch_num += 1

                if failed_patch_result.patch_output:
                    self.stdout.new_line()

                    patch_output = failed_patch_result.patch_output.strip()
                    self.stdout_bytes.write(patch_output)
                    self.stdout.new_line()
                    self.stdout.new_line()

                if failed_patch_result.has_conflicts:
                    if failed_patch_result.conflicting_files:
                        self.stdout.new_line()
                        self.stdout.write('Conflicting files:')
                        self.stdout.new_line()

                        for filename in failed_patch_result.conflicting_files:
                            filename = force_unicode(filename)
                            self.stdout.write(f'    {filename}')
                            self.json.append('conflicting_files', filename)

                    self.stdout.new_line()

                self.json.add_error(str(e))

            if revert:
                error = _('Could not revert patch %(num)d of %(total)d')
            else:
                error = _('Could not apply patch %(num)d of %(total)d')

            raise CommandError(error % {
                'num': patch_num,
                'total': total_patches,
            })
