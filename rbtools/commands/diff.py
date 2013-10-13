from rbtools.commands import Command, Option
from rbtools.utils.diffs import get_diff


class Diff(Command):
    """Prints a diff to the terminal."""
    name = "diff"
    author = "The Review Board Project"
    args = "[changenum]"
    option_list = [
        Option("--server",
               dest="server",
               metavar="SERVER",
               config_key="REVIEWBOARD_URL",
               default=None,
               help="specify a different Review Board server to use"),
        Option("--revision-range",
               dest="revision_range",
               default=None,
               help="generate the diff for review based on given "
                    "revision range"),
        Option("--parent",
               dest="parent_branch",
               metavar="PARENT_BRANCH",
               help="the parent branch this diff should be against "
                    "(only available if your repository supports "
                    "parent diffs)"),
        Option("--tracking-branch",
               dest="tracking",
               metavar="TRACKING",
               help="Tracking branch from which your branch is derived "
                    "(git only, defaults to origin/master)"),
        Option("--svn-show-copies-as-adds",
               dest="svn_show_copies_as_adds",
               metavar="y/n",
               default=None,
               help="don't diff copied or moved files with their source"),
        Option('--svn-changelist',
               dest='svn_changelist',
               default=None,
               help='generate the diff for review based on a local SVN '
                    'changelist'),
        Option("--repository-url",
               dest="repository_url",
               help="the url for a repository for creating a diff "
                    "outside of a working copy (currently only "
                    "supported by Subversion with --revision-range or "
                    "--diff-filename and ClearCase with relative "
                    "paths outside the view). For git, this specifies"
                    "the origin url of the current repository, "
                    "overriding the origin url supplied by the git "
                    "client."),
        Option("--username",
               dest="username",
               metavar="USERNAME",
               config_key="USERNAME",
               default=None,
               help="user name to be supplied to the Review Board server"),
        Option("--password",
               dest="password",
               metavar="PASSWORD",
               config_key="PASSWORD",
               default=None,
               help="password to be supplied to the Review Board server"),
        Option('--repository-type',
               dest='repository_type',
               config_key="REPOSITORY_TYPE",
               default=None,
               help='the type of repository in the current directory. '
                    'In most cases this should be detected '
                    'automatically but some directory structures '
                    'containing multiple repositories require this '
                    'option to select the proper type. Valid '
                    'values include bazaar, clearcase, cvs, git, '
                    'mercurial, perforce, plastic, and svn.'),
    ]

    def main(self, *args):
        """Print the diff to terminal."""
        # The 'args' tuple must be made into a list for some of the
        # SCM Clients code. See comment in post.
        args = list(args)

        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(tool, api_root=api_root)

        diff_info = get_diff(
            tool,
            repository_info,
            revision_range=self.options.revision_range,
            svn_changelist=self.options.svn_changelist,
            files=args)

        diff = diff_info['diff']

        if diff:
            print diff
