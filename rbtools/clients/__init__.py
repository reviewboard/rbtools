"""SCM Client definitions."""

from __future__ import print_function, unicode_literals

import logging
import os
import re
import sys

import pkg_resources
import six

from rbtools.clients.errors import SCMError
from rbtools.utils.process import execute


# The clients are lazy loaded via load_scmclients()
SCMCLIENTS = None


class PatchResult(object):
    """The result of a patch operation.

    This stores state on whether the patch could be applied (fully or
    partially), whether there are conflicts that can be resolved (as in
    conflict markers, not reject files), which files conflicted, and the
    patch output.
    """

    def __init__(self, applied, has_conflicts=False,
                 conflicting_files=[], patch_output=None):
        """Initialize the object.

        Args:
            applied (bool):
                Whether the patch was applied.

            has_conflicts (bool, optional):
                Whether the applied patch included conflicts.

            conflicting_files (list of unicode, optional):
                A list of the filenames containing conflicts.

            patch_output (unicode, optional):
                The output of the patch command.
        """
        self.applied = applied
        self.has_conflicts = has_conflicts
        self.conflicting_files = conflicting_files
        self.patch_output = patch_output


class SCMClient(object):
    """A base representation of an SCM tool.

    These are used for fetching repository information and generating diffs.
    """

    name = None

    supports_diff_extra_args = False
    supports_diff_exclude_patterns = False
    supports_no_renames = False
    supports_patch_revert = False

    can_amend_commit = False
    can_merge = False
    can_push_upstream = False
    can_delete_branch = False
    can_branch = False
    can_bookmark = False

    def __init__(self, config=None, options=None):
        """Initialize the client.

        Args:
            config (dict, optional):
                The loaded user config.

            options (argparse.Namespace, optional):
                The parsed command line arguments.
        """
        self.config = config or {}
        self.options = options
        self.capabilities = None

    def get_repository_info(self):
        """Return repository information for the current working tree.

        This is expected to be overridden by subclasses.

        Returns:
            rbtools.clients.RepositoryInfo:
            The repository info structure.
        """
        return None

    def check_options(self):
        """Verify the command line options.

        This is expected to be overridden by subclasses, if they need to do
        specific validation of the command line.

        Raises:
            rbtools.clients.errors.OptionsCheckError:
                The supplied command line options were incorrect. In
                particular, if a file has history scheduled with the commit,
                the user needs to explicitly choose what behavior they want.
        """
        pass

    def get_changenum(self, revisions):
        """Return the change number for the given revisions.

        This is only used when the client is supposed to send a change number
        to the server (such as with Perforce).

        Args:
            revisions (dict):
                A revisions dictionary as returned by ``parse_revision_spec``.

        Returns:
            unicode:
            The change number to send to the Review Board server.
        """
        return None

    def scan_for_server(self, repository_info):
        """Find the server path.

        This will search for the server name in the .reviewboardrc config
        files. These are loaded with the current directory first, and searching
        through each parent directory, and finally $HOME/.reviewboardrc last.

        Args:
            repository_info (rbtools.clients.RepositoryInfo):
                The repository information structure.

        Returns:
            unicode:
            The Review Board server URL, if available.
        """
        return self._get_server_from_config(self.config, repository_info)

    def parse_revision_spec(self, revisions=[]):
        """Parse the given revision spec.

        The 'revisions' argument is a list of revisions as specified by the
        user. Items in the list do not necessarily represent a single revision,
        since the user can use SCM-native syntaxes such as "r1..r2" or "r1:r2".
        SCMTool-specific overrides of this method are expected to deal with
        such syntaxes.

        Args:
            revisions (list of unicode, optional):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use SCM-native syntaxes such as ``r1..r2`` or ``r1:r2``.
                SCMTool-specific overrides of this method are expected to deal
                with such syntaxes.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.

        Returns:
            dict:
            A dictionary with the following keys:

            ``base`` (:py:class:`unicode`):
                A revision to use as the base of the resulting diff.

            ``tip`` (:py:class:`unicode`):
                A revision to use as the tip of the resulting diff.

            ``parent_base`` (:py:class:`unicode`, optional):
                The revision to use as the base of a parent diff.

            ``commit_id`` (:py:class:`unicode`, optional):
                The ID of the single commit being posted, if not using a
                range.

            Additional keys may be included by subclasses for their own
            internal use.

            These will be used to generate the diffs to upload to Review Board
            (or print). The diff for review will include the changes in (base,
            tip], and the parent diff (if necessary) will include (parent,
            base].

            If a single revision is passed in, this will return the parent of
            that revision for "base" and the passed-in revision for "tip".

            If zero revisions are passed in, this will return revisions
            relevant for the "current change". The exact definition of what
            "current" means is specific to each SCMTool backend, and documented
            in the implementation classes.
        """
        return {
            'base': None,
            'tip': None,
        }

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             no_renames=False, extra_args=[]):
        """Perform a diff using the given revisions.

        This is expected to be overridden by subclasses.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            include_files (list of unicode, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of unicode, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

            extra_args (list, unused):
                Additional arguments to be passed to the diff generation.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.

            ``parent_diff`` (:py:class:`bytes`, optional):
                The contents of the parent diff, if available.

            ``commit_id`` (:py:class:`unicode`, optional):
                The commit ID to include when posting, if available.

            ``base_commit_id` (:py:class:`unicode`, optional):
                The ID of the commit that the change is based on, if available.
                This is necessary for some hosting services that don't provide
                individual file access.
        """
        return {
            'diff': None,
            'parent_diff': None,
            'commit_id': None,
            'base_commit_id': None,
        }

    def _get_server_from_config(self, config, repository_info):
        """Return the Review Board server URL in the config.

        Args:
            config (dict):
                The loaded user config.

            repository_info (rbtools.clients.RepositoryInfo):
                The repository info structure.

        Returns:
            unicode:
            The server URL, if available.
        """
        if 'REVIEWBOARD_URL' in config:
            return config['REVIEWBOARD_URL']
        elif 'TREES' in config:
            trees = config['TREES']
            if not isinstance(trees, dict):
                raise ValueError('"TREES" in config file is not a dict!')

            # If repository_info is a list, check if any one entry is in trees.
            path = None

            if isinstance(repository_info.path, list):
                for path in repository_info.path:
                    if path in trees:
                        break
                else:
                    path = None
            elif repository_info.path in trees:
                path = repository_info.path

            if path and 'REVIEWBOARD_URL' in trees[path]:
                return trees[path]['REVIEWBOARD_URL']

        return None

    def _get_p_number(self, base_path, base_dir):
        """Return the appropriate value for the -p argument to patch.

        This function returns an integer. If the integer is -1, then the -p
        option should not be provided to patch. Otherwise, the return value is
        the argument to :command:`patch -p`.

        Args:
            base_path (unicode):
                The relative path beetween the repository root and the
                directory that the diff file was generated in.

            base_dir (unicode):
                The current relative path between the repository root and the
                user's working directory.

        Returns:
            int:
            The prefix number to pass into the :command:`patch` command.
        """
        if base_path and base_dir.startswith(base_path):
            return base_path.count('/') + 1
        else:
            return -1

    def _strip_p_num_slashes(self, files, p_num):
        """Strip the smallest prefix containing p_num slashes from filenames.

        To match the behavior of the :command:`patch -pX` option, adjacent
        slashes are counted as a single slash.

        Args:
            files (list of unicode):
                The filenames to process.

            p_num (int):
                The number of prefixes to strip.

        Returns:
            list of unicode:
            The processed list of filenames.
        """
        if p_num > 0:
            regex = re.compile(r'[^/]*/+')
            return [regex.sub('', f, p_num) for f in files]
        else:
            return files

    def has_pending_changes(self):
        """Return whether there are changes waiting to be committed.

        Derived classes should override this method if they wish to support
        checking for pending changes.

        Returns:
            bool:
            ``True`` if the working directory has been modified or if changes
            have been staged in the index.
        """
        raise NotImplementedError

    def apply_patch(self, patch_file, base_path, base_dir, p=None,
                    revert=False):
        """Apply the patch and return a PatchResult indicating its success.

        Args:
            patch_file (unicode):
                The name of the patch file to apply.

            base_path (unicode):
                The base path that the diff was generated in.

            base_dir (unicode):
                The path of the current working directory relative to the root
                of the repository.

            p (unicode, optional):
                The prefix level of the diff.

            revert (bool, optional):
                Whether the patch should be reverted rather than applied.

        Returns:
            rbtools.clients.PatchResult:
            The result of the patch operation.
        """
        # Figure out the -p argument for patch. We override the calculated
        # value if it is supplied via a commandline option.
        p_num = p or self._get_p_number(base_path, base_dir)

        cmd = ['patch']

        if revert:
            cmd.append('-R')

        try:
            p_num = int(p_num)
        except ValueError:
            p_num = 0
            logging.warn('Invalid -p value: %s; assuming zero.', p_num)

        if p_num is not None:
            if p_num >= 0:
                cmd.append('-p%d' % p_num)
            else:
                logging.warn('Unsupported -p value: %d; assuming zero.', p_num)

        cmd.extend(['-i', six.text_type(patch_file)])

        # Ignore return code 2 in case the patch file consists of only empty
        # files, which 'patch' can't handle. Other 'patch' errors also give
        # return code 2, so we must check the command output.
        rc, patch_output = execute(cmd, extra_ignore_errors=(2,),
                                   return_error_code=True)
        only_garbage_in_patch = ('patch: **** Only garbage was found in the '
                                 'patch input.\n')

        if (patch_output and patch_output.startswith('patch: **** ') and
            patch_output != only_garbage_in_patch):
            raise SCMError('Failed to execute command: %s\n%s'
                           % (cmd, patch_output))

        # Check the patch for any added/deleted empty files to handle.
        if self.supports_empty_files():
            try:
                with open(patch_file, 'rb') as f:
                    patch = f.read()
            except IOError as e:
                logging.error('Unable to read file %s: %s', patch_file, e)
                return

            patched_empty_files = self.apply_patch_for_empty_files(
                patch, p_num, revert=revert)

            # If there are no empty files in a "garbage-only" patch, the patch
            # is probably malformed.
            if (patch_output == only_garbage_in_patch and
                not patched_empty_files):
                raise SCMError('Failed to execute command: %s\n%s'
                               % (cmd, patch_output))

        # TODO: Should this take into account apply_patch_for_empty_files ?
        #       The return value of that function is False both when it fails
        #       and when there are no empty files.
        return PatchResult(applied=(rc == 0), patch_output=patch_output)

    def create_commit(self, message, author, run_editor,
                      files=[], all_files=False):
        """Create a commit based on the provided message and author.

        Derived classes should override this method if they wish to support
        committing changes to their repositories.

        Args:
            message (unicode):
                The commit message to use.

            author (object):
                The author of the commit. This is expected to have ``fullname``
                and ``email`` attributes.

            run_editor (bool):
                Whether to run the user's editor on the commmit message before
                committing.

            files (list of unicode, optional):
                The list of filenames to commit.

            all_files (bool, optional):
                Whether to commit all changed files, ignoring the ``files``
                argument.
        """
        raise NotImplementedError

    def get_commit_message(self, revisions):
        """Return the commit message from the commits in the given revisions.

        This pulls out the first line from the commit messages of the given
        revisions. That is then used as the summary.

        Args:
            revisions (dict):
                A dictionary as returned by :py:meth:`parse_revision_spec`.

        Returns:
            dict:
            A dictionary containing ``summary`` and ``description`` keys,
            matching the first line of the commit message and the remainder,
            respectively.
        """
        commit_message = self.get_raw_commit_message(revisions)
        lines = commit_message.splitlines()

        if not lines:
            return None

        result = {
            'summary': lines[0],
        }

        # Try to pull the body of the commit out of the full commit
        # description, so that we can skip the summary.
        if len(lines) >= 3 and lines[0] and not lines[1]:
            result['description'] = '\n'.join(lines[2:]).strip()
        else:
            result['description'] = commit_message

        return result

    def delete_branch(self, branch_name, merged_only=True):
        """Delete the specified branch.

        Args:
            branch_name (unicode):
                The name of the branch to delete.

            merged_only (bool, optional):
                Whether to limit branch deletion to only those branches which
                have been merged into the current HEAD.
        """
        raise NotImplementedError

    def merge(self, target, destination, message, author, squash=False,
              run_editor=False):
        """Merge the target branch with destination branch.

        Args:
            target (unicode):
                The name of the branch to merge.

            destination (unicode):
                The name of the branch to merge into.

            message (unicode):
                The commit message to use.

            author (object):
                The author of the commit. This is expected to have ``fullname``
                and ``email`` attributes.

            squash (bool, optional):
                Whether to squash the commits or do a plain merge.

            run_editor (bool, optional):
                Whether to run the user's editor on the commmit message before
                committing.

        Raises:
            rbtools.clients.errors.MergeError:
                An error occurred while merging the branch.
        """
        raise NotImplementedError

    def push_upstream(self, remote_branch):
        """Push the current branch to upstream.

        Args:
            remote_branch (unicode):
                The name of the branch to push to.

        Raises:
            rbtools.client.errors.PushError:
                The branch was unable to be pushed.
        """
        raise NotImplementedError

    def get_raw_commit_message(self, revisions):
        """Extract the commit messages on the commits in the given revisions.

        Derived classes should override this method in order to allow callers
        to fetch commit messages. This is needed for description guessing.

        If a derived class is unable to fetch the description, ``None`` should
        be returned.

        Callers that need to differentiate the summary from the description
        should instead use get_commit_message().

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

        Returns:
            unicode:
            The commit messages of all commits between (base, tip].
        """
        raise NotImplementedError

    def get_current_branch(self):
        """Return the repository branch name of the current directory.

        Derived classes should override this method if they are able to
        determine the current branch of the working directory.

        Returns:
            unicode:
            A string with the name of the current branch. If the branch is
            unable to be determined, returns ``None``.
        """
        raise NotImplementedError

    def supports_empty_files(self):
        """Return whether the server supports added/deleted empty files.

        Returns:
            bool:
            ``True`` if the Review Board server supports added or deleted empty
            files.
        """
        return False

    def apply_patch_for_empty_files(self, patch, p_num, revert=False):
        """Return whether any empty files in the patch are applied.

        Args:
            patch (bytes):
                The contents of the patch.

            p_num (unicode):
                The prefix level of the diff.

            revert (bool, optional):
                Whether the patch should be reverted rather than applied.

        Returns:
            ``True`` if there are empty files in the patch. ``False`` if there
            were no empty files, or if an error occurred while applying the
            patch.
        """
        raise NotImplementedError

    def amend_commit_description(self, message, revisions=None):
        """Update a commit message to the given string.

        Args:
            message (unicode):
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
        raise NotImplementedError


class RepositoryInfo(object):
    """A representation of a source code repository."""

    def __init__(self, path=None, base_path=None, local_path=None,
                 supports_changesets=False, supports_parent_diffs=False):
        """Initialize the object.

        Args:
            path (unicode, optional):
                The path of the repository.

            base_path (unicode, optional):
                The relative path between the current working directory and the
                repository root.

            local_path (unicode, optional):
                The local filesystem path for the repository. This can
                sometimes be the same as ``path``, but may not be (since that
                can contain a remote repository path).

            supports_changesets (bool, optional):
                Whether the repository type supports changesets that store
                their data server-side.

            supports_parent_diffs (bool, optional):
                Whether the repository type supports posting changes with
                parent diffs.
        """
        self.path = path
        self.base_path = base_path
        self.local_path = local_path
        self.supports_changesets = supports_changesets
        self.supports_parent_diffs = supports_parent_diffs
        logging.debug('Repository info: %s', self)

    def __str__(self):
        """Return a string representation of the repository info.

        Returns:
            unicode:
            A loggable representation.
        """
        return 'Path: %s, Base path: %s, Supports changesets: %s' % \
            (self.path, self.base_path, self.supports_changesets)

    def set_base_path(self, base_path):
        """Set the base path of the repository info.

        Args:
            base_path (unicode):
                The relative path between the current working directory and the
                repository root.
        """
        if not base_path.startswith('/'):
            base_path = '/' + base_path

        logging.debug('changing repository info base_path from %s to %s',
                      self.base_path, base_path)
        self.base_path = base_path

    def find_server_repository_info(self, server):
        """Try to find the repository from the list of repositories on the server.

        For Subversion, this could be a repository with a different URL. For
        all other clients, this is a noop.

        Args:
            server (rbtools.api.resource.RootResource):
                The root resource for the Review Board server.

        Returns:
            RepositoryInfo:
            The server-side information for this repository.
        """
        return self


def load_scmclients(config, options):
    """Load the available SCM clients.

    Args:
        config (dict):
            The loaded user config.

        options (argparse.Namespace):
            The parsed command line arguments.
    """
    global SCMCLIENTS

    SCMCLIENTS = {}

    for ep in pkg_resources.iter_entry_points(group='rbtools_scm_clients'):
        try:
            client = ep.load()(config=config, options=options)
            client.entrypoint_name = ep.name
            SCMCLIENTS[ep.name] = client
        except Exception:
            logging.exception('Could not load SCM Client "%s"', ep.name)


def scan_usable_client(config, options, client_name=None):
    """Scan for a usable SCMClient.

    Args:
        config (dict):
            The loaded user config.

        options (argparse.Namespace):
            The parsed command line arguments.

        client_name (unicode, optional):
            A specific client name, which can come from the configuration. This
            can be used to disambiguate if there are nested repositories, or to
            speed up detection.

    Returns:
        tuple:
        A 2-tuple, containing the repository info structure and the tool
        instance.
    """
    from rbtools.clients.perforce import PerforceClient

    repository_info = None
    tool = None

    # TODO: We should only load all of the scm clients if the client_name
    # isn't provided.
    if SCMCLIENTS is None:
        load_scmclients(config, options)

    if client_name:
        if client_name not in SCMCLIENTS:
            logging.error('The provided repository type "%s" is invalid.',
                          client_name)
            sys.exit(1)
        else:
            scmclients = {
                client_name: SCMCLIENTS[client_name]
            }
    else:
        scmclients = SCMCLIENTS

    candidate_repos = []

    for name, tool in six.iteritems(scmclients):
        logging.debug('Checking for a %s repository...', tool.name)
        repository_info = tool.get_repository_info()

        if repository_info:
            candidate_repos.append((repository_info, tool))

    if candidate_repos:
        if len(candidate_repos) == 1:
            repository_info, tool = candidate_repos[0]
        else:
            logging.debug('Finding deepest repository of multiple matching '
                          'repository types.')

            deepest_repo_len = 0
            deepest_repo_info = None
            deepest_repo_tool = None

            for repo, tool in candidate_repos:
                if (repo.local_path and
                    len(os.path.normpath(repo.local_path)) > deepest_repo_len):
                    deepest_repo_len = len(repo.local_path)
                    deepest_repo_info = repo
                    deepest_repo_tool = tool

            if deepest_repo_info:
                repository_info = deepest_repo_info
                tool = deepest_repo_tool

                logging.warn('Multiple matching repositories were found. '
                             'Using %s repository at %s.',
                             tool.name, repository_info.local_path)
                logging.warn('Define REPOSITORY_TYPE in .reviewboardrc if '
                             'you wish to use a different repository.')
            else:
                # If finding the deepest repository fails (for example, when
                # posting against a remote SVN repository there will be no
                # local path), just default to the first repository found
                repository_info, tool = candidate_repos[0]
    else:
        if client_name:
            logging.error('The provided repository type was not detected '
                          'in the current directory.')
        elif getattr(options, 'repository_url', None):
            logging.error('No supported repository could be accessed at '
                          'the supplied url.')
        else:
            logging.error('The current directory does not contain a checkout '
                          'from a supported source code repository.')

        sys.exit(1)

    # Verify that options specific to an SCM Client have not been mis-used.
    if (getattr(options, 'change_only', False) and
        not repository_info.supports_changesets):
        sys.stderr.write('The --change-only option is not valid for the '
                         'current SCM client.\n')
        sys.exit(1)

    if (getattr(options, 'parent_branch', None) and
        not repository_info.supports_parent_diffs):
        sys.stderr.write('The --parent option is not valid for the '
                         'current SCM client.\n')
        sys.exit(1)

    if (not isinstance(tool, PerforceClient) and
        (getattr(options, 'p4_client', None) or
         getattr(options, 'p4_port', None))):
        sys.stderr.write('The --p4-client and --p4-port options are not valid '
                         'for the current SCM client.\n')
        sys.exit(1)

    return (repository_info, tool)


def print_clients(config, options):
    """Print the supported detected SCM clients.

    Each SCM client, including those provided by third party packages,
    will be printed. Additionally, SCM clients which are detected in
    the current directory will be highlighted.

    Args:
        config (dict):
            The loaded user config.

        options (argparse.Namespace):
            The parsed command line options.
    """
    print('The following repository types are supported by this installation')
    print('of RBTools. Each "<type>" may be used as a value for the')
    print('"--repository-type=<type>" command line argument. Repository types')
    print('which are detected in the current directory are marked with a "*"')
    print('[*] "<type>": <Name>')

    if SCMCLIENTS is None:
        load_scmclients(config, options)

    for name, tool in six.iteritems(SCMCLIENTS):
        repository_info = tool.get_repository_info()

        if repository_info:
            print(' * "%s": %s' % (name, tool.name))
        else:
            print('   "%s": %s' % (name, tool.name))
