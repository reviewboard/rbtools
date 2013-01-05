from optparse import make_option

from rbtools.commands import Command
from rbtools.utils.process import die


class Diff(Command):
    """Prints a diff to the terminal."""
    name = "diff"
    author = "The Review Board Project"
    option_list = [
        make_option("--revision-range",
                    dest="revision_range",
                    default=None,
                    help="generate the diff for review based on given "
                         "revision range"),
        make_option("--parent",
                    dest="parent_branch",
                    metavar="PARENT_BRANCH",
                    help="the parent branch this diff should be against "
                         "(only available if your repository supports "
                         "parent diffs)"),
        make_option("--tracking-branch",
                    dest="tracking",
                    metavar="TRACKING",
                    help="Tracking branch from which your branch is derived "
                         "(git only, defaults to origin/master)"),
        make_option('--svn-changelist',
                    dest='svn_changelist',
                    default=None,
                    help='generate the diff for review based on a local SVN '
                         'changelist'),
        make_option("--repository-url",
                    dest="repository_url",
                    help="the url for a repository for creating a diff "
                         "outside of a working copy (currently only "
                         "supported by Subversion with --revision-range or "
                         "--diff-filename and ClearCase with relative "
                         "paths outside the view). For git, this specifies"
                         "the origin url of the current repository, "
                         "overriding the origin url supplied by the git "
                         "client."),
        make_option("-d", "--debug",
                    action="store_true",
                    dest="debug",
                    help="display debug output"),
    ]

    def __init__(self):
        super(Diff, self).__init__()

        self.option_defaults = {
            'p4_client': self.config.get('P4_CLIENT', None),
            'p4_port': self.config.get('P4_PORT', None),
            'p4_passwd': self.config.get('P4_PASSWD', None),
            'debug': self.config.get('DEBUG', False),
        }

    def get_diff(self, *args):
        """Returns a diff as a string."""
        repository_info, tool = self.initialize_scm_tool()

        if self.options.revision_range:
            diff, parent_diff = tool.diff_between_revisions(
                self.options.revision_range,
                args,
                repository_info)
        elif self.options.svn_changelist:
            diff, parent_diff = tool.diff_changelist(
                self.options.svn_changelist)
        else:
            diff, parent_diff = tool.diff(list(args))

        return diff

    def main(self, *args):
        """Print the diff to terminal."""
        diff = self.get_diff(*args)

        if not diff:
            die("There don't seem to be any diffs!")

        print diff
