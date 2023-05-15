"""Implementation of rbt diff."""

from rbtools.clients.errors import InvalidRevisionSpecError
from rbtools.commands import Command, CommandError


class Diff(Command):
    """Prints a diff to the terminal."""

    name = 'diff'
    author = 'The Review Board Project'

    # The diff command uses the API because some of the clients may change
    # their diff behavior based on server capabilities (for example, very old
    # servers may not have support for moved files with some SCM types). We
    # might want to consider adding a mode for running this command in a purely
    # offline way, or we might just want to define a supported baseline version
    # of Review Board and get rid of some of the capability conditionals.
    needs_api = True
    needs_diffs = True
    needs_repository = True
    needs_scm_client = True

    args = '[revisions]'
    option_list = [
        Command.server_options,
        Command.diff_options,
        Command.branch_options,
        Command.repository_options,
        Command.git_options,
        Command.perforce_options,
        Command.subversion_options,
        Command.tfs_options,
    ]

    def main(self, *args):
        """Print the diff to terminal."""
        # The 'args' tuple must be made into a list for some of the
        # SCM Clients code. See comment in post.
        args = list(args)

        if self.options.revision_range:
            raise CommandError(
                'The --revision-range argument has been removed. To create a '
                'diff for one or more specific revisions, pass those '
                'revisions as arguments. For more information, see the '
                'RBTools 0.6 Release Notes.')

        if self.options.svn_changelist:
            raise CommandError(
                'The --svn-changelist argument has been removed. To use a '
                'Subversion changelist, pass the changelist name as an '
                'additional argument after the command.')

        tool = self.tool

        try:
            revisions = tool.parse_revision_spec(args)
            extra_args = None
        except InvalidRevisionSpecError:
            if not tool.supports_diff_extra_args:
                raise

            revisions = None
            extra_args = args

        if (self.options.exclude_patterns and
            not tool.supports_diff_exclude_patterns):

            raise CommandError(
                'The %s backend does not support excluding files via the '
                '-X/--exclude commandline options or the EXCLUDE_PATTERNS '
                '.reviewboardrc option.' % tool.name)

        diff_kwargs = {}

        if self.options.no_renames:
            if not tool.supports_no_renames:
                raise CommandError('The %s SCM tool does not support diffs '
                                   'without renames.', tool.type)

            diff_kwargs['no_renames'] = True

        diff_info = tool.diff(
            revisions=revisions,
            include_files=self.options.include_files or [],
            exclude_patterns=self.options.exclude_patterns or [],
            repository_info=self.repository_info,
            extra_args=extra_args,
            **diff_kwargs)

        diff = diff_info['diff']

        if diff:
            # Write the non-decoded binary diff to standard out.
            self.stdout_bytes.write(diff)
            self.stdout.new_line()
