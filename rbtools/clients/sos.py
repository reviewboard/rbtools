"""A client for Cliosoft SOS.

`Cliosoft SOS <https://www.cliosoft.com/products/sos/>`_ is an Enterprise
SCM focused on hardware design and configuration management.

Version Added:
    3.1
"""

import io
import logging
import os
import re
import sqlite3
from collections import OrderedDict
from contextlib import contextmanager
from typing import List, Optional, Union, cast

from pydiffx import DiffType, DiffX
from pydiffx.utils.text import guess_line_endings
from typing_extensions import NotRequired, TypedDict

from rbtools.api.resource import ReviewRequestResource
from rbtools.clients import RepositoryInfo
from rbtools.clients.base.scmclient import (BaseSCMClient,
                                            SCMClientDiffResult,
                                            SCMClientRevisionSpec)
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    SCMError,
                                    TooManyRevisionsError)
from rbtools.deprecation import (RemovedInRBTools50Warning,
                                 deprecate_non_keyword_only_args)
from rbtools.diffs.tools.base import DiffFileResult
from rbtools.diffs.writers import UnifiedDiffWriter
from rbtools.utils.checks import check_install
from rbtools.utils.diffs import filename_match_any_patterns
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import execute


logger = logging.getLogger(__name__)


class SOSRevisionSpecExtra(TypedDict):
    """Extra revision information for a SOS revision specification.

    This contains information on the SOS changelist or selection, computed
    based on the revision information provided to SOS.

    This goes into the ``extra`` key in
    :py:class:`~rbtools.clients.base.scmclient.SCMClientRevisionSpec`.

    Version Added:
        4.0:
        In prior versions, these keys lived directly in the base of the
        revision spec.
    """

    #: Whether an explicit selection was provided.
    #:
    #: If ``False``, a default selection will be used instead.
    #:
    #: This is only present if :py:attr:`sos_selection` is present.
    #:
    #: Type:
    #:     bool
    has_explicit_selection: NotRequired[bool]

    #: The changelist ID being posted for review.
    #:
    #: Type:
    #:     str
    sos_changelist: NotRequired[str]

    #: A list of SOS selection flags representing files to post for review.
    #:
    #: Type:
    #:     list of str
    sos_selection: NotRequired[List[str]]


class SOSObjectType(object):
    """Constants for SOS object types.

    Version Added:
        3.1
    """

    #: Directory.
    DIR = b'd'

    #: Normal file.
    FILE = b'f'

    #: Package.
    PACKAGE = b'p'

    #: Symbolic link.
    SYMLINK = b's'

    #: Directory imported from another SOS project.
    REFERENCE_DIR = b'D'

    #: Normal file imported from another SOS project.
    REFERENCE_FILE = b'F'

    #: Package imported from another SOS project.
    REFERENCE_PACKAGE = b'P'

    #: Symbolic link imported from another SOS project.
    REFERENCE_SYMLINK = b'S'


class SOSObjectState(object):
    """Constants for SOS object states.

    Version Added:
        3.1
    """

    #: An object that's checked into the central server.
    CHECKED_IN = b'-'

    #: An object checked out for modification.
    CHECKED_OUT = b'O'

    #: An object checked out for modification without server-side lock.
    CHECKED_OUT_WITHOUT_LOCK = b'W'

    #: A directory populated non-recursively.
    DIR_POULATED_NON_RECURSIVE = b'C'

    #: An object disallowing read access.
    READ_ACCESS_DENIED = b'X'

    #: An object not managed by SOS.
    UNMANAGED = b'?'

    #: An object not populated in the local project directory.
    UNPOPULATED = b'N'


class SOSObjectChangeStatus(object):
    """Constants for SOS object change statuses.

    Version Added:
        3.1
    """

    #: An object is being deleted from the project.
    DELETED = b'!'

    #: An object is being modified.
    MODIFIED = b'M'

    #: Change statuses are not applicable to the type of object.
    NOT_APPLICABLE = b'?'

    #: An object is unchanged.
    UNCHANGED = b'-'


class SOSObjectRevision(object):
    """Constants for SOS revisions.

    Version Added:
        3.1
    """

    #: An object is not managed by SOS, and has no revision.
    UNMANAGED = b'?'


class SOSChangeList(object):
    """A representation of a SOS changelist.

    A changelist records the added, modified, and deleted files scheduled to
    be posted for review or checked into a project. These are managed via
    the :command:`soscmd add`, :command:`soscmd commit`, and
    :command:`soscmd describe` commands in SOS 7.20+.

    Version Added:
        3.1

    Attributes:
        adds (set, optional):
            File paths scheduled to be added. Each is relative to the
            workarea root.

        deletes (set, optional):
            File paths scheduled to be added. Each is relative to the
            workarea root.

        modifications (set, optional):
            File paths scheduled to be modified. Each is relative to the
            workarea root.
    """

    def __init__(self, adds=None, deletes=None, modifications=None):
        """Initialize the changelist.

        Args:
            adds (set, optional):
                File paths scheduled to be added. Each is relative to the
                workarea root.

            deletes (set, optional):
                File paths scheduled to be added. Each is relative to the
                workarea root.

            modifications (set, optional):
                File paths scheduled to be modified. Each is relative to the
                workarea root.
        """
        self.adds = adds or set()
        self.deletes = deletes or set()
        self.modifications = modifications or set()


