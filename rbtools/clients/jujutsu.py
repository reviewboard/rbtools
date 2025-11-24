"""Client implementation for Jujutsu.

Version Added:
    6.0
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from gettext import gettext as _
from typing import TYPE_CHECKING

from rbtools.clients.base.repository import RepositoryInfo
from rbtools.clients.base.scmclient import (
    BaseSCMClient,
    SCMClientCommitHistoryItem,
    SCMClientDiffResult,
    SCMClientPatcher,
    SCMClientRevisionSpec,
)
from rbtools.clients.errors import (
    AmendError,
    CreateCommitError,
    MergeError,
    PushError,
    SCMError,
    SCMClientDependencyError,
    TooManyRevisionsError,
)
from rbtools.utils.console import edit_text
from rbtools.deprecation import RemovedInRBTools80Warning
from rbtools.utils.diffs import (
    normalize_patterns,
    remove_filenames_matching_patterns,
)
from rbtools.utils.checks import check_install
from rbtools.utils.errors import EditorError
from rbtools.utils.process import RunProcessError, run_process

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from rbtools.diffs.patches import Patch, PatchAuthor, PatchResult


logger = logging.getLogger(__name__)


class JujutsuPatcher(SCMClientPatcher['JujutsuClient']):
    """A patcher that applies patches to a Jujutsu tree.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: Whether the current change was empty when the operation started.
    _was_current_empty: bool

    def get_default_prefix_level(
        self,
        *,
        patch: Patch,
    ) -> int:
        """Return the default path prefix strip level for a patch.

        This adds one to the prefix level to handle Git-format "a/" and "b/"
        paths.

        Args:
            patch (rbtools.diffs.patches.Patch):
                The path to generate a default prefix strip level for.

        Returns:
            int:
            The prefix strip level.
        """
        p = super().get_default_prefix_level(patch=patch)

        if p is not None:
            return p + 1
        else:
            return 1

    def patch(self) -> Iterator[PatchResult]:
        """Apply patches to the tree.

        Yields:
            rbtools.diffs.patches.PatchResult:
            The result of each patch application, whether the patch applied
            successfully or with normal patch failures.

        Raises:
            rbtools.diffs.errors.ApplyPatchError:
                There was an error attempting to apply a patch.

                This won't be raised simply for conflicts or normal patch
                failures. It may be raised for errors encountered during
                the patching process.
        """
        # Check if there's any data in the working copy first.
        has_info = (
            (
                run_process(['jj', 'log', '-r', '@', '--no-graph', '-T',
                             'empty'])
                .stdout
                .read()
                .strip()
            ) != 'true')

        if not has_info:
            # No diff, but now check if there's a change description.
            has_info = (
                (
                    run_process(['jj', 'log', '-r', '@', '--no-graph', '-T',
                                 'description'])
                    .stdout
                    .read()
                    .strip()
                ) != '')

        if has_info:
            run_process(['jj', 'new'])

        yield from super().patch()

    def create_commit(
        self,
        *,
        patch_result: PatchResult,
        run_commit_editor: bool,
    ) -> None:
        """Create a commit based on a patch result.

        Args:
            patch_result (rbtools.diffs.patches.PatchResult):
                The patch result containing the patch/patches to commit.

            run_commit_editor (bool):
                Whether to run the configured commit editor to alter the
                commit message.

        Raises:
            rbtools.diffs.errors.ApplyPatchResult:
                There was an error attempting to commit the patch.
        """
        patch = patch_result.patch
        assert patch

        author = patch.author
        message = patch.message

        assert author
        assert message

        self.scmclient.create_commit(author=author,
                                     message=message,
                                     run_editor=self.run_commit_editor,
                                     create_new_change=True)


