"""Support for applying patches to a local source tree.

Version Added:
    5.1
"""

from __future__ import annotations

import logging
import os
import re
from gettext import gettext as _
from pathlib import Path
from typing import TYPE_CHECKING

from typing_extensions import NotRequired, TypedDict, assert_never

from rbtools.diffs.errors import ApplyPatchError
from rbtools.diffs.patches import PatchAuthor, PatchResult
from rbtools.utils.commands import extract_commit_message
from rbtools.utils.encoding import force_unicode
from rbtools.utils.filesystem import chdir
from rbtools.utils.process import run_process

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from rbtools.api.resource import ReviewRequestItemResource
    from rbtools.clients.base.repository import RepositoryInfo
    from rbtools.diffs.patches import BinaryFilePatch, Patch


logger = logging.getLogger(__name__)


_PATCHING_RE = re.compile(
    br'patching file (?P<filename>.+)'
)

_CHECK_EMPTY_FILES_RE = re.compile(
    br"("

    # GNU Patch
    br"[A-Za-z0-9_-]+: \*{4} Only garbage was found in the patch input\."
    br"|"

    # Apple/BSD Patch
    br"I can't seem to find a patch in there anywhere\."
    br")"
)

_FATAL_PATCH_ERROR_RE = re.compile(
    br"(?P<error>"

    # GNU Patch
    br"[A-Za-z0-9_-]+: \*{4}(.*)"
    br"|"

    # Apple Patch
    br"I can't seem to find a patch in there anywhere\.(.*)"
    br")",
    re.S)

_CONFLICTS_RE = re.compile(
    # Cover both the BSD/Apple Diff and GNU Diff variations of the output.
    br'(?P<num_hunks>\d+) out of (?P<total_hunks>\d+) hunks? '
    br'(failed|FAILED)\s?--\s?saving rejects to (file )?(?P<filename>.+)\.rej'
)


class ParsedPatchOutput(TypedDict):
    """Parsed output from a patch command.

    This is designed to collect information from parsing an unstructured
    :command:`patch` output stream. The default :py:class:`Patcher` supports
    pulling information from GNU Patch and Apple Patch commands, though this
    data can be returned from any patch tool.

    Version Added:
        5.1
    """

    #: A list of conflicting filenames.
    conflicting_files: list[str]

    #: Whether the patch indicates any empty files were potentially found.
    has_empty_files: bool

    #: Whether the patch may have partially-applied files.
    has_partial_applied_files: bool

    #: A list of filenames for files patched or attempted to be patched.
    #:
    #: This may include files that had conflicts and could not be fully
    #: patched.
    patched_files: list[str]

    #: Any fatal error text present in the stream.
    fatal_error: NotRequired[str | None]


class PatcherKwargs(TypedDict):
    """Keyword arguments available when instantiating a Patcher.

    Version Added:
        5.1
    """

    #: The list of patches to apply (or revert), in order.
    patches: Sequence[Patch]

    #: The local path where patches will be applied.
    #:
    #: If not provided, this will patch in the current directory by default.
    dest_path: NotRequired[Path | None]

    #: Information on the current source code repository.
    repository_info: NotRequired[RepositoryInfo | None]

    #: Whether to revert the patches.
    revert: NotRequired[bool]

    #: Whether to squash the patches together into one patch.
    squash: NotRequired[bool]


