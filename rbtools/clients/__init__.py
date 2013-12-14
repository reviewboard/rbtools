import logging
import pkg_resources
import sys

from rbtools.utils.process import die, execute


# The clients are lazy loaded via load_scmclients()
SCMCLIENTS = None


class SCMClient(object):
    """
    A base representation of an SCM tool for fetching repository information
    and generating diffs.
    """
    name = None

    def __init__(self, user_config=None, configs=[], options=None,
                 capabilities=None):
        self.user_config = user_config
        self.configs = configs
        self.options = options
        self.capabilities = capabilities

    def get_repository_info(self):
        return None

    def check_options(self):
        pass

    def scan_for_server(self, repository_info):
        """
        Scans the current directory on up to find a .reviewboard file
        containing the server path.
        """
        server_url = None

        if self.user_config:
            server_url = self._get_server_from_config(self.user_config,
                                                      repository_info)

        if not server_url:
            for config in self.configs:
                server_url = self._get_server_from_config(config,
                                                          repository_info)

                if server_url:
                    break

        return server_url

    def parse_revision_spec(self, revisions=[]):
        """Parses the given revision spec.

        The 'revisions' argument is a list of revisions as specified by the
        user. Items in the list do not necessary represent a single revision,
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

    def diff(self, args):
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

    def diff_between_revisions(self, revision_range, args, repository_info):
        """Returns the generated diff between revisions in the repository.

        This has the same return values as diff.
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
                die("Warning: 'TREES' in config file is not a dict!")

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

    def _get_p_number(self, patch_file, base_path, base_dir):
        """
        Returns the appropriate int used for patch -pX argument,
        where x is the aforementioned int.
        """
        if (base_dir.startswith(base_path)):
            return base_path.count('/') + 1
        else:
            return -1

    def _execute(self, cmd):
        """
        Prints the results of the executed command and returns
        the data result from execute.
        """
        print 'Command:\n' + str(cmd)
        res = execute(cmd, ignore_errors=True)
        print 'Results:\n' + res
        return res

    def has_pending_changes(self):
        """Checks if there are changes waiting to be committed.

        Derived classes should override this method if they wish to support
        checking for pending changes.
        """
        raise NotImplementedError

    def apply_patch(self, patch_file, base_path, base_dir, p=None):
        """
        Apply the patch patch_file and return True if the patch was
        successful, otherwise return False.
        """
        # Figure out the pX for patch. Override the p_num if it was
        # specified in the command's options.
        p_num = p or self._get_p_number(patch_file, base_path, base_dir)
        if (p_num >= 0):
            cmd = ['patch', '-p' + str(p_num), '-i', str(patch_file)]
        else:
            cmd = ['patch', '-i', str(patch_file)]
        self._execute(cmd)

    def create_commmit(self, message, author):
        """Creates a commit based on the provided message and author.

        Derived classes should override this method if they wish to support
        committing changes to their repositories.
        """
        raise NotImplementedError

    def sanitize_changenum(self, changenum):
        """Return a "sanitized" change number.

        Dervied classes should override this method if they
        support change numbers. It will be called before
        uploading the change number to the Review Board
        server.

        TODO: Possibly refactor this into get_changenum
        once post-review is deprecated.
        """
        raise NotImplementedError

    def extract_summary(self, revision_range=None):
        """Returns the summary from the commits on the current branch.

        Derived classes should override this method if they wish to support
        summary guessing.

        If a derived class is unable to guess the summary, ``None`` should be
        returned.
        """
        raise NotImplementedError

    def extract_description(self, revision_range=None):
        """Returns the description based on commits on the current branch.

        Derived classes should override this method if they wish to support
        description guessing.

        If a derived class is unable to guess the description, ``None`` should
        be returned.
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
        logging.debug("repository info: %s" % self)

    def __str__(self):
        return "Path: %s, Base path: %s, Supports changesets: %s" % \
            (self.path, self.base_path, self.supports_changesets)

    def set_base_path(self, base_path):
        if not base_path.startswith('/'):
            base_path = '/' + base_path
        logging.debug("changing repository info base_path from %s to %s" %
                      (self.base_path, base_path))
        self.base_path = base_path

    def find_server_repository_info(self, server):
        """
        Try to find the repository from the list of repositories on the server.
        For Subversion, this could be a repository with a different URL. For
        all other clients, this is a noop.
        """
        return self


def load_scmclients(options):
    global SCMCLIENTS

    SCMCLIENTS = {}

    for ep in pkg_resources.iter_entry_points(group='rbtools_scm_clients'):
        try:
            SCMCLIENTS[ep.name] = ep.load()(options=options)
        except Exception, e:
            logging.error('Could not load SCM Client "%s": %s' % (ep.name, e))


def scan_usable_client(options, client_name=None):
    from rbtools.clients.perforce import PerforceClient

    repository_info = None
    tool = None

    # TODO: We should only load all of the scm clients if the
    # client_name isn't provided.
    if SCMCLIENTS is None:
        load_scmclients(options)

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

    for name, tool in scmclients.iteritems():
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
        sys.stderr.write("The --change-only option is not valid for the "
                         "current SCM client.\n")
        sys.exit(1)

    if (getattr(options, 'parent_branch', None) and
        not repository_info.supports_parent_diffs):
        sys.stderr.write("The --parent option is not valid for the "
                         "current SCM client.\n")
        sys.exit(1)

    if (not isinstance(tool, PerforceClient) and
        (getattr(options, 'p4_client', None) or
         getattr(options, 'p4_port', None))):
        sys.stderr.write("The --p4-client and --p4-port options are not valid "
                         "for the current SCM client.\n")
        sys.exit(1)

    return (repository_info, tool)


def print_clients(options):
    """Print the supported detected SCM clients.

    Each SCM client, including those provided by third party packages,
    will be printed. Additionally, SCM clients which are detected in
    the current directory will be highlighted.
    """
    print 'The following repository types are supported by this installation'
    print 'of RBTools. Each "<type>" may be used as a value for the'
    print '"--repository-type=<type>" command line argument. Repository types'
    print 'which are detected in the current directory are marked with a "*"'
    print '[*] "<type>": <Name>'

    if SCMCLIENTS is None:
        load_scmclients(options)

    for name, tool in SCMCLIENTS.iteritems():
        repository_info = tool.get_repository_info()

        if repository_info:
            print ' * "%s": %s' % (name, tool.name)
        else:
            print '   "%s": %s' % (name, tool.name)
