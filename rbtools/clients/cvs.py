"""A client for CVS."""

import logging
import os
import re
import socket
from typing import List, Optional

from rbtools.clients.base.repository import RepositoryInfo
from rbtools.clients.base.scmclient import (BaseSCMClient,
                                            SCMClientDiffResult,
                                            SCMClientRevisionSpec)
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    TooManyRevisionsError)
from rbtools.deprecation import (RemovedInRBTools50Warning,
                                 deprecate_non_keyword_only_args)
from rbtools.utils.checks import check_install
from rbtools.utils.diffs import filter_diff, normalize_patterns
from rbtools.utils.process import run_process


class CVSClient(BaseSCMClient):
    """A client for CVS.

    This is a wrapper around the cvs executable that fetches repository
    information and generates compatible diffs.
    """

    scmclient_id = 'cvs'
    name = 'CVS'
    server_tool_names = 'CVS'
    supports_diff_exclude_patterns = True
    supports_patch_revert = True

    INDEX_FILE_RE = re.compile(b'^Index: (.+)\n$')

    REVISION_WORKING_COPY = '--rbtools-working-copy'

    def check_dependencies(self) -> None:
        """Check whether all dependencies for the client are available.

        This will check for :command:`cvs` in the path.

        Version Added:
            4.0

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                :command:`cvs` could not be found.
        """
        if not check_install(['cvs']):
            raise SCMClientDependencyError(missing_exes=['cvs'])

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        # NOTE: This can be removed once check_dependencies() is mandatory.
        if not self.has_dependencies(expect_checked=True):
            logging.debug('Unable to execute "cvs": skipping CVS')
            return None

        cvsroot_path = os.path.join('CVS', 'Root')

        if not os.path.exists(cvsroot_path):
            return None

        with open(cvsroot_path, 'r') as fp:
            repository_path = fp.read().strip()

        i = repository_path.find('@')

        if i != -1:
            repository_path = repository_path[i + 1:]

        i = repository_path.rfind(':')

        if i != -1:
            host = repository_path[:i]

            try:
                canon = socket.getfqdn(host)
                repository_path = repository_path.replace('%s:' % host,
                                                          '%s:' % canon)
            except socket.error as msg:
                logging.error('failed to get fqdn for %s, msg=%s',
                              host, msg)

        return repository_path

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        repository_path = self.get_local_path()

        if not repository_path:
            return None

        return RepositoryInfo(path=repository_path,
                              local_path=repository_path)

    def parse_revision_spec(
        self,
        revisions: List[str] = [],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The diff for review will include the changes in (base,
        tip].

        If a single revision is passed in, this will raise an exception,
        because CVS doesn't have a repository-wide concept of "revision",
        so selecting an individual "revision" doesn't make sense.

        With two revisions, this will treat those revisions as tags and do
        a diff between those tags.

        If zero revisions are passed in, this will return revisions
        relevant for the current change.

        The CVS SCMClient never fills in the ``parent_base`` key. Users who
        are using other patch-stack tools who want to use parent diffs with
        CVS will have to generate their diffs by hand.

        Because :command:`cvs diff` uses multiple arguments to define
        multiple tags, there's no single-argument/multiple-revision syntax
        available.

        Args:
            revisions (list of str, optional):
                A list of revisions as specified by the user.

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates ``base`` and ``tip``.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.
        """
        n_revs = len(revisions)

        if n_revs == 0:
            return {
                'base': 'BASE',
                'tip': self.REVISION_WORKING_COPY,
            }
        elif n_revs == 1:
            raise InvalidRevisionSpecError(
                'CVS does not support passing in a single revision.')
        elif n_revs == 2:
            return {
                'base': revisions[0],
                'tip': revisions[1],
            }
        else:
            raise TooManyRevisionsError

    @deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
    def diff(
        self,
        revisions: SCMClientRevisionSpec,
        *,
        include_files: List[str] = [],
        exclude_patterns: List[str] = [],
        **kwargs
    ) -> SCMClientDiffResult:
        """Perform a diff using the given revisions.

        If no revisions are specified, this will return the diff for the
        modified files in the working directory. If it's not empty and contains
        two revisions, this will do a diff between those revisions.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            include_files (list of str, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of str, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary containing keys documented in
            :py:class:`SCMClientDiffResult`.

            This will only populate the ``diff`` key.
        """
        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        # CVS paths are always relative to the current working directory.
        cwd = os.getcwd()
        exclude_patterns = normalize_patterns(
            patterns=exclude_patterns,
            base_dir=cwd,
            cwd=cwd)

        # Bulid the command to diff the files.
        diff_cmd = ['cvs', 'diff', '-uN']

        if not (base == 'BASE' and
                tip == self.REVISION_WORKING_COPY):
            diff_cmd += ['-r', base, '-r', tip]

        if include_files:
            diff_cmd += include_files

        # Generate the diff.
        #
        # Note that `cvs diff` returns "1" if differences were found, so we
        # have to ignore that as an error.
        diff = iter(
            run_process(diff_cmd + include_files,
                        ignore_errors=(1,),
                        log_debug_output_on_error=False)
            .stdout_bytes
        )

        if exclude_patterns:
            # CVS diffs are relative to the current working directory, so the
            # base_dir parameter to filter_diff is unnecessary.
            diff = filter_diff(diff, self.INDEX_FILE_RE,
                               exclude_patterns=exclude_patterns,
                               base_dir=cwd)

        return {
            'diff': b''.join(diff),
        }