class JujutsuClient(BaseSCMClient):
    """Client implementation for Jujutsu.

    Version Added:
        6.0
    """

    scmclient_id = 'jujutsu'
    name = 'Jujutsu'
    patcher_cls = JujutsuPatcher
    server_tool_names = 'Git'
    server_tool_ids = ['git']

    supports_commit_history = True
    supports_diff_exclude_patterns = True
    supports_parent_diffs = True

    can_amend_commit = True
    can_bookmark = True
    can_delete_branch = False
    can_get_file_content = True
    can_merge = True
    can_push_upstream = True
    can_squash_merges = True

    ######################
    # Instance variables #
    ######################

    #: The path to the Git object storage within the .jj directory.
    _git_store: str

    #: Whether multiple remotes were found.
    _has_multiple_remotes: (bool | None) = None

    #: The path to the top level of the repository.
    _local_path: str | None

    def __init__(self, **kwargs) -> None:
        """Initialize the client.

        Args:
            **kwargs (dict):
                Keyword arguments to pass through to the superclass.
        """
        super().__init__(**kwargs)

        self._local_path = None

    def check_dependencies(self) -> None:
        """Check whether all dependencies for the client are available.

        This checks that both the ``git`` and ``jj`` commands are available.

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                The required command-line tools were not available.
        """
        missing_exes: SCMClientDependencyError.MissingList = []

        if not check_install(['git', '--help']):
            missing_exes.append('git')

        if not check_install(['jj', '--help']):
            missing_exes.append('jj')

        if missing_exes:
            raise SCMClientDependencyError(missing_exes=missing_exes)

    def get_local_path(self) -> str | None:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        if self._local_path is None:
            try:
                jj_root = (
                    run_process(['jj', 'root'])
                    .stdout
                    .read()
                    .strip()
                )

                repo = os.path.join(jj_root, '.jj', 'repo')

                # jj workspaces have 'repo' as a file containing the path to
                # the parent checkout.
                if not os.path.isdir(repo):
                    with open(repo, encoding='utf-8') as f:
                        repo = f.read().strip()

                store_base = os.path.join(repo, 'store')
                target = os.path.join(store_base, 'git_target')

                if not os.path.exists(target):
                    logger.warning('Jujutsu repository root found at %s, but '
                                   'git_target file was not.',
                                   jj_root)
                    return None

                with open(target) as fp:
                    relpath = fp.read().strip()
                    git_store = os.path.normpath(
                        os.path.join(store_base, relpath))

                if not os.path.exists(git_store):
                    logger.warning('Jujutsu repository root found at %s, but '
                                   'Git store was not.',
                                   jj_root)
                    return None

                self._local_path = jj_root
                self._git_store = git_store
            except RunProcessError:
                pass

        return self._local_path

    def get_repository_info(self) -> RepositoryInfo | None:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.

        Raises:
            rbtools.clients.errors.SCMError:
                An error occurred trying to find the repository info.
        """
        local_path = self.get_local_path()

        if not local_path:
            return None

        repository_url = getattr(self.options, 'repository_url', None)
        url: (str | None) = None

        if repository_url:
            url = repository_url
        else:
            try:
                remotes = self._get_remotes()
                self._has_multiple_remotes = (len(remotes) > 1)

                if not self._has_multiple_remotes:
                    url = remotes[0].split()[1]
                else:
                    parent_bookmark = self._get_parent_bookmark()

                    if '@' in parent_bookmark:
                        parent_remote = parent_bookmark.split('@', 1)[1]

                        for line in remotes:
                            try:
                                line_name, line_url = line.split(' ', 1)
                            except Exception:
                                continue

                            if line_name == parent_remote:
                                url = line_url
                                break
            except RunProcessError as e:
                raise SCMError(
                    _('Could not determine Git remote for Jujutsu '
                      'repository: {error}')
                    .format(error=str(e)))

        if url:
            return RepositoryInfo(path=url,
                                  base_path='',
                                  local_path=local_path)
        else:
            return None

    def parse_revision_spec(
        self,
        revisions: (Sequence[str] | None) = None,
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        This will parse revision arguments in order to generate the diffs to
        upload to Review Board (or print). The diff for review will include the
        changes in (base, tip], and the parent diff (if necessary) will include
        (parent_base, base].

        If a single revision is passed in, this will return the parent of that
        revision for "base" and the passed-in revision for "tip".

        If zero revisions are passed in, this will return the current HEAD as
        "tip" and the upstream bookmark as "base", taking into account parent
        branches (bookmarks) explicitly specified via :option:`--parent`.

        Args:
            revisions (list of str, optional):
                A list of revisions as specified by the user.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.SCMError:
                There was an error retrieving information from Git.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.
        """
        if revisions is None:
            RemovedInRBTools80Warning.warn(
                'parse_revision_spec was called without any '
                'arguments, or with None. The revisions argument will become '
                'mandatory in RBTools 8.0.'
            )
            revisions = []

        n_revs = len(revisions)
        result: SCMClientRevisionSpec

        tip: str
        base: str
        parent_bookmark: str
        parent_base: str

        if n_revs == 0:
            # No revisions were passed in. Start with @, and find the tracking
            # branch automatically.
            tip = self._get_change_id('@')
            parent_bookmark = self._get_parent_bookmark()
            base = self._get_change_id(parent_bookmark)

            result = {
                'base': base,
                'tip': tip,
                'commit_id': tip,
            }
        elif n_revs == 1:
            # A single revision was passed in. This could be an actual single
            # revision, or it could be a revset that represents a range.
            changes = self._get_change_ids(revisions[0])
            n_changes = len(changes)

            if n_changes == 1:
                # The revset returned a single change. Use that as the tip and
                # find its parent as the base.
                tip = changes[0]
                base = self._get_change_id(f'{tip}-')
                parent_bookmark = self._get_parent_bookmark(base)

                result = {
                    'base': base,
                    'tip': tip,
                    'commit_id': tip,
                }
            else:
                # The revset returned multiple changes. Use the top and bottom
                # of that range.
                tip = changes[0]
                base = changes[-1]
                parent_bookmark = self._get_parent_bookmark(base)

                result = {
                    'base': base,
                    'commit_id': tip,
                    'tip': tip,
                }
        elif n_revs == 2:
            base = self._get_change_id(revisions[0])
            tip = self._get_change_id(revisions[1])
            parent_bookmark = self._get_parent_bookmark(base)

            result = {
                'base': base,
                'commit_id': tip,
                'tip': tip,
            }
        else:
            raise TooManyRevisionsError

        if '@' in parent_bookmark:
            parent_base = self._get_fork_point(tip, parent_bookmark)
        else:
            remote_bookmark = self._get_remote_bookmark(base)
            parent_base = self._get_fork_point(tip, remote_bookmark)

        # If the most recent upstream commit is not the same as our revision
        # range base, include a parent base in the result.
        if base != parent_base:
            result['parent_base'] = parent_base

        return result

    def diff(
        self,
        revisions: SCMClientRevisionSpec | None,
        *,
        include_files: (Sequence[str] | None) = None,
        exclude_patterns: (Sequence[str] | None) = None,
        no_renames: bool = False,
        repository_info: (RepositoryInfo | None) = None,
        with_parent_diff: bool = True,
        **kwargs,
    ) -> SCMClientDiffResult:
        """Perform a diff using the given revisions.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            include_files (list of str, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of str, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

            no_renames (bool, optional):
                Whether to avoid rename detection.

            repository_info (rbtools.clients.base.repository.RepositoryInfo,
                             optional):
                The repository info.

            with_parent_diff (bool, optional):
                Whether or not to compute a parent diff.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary containing keys documented in
            :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`.
        """
        if include_files is None:
            include_files = []

        if exclude_patterns is None:
            exclude_patterns = []
        else:
            assert self._local_path is not None
            exclude_patterns = normalize_patterns(
                patterns=exclude_patterns,
                base_dir=self._local_path,
                cwd=os.getcwd())

        assert revisions is not None
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        diff = self._do_diff(
            base=base,
            tip=tip,
            include_files=include_files,
            exclude_patterns=exclude_patterns)

        if 'parent_base' in revisions and with_parent_diff:
            parent_base = revisions['parent_base']
            assert isinstance(parent_base, str)

            parent_diff = self._do_diff(
                base=parent_base,
                tip=base,
                include_files=include_files,
                exclude_patterns=exclude_patterns)
            base_commit_id = parent_base
        else:
            parent_diff = None
            base_commit_id = base

        return {
            'base_commit_id': base_commit_id,
            'commit_id': revisions.get('commit_id'),
            'diff': diff,
            'parent_diff': parent_diff,
        }

    def get_raw_commit_message(
        self,
        revisions: SCMClientRevisionSpec,
    ) -> str:
        """Extract the commit message based on the provided revision range.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

        Returns:
            str:
            The commit messages of all commits between (base, tip].
        """
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        return (
            run_process(['jj', 'log', '-r', f'{base}..{tip}',
                         '--reversed', '-T', 'description', '--no-graph'])
            .stdout
            .read()
            .strip()
        )

    def get_commit_history(
        self,
        revisions: SCMClientRevisionSpec,
    ) -> Sequence[SCMClientCommitHistoryItem] | None:
        """Return the commit history specified by the revisions.

        Args:
            revisions (dict):
                A dictionary of revisions to generate history for, as returned
                by :py:meth:`parse_revision_spec`.

        Returns:
            list of dict:
            The list of history entries, in order.

        Raises:
            rbtools.clients.errors.SCMError:
                The history is non-linear or there is a commit with no parents.
        """
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        log_fields = {
            'commit_id': 'change_id',
            'parent_id': 'parents.map(|c| c.change_id())',
            'author_name': 'author.name()',
            'author_email': 'author.email()',
            'author_date': 'author.timestamp().format("%+")',
            'committer_name': 'committer.name()',
            'committer_email': 'committer.email()',
            'committer_date': 'committer.timestamp().format("%+")',
            'commit_message': 'description',
        }

        if self.config.get('JJ_COMMITS_USE_GIT_SHA', False):
            log_fields['commit_id'] = 'commit_id'

        log_format = ' ++ "\x1f" ++ '.join(log_fields.values())
        log_entries = (
            run_process(['jj', 'log', '-r', f'{base}..{tip}', '--reversed',
                         '-T', f'{log_format} ++ "\x1e"', '--no-graph'])
            .stdout
            .read()
            .split("\x1e")
        )

        history: list[SCMClientCommitHistoryItem] = []
        field_names = log_fields.keys()

        for log_entry in log_entries:
            if not log_entry:
                break

            fields = log_entry.split("\x1f")
            entry = SCMClientCommitHistoryItem(
                **dict(zip(field_names, fields)))

            parent_id = entry['parent_id']
            assert isinstance(parent_id, str)

            parents = parent_id.split()

            if len(parents) > 1:
                raise SCMError(_(
                    'The Jujutsu SCMClient only supports posting commit '
                    'histories that are entirely linear.',
                ))
            elif len(parents) == 0:
                raise SCMError(_(
                    'The Jujutsu SCMClient only supports posting commits '
                    'that have exactly one parent.',
                ))

            message = entry['commit_message']
            assert isinstance(message, str)

            message = message.strip()

            if not message:
                # It's not unusual in Jujutsu for the working-copy commit (or
                # even parent changes) to not yet have a commit message.
                message = 'No description set'

            entry['commit_message'] = message

            history.append(entry)

        return history

    def get_file_content(
        self,
        *,
        filename: str,
        revision: str,
    ) -> bytes:
        """Return the contents of a file at a given revision.

        Args:
            filename (str):
                The file to fetch.

            revision (str):
                The revision of the file to get.

        Returns:
            bytes:
            The read file.

        Raises:
            rbtools.clients.errors.SCMError:
                An error occurred trying to get the file content.
        """
        try:
            return (
                run_process(['git', 'cat-file', 'blob', revision],
                            cwd=self._git_store)
                .stdout_bytes
                .read()
            )
        except RunProcessError as e:
            raise SCMError(
                _('Unable to get file content for {filename} (revision '
                  '{revision}): {error}')
                .format(filename=filename, revision=revision, error=str(e)))

    def get_file_size(
        self,
        *,
        filename: str,
        revision: str,
    ) -> int:
        """Return the size of a file at a given revision.

        Args:
            filename (str):
                The file to check.

            revision (str):
                The revision of the file to check.

        Returns:
            int:
            The size of the file, in bytes.

        Raises:
            rbtools.clients.errors.SCMError:
                An error occurred trying to get the size of the file.
        """
        try:
            return int(
                run_process(['git', 'cat-file', '-s', revision],
                            cwd=self._git_store)
                .stdout
                .read())
        except RunProcessError as e:
            raise SCMError(
                _('Unable to get file size for {filename} (revision '
                  '{revision}): {error}')
                .format(
                    filename=filename,
                    revision=revision,
                    error=str(e),
                )
            )

    def get_current_bookmark(self) -> str:
        """Return the current bookmark of this repository.

        Returns:
            str:
            The name of the bookmark at the current commit.

        Raises:
            rbtools.clients.errors.SCMError:
                An error occurred trying to get the current bookmark.
        """
        try:
            return (
                run_process(['jj', 'bookmark', 'list', '-r', '@', '-T',
                             'name ++ "\n"'])
                .stdout
                .read()
                .split('\n')[0]
            )
        except RunProcessError as e:
            raise SCMError(
                _('Unable to get the current bookmark: {error}')
                .format(error=str(e)))

    def supports_empty_files(self) -> bool:
        """Return whether the server supports added/deleted empty files.

        Returns:
            bool:
            ``True`` if the Review Board server supports added or deleted empty
            files.
        """
        return (self.capabilities is not None and
                self.capabilities.has_capability('scmtools', 'git',
                                                 'empty_files'))

    def amend_commit_description(
        self,
        message: str,
        revisions: (SCMClientRevisionSpec | None) = None,
    ) -> None:
        """Update a commit message to the given string.

        Args:
            message (str):
                The commit message to use when amending the commit.

            revisions (dict, optional):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`. This provides compatibility
                with SCMs that allow modifications of multiple changesets at
                any given time, and will amend the change referenced by the
                ``tip`` key.

        Raises:
            rbtools.clients.errors.AmendError:
                The amend operation failed.
        """
        command = ['jj', 'describe', '--quiet', '-m', message]

        if revisions and revisions['tip']:
            tip = revisions['tip']
            assert isinstance(tip, str)

            command.append(tip)

        try:
            run_process(command)
        except RunProcessError as e:
            raise AmendError(str(e))

    def create_commit(
        self,
        *,
        message: str,
        author: PatchAuthor,
        run_editor: bool,
        files: (Sequence[str] | None) = None,
        all_files: bool = False,
        create_new_change: bool = True,
    ) -> None:
        """Create a commit based on the provided message and author.

        Args:
            message (str):
                The commit message to use.

            author (rbtools.diffs.patches.PatchAuthor):
                The author of the commit.

            run_editor (bool):
                Whether to run the user's editor on the commit message before
                committing.

            files (list of str, optional):
                The list of filenames to commit.

            all_files (bool, optional):
                Whether to commit all changed files, ignoring the ``files``
                argument.

            create_new_change (bool, optional):
                Whether to create a new change after setting the description.

        Raises:
            rbtools.clients.errors.CreateCommitError:
                The commit message could not be created. It may have been
                aborted by the user.
        """
        if files:
            raise CreateCommitError(_(
                'The Jujutsu backend does not support creating commits with a '
                'subset of files.',
            ))

        if run_editor:
            try:
                modified_message = edit_text(message,
                                             filename='COMMIT_EDITMSG')
            except EditorError as e:
                raise CreateCommitError(str(e))
        else:
            modified_message = message

        if not modified_message.strip():
            raise CreateCommitError(_(
                "A commit message wasn't provided. The patched files are in "
                "your working copy. You may run `jj describe` to provide a "
                "change description.",
            ))

        cmd = ['jj', 'describe', '-m', modified_message]

        try:
            cmd += ['--author', f'{author.full_name} <{author.email}>']
        except AttributeError:
            # Users who have marked their profile as private won't include the
            # full name or email fields in the API payload. Just commit as the
            # user running RBTools.
            logger.warning('The author has marked their Review Board profile '
                           'information as private. Committing without '
                           'author attribution.')

        try:
            run_process(cmd)

            if create_new_change:
                run_process(['jj', 'new'])
        except RunProcessError as e:
            raise CreateCommitError(str(e))

    def merge(
        self,
        *,
        target: str,
        destination: str,
        message: str,
        author: PatchAuthor,
        squash: bool = False,
        run_editor: bool = False,
        close_branch: bool = True,
    ) -> None:
        """Merge the target branch with destination branch.

        Args:
            target (str):
                The name of the branch to merge.

            destination (str):
                The name of the branch to merge into.

            message (str):
                The commit message to use.

            author (rbtools.diffs.patches.PatchAuthor):
                The author of the commit.

            squash (bool, optional):
                Whether to squash the commits or do a plain merge.

            run_editor (bool, optional):
                Whether to run the user's editor on the commit message before
                committing.

            close_branch (bool, optional):
                Whether to close/delete the merged branch.

        Raises:
            rbtools.clients.errors.MergeError:
                An error occurred while merging the branch.
        """
        current_change = self._get_change_id('@')

        if target == '@':
            target = current_change

        if run_editor:
            try:
                modified_message = edit_text(message,
                                             filename='COMMIT_EDITMSG')
            except EditorError as e:
                raise MergeError(str(e))
        else:
            modified_message = message

        if squash:
            try:
                run_process(['jj', 'new', '-m', modified_message, destination])

                squash_cmd = ['jj', 'squash', '-u', '--from', target]

                if not close_branch:
                    squash_cmd.append('-k')

                run_process(['jj', 'squash', '--from', target, '-u'])
            except RunProcessError as e:
                raise MergeError(
                    _('Unable to create new squashed commit\n{output}')
                    .format(output=e.result.stdout.read()))
        else:
            try:
                run_process(['jj', 'new', '-m', modified_message, destination,
                             target])
            except RunProcessError as e:
                raise MergeError(
                    _('Unable to create new merge commit\n{output}')
                    .format(output=e.result.stdout.read()))

        try:
            run_process(['jj', 'bookmark', 'move', destination])
        except RunProcessError as e:
            raise MergeError(
                _('Unable to move boorkmark\n{output}')
                .format(output=e.result.stdout.read()))

        if target != current_change:
            # Try to switch back to the original current change. It's possible
            # that this no longer exists if it was squashed.
            try:
                run_process(['jj', 'edit', current_change])
            except RunProcessError as e:
                if not squash:
                    logger.debug(
                        'Failed to switch back to original change %s: %s',
                        current_change, e)

    def push_upstream(
        self,
        remote_branch: str,
    ) -> None:
        """Push the current branch to upstream.

        Args:
            remote_branch (str):
                The name of the branch to push to.

        Raises:
            rbtools.client.errors.PushError:
                The branch was unable to be pushed.
        """
        try:
            run_process(['jj', 'git', 'push', '-b', remote_branch])
        except RunProcessError as e:
            raise PushError(str(e))

    def has_pending_changes(self) -> bool:
        """Check if there are changes in the working copy.

        Returns:
            bool:
            ``False``, always.

            For most SCM implementations, a ``True`` return value indicates
            that there are pending changes in the working copy, and RBTools
            will error out.

            In Jujutsu, the "working copy" is a real commit, and we don't mind
            if it has content because that doesn't block us from doing any
            operations. Our implementation of patch/merge/etc. are designed to
            handle a non-empty working copy commit and create a new change
            before applying anything.
        """
        return False

    def _do_diff(
        self,
        *,
        base: str,
        tip: str,
        include_files: Sequence[str],
        exclude_patterns: Sequence[str],
    ) -> bytes:
        """Perform a diff between two revisions.

        Args:
            base (str):
                The base revision for the diff.

            tip (str):
                The tip revision for the diff.

            include_files (list of str):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of str):
                A list of shell-style glob patterns to blacklist during diff
                generation.

        Returns:
            bytes:
            The diff output.

        Raises:
            rbtools.utils.process.RunProcessError:
                An error occurred attempting to run a :command:`jj` command.
        """
        if exclude_patterns:
            assert self._local_path is not None

            changed_files = (
                run_process(['jj', 'diff', '--from', base, '--to', tip,
                             '--name-only'])
                .stdout
                .read()
            ).splitlines()

            changed_files = remove_filenames_matching_patterns(
                filenames=changed_files, patterns=exclude_patterns,
                base_dir=os.getcwd())

            diff_lines: list[bytes] = []

            for filename in changed_files:
                lines = (
                    run_process(['jj', 'diff', '--git', '--from', base,
                                 '--to', tip, '--', filename])
                    .stdout_bytes
                    .readlines()
                )

                if not lines:
                    logger.error(
                        'Could not get diff for all files (jj diff failed for '
                        '%s). Refusing to return a partial diff',
                        filename)
                    diff_lines = []
                    break

                diff_lines += lines
        else:
            diff_cmd = ['jj', 'diff', '--git', '--from', base, '--to', tip]

            if include_files:
                diff_cmd += ['--', *include_files]

            diff_lines = (
                run_process(diff_cmd,
                            ignore_errors=True,
                            log_debug_output_on_error=False)
                .stdout_bytes
                .readlines()
            )

        return b''.join(self._expand_short_git_indexes(diff_lines))

    def _get_parent_bookmark(
        self,
        tip: str = '@',
    ) -> str:
        """Return the parent bookmark.

        Args:
            tip (str, optional):
                The change to find the parent bookmark for.

        Returns:
            str:
            The name of the current parent bookmark.
        """
        return (getattr(self.options, 'parent_branch', None) or
                getattr(self.options, 'tracking', None) or
                self._get_remote_bookmark(tip))

    def _get_remote_bookmark(
        self,
        tip: str = '@',
    ) -> str:
        """Return the closest remote bookmark.

        Args:
            tip (str, optional):
                A revset for the tip change to find the closest bookmark for.

        Returns:
            str:
            The name of the closest remote bookmark.

        Raises:
            rbtools.clients.errors.SCMError:
                An error occurred attempting to get the bookmark.
        """
        if self._has_multiple_remotes is None:
            remotes = self._get_remotes()
            self._has_multiple_remotes = (len(remotes) > 1)

        if self._has_multiple_remotes:
            logger.warning(
                'There are multiple Git remotes are configured in your jj '
                'repository. Attempting to use the most recent remote '
                'bookmark, but that may be on a remote which is not '
                'connected to your Review Board server. We recommend '
                'setting TRACKING_BRANCH in your .reviewboardrc file to '
                'the upstream remote branch you want to use '
                '(e.g. main@origin).')

        bookmarks_template = \
            'remote_bookmarks.filter(|b| b.remote() != "git")'

        try:
            reachable = [
                line
                for line in run_process([
                    'jj', 'log',
                    '-r', f'(remote_bookmarks()::{tip})-',
                    '-T', f'{bookmarks_template} ++ "\n"',
                    '--no-graph',
                ])
                .stdout
                .read()
                .splitlines()
                if line
            ]

            if reachable:
                remote_bookmarks = [
                    line
                    for line in run_process([
                        'jj', 'log',
                        '-r', f'latest({" | ".join(reachable)})',
                        '-T', bookmarks_template,
                        '--no-graph',
                        '-n', '1',
                    ])
                    .stdout
                    .read()
                    .splitlines()
                    if line
                ]

                if remote_bookmarks:
                    return remote_bookmarks[0]
        except RunProcessError as e:
            logger.warning(
                'Unable to get log for reachable commits on remote '
                'bookmarks: %s',
                e)

        try:
            remote_bookmarks = [
                line
                for line in run_process([
                    'jj', 'log',
                    '-r', 'trunk()',
                    '-T', bookmarks_template,
                    '--no-graph',
                    '-n', '1',
                ])
                .stdout
                .read()
                .splitlines()
                if line
            ]

            if remote_bookmarks:
                return remote_bookmarks[0]
        except RunProcessError as e:
            logger.warning(
                'Unable to get log for remote_bookmarks on trunk: %s', e)

        raise SCMError(_(
            'Unable to determine parent or tracking bookmark for '
            'remote.',
        ))

    def _get_change_id(
        self,
        revset: str,
    ) -> str:
        """Return the change ID of the given revset.

        This method assumes that the revset is referring to a single change or
        commit. The results will be limited to one change ID.

        Args:
            revset (str):
                The revset to query.

        Returns:
            str:
            The change ID.

        Raises:
            rbtools.utils.process.RunProcessError:
                An error occurred while running :command:`jj`.
        """
        return (
            run_process(['jj', 'log', '-r', revset, '-n', '1', '--no-graph',
                         '-T', 'change_id'])
            .stdout
            .read()
        )

    def _get_change_ids(
        self,
        revset: str,
    ) -> Sequence[str]:
        """Return all change IDs for the given revset.

        Args:
            revset (str):
                The revset to query.

        Returns:
            list of str:
            A list of all the change IDs in the revset.

        Raises:
            rbtools.utils.process.RunProcessError:
                An error occurred while running :command:`jj`.
        """
        return (
            run_process(['jj', 'log', '-r', revset, '--no-graph',
                         '-T', 'change_id ++ "\n"'])
            .stdout
            .read()
            .splitlines()
        )

    def _get_remotes(
        self,
    ) -> Sequence[str]:
        """Return the Git remotes for the repository.

        Returns:
            list of str:
            A list of remotes.

        Raises:
            rbtools.utils.process.RunProcessError:
                An error occurred while running :command:`jj`.
        """
        return (
            run_process(['jj', 'git', 'remote', 'list'])
            .stdout
            .read()
            .strip()
            .splitlines()
        )

    def _get_fork_point(
        self,
        revset1: str,
        revset2: str,
    ) -> str:
        """Return the change ID of the fork point of two revsets.

        This will determine the point at which the history from two commits
        diverged. This is most useful for determining the most recent upstream
        commit to work from when creating parent diffs.

        Args:
            revset1 (str):
                The revset (referring to a single change) of the first branch.

            revset2 (str):
                The revset (referring to a single change) of the second branch.

        Returns:
            str:
            The ID of the change at which the branches containing the two
            referenced revsets diverged.

        Raises:
            rbtools.clients.errors.SCMError:
                An error occurred attempting to get the fork point.
        """
        try:
            return (
                run_process(['jj', 'log', '-r',
                             f'fork_point({revset1} | {revset2})',
                             '--no-graph', '-T', 'change_id'])
                .stdout
                .read()
            )
        except RunProcessError as e:
            raise SCMError(
                _('Unable to determine the fork point between revisions '
                  '"{revset1}" and "{revset2}": {error}')
                .format(
                    revset1=revset1,
                    revset2=revset2,
                    error=e,
                )
            )

    def _expand_short_git_indexes(
        self,
        diff_lines: Sequence[bytes],
    ) -> Iterable[bytes]:
        """Expand short indexes in a Git-style diff.

        Jujutsu's ``jj diff --git`` command returns a diff that works, but
        there's no way to tell it to use full indexes.

        Args:
            diff_lines (iterable of bytes):
                The lines in the diff.

        Yields:
            bytes:
            Each line of the diff, with the index lines expanded.

        Raises:
            rbtools.clients.errors.SCMError:
                An error occurred while processing the diff.
        """
        index_re = re.compile(
            br'^index (?P<a>[0-9a-f]+)..(?P<b>[0-9a-f]+)((?P<rest>\s.*)?)$')
        sha_result_re = re.compile(r'^(?P<sha>[0-9a-f]+) blob \d+$')

        with subprocess.Popen(
            ['git', 'cat-file', '--batch-check'],
            cwd=self._git_store,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            close_fds=True,
            text=True,
        ) as p:
            assert p.stdin is not None
            assert p.stdout is not None

            partial_hashes: list[str] = []
            full_hashes: list[str] = []
            index_lines: set[int] = set()
            index_lines_rest: list[str] = []

            for i, line in enumerate(diff_lines):
                m = index_re.match(line)

                if m:
                    sha_a = m.group('a').decode()
                    sha_b = m.group('b').decode()
                    rest = m.group('rest') or b''

                    partial_hashes.append(sha_a)
                    partial_hashes.append(sha_b)

                    p.stdin.write(f'{sha_a}\n')
                    p.stdin.write(f'{sha_b}\n')

                    index_lines.add(i)
                    index_lines_rest.append(rest.decode())

            p.stdin.close()

            sha_results = p.stdout.read().splitlines()

            for i, result in enumerate(sha_results):
                if result == '0000000000 missing':
                    full_hashes.append('0' * 40)

                    continue

                m = sha_result_re.match(result)

                if m:
                    sha = m.group('sha')
                    full_hashes.append(sha)
                else:
                    partial_sha = partial_hashes[i]

                    logger.error('Got unexpected result when finding full Git '
                                 'file SHA for partial %s: "%s"',
                                 partial_sha, result)
                    raise SCMError(_(
                        'Unable to create Git-style diff for Jujutsu: full '
                        'file SHA for {partial_sha} could not be found.')
                        .format(partial_sha=partial_sha))

            full_hashes.reverse()
            index_lines_rest.reverse()

            for i, line in enumerate(diff_lines):
                if i in index_lines:
                    sha_a = full_hashes.pop()
                    sha_b = full_hashes.pop()
                    rest = index_lines_rest.pop()

                    yield f'index {sha_a}..{sha_b}{rest}\n'.encode()
                else:
                    yield line