class SOSClient(BaseSCMClient):
    """A client for Cliosoft SOS.

    `Cliosoft SOS <https://www.cliosoft.com/products/sos/>`_ is an Enterprise
    SCM focused on hardware design and configuration management.

    This implementation makes use of :command:`soscmd` to fetch information on
    repositories and generate suitable diffs.

    Diff generation makes use of the proposed `DiffX <https://diffx.org/>`_
    standard (SOS itself doesn't have a native diff format with metadata).

    This implementation is expected to be used with SOS 7.20 or higher.

    Version Added:
        3.1
    """

    scmclient_id = 'sos'
    name = 'Cliosoft SOS'

    requires_diff_tool = True

    supports_diff_exclude_patterns = True

    REVISION_WORKING_COPY = '--rbtools-working-copy'

    DEFAULT_SELECTION = ['-scm']
    INCLUDE_FILES_SELECTION = ['-sor', '-sfo', '-sdo', '-sunm']

    RSO_SPLIT_RE = re.compile(r',\s*')

    def __init__(self, *args, **kwargs):
        """Initialize the client.

        Args:
            *args (tuple):
                Positional arguments for the parent constructor.

            **kwargs (dict):
                Keyword arguments for the parent constructor.
        """
        super(SOSClient, self).__init__(*args, **kwargs)

        self._cache = {}

    def check_dependencies(self) -> None:
        """Check whether all base dependencies are available.

        This checks for the presence of :command:`soscmd` in the system path.

        Version Added:
            4.0

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                A :command:`soscmd` tool could not be found.
        """
        if not check_install(['soscmd', 'version']):
            raise SCMClientDependencyError(missing_exes=['soscmd'])

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system, or
            ``None`` if not inside of a workarea.
        """
        # NOTE: This can be removed once check_dependencies() is mandatory.
        if not self.has_dependencies(expect_checked=True):
            logger.debug('Unable to execute "soscmd version"; skipping SOS')
            return None

        # Grab the workarea.
        try:
            return self._get_wa_root()
        except Exception:
            # This is not a SOS workarea.
            return None

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current SOS workarea.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The workarea repository information, or ``None`` if not in a
            SOS workarea.
        """
        local_path = self.get_local_path()

        if not local_path:
            return None

        project = self._query_sos_info('project')
        server = self._query_sos_info('server')

        # The path matches what's used in Power Pack. We don't have hostnames
        # to consider, so it's purely server/project.
        return RepositoryInfo(path='SOS:%s:%s' % (server, project),
                              local_path=local_path)

    def parse_revision_spec(
        self,
        revisions: List[str] = [],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        If a single revision is passed in, and it begins with ``select:``,
        then anything after is expected to be SOS selection flags to
        match files to post.

        If a single revision is passed in, and it does not begin with
        ``select:``, then it's assumed to be a changelist ID.

        If zero revisions are passed in, a default selection of ``-scm``
        will be used.

        Anything else is unsupported.

        Args:
            revisions (list of str, optional):
                A list of SOS selection patterns or changelist IDs, as
                specified by the user.

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This only makes use of the ``extra`` field, which is documented
            in :py:class:`SOSRevisionSpecExtra`.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.
        """
        n_revs = len(revisions)

        sos_revisions: SOSRevisionSpecExtra

        if n_revs == 0:
            sos_revisions = {
                'sos_selection': self.DEFAULT_SELECTION,
                'has_explicit_selection': False,
            }
        elif n_revs == 1:
            if revisions[0].startswith('select:'):
                # The user is providing an SOS selection.
                sos_revisions = {
                    'sos_selection': revisions[0].split(':', 1)[1].split(' '),
                    'has_explicit_selection': True,
                }
            elif self._has_changelist_support():
                sos_revisions = {
                    'sos_changelist': revisions[0],
                }
            else:
                raise InvalidRevisionSpecError(
                    'SOS requires a revision argument to be a selection in '
                    'the form of: "select:<selection>". For example: '
                    'select:-scm')
        else:
            raise TooManyRevisionsError

        return {
            'base': None,
            'tip': None,
            'extra': sos_revisions,
        }

    def get_tree_matches_review_request(
        self,
        review_request: ReviewRequestResource,
        revisions: SCMClientRevisionSpec,
        **kwargs,
    ) -> bool:
        """Return whether a tree matches metadata in a review request.

        This will compare the stored state in a review request (set when
        posting a change for review) to the project, server, workarea ID,
        and changelist ID of the current tree.

        This is used for enhanced guessing of review requests, available in
        RBTools 3.1+.

        Args:
            review_request (rbtools.api.resources.ReviewRequestResource):
                The review request being matched.

            revisions (dict):
                The posted revision information. This is expected to be the
                result of :py:meth:`parse_revision_spec`.

            **kwargs (dict, unused):
                Additional keyword arguments for future expansion.

        Returns:
            bool:
            ``True`` if the review request matches the tree. ``False`` if it
            does not.
        """
        assert 'extra' in revisions
        revisions_extra = cast(SOSRevisionSpecExtra, revisions['extra'])

        local_changelist_id = revisions_extra.get('sos_changelist')

        if not local_changelist_id:
            return False

        extra_data = review_request.extra_data

        try:
            project = extra_data['sos_project']
            server = extra_data['sos_server']
            workarea_id = extra_data['sos_workarea']
            changelist_id = extra_data['sos_changelist']
        except KeyError:
            return False

        return (changelist_id == local_changelist_id and
                workarea_id == self._get_workarea_id() and
                project == self._query_sos_info('project') and
                server == self._query_sos_info('server'))

    @deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
    def diff(
        self,
        revisions: SCMClientRevisionSpec,
        *,
        include_files: List[str] = [],
        exclude_patterns: List[str] = [],
        with_parent_diff: bool = True,
        **kwargs,
    ) -> SCMClientDiffResult:
        """Perform a diff using the given revisions.

        This goes through the work of generating a diff for SOS, generating a
        DiffX-compatible diff.

        It will start by grabbing the changelist details or the files matched
        by a selection, exporting the old revision of each, and diffing that
        to the current version in the tree.

        The DiffX metadata contains the SOS project, server, RSO, and the
        changelist ID if posting a change for review. This is needed
        server-side for looking up each file.

        The current selection will be stashed before this operation and then
        restored afterward, in order to avoid impacting any current selections
        from the user.

        The results will also contain additional metadata used to store in
        the review request's ``extra_data`` field, for smart review request
        matching. This includes the SOS project, server, workarea ID, and
        the changelist ID if posting a changelist for review.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            include_files (list of unicode, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of unicode, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary containing keys documented in
            :py:class:`~rbtools.clients.base.scmclient.SCMClientDiffResult`.
        """
        assert 'extra' in revisions
        revisions_extra = cast(SOSRevisionSpecExtra, revisions['extra'])

        wa_root = self._get_wa_root()
        changelist = None

        assert wa_root

        # We'll be overriding the selection every time we export, so make sure
        # that we stash the old selection and restore it after.
        #
        # XXX Seems that selecting multiple revisions of a file just reports
        #     multiple entries without useful revision information.
        with self._stash_selection():
            # Determine if we're building a list of files from a changelist or
            # a selection.
            #
            # Any included/excluded files will be matched during diff
            # generation below. However, if we're including files and are
            # using the default selection now, we'll simply provide those
            # files as part of the selection criteria.
            selection = None

            if 'sos_changelist' in revisions_extra:
                changelist = revisions_extra['sos_changelist']
            elif 'sos_selection' in revisions_extra:
                if (include_files and
                    not revisions_extra.get('has_explicit_selection')):
                    # Select all specified files (-sfo) or directories (-sdo),
                    # and allow for unmanaged files (-sunm).
                    selection = self.INCLUDE_FILES_SELECTION + include_files
                else:
                    selection = revisions_extra['sos_selection']
            else:
                raise KeyError(
                    'revisions is missing either a "sos_changelist" or '
                    '"sos_selection" key.'
                )

            selected_files = self._get_files(
                changelist=changelist,
                selection=selection,
                include_files=include_files,
                exclude_patterns=exclude_patterns)

            if not selected_files:
                # No files from the selection were found. We can return an
                # empty diff.
                return {
                    'diff': b'',
                }

            # Begin building the diff.
            project = self._query_sos_info('project')
            server = self._query_sos_info('server')
            rso = self._query_sos_info('rso')

            assert rso

            diffx = DiffX(meta={
                'scm': 'sos',
                'sos': {
                    'project': project,
                    'rso': self.RSO_SPLIT_RE.split(rso),
                    'server': server,
                }
            })

            if changelist:
                diffx.meta['sos']['changelist'] = changelist

            diffx_change = diffx.add_change()

            # Build the diff header.
            for selected_file in selected_files:
                # Gather metadata for this entry.
                selected_file_op = selected_file['op']
                old_filename = selected_file['old_filename']
                new_filename = selected_file['new_filename']
                revision = selected_file['revision']
                rev_id = selected_file['rev_id']
                obj_type = selected_file['type']
                change_status = selected_file['change_status']

                if obj_type in (SOSObjectType.DIR,
                                SOSObjectType.REFERENCE_DIR):
                    # Don't include directories themselves in the diff.
                    continue

                # Determine the operation performed.
                if selected_file_op == 'modify':
                    # This should be a moved or modified file.
                    if old_filename == new_filename:
                        op = 'modify'
                    else:
                        # This may change to "move-modify" below when we
                        # generate the diff.
                        op = 'move'
                elif selected_file_op == 'create':
                    # This should be a created file.
                    op = 'create'
                elif selected_file_op == 'delete':
                    # This should be a deleted file.
                    op = 'delete'
                elif selected_file_op == 'move':
                    op = 'move'
                else:
                    raise AssertionError(
                        'Invalid operation for path "%s". This is an internal '
                        'error in RBTools. Please report this and include '
                        'this data: %r'
                        % (new_filename or old_filename, selected_file))

                # We need to track two versions of the filenames:
                #
                # 1) The SOS version ("./path"), which we'll use for diffing.
                # 2) The normalized filename to put into the metadata.
                sos_old_filename = old_filename
                sos_new_filename = new_filename

                old_filename = self._normalize_sos_path(sos_old_filename)
                new_filename = self._normalize_sos_path(sos_new_filename)

                # Determine the file path information we'll store in the
                # DiffX file metadata.
                #
                # We'll only record old/new filenames if the filename has
                # changed.
                if old_filename and new_filename:
                    if old_filename == new_filename:
                        path_info = new_filename
                    else:
                        path_info = {
                            'old': old_filename,
                            'new': new_filename,
                        }
                else:
                    path_info = new_filename or old_filename

                # Add the file to the diff. We'll fill in details in the
                # next few steps.
                diffx_file = diffx_change.add_file(meta={
                    'path': path_info,
                })

                if obj_type == SOSObjectType.FILE:
                    # This is a standard file, or something that can be
                    # represented as a standard file.
                    if op == 'create':
                        diff_old_filename = '/dev/null'
                    else:
                        diff_old_filename = old_filename

                    if op == 'delete':
                        diff_new_filename = '/dev/null'
                    else:
                        diff_new_filename = new_filename

                    if (change_status != SOSObjectChangeStatus.UNCHANGED or
                        op == 'move'):
                        # Generate a diff of the file contents.
                        diff_result = self._diff_file_hunks(
                            wa_root=wa_root,
                            filename=sos_new_filename or sos_old_filename,
                            orig_revision=revision,
                            orig_content=selected_file.get('orig_content'))

                        stream = io.BytesIO()
                        diff_writer = UnifiedDiffWriter(stream)

                        if diff_result.is_binary:
                            # Mark this as a binary file. We don't currently
                            # provide any binary file contents.
                            diffx_file.diff_type = DiffType.BINARY
                            diff_writer.write_binary_files_differ(
                                orig_path=diff_old_filename,
                                modified_path=diff_new_filename)
                        elif diff_result.has_text_differences:
                            # If we thought this was a moved file, it's time to
                            # change it to indicate there are modifications.
                            if op == 'move':
                                op = 'move-modify'

                            # Populate the diff content.
                            hunks = diff_result.hunks
                            line_endings, newline = guess_line_endings(hunks)
                            diffx_file.diff_line_endings = line_endings

                            diff_writer.write_file_headers(
                                orig_path=diff_old_filename,
                                modified_path=diff_new_filename)
                            diff_writer.write_diff_file_result_hunks(
                                diff_result)

                        diffx_file.diff = stream.getvalue()
                elif obj_type == SOSObjectType.SYMLINK:
                    # This is a symlink.
                    #
                    # NOTE: This support is currently incomplete, and does not
                    #       support most operations around a symlink. We are
                    #       planning to greatly improve symlink support, but
                    #       it needs to go through a new round of testing
                    #       with Cliosoft, post-release, as current behavior
                    #       has already been vetted.
                    diffx_file.meta.update({
                        'type': 'symlink',
                        'symlink target': os.readlink(new_filename),
                    })
                else:
                    raise AssertionError(
                        'Invalid object type for path "%s". This is an '
                        'internal error in RBTools. Please report this '
                        'and include this data: %r'
                        % (new_filename or old_filename, selected_file))

                diffx_file.meta['op'] = op

                # Note that currently, a revision range of older files
                # cannot be diffed, so we don't have a "new" key to include.
                # This might change in the future.
                if revision != SOSObjectRevision.UNMANAGED:
                    diffx_file.meta['revision'] = {
                        'old': str(revision),
                    }

                if rev_id not in (None, SOSObjectRevision.UNMANAGED):
                    diffx_file.meta['sos'] = {
                        'rev_id': {
                            'old': rev_id,
                        },
                    }

            diffx.generate_stats()

        # We've finished. Make sure there's something of substance in the
        # diff before we return it.
        if diffx.meta['stats']['files'] > 0:
            diff_content = diffx.to_bytes()

            # Store data that can be used to later match the review request.
            review_request_extra_data = {
                'sos_project': project,
                'sos_server': server,
                'sos_workarea': self._get_workarea_id(),
            }

            if changelist:
                review_request_extra_data['sos_changelist'] = changelist
        else:
            # There are no files to post. Return an empty diff.
            diff_content = b''
            review_request_extra_data = None

        return {
            'diff': diff_content,
            'review_request_extra_data': review_request_extra_data,
        }

    def run_soscmd(self, subcommand, *args, **kwargs):
        """Run soscmd with the provided arguments.

        This will be run in the specified directory (if passing ``cwd`` as
        a keyword argument), or in the workarea root. If neither are set,
        it will instead run in the current directory.

        Args:
            subcommand (unicode):
                The :command:`soscmd` sub-command to run.

            *args (tuple):
                Additional arguments to pass to the sub-command.

            **kwargs (dict):
                Keyword arguments to pass to
                :py:func:`~rbtools.utils.process.execute`.

        Returns:
            object:
            The result from the execution, based on the keyword arguments.
        """
        cwd = (
            kwargs.pop('cwd', None) or
            self._get_wa_root() or
            os.getcwd()
        )

        return execute(['soscmd', subcommand] + list(args),
                       cwd=cwd,
                       **kwargs)

    def _get_files(self, changelist=None, selection=None, include_files=None,
                   exclude_patterns=None):
        """Return the list of modified files/objects in the workarea.

        This can take either a changelist ID or an explicit selection. If
        neither are provided, the current selection will be used.

        Args:
            changelist (unicode, optional):
                An explicit changelist ID to return files from.

            selection (list of unicode, optional):
                An explicit selection for the status.

            include_files (list of unicode, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of unicode, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

        Returns:
            list of dict:
            A list of modified files/objects. Each entry is a dictionary with
            the following keys:

            ``change_status`` (:py:class:`bytes`):
                The change status of the file/object, corresponding to a value
                in :py:class:`SOSObjectChangeStatus`.

            ``new_filename`` (:py:class:`unicode`):
                The old path to the file/object, relative to the root of the
                workarea.

            ``old_filename`` (:py:class:`unicode`):
                The old path to the file/object, relative to the root of the
                workarea.

            ``op`` (:py:class:`unicode`):
                The operation being performed. This will correspond to a
                DiffX file operation.

            ``orig_content`` (:py:class:`bytes`, optional):
                The original file contents. This will only be present if
                ``op`` is ``delete``.

            ``revision`` (:py:class:`int`):
                The revision of the file/object.

                If the file is not managed, this will be ``None``.

            ``state`` (:py:class:`bytes`):
                The state of the file/object, corresponding to a value in
                :py:class:`SOSObjectState`.

            ``type`` (:py:class:`bytes`):
                The file/object type, corresponding to a value in
                :py:class:`SOSObjectType`.
        """
        if changelist:
            selected_files = self._get_changelist_files(changelist)
        else:
            selected_files = self._get_selection_files(selection)

        # Include or exclude any files from the selection/changelist as
        # specified by the user.
        if include_files or exclude_patterns:
            new_selected_files = []

            if include_files:
                include_files = {
                    self._normalize_sos_path(_filename)
                    for _filename in include_files
                }

            for selected_file in selected_files:
                filename = self._normalize_sos_path(
                    selected_file['new_filename'])

                if ((not include_files or filename in include_files) and
                    (not exclude_patterns or
                     not filename_match_any_patterns(filename,
                                                     exclude_patterns))):
                    new_selected_files.append(selected_file)

            selected_files = new_selected_files

        return selected_files

    def _get_changelist_files(self, changelist):
        """Return a list of files recorded in a SOS changelist.

        Args:
            changelist (unicode):
                The changelist ID.

        Returns:
            list of dict:
            A list of modified files/objects. See :py:meth:`_get_files`
            for the contents of the dictionaries.
        """
        lines = self.run_soscmd('add', '-s', '-c', changelist,
                                split_lines=True)

        adds = set()
        deletes = set()
        modifications = set()

        actions_map = {
            'Adding': adds,
            'Deleting': deletes,
            'Modifying': modifications,

            # "Modifing" is present in the soscmd_utils beta, which may be
            # in use by customers still running older beta versions of SOS.
            'Modifing': modifications,
        }

        for line in lines:
            line = line.strip()

            if not line:
                continue

            try:
                action, filename = line.split(' ', 1)
            except Exception:
                logger.warning('Unexpected line from `soscmd add -s`: %r',
                               line)
                continue

            try:
                actions_map[action].add(filename)
            except KeyError:
                logger.warning('Unexpected action from `socsmd add -s`: %r',
                               action)
                continue

        changelist = SOSChangeList(adds=adds,
                                   deletes=deletes,
                                   modifications=modifications)

        return self._get_selection_files(['-sor', '-scm', '-sunm', '-sne'],
                                         changelist=changelist)

    def _get_selection_files(self, selection, changelist=None):
        """Return a list of files based on selection criteria.

        Args:
            changelist (SOSChangeList):
                The changelist of files to include in the results.

        Returns:
            list of dict:
            A list of modified files/objects. See :py:meth:`_get_files`
            for the contents of the dictionaries.
        """
        wa_root = self._get_wa_root()

        files = OrderedDict()
        dir_items = []
        file_items = []
        tree_ops = {}
        pending_revision_payloads = {}

        # If we're working with a changelist, determine the parent directories
        # for any changes so that we can filter out paths early and avoid
        # workarea lookups.
        if changelist:
            filtered_parent_dirs = {
                os.path.dirname(_path)
                for _paths in (changelist.adds,
                               changelist.deletes,
                               changelist.modifications)
                for _path in _paths
            }
        else:
            filtered_parent_dirs = None

        # This is used to normalize types to something we can reference
        # during object selection and diff building.
        OBJ_BASE_TYPE_MAP = {
            SOSObjectType.DIR: SOSObjectType.DIR,
            SOSObjectType.FILE: SOSObjectType.FILE,
            SOSObjectType.SYMLINK: SOSObjectType.SYMLINK,
            SOSObjectType.REFERENCE_DIR: SOSObjectType.DIR,
            SOSObjectType.REFERENCE_FILE: SOSObjectType.FILE,
            SOSObjectType.REFERENCE_SYMLINK: SOSObjectType.SYMLINK,
        }

        # Parse the list of changes and separate them into directories and
        # files. We'll parse the directories first to determine the operations
        # made to the tree.
        for line in self._iter_status(selection):
            filename = line[3].decode('utf-8')

            if (filtered_parent_dirs is not None and
                filename not in filtered_parent_dirs and
                os.path.dirname(filename) not in filtered_parent_dirs):
                # This path doesn't appear to be relevant to the changelist.
                # Skip it.
                continue

            obj_type = OBJ_BASE_TYPE_MAP.get(line[0])
            obj_state = line[1]
            change_status = line[2]

            if obj_type == SOSObjectType.DIR:
                items = dir_items
            elif obj_type in (SOSObjectType.FILE,
                              SOSObjectType.SYMLINK):
                items = file_items
            else:
                continue

            items.append({
                'change_status': change_status,
                'filename': filename,
                'obj_state': obj_state,
                'obj_type': obj_type,
            })

        # Determine the operations made on any directories. We need the
        # rename information when we process modifications to files. Adds
        # and deletes will be processed after.
        for item in dir_items:
            self._get_pending_tree_ops(wa_root, item['filename'], tree_ops)

        renamed_dirs = tree_ops.get('renamed_dirs', {})
        renamed_files = tree_ops.get('renamed_files', {})

        # Process all modifications reported by `soscmd status`.
        #
        # We'll generate an operation and filenames from each and store
        # them for further processing.
        for item in file_items:
            old_filename = None
            new_filename = None

            change_status = item['change_status']
            filename = item['filename']
            obj_state = item['obj_state']
            obj_type = item['obj_type']

            if change_status == SOSObjectChangeStatus.MODIFIED:
                # This is a modified file tracked by SOS.
                if changelist and filename not in changelist.modifications:
                    # This file is not present in the changelist. Skip it.
                    continue

                op = 'modify'
                old_filename = self._get_rename_old_name(
                    filename,
                    renamed_files=renamed_files,
                    renamed_dirs=renamed_dirs)
                new_filename = filename
            elif (obj_state == SOSObjectState.UNMANAGED and
                  change_status == SOSObjectChangeStatus.NOT_APPLICABLE):
                # This is a file not managed by SOS. It's considered a new
                # file.
                if changelist and filename not in changelist.adds:
                    # This file is not present in the changelist. Skip it.
                    continue

                op = 'create'
                new_filename = filename
            elif change_status == SOSObjectChangeStatus.DELETED:
                # This is a deleted file tracked by SOS.
                if changelist and filename not in changelist.deletes:
                    # This file is not present in the changelist. Skip it.
                    continue

                op = 'delete'
                old_filename = filename
            else:
                logger.debug('Skipping selected path "%s". Does not '
                             'appear to be a created, modified, or '
                             'deleted file.',
                             filename)
                continue

            payload = {
                'change_status': change_status,
                'new_filename': new_filename,
                'old_filename': old_filename,
                'op': op,
                'rev_id': SOSObjectRevision.UNMANAGED,
                'revision': SOSObjectRevision.UNMANAGED,
                'state': obj_state,
                'type': obj_type,
            }

            if op != 'create':
                pending_revision_payloads[filename] = payload

            files[filename] = payload

        # Handle any renamed directories.
        #
        # We start with this in order to convert any renamed directories
        # into lists of renamed files, which may themselves be converted
        # into individual adds/deletes in the next phase.
        #
        # Generally, if any directories were renamed, we'll want to include
        # each file in that directory or any subdirectories in the diff as a
        # moved file.
        for new_dirname, old_dirname in renamed_dirs.items():
            full_walk_path = os.path.normpath(
                os.path.join(wa_root, new_dirname))

            for walk_root, walk_dirs, walk_files in os.walk(full_walk_path):
                # We need to ensure all file paths use "./" syntax.
                walk_root = self._make_sos_path(walk_root, wa_root)

                for filename in walk_files:
                    full_path = os.path.join(walk_root, filename)

                    renamed_files[full_path] = os.path.join(
                        old_dirname,
                        full_path[len(new_dirname):])

        # Handle any files marked as renamed.
        #
        # This may include files from the step above.
        #
        # If we're working with a changelist, then the changelist must include
        # both the add and the delete in order to treat it as a rename.
        # Otherwise, we'll process this in the adds or deletes blocks below.
        for new_filename, old_filename in renamed_files.items():
            if changelist:
                is_deleted = old_filename in changelist.deletes
                is_added = new_filename in changelist.adds

                if not is_deleted and not is_added:
                    # This isn't in the changelist at all. Skip it.
                    continue
                elif not is_deleted:
                    # This was marked as deleted in the changelist, but not
                    # added. Queue it up to be treated as an add.
                    if old_filename not in files:
                        tree_ops.setdefault('deletes', []).append({
                            'filename': old_filename,
                            'type': SOSObjectType.FILE,
                        })

                    continue
                elif not is_added:
                    # This was marked as added in the changelist, but not
                    # deleted. Queue it up to be treated as a delete.
                    if new_filename not in files:
                        tree_ops.setdefault('adds', []).append({
                            'filename': new_filename,
                            'type': SOSObjectType.FILE,
                        })

                    continue
            elif new_filename in files:
                # This file is already tracked. Skip it.
                continue

            # This file was renamed but not changed.
            payload = {
                'change_status': SOSObjectChangeStatus.UNCHANGED,
                'new_filename': new_filename,
                'old_filename': old_filename,
                'op': 'move',
                'rev_id': SOSObjectRevision.UNMANAGED,
                'revision': SOSObjectRevision.UNMANAGED,
                'state': SOSObjectState.CHECKED_OUT,
                'type': SOSObjectType.FILE,
            }

            pending_revision_payloads[new_filename] = payload
            files[new_filename] = payload

        # Add any newly-added files that may not be present in the above
        # file list.
        for add_info in tree_ops.get('adds', []):
            filename = add_info['filename']

            if (filename not in files and
                (not changelist or filename in changelist.adds)):
                files[filename] = {
                    'change_status': SOSObjectChangeStatus.NOT_APPLICABLE,
                    'new_filename': filename,
                    'old_filename': None,
                    'op': 'create',
                    'rev_id': None,
                    'revision': SOSObjectRevision.UNMANAGED,
                    'state': SOSObjectState.UNMANAGED,
                    'type': add_info['type'],
                }

        # Add any newly-deleted files not present in the above file list.
        for delete_info in tree_ops.get('deletes', []):
            filename = delete_info['filename']

            if (filename not in files and
                (not changelist or filename in changelist.deletes)):
                # In order to retrieve information on deleted files, we'll
                # need to undelete them, grab the information, and re-delete.
                try:
                    with self._access_deleted_file(filename):
                        with open(os.path.join(wa_root, filename), 'rb') as fp:
                            orig_content = fp.read()

                        revisions = next(self._iter_obj_revisions([filename]))
                except Exception as e:
                    logger.warning('Unable to access information on deleted '
                                   'file "%s". This file will not be '
                                   'included in the diff. Error: %s',
                                   filename, e)
                    continue

                files[filename] = {
                    'change_status': SOSObjectChangeStatus.DELETED,
                    'new_filename': None,
                    'old_filename': filename,
                    'op': 'delete',
                    'rev_id': revisions['rev_id'],
                    'revision': revisions['revision'],
                    'state': SOSObjectState.CHECKED_OUT,
                    'type': delete_info['type'],
                    'orig_content': orig_content,
                }

        # Batch-fetch revision information and populate the payloads.
        # We'll fetch 25 at a time so we won't have any real risk of
        # hitting max command line lengths, even with very long path names.
        revisions_iter = self._iter_obj_revisions(
            list(pending_revision_payloads.keys()))

        for info in revisions_iter:
            pending_revision_payloads[info['path']].update({
                'rev_id': info['rev_id'],
                'revision': info['revision'],
            })

        logger.debug('File information for diff: %r', files)

        return sorted(
            files.values(),
            key=lambda info: os.path.split(info['new_filename'] or
                                           info['old_filename']))

    @contextmanager
    def _access_deleted_file(self, path):
        """Provide temporary access to a deleted file.

        This will temporarily undelete a file, yield to the caller, and then
        re-delete the file.

        Callers are responsible for handling any exceptions caused when
        undeleting or deleting the file.

        Args:
            path (unicode):
                The path to the deleted file.

        Context:
            The file will be available for reading and querying.
        """
        self.run_soscmd('undelete',
                        os.path.dirname(path),
                        os.path.basename(path))

        try:
            yield
        finally:
            # Re-delete the file.
            self.run_soscmd('delete', path)

    def _iter_status(self, selection, fields=['%T', '%S', '%C', '%P']):
        """Iterate through the results of soscmd status.

        Args:
            selection (list of unicode):
                The selection for the status.

            fields (list of unicode, optional):
                The fields to provide in status output.

        Yields:
            tuple:
            Values corresponding to each field for a given file.
        """
        soscmd_args = [
            'status',
            '-f%s' % r'\t'.join(fields),
            '-Nhdr',
        ] + (selection or [])

        status = self.run_soscmd(*soscmd_args,
                                 results_unicode=False,
                                 split_lines=True)

        # Parse the status results.
        for _line in status:
            if not _line.startswith(b'!!'):
                yield _line.strip().split(b'\t')

    def _iter_obj_revisions(self, paths):
        """Iterate revision and rev IDs for paths.

        This will fetch revisions for paths in batches, to avoid large
        numbers of files with long file paths from hitting process command
        line execution limits.

        Args:
            paths (list of unicode):
                The paths to retrieve revision information for.

        Yields:
            dict:
            A dictionary containing:

            Keys:
                path (unicode):
                    The SOS path to the file.

                rev_id (int):
                    The globally-unique revision ID of the file.

                revision (int):
                    The revision of the file. This may be different from the
                    globally-unique revision ID.
        """
        attributes = ['Revision', 'RevId']
        batch_size = 25

        # Sort the paths, to ease unit testing.
        paths = sorted(paths)

        for i in range(0, len(paths), batch_size):
            batch_paths = paths[i:i + batch_size]

            nobjstatus_iter = self._iter_nobjstatus(attributes=attributes,
                                                    selection=batch_paths)

            for nobj_status in nobjstatus_iter:
                revision = nobj_status.get('Revision',
                                           SOSObjectRevision.UNMANAGED)
                rev_id = nobj_status.get('RevId',
                                         SOSObjectRevision.UNMANAGED)

                yield {
                    'path': nobj_status['filename'],
                    'rev_id': rev_id,
                    'revision': revision,
                }

    def _get_pending_tree_ops(self, wa_root, path, tree_ops):
        """Return tree-level operations pending for check-in.

        This will look for any files being created, deleted, moved, or renamed
        in a directory, and gather information necessary for building the diff.

        This does not recurse. However, any moved/renamed directories will
        recurse into them and provide a rename entry for all files within.

        Args:
            wa_root (unicode):
                The root of the workarea.

            path (unicode):
                The path to a directory.

            tree_ops (dict):
                A dictionary of operations to populate. This will create or
                update the following keys: ``adds``, ``deletes``,
                ``renamed_dirs``, ``renamed_files``
        """
        try:
            lines = self.run_soscmd('diff', path, split_lines=True)
        except Exception:
            # We may not be able to diff this directory. Bail.
            return

        # That command will generate a diff.out file, so get rid of it.
        try:
            os.unlink(os.path.join(wa_root, path, 'diff.out'))
        except Exception:
            # The file wasn't there, or we couldn't delete it. We were just
            # trying to clean up, so don't let this failure stop us from
            # doing anything else. Ignore it.
            pass

        file_changes = {}

        file_re = re.compile(r'^(?P<op>[<>]) (?P<type>[FLDX]):\s{1,4}'
                             r'(?P<filename>.+?)\s{1,}(?P<id>\d+)'
                             r'\s{1,}(?:[A-Za-z].*|$)',
                             re.S)

        # Parse this diff output so we can figure out what may have changed.
        for line in lines:
            m = file_re.match(line)

            if m:
                op = m.group('op')
                filename = m.group('filename')
                obj_type = m.group('type')
                obj_id = m.group('id')

                file_change = file_changes.setdefault(obj_id, {
                    'type': obj_type,
                })

                if op == '<':
                    file_change['old_filename'] = filename
                elif op == '>':
                    file_change['new_filename'] = filename

        FILE_CHANGE_TYPE_MAP = {
            'D': SOSObjectType.DIR,
            'F': SOSObjectType.FILE,
            'L': SOSObjectType.SYMLINK,
            'X': SOSObjectType.FILE,
        }

        logger.debug('Directory diff parse results: %r',
                     file_changes)

        deletes = []
        adds = []
        renamed_dirs = {}
        renamed_files = {}

        for file_change in file_changes.values():
            obj_type = FILE_CHANGE_TYPE_MAP.get(file_change['type'])
            old_filename = file_change.get('old_filename')
            new_filename = file_change.get('new_filename')

            if old_filename:
                old_filename = os.path.join(path, old_filename)

            if new_filename:
                new_filename = os.path.join(path, new_filename)

            if old_filename and new_filename:
                if obj_type == SOSObjectType.FILE:
                    renamed_files[new_filename] = old_filename
                elif obj_type == SOSObjectType.DIR:
                    new_dirname = '%s%s' % (new_filename, os.path.sep)
                    old_dirname = '%s%s' % (old_filename, os.path.sep)

                    renamed_dirs[new_dirname] = old_dirname
            elif old_filename:
                deletes.append({
                    'filename': old_filename,
                    'type': obj_type,
                })
            elif new_filename:
                adds.append({
                    'filename': new_filename,
                    'type': obj_type,
                })

        logger.debug('Directory diff results for "%s": adds=%r, deletes=%s, '
                     'renamed_dirs=%r, renamed_files=%r',
                     path, adds, deletes, renamed_dirs, renamed_files)

        tree_ops.setdefault('adds', []).extend(adds)
        tree_ops.setdefault('deletes', []).extend(deletes)
        tree_ops.setdefault('renamed_dirs', {}).update(renamed_dirs)
        tree_ops.setdefault('renamed_files', {}).update(renamed_files)

    def _get_rename_old_name(self, path, renamed_files, renamed_dirs):
        """Return the old name of a file from a rename operation.

        If the file is not explicitly renamed, this will go through the
        renamed directory entries and try to find a new directory name used
        as the prefix for this file. If found, a new path will be generated
        based on the old directory name and the remaning part of the file
        path.

        If an original name could not be found, this will just return the
        provided path.

        Args:
            path (unicode):
                The new path to a file in the workarea.

            renamed_files (dict):
                A pre-computed mapping of renamed files.

            renamed_dirs (dict):
                A pre-computed mapping of renamed directories.

        Return:
            unicode:
            The original name/path of a file, if found.
        """
        if path in renamed_files:
            return renamed_files[path]

        if renamed_dirs:
            for new_dir_name, old_dir_name in renamed_dirs.items():
                if path.startswith(new_dir_name):
                    return os.path.join(old_dir_name,
                                        path[len(new_dir_name):])

        return path

    def _iter_nobjstatus(self, attributes, selection=None):
        """Iterate through records and attributes on objects using nobjstatus.

        Args:
            attributes (list of unicode):
                An explicit list of attributes to fetch.

            selection (list of unicode, optional):
                An explicit selection to pass to :command:`soscmd nobjstatus`.

        Yields:
            dict:
            The record information for each file in the selection. This
            has the following keys:

            Keys:
                filename (unicode):
                    The filename shown in the record, without any revision
                    information.

                full_filename (unicode):
                    The filename shown in the record. This will include
                    revision information if present.

                object_type (int):
                    The numeric object type code.

                status (int):
                    The numeric status code.
        """
        # Fetch the given attributes from soscmd nobjstatus.
        soscmd_args = [
            'nobjstatus',
            '-ucl',
        ] + [
            '-ga%s' % _attr_name
            for _attr_name in attributes
        ]

        if selection:
            soscmd_args += selection

        lines = self.run_soscmd(*soscmd_args,
                                split_lines=True)

        # We now need to parse the nobjstatus results. This is in the form
        # of:
        #
        #     !nObjStatus! 1
        #     <Records>
        #
        # Each record is in the form of:
        #
        #     !Record!
        #     <Filename>[/#/<Revision>]
        #     <Status Code>
        #     <Object Type>
        #     <Attributes>
        #
        # Each attribute is in the form of:
        #
        #     <Attribute Name>
        #     <Value Length>
        #     <Value>
        #
        # All content is encoded as UTF-8.
        if lines[0].strip() != '!nObjStatus! 1':
            # We didn't get the results we expected. Don't yield anything.
            return

        filename_re = \
            re.compile(r'^(?P<filename>.+?)(?:/#/(?P<revision>\d+))?$')

        i = 1

        while i < len(lines):
            # Parse a file record.
            line = lines[i].strip()
            assert line == '!Record!'

            # Parse the information about the file.
            full_filename = lines[i + 1].strip()

            m = filename_re.match(full_filename)
            assert m

            record = {
                'filename': m.group('filename'),
                'full_filename': full_filename,
                'object_type': int(lines[i + 3]),
                'status': int(lines[i + 2]),
            }

            i += 4

            # Parse the attributes within the file record.
            while i < len(lines) and lines[i].strip() != '!Record!':
                attr_name = lines[i].strip()
                value_len = int(lines[i + 1])
                i += 2

                if value_len > 0:
                    attr_value = lines[i]

                    # Automatically convert any numeric values to integers.
                    try:
                        attr_value = int(attr_value)
                    except ValueError:
                        pass

                    i += 1
                else:
                    attr_value = None

                record[attr_name] = attr_value

            yield record

    @contextmanager
    def _stash_selection(self):
        """Stash the selection for the duration of an operation.

        SOS has a concept of "selections", which are a list of files that
        operations will be performed on. These are kept in sync between
        :command:`soscmd` calls and user-initiated list selections in the
        graphical UI.

        This context manager will back up the user's current selection before
        performing an operation, restoring it once the operation is complete.

        In the future, we may be able to perform selections independent of
        the user's selection, but will likely need to keep current logic for
        compatibility with older versions of SOS.

        Context:
            Operations can be performed that modify the selection.
        """
        filename = make_tempfile()

        try:
            # Store the current SOS selection to a file.
            selection = [
                _line
                for _line in self.run_soscmd('status', '-f%P',
                                             results_unicode=False,
                                             split_lines=True)
                if not _line.startswith(b'!!')
            ]

            logger.debug('Stashing %s item(s) from current SOS selection',
                         len(selection))

            with open(filename, 'wb') as fp:
                fp.write(b''.join(selection))

            # Execute the operation.
            try:
                yield
            finally:
                # Restore the old selection.
                logger.debug('Restoring SOS selection')
                self.run_soscmd('select', '-sall', '-sNr',
                                '-sfile%s' % filename)
        finally:
            try:
                os.unlink(filename)
            except Exception:
                # Ignore this.
                pass

    def _diff_file_hunks(
        self,
        wa_root: str,
        filename: str,
        orig_revision: Union[int, str],
        orig_content: Optional[bytes] = None,
    ) -> DiffFileResult:
        """Return diff hunks for a given file.

        This will diff a file against a prior revision (or explicit content),
        returning a diff result.

        Args:
            wa_root (str):
                The root of the workarea.

            filename (str):
                The path to the modified version of the file.

            revision (int or bytes):
                The original file revision.

            orig_content (bytes, optional):
                The original file contents.

        Returns:
            rbtools.diffs.tools.base.diff_file_result.DiffFileResult:
            The result of the diff operation.
        """
        diff_tool = self.get_diff_tool()
        assert diff_tool is not None

        # Get the contents of the original file.
        tmp_orig_filename = make_tempfile()
        abs_filename = os.path.normpath(os.path.join(wa_root, filename))

        try:
            if orig_content is not None:
                # We're comparing against an existing file, and we already
                # have the content. Skip exporting and just write it to the
                # temp location so we can diff it.
                with open(tmp_orig_filename, 'wb') as fp:
                    fp.write(orig_content)
            else:
                # For unmanaged (generally new) files, we want to diff against
                # an empty temp file. We'll export if it's anything but new.
                if orig_revision != SOSObjectRevision.UNMANAGED:
                    assert isinstance(orig_revision, int)

                    os.unlink(tmp_orig_filename)
                    self.run_soscmd('exportrev',
                                    '%s/#/%d' % (filename, orig_revision),
                                    '-out%s' % tmp_orig_filename)

            # Diff the new file against that.
            diff_result = diff_tool.run_diff_file(orig_path=tmp_orig_filename,
                                                  modified_path=abs_filename)
        finally:
            if os.path.exists(tmp_orig_filename):
                os.unlink(tmp_orig_filename)

        return diff_result

    def _normalize_sos_path(self, sos_path):
        """Normalize an SOS path to a local path.

        This will simply strip off any leading ``./`` prefix.

        THis will leave the file separators alone. It does not convert
        between native paths for platforms.

        Args:
            sos_path (unicode):
                The path in ``./sos/path`` format. This may be ``None``, in
                which case ``None`` will be returned.

        Returns:
            unicode:
            The resulting SOS path.
        """
        if sos_path and sos_path.startswith('./'):
            sos_path = sos_path[2:]

        return sos_path

    def _make_sos_path(self, path, wa_root):
        """Build an SOS path relative to the workarea root.

        The resulting path will be in :file:`./dir/file` format.

        If the path is outside of the workarea root, this will assert.

        Args:
            path (unicode):
                The absolute or relative path to the file or directory.

            wa_root (unicode):
                The workarea root.

        Returns:
            unicode:
            The resulting SOS path.
        """
        if os.path.isabs(path):
            path = os.path.relpath(path, wa_root)

        return '/'.join(['.'] + os.path.normpath(path).split(os.path.sep))

    def _get_wa_root(self):
        """Return the top of the current workarea.

        This requires the user's current directory to be within the workarea.

        Returns:
            unicode:
            The current workarea, if found, or ``None``.
        """
        return self._query_sos_info('wa_root')

    def _get_workarea_id(self):
        """Return the ID of the current workarea.

        This value will be cached.

        Returns:
            unicode:
            The current workarea ID.
        """
        try:
            return self._cache['waid']
        except KeyError:
            project_name = self._query_sos_info('project')
            wa_root = self._get_wa_root()

            db_path = os.path.join(wa_root, '.SOS', '.workareadb',
                                   project_name, 'meta.db')

            if not os.path.exists(db_path):
                raise SCMError('Unable to determine workarea ID for "%s"'
                               % wa_root)

            db = sqlite3.connect(db_path)

            try:
                # This should only return a single result for the workarea.
                #
                # If it turns out that a workarea could ever have multiple
                # IDs, this will do the wrong thing.
                cursor = db.cursor()
                cursor.execute('SELECT waid FROM header')
                row = cursor.fetchone()
                workarea_id = row[0]
            finally:
                db.close()

            self._cache['waid'] = workarea_id

            return workarea_id

    def _has_changelist_support(self):
        """Return whether changelist support is available.

        This value will be cached.

        Returns:
            bool:
            ``True`` if changelist support is available. ``False`` if it is
            not.
        """
        try:
            supports_changelists = self._cache['supports_changelists']
        except KeyError:
            if self._get_sos_version() >= (7, 20):
                supports_changelists = True
            else:
                # The user may be running an old pre-7.20 beta that contains
                # soscmd describe.
                try:
                    self.run_soscmd('describe')
                    supports_changelists = True
                except Exception:
                    supports_changelists = False

            self._cache['supports_changelists'] = supports_changelists

        return supports_changelists

    def _get_sos_version(self):
        """Return the version of SOS.

        This value will be cached.

        Returns:
            tuple:
            The version information as a tuple.
        """
        try:
            version = self._cache['sos_version']
        except KeyError:
            version_str = self.run_soscmd('version', cwd=os.getcwd())

            m = re.match(r'^soscmd version (?P<major_version>\d+)\.'
                         r'(?P<minor_version>\d+).*',
                         version_str)

            if m:
                version = (int(m.group('major_version')),
                           int(m.group('minor_version')))
            else:
                logger.debug('Unexpected result from "soscmd version": "%s"; '
                             'skipping SOS',
                             version_str)
                version = None

            self._cache['sos_version'] = version

        return version

    def _query_sos_info(self, info_type):
        """Return information from SOS.

        This wraps :command:`soscmd query` to fetch information about the
        SOS server or the workarea.

        Queried information is stored in a local memory cache, for future
        queries during the process.

        Args:
            info_type (unicode):
                A query type to pass to :command:`soscmd query`.

        Returns:
            unicode:
            The queried value.
        """
        try:
            return self._cache[info_type]
        except KeyError:
            rc, value = self.run_soscmd('query', info_type,
                                        cwd=os.getcwd(),
                                        return_error_code=True)

            if rc == 0:
                value = value.strip()
            else:
                value = None

            self._cache[info_type] = value

            return value
