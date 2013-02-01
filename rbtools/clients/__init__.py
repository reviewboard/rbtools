import logging
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

    def diff(self, args):
        """
        Returns the generated diff and optional parent diff for this
        repository.

        The returned tuple is (diff_string, parent_diff_string)
        """
        return (None, None)

    def diff_between_revisions(self, revision_range, args, repository_info):
        """
        Returns the generated diff between revisions in the repository.
        """
        return (None, None)

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

    from rbtools.clients.bazaar import BazaarClient
    from rbtools.clients.clearcase import ClearCaseClient
    from rbtools.clients.cvs import CVSClient
    from rbtools.clients.git import GitClient
    from rbtools.clients.mercurial import MercurialClient
    from rbtools.clients.perforce import PerforceClient
    from rbtools.clients.plastic import PlasticClient
    from rbtools.clients.svn import SVNClient

    SCMCLIENTS = [
        BazaarClient(options=options),
        CVSClient(options=options),
        ClearCaseClient(options=options),
        GitClient(options=options),
        MercurialClient(options=options),
        PerforceClient(options=options),
        PlasticClient(options=options),
        SVNClient(options=options),
    ]


def scan_usable_client(options):
    from rbtools.clients.perforce import PerforceClient

    repository_info = None
    tool = None

    if SCMCLIENTS is None:
        load_scmclients(options)

    # Try to find the SCM Client we're going to be working with.
    for tool in SCMCLIENTS:
        logging.debug('Checking for a %s repository...' % tool.name)
        repository_info = tool.get_repository_info()

        if repository_info:
            break

    if not repository_info:
        if options.repository_url:
            print "No supported repository could be accessed at the supplied "\
                  "url."
        else:
            print "The current directory does not contain a checkout from a"
            print "supported source code repository."
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