class Patcher:
    """Applies patches and optionally commits to source trees.

    This takes a list of patches and criteria for applying those patches and
    attempts to apply them to the source tree. After construction, consumers
    can call :py:meth:`patch` to apply the patches.

    By default, this will apply the patches one-by-one using the
    :command:`patch` command. Subclasses may override the patching behavior
    to use native SCM patching capabilities, or to apply multiple patches in
    one go.

    Depending on the implementation, this will also allow callers to commit
    those patches to the repository. They must first check for
    :py:attr:`can_commit` and then call :py:meth:`prepare_for_commit` prior
    to beginning the :py:meth:`patch` operation.

    Version Added:
        5.1
    """

    #: Whether this patcher is capable of committing to a repository.
    #:
    #: This can be enabled by SCM-specific patchers to enable committing
    #: after applying patches.
    can_commit: bool = False

    #: Whether empty files can be patched.
    #:
    #: By default, empty files cannot be patched. Subclasses must set this
    #: to ``True`` if they are capable of applying empty patches.
    can_patch_empty_files: bool = False

    ######################
    # Instance variables #
    ######################

    #: The list of any results from applied patches.
    applied_patch_results: list[PatchResult]

    #: The local path where patches will be applied.
    dest_path: Path

    #: Whether patches will be committed after applying.
    commit: bool

    #: The patches to apply (or revert), in order.
    patches: Sequence[Patch]

    #: Information on the current source code repository.
    #:
    #: This may be needed in order to apply patches correctly to some kinds
    #: of repositories.
    repository_info: RepositoryInfo | None

    #: Whether the patches will be reverted.
    revert: bool

    #: Whether the user's editor will be opened as part of making a commit.
    run_commit_editor: bool

    #: Whether the patches will be squashed together into one patch.
    squash: bool

    #: Whether the patcher has applied patches.
    _patched: bool

    #: Whether the patcher is currently applying patches.
    _patching: bool

    def __init__(
        self,
        *,
        patches: Sequence[Patch],
        dest_path: (Path | None) = None,
        repository_info: (RepositoryInfo | None) = None,
        revert: bool = False,
        squash: bool = False,
    ) -> None:
        """Initialize the patcher.

        Args:
            patches (list of rbtools.diffs.patches.Patch):
                The list of patches to apply (or revert), in order.

            dest_path (pathlib.Path, optional):
                The local path where patches will be applied.

                If not provided, this will patch in the current directory
                by default.

            repository_info (rbtools.clients.base.repository.RepositoryInfo):
                Information on the current source code repository.

                This may be needed in order to apply patches correctly to
                some kinds of repositories.

            revert (bool, optional):
                Whether to revert the patches.

            squash (bool, optional):
                Whether to squash the patches together into one patch.
        """
        self.dest_path = dest_path or Path.cwd()
        self.patches = patches
        self.repository_info = repository_info
        self.revert = revert
        self.squash = squash

        self.applied_patch_results = []
        self.commit = False
        self.run_commit_editor = False

        self._patching = False
        self._patched = False

    def prepare_for_commit(
        self,
        *,
        default_author: (PatchAuthor | None) = None,
        default_message: (str | None) = None,
        review_request: (ReviewRequestItemResource | None) = None,
        run_commit_editor: bool = False,
    ) -> None:
        """Prepare the patching process to commit applied changes.

        Once called, the patcher will be responsible for taking any applied
        changes and turning it into one or more commits.

        This only works if :py:attr:`can_commit` is ``True``.

        The caller is responsible for providing either a default author and
        commit message, or a review request containing defaults to use. These
        will be used if the patch doesn't contain that information already.

        Args:
            default_author (rbtools.diffs.patches.PatchAuthor, optional):
                The default author to use for commits.

            default_message (str, optional):
                The default message to use for commits.

            review_request (rbtools.api.resource.ReviewRequestItemResource,
                            optional):
                The review request to use for a default author and message.

            run_commit_editor (bool, optional):
                Whether to run the user's editor to edit a commit message
                before making the commit.
        """
        assert not self._patching, (
            'prepare_for_commit() cannot be called while patching.'
        )
        assert not self._patched, (
            'prepare_for_commit() cannot be called after patch().'
        )

        if not self.can_commit:
            raise NotImplementedError(_(
                'This patcher does not support committing applied patches.'
            ))

        if not review_request and (not default_author or not default_message):
            raise ValueError(_(
                'Patches cannot be prepared to be committed without a '
                'review_request= argument or both default_author= and '
                'default_message=.'
            ))

        patches = self.patches
        squash = self.squash
        total_patches = len(patches)
        patches_to_prepare: list[tuple[int, Patch]]

        # We need to determine if we need to set explicit commit information.
        # If we're squashing, only applying one patch, or are missing any
        # metadata, we'll override the author and commit message.
        if total_patches == 1:
            # We're applying one patch, and will use the review request
            # information for the metadata.
            patches_to_prepare = [(1, patches[0])]
        elif squash:
            # We're squashing more than one commit down, and will use the
            # review request metadata.
            patches_to_prepare = list(zip(
                range(1, total_patches + 1),
                patches))
        else:
            # Check if there's missing metadata. If so, we'll just update
            # those.
            patches_to_prepare = [
                (patch_num, patch)
                for patch_num, patch in enumerate(patches, start=1)
                if not patch.author or not patch.message
            ]

        if patches_to_prepare:
            if not default_author or not default_message:
                if review_request is None:
                    raise AssertionError(
                        'A review request needs to be passed to '
                        'prepare_for_commit().'
                    )

                if hasattr(review_request, 'submitter'):
                    submitter = review_request['submitter']
                elif hasattr(review_request, 'get_submitter'):
                    submitter = review_request.get_submitter()
                else:
                    raise AssertionError(
                        'Review request is missing a submitter when '
                        'patching! This is either an error or a problem '
                        'with the review request passed in '
                        'prepare_for_commit().'
                    )

                fullname = submitter.fullname
                assert isinstance(fullname, str)

                email = submitter.email
                assert isinstance(email, str)

                default_author = PatchAuthor(full_name=fullname,
                                             email=email)
                default_message = extract_commit_message(review_request)

            if total_patches == 1:
                # Set the patch based on the provided or determined default
                # author and message.
                assert len(patches_to_prepare) == 1

                patch = patches_to_prepare[0][1]
                patch.author = default_author
                patch.message = default_message
            else:
                # Record the patch number to help differentiate, in case we
                # only have review request information and not commit messages.
                # In practice, this shouldn't happen, as we should always have
                # commit messages in any typical flow, but it's a decent
                # safeguard.
                for patch_num, patch in patches_to_prepare:
                    if not patch.author or squash:
                        patch.author = default_author

                    if squash:
                        patch.message = default_message
                    elif not patch.message:
                        patch.message = \
                            f'[{patch_num}/{total_patches}] {default_message}'

            if self.revert:
                # Make it clear that this commit is reverting a prior patch,
                # so it's easy to identify.
                for patch in patches:
                    patch.message = f'[Revert] {patch.message}'

        self.commit = True
        self.run_commit_editor = run_commit_editor

    def patch(self) -> Iterator[PatchResult]:
        """Apply the patches to the tree.

        This is the primary method used to apply the patches. It will handle
        applying the patches, returning results, and raising exceptions on
        errors.

        This method may only be called once.

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
        assert not self._patching, 'patch() cannot be called while patching.'
        assert not self._patched, 'patch() cannot be called more than once.'

        self._patching = True

        applied_patch_results: list[PatchResult] = []
        self.applied_patch_results = applied_patch_results

        with chdir(str(self.dest_path)):
            for patch_result in self.apply_patches():
                if not patch_result.success:
                    if patch_result.applied and patch_result.has_conflicts:
                        if self.revert:
                            error = _(
                                'Partially reverted %(patch_subject)s, but '
                                'there were conflicts.'
                            )
                        else:
                            error = _(
                                'Partially applied %(patch_subject)s, but '
                                'there were conflicts.'
                            )
                    elif patch_result.binary_failed:
                        error = '\n'.join([
                            _('Failed to patch binary files:'),
                            *(
                                f'    {filename}: {failure}'
                                for filename, failure in
                                patch_result.binary_failed.items()
                            )
                          ])
                    else:
                        if self.revert:
                            error = _(
                                'Could not revert %(patch_subject)s. The '
                                'patch may be invalid, or there may be '
                                'conflicts that could not be resolved.'
                            )
                        else:
                            error = _(
                                'Could not apply %(patch_subject)s. The '
                                'patch may be invalid, or there may be '
                                'conflicts that could not be resolved.'
                            )

                    # The patch failed to apply. Raise an exception to let the
                    # caller know what happened.
                    raise ApplyPatchError(error,
                                          failed_patch_result=patch_result,
                                          patcher=self)

                applied_patch_results.append(patch_result)

                yield patch_result

        self._patching = False
        self._patched = True

    def apply_patches(self) -> Iterator[PatchResult]:
        """Apply the patches.

        This is an internal function that will handle applying all patches
        provided to the patcher.

        Subclasses should override this if providing batch-patching logic.
        They would also be responsible for handling commits, if requested
        by the caller and supported by the subclass.

        This must only be called internally by the patcher.

        Yields:
            rbtools.diffs.patches.PatchResult:
            The result of each patch application, whether the patch applied
            successfully or with normal patch failures.

        Raises:
            rbtools.diffs.errors.ApplyPatchResult:
                There was an error attempting to apply a patch.

                This won't be raised simply for conflicts or normal patch
                failures. It may be raised for errors encountered during
                the patching process.
        """
        assert self._patching, (
            'apply_patches() must be called from a patch() call.'
        )
        assert not self._patched, (
            'apply_patches() cannot be called after patch().'
        )

        patches = self.patches
        commit = self.commit
        squash = self.squash
        run_commit_editor = self.run_commit_editor
        total_patches = len(patches)

        if self.revert:
            patches = list(reversed(patches))

        for patch_num, patch in enumerate(patches, start=1):
            with patch.open():
                patch_result = self.apply_single_patch(patch=patch,
                                                       patch_num=patch_num)

            patch_range = patch_result.patch_range

            if patch_range is not None:
                end_patch_num = patch_range[1]
            else:
                # This is an older implementation. We'll have to assume
                # 1 higher than the previous patch.
                #
                # TODO [DEPRECATED]: This can go away with RBTools 7.
                end_patch_num = patch_num

            # If the user wants to commit, then we'll be committing every
            # patch individually, unless the user wants to squash commits
            # in which case we'll only do this on the final commit.
            if (patch_result.success and
                commit and
                (not squash or end_patch_num == total_patches)):
                # If this is an older implementation, we may need to
                # set the patch.
                #
                # TODO [DEPRECATED]: This can go away with RBTools 7.
                if not patch_result.patch:
                    patch_result.patch = patch

                self.create_commit(patch_result=patch_result,
                                   run_commit_editor=run_commit_editor)

            yield patch_result

    def apply_single_patch(
        self,
        *,
        patch: Patch,
        patch_num: int,
    ) -> PatchResult:
        """Apply a single patch.

        This is an internal method that will take a single patch and apply it.
        It may be applied to files that already contain other modifications or
        have had other patches applied to it.

        Subclasses that can apply patches one-by-one may override this to
        apply patches using SCM-specific methods.

        This must only be called internally by the patcher.

        Args:
            patch (rbtools.diffs.patches.Patch):
                The patch to apply, opened for reading.

            patch_num (int):
                The 1-based index of this patch in the full list of patches.

        Returns:
            rbtools.diffs.patches.PatchResult:
            The result of the patch application, whether the patch applied
            successfully or with normal patch failures.

        Raises:
            rbtools.diffs.errors.ApplyPatchResult:
                There was an error attempting to apply the patch.

                This won't be raised simply for conflicts or normal patch
                failures. It may be raised for errors encountered during
                the patching process.
        """
        assert self._patching, (
            'apply_patches() must be called from a patch() call.'
        )
        assert not self._patched, (
            'apply_single_patch() cannot be called after patch().'
        )

        # Figure out the -p argument for patch. We override the calculated
        # value if it is supplied via a commandline option.
        patch_file = patch.path
        patch_command = os.environ.get('RBTOOLS_PATCH_COMMAND', 'patch')

        cmd: list[str] = [patch_command, '-f']

        if self.revert:
            cmd.append('-R')

        prefix_level = patch.prefix_level

        if prefix_level is None:
            prefix_level = self.get_default_prefix_level(patch=patch)

        if prefix_level is not None:
            if prefix_level >= 0:
                cmd.append(f'-p{prefix_level}')
            else:
                logger.warning('Unsupported -p value: %d; assuming zero.',
                               prefix_level)

        cmd += ['-i', str(patch_file)]

        # Ignore any return codes, since these signify how many errors may
        # have been found. We instead need to look for these errors. They
        # may be caused by a patch file consisting of only empty files (which
        # `patch` can't handle), patch application errors, conflicts, bad
        # diffs, or missing hunks.
        result = run_process(cmd,
                             ignore_errors=True,
                             redirect_stderr=True)
        patch_output = result.stdout_bytes.read()

        # Next, apply any binary files.
        if (binary_files := patch.binary_files):
            binary_applied, binary_failed = self.apply_binary_files(
                binary_files)
        else:
            binary_applied = None
            binary_failed = None

        if self.can_patch_empty_files:
            patched_empty_files = self.apply_patch_for_empty_files(patch)
        else:
            patched_empty_files = False

        conflicting_files: list[str]
        patched: bool

        if result.exit_code == 0:
            patched = True
            conflicting_files = []
        else:
            parsed_output = self.parse_patch_output(patch_output)
            conflicting_files = parsed_output['conflicting_files']

            patched = bool(
                parsed_output['has_partial_applied_files'] or
                binary_applied or
                patched_empty_files
            )

            if not patched and parsed_output.get('fatal_error'):
                raise ApplyPatchError(
                    _('There was an error applying %%(patch_subject)s: '
                      '%(error)s')
                    % {
                        'error': force_unicode(patch_output).strip(),
                    },
                    patcher=self,
                    failed_patch_result=PatchResult(
                        applied=False,
                        patch=patch,
                        patch_output=patch_output,
                        patch_range=(patch_num, patch_num)))

        # We're done here. Send the result.
        return PatchResult(
            applied=patched,
            patch=patch,
            patch_output=patch_output,
            patch_range=(patch_num, patch_num),
            has_conflicts=len(conflicting_files) > 0,
            conflicting_files=conflicting_files,
            binary_applied=binary_applied,
            binary_failed=binary_failed)

    def get_default_prefix_level(
        self,
        *,
        patch: Patch,
    ) -> int | None:
        """Return the default path prefix strip level for a patch.

        This function determines how much of a path to strip by default,
        if an explicit value isn't given.

        Subclasses can override this to provide a different default.

        Args:
            patch (rbtools.diffs.patches.Patch):
                The path to generate a default prefix strip level for.

        Returns:
            int:
            The prefix strip level, or ``None`` if a clear one could not be
            determined.
        """
        repository_info = self.repository_info

        if repository_info is not None and patch.base_dir:
            base_path = repository_info.base_path

            if base_path and patch.base_dir.startswith(base_path):
                return base_path.count('/') + 1

        return None

    def parse_patch_output(
        self,
        patch_output: bytes,
    ) -> ParsedPatchOutput:
        """Parse the patch command's output for useful information.

        This will parse the standard output from a supported patch command
        to return information that can be used to identify patched files,
        partially-applied files, conflicting files, and error messages.

        It's only used if the patcher uses the default patch application
        logic or if it's called explicitly.

        Args:
            patch_output (bytes):
                The patch output to parse.

        Returns:
            ParsedPatchOutput:
            The parsed data found from the patch output.
        """
        patch_output = patch_output.strip()

        # Check if there are empty files found.
        has_empty_files = bool(_CHECK_EMPTY_FILES_RE.search(patch_output))

        # Check if there's a fatal error found.
        #
        # There's some overlap with empty file indicators, so both states may
        # be returned.
        fatal_error: str | None

        m = _FATAL_PATCH_ERROR_RE.search(patch_output)

        if m:
            fatal_error = force_unicode(m.group('error'))
        else:
            fatal_error = None

        # Look for any patched files.
        patched_files: list[str] = [
            force_unicode(m.group('filename'))
            for m in _PATCHING_RE.finditer(patch_output)
        ]

        # Start looking for any files with failed hunks. We'll determine
        # if this patch was partially applied.
        conflicting_files: list[str] = []
        has_partial_applied_files: bool = False

        for m in _CONFLICTS_RE.finditer(patch_output):
            num_hunks = int(m.group('num_hunks'))
            total_hunks = int(m.group('total_hunks'))
            filename = force_unicode(m.group('filename'))

            conflicting_files.append(filename)

            if num_hunks != total_hunks:
                # This is a partially-applied patch.
                has_partial_applied_files = True

        if not has_partial_applied_files and conflicting_files:
            has_partial_applied_files = \
                (len(conflicting_files) != len(patched_files))

        return {
            'conflicting_files': conflicting_files,
            'fatal_error': fatal_error,
            'has_empty_files': has_empty_files,
            'has_partial_applied_files': has_partial_applied_files,
            'patched_files': patched_files,
        }

    def create_commit(
        self,
        *,
        patch_result: PatchResult,
        run_commit_editor: bool,
    ) -> None:
        """Create a commit based on a patch result.

        Subclasses must implement this and set :py:attr:`can_commit` if
        it supports creating commits based on changes in the working tree.

        This must only be called internally by the patcher.

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
        raise NotImplementedError

    def apply_patch_for_empty_files(
        self,
        patch: Patch,
    ) -> bool:
        """Apply an empty file patch to a file.

        Normally, a patching tool can't apply an empty patch to a file (which
        may be done to create a file, delete a file, or change metadata for a
        file). Subclasses can override this and enable
        :py:attr:`can_patch_empty_files` to opt into special logic for
        applying empty-file patches.

        The logic for applying the patch is entirely up to the subclass, and
        is not required for a patcher.

        Args:
            patch (rbtools.diffs.patches.Patch):
                The opened patch to check and possibly apply.

        Returns:
            bool:
            ``True`` if there are empty files in the patch that were applied.
            ``False`` if there were no empty files or the files could not be
            applied (which will lead to an error).

        Raises:
            rbtools.diffs.errors.ApplyPatchError:
                There was an error while applying the patch.
        """
        raise NotImplementedError

    def apply_binary_files(
        self,
        binary_files: Sequence[BinaryFilePatch],
    ) -> tuple[Sequence[str], Mapping[str, str]]:
        """Apply binary files to the filesystem.

        Version Added:
            6.0

        Args:
            binary_files (list of rbtools.diffs.patches.BinaryFilePatch):
                List of binary files to apply.

        Returns:
            tuple:
            A 2-tuple of:

            Tuple:
                0 (list of str):
                    A list of file paths that were successfully applied.

                1 (dict):
                    A mapping of file paths to failure reasons.
        """
        successfully_applied: list[str] = []
        failed_files: dict[str, str] = {}

        for f in binary_files:
            try:
                success, err = self.apply_binary_file(f)
            except Exception as e:
                success = False
                err = str(e)

            if success:
                successfully_applied.append(f.path)
            else:
                assert err is not None

                failed_files[f.path] = err

        return successfully_applied, failed_files

    def apply_binary_file(
        self,
        binary_file: BinaryFilePatch,
    ) -> tuple[bool, str | None]:
        """Apply a single binary file.

        Version Added:
            6.0

        Args:
            binary_file (rbtools.diffs.patches.BinaryFilePatch):
                The binary file to apply.

        Returns:
            tuple:
            A 2-tuple of:

            Tuple:
                0 (bool):
                    Whether the operation was a success.

                1 (str or None):
                    The error, if the operation failed.
        """
        status = binary_file.status
        old_path = binary_file.old_path
        new_path = binary_file.new_path

        if status == 'deleted':
            # Remove the file if it exists.
            assert old_path is not None
            self.handle_remove_file(old_path)

            return True, None
        else:
            # For added/modified files, write the content.
            content = binary_file.content

            if content is None:
                if binary_file.download_error:
                    error = _('Failed to download: {error}').format(
                        error=binary_file.download_error)
                    return False, error
                else:
                    return False, _('Binary file content not available')

            if status == 'added':
                assert new_path is not None
                self.handle_add_file(new_path, content)
            elif status == 'moved':
                assert old_path is not None
                assert new_path is not None

                self.handle_move_file(old_path, new_path)
                self.handle_write_file(new_path, content)
            elif status == 'modified':
                assert new_path is not None
                self.handle_write_file(new_path, content)
            else:
                assert_never(status)

            return True, None

    def handle_add_file(
        self,
        path: str,
        content: bytes,
    ) -> None:
        """Add a file.

        This may be overridden by subclasses if they need to interact with an
        SCM to perform the add.

        Version Added:
            6.0

        Args:
            path (str):
                The path to the file.

            content (bytes):
                The content for the file.

        Raises:
            OSError:
                A file operation failed.
        """
        # Create the directory if it doesn't exist.
        dirname = os.path.dirname(path)

        if dirname:
            os.makedirs(dirname, exist_ok=True)

        self.handle_write_file(path, content)

    def handle_move_file(
        self,
        old_path: str,
        new_path: str,
    ) -> None:
        """Move a file.

        This may be overridden by subclasses if they need to interact with an
        SCM to perform the move.

        Version Added:
            6.0

        Args:
            old_path (str):
                The old filename.

            new_path (str):
                The new filename.

        Raises:
            OSError:
                A file operation failed.
        """
        # Create the directory if it doesn't exist.
        dirname = os.path.dirname(new_path)

        if dirname:
            os.makedirs(dirname, exist_ok=True)

        os.rename(old_path, new_path)

    def handle_remove_file(
        self,
        path: str,
    ) -> None:
        """Delete a file.

        This may be overridden by subclasses if they need to interact with an
        SCM to perform the move.

        Version Added:
            6.0

        Args:
            path (str):
                The path to the file to delete.

        Raises:
            OSError:
                A file operation failed.
        """
        if os.path.exists(path):
            os.remove(path)
        else:
            # File doesn't exist, but that's ok for deletion.
            logger.warning('Binary file %s was deleted in the '
                           'patch, but local file was not found.',
                           path)

    def handle_write_file(
        self,
        path: str,
        content: bytes,
    ) -> None:
        """Write the content of a file.

        This may be overridden by subclasses if they need to interact with an
        SCM to perform the operation.

        Version Added:
            6.0

        Args:
            path (str):
                The path to the file.

            content (bytes):
                The content for the file.

        Raises:
            OSError:
                A file operation failed.
        """
        with open(path, 'wb') as fp:
            fp.write(content)
