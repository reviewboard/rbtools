from __future__ import print_function, unicode_literals

import logging
import pkg_resources
import re
import six
import sys

from rbtools.utils.process import die, execute


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
    supports_patch_revert = False

    can_amend_commit = False
    can_merge = False
    can_push_upstream = False
    can_delete_branch = False

    def __init__(self, config=None, options=None):
        self.config = config or {}
        self.options = options
        self.capabilities = None

    def get_repository_info(self):
        return None

    def check_options(self):
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
        """
        return self._get_server_from_config(self.config, repository_info)

    def parse_revision_spec(self, revisions=[]):
        """Parses the given revision spec.

        The 'revisions' argument is a list of revisions as specified by the
        user. Items in the list do not necessarily represent a single revision,
        since the user can use SCM-native syntaxes such as "r1..r2" or "r1:r2".
        SCMTool-specific overrides of this method are expected to deal with
        such syntaxes.

        This will return a dictionary with the following keys:
            'base':        A revision to use as the base of the resulting diff.
            'tip':         A revision to use as the tip of the resulting diff.
            'parent_base': (optional) The revision to use as the base of a
                           parent diff.

        These will be used to generate the diffs to upload to Review Board (or
        print). The diff for review will include the changes in (base, tip],
        and the parent diff (if necessary) will include (parent, base].

        If a single revision is passed in, this will return the parent of that
        revision for 'base' and the passed-in revision for 'tip'.

        If zero revisions are passed in, this will return revisions relevant
        for the "current change". The exact definition of what "current" means
        is specific to each SCMTool backend, and documented in the
        implementation classes.
        """
        return {
            'base': None,
            'tip': None,
        }

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             extra_args=[]):
        """
        Returns the generated diff and optional parent diff for this
        repository.

        The return value must be a dictionary, and must have, at a minimum,
        a 'diff' field. A 'parent_diff' can also be provided.

        It may also return 'base_commit_id', representing the revision/ID of
        the commit that the diff or parent diff is based on. This exists
        because in some diff formats, this may different from what's provided
        in the diff.
        """
        return {
            'diff': None,
            'parent_diff': None,
            'base_commit_id': None,
        }

    def _get_server_from_config(self, config, repository_info):
        if 'REVIEWBOARD_URL' in config:
            return config['REVIEWBOARD_URL']
        elif 'TREES' in config:
            trees = config['TREES']
            if not isinstance(trees, dict):
                die('Warning: "TREES" in config file is not a dict!')

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
        the argument to patch -p.
        """
        if base_path and base_dir.startswith(base_path):
            return base_path.count('/') + 1
        else:
            return -1

    def _strip_p_num_slashes(self, files, p_num):
        """Strips the smallest prefix containing p_num slashes from file names.

        To match the behavior of the patch -pX option, adjacent slashes are
        counted as a single slash.
        """
        if p_num > 0:
            regex = re.compile(r'[^/]*/+')
            return [regex.sub('', f, p_num) for f in files]
        else:
            return files

    def _execute(self, cmd, *args, **kwargs):
        """
        Prints the results of the executed command and returns
        the data result from execute.
        """
        return execute(cmd, ignore_errors=True, *args, **kwargs)

    def has_pending_changes(self):
        """Checks if there are changes waiting to be committed.

        Derived classes should override this method if they wish to support
        checking for pending changes.
        """
        raise NotImplementedError

    def apply_patch(self, patch_file, base_path, base_dir, p=None,
                    revert=False):
        """Apply the patch and return a PatchResult indicating its success."""
        # Figure out the -p argument for patch. We override the calculated
        # value if it is supplied via a commandline option.
        p_num = p or self._get_p_number(base_path, base_dir)

        cmd = ['patch']

        if revert:
            cmd.append('-R')

        if p_num >= 0:
            cmd.append('-p%d' % p_num)

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
            die('Failed to execute command: %s\n%s' % (cmd, patch_output))

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
                die('Failed to execute command: %s\n%s' % (cmd, patch_output))

        # TODO: Should this take into account apply_patch_for_empty_files ?
        #       The return value of that function is False both when it fails
        #       and when there are no empty files.
        return PatchResult(applied=(rc == 0), patch_output=patch_output)

    def create_commit(self, message, author, run_editor,
                      files=[], all_files=False):
        """Creates a commit based on the provided message and author.

        Derived classes should override this method if they wish to support
        committing changes to their repositories.
        """
        raise NotImplementedError

    def get_commit_message(self, revisions):
        """Returns the commit message from the commits in the given revisions.

        This pulls out the first line from the commit messages of the
        given revisions. That is then used as the summary.
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
        """Deletes the specified branch.

        If merged_only is False, then the branch will be deleted even if not
        yet merged into an upstream branch.
        """
        raise NotImplementedError

    def merge(self, target, destination, message, author, squash=False,
              run_editor=False):
        """Merges the target branch with destination branch."""
        raise NotImplementedError

    def push_upstream(self, remote_branch):
        """Pushes the current branch to upstream."""
        raise NotImplementedError

    def get_raw_commit_message(self, revisions):
        """Extracts the commit messages on the commits in the given revisions.

        Derived classes should override this method in order to allow callers
        to fetch commit messages. This is needed for description guessing.

        If a derived class is unable to fetch the description, ``None`` should
        be returned.

        Callers that need to differentiate the summary from the description
        should instead use get_commit_message().
        """
        raise NotImplementedError

    def get_current_branch(self):
        """Returns the repository branch name of the current directory.

        Derived classes should override this method if they are able to
        determine the current branch of the working directory.

        If a derived class is unable to unable to determine the branch,
        ``None`` should be returned.
        """
        raise NotImplementedError

    def supports_empty_files(self):
        """Check if the RB server supports added/deleted empty files.

        This method returns False. To change this behaviour, override it in a
        subclass.
        """
        return False

    def apply_patch_for_empty_files(self, patch, p_num, revert=False):
        """Return True if any empty files in the patch are applied.

        If there are no empty files in the patch or if an error occurs while
        applying the patch, we return False.
        """
        raise NotImplementedError

    def amend_commit_description(self, message, revisions=None):
        """Update a commit message to the given string.

        The optional revisions argument exists to provide compatibility with
        SCMs that allow modification of multiple changesets at any given time.
        It takes a parsed revision spec, and will amend the change referenced
        by the tip revision therein.
        """
        raise NotImplementedError


class RepositoryInfo(object):
    """
    A representation of a source code repository.
    """
    def __init__(self, path=None, base_path=None, supports_changesets=False,
                 supports_parent_diffs=False):
        self.path = path
        self.base_path = base_path
        self.supports_changesets = supports_changesets
        self.supports_parent_diffs = supports_parent_diffs
        logging.debug('repository info: %s' % self)

    def __str__(self):
        return 'Path: %s, Base path: %s, Supports changesets: %s' % \
            (self.path, self.base_path, self.supports_changesets)

    def set_base_path(self, base_path):
        if not base_path.startswith('/'):
            base_path = '/' + base_path
        logging.debug('changing repository info base_path from %s to %s',
                      (self.base_path, base_path))
        self.base_path = base_path

    def find_server_repository_info(self, server):
        """
        Try to find the repository from the list of repositories on the server.
        For Subversion, this could be a repository with a different URL. For
        all other clients, this is a noop.
        """
        return self


def load_scmclients(config, options):
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
    from rbtools.clients.perforce import PerforceClient

    repository_info = None
    tool = None

    # TODO: We should only load all of the scm clients if the
    # client_name isn't provided.
    if SCMCLIENTS is None:
        load_scmclients(config, options)

    if client_name:
        if client_name not in SCMCLIENTS:
            logging.error('The provided repository type "%s" is invalid.' %
                          client_name)
            sys.exit(1)
        else:
            scmclients = {
                client_name: SCMCLIENTS[client_name]
            }
    else:
        scmclients = SCMCLIENTS

    for name, tool in six.iteritems(scmclients):
        logging.debug('Checking for a %s repository...' % tool.name)
        repository_info = tool.get_repository_info()

        if repository_info:
            break

    if not repository_info:
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
