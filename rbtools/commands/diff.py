from __future__ import print_function, unicode_literals

from rbtools.clients.errors import InvalidRevisionSpecError
from rbtools.commands import Command, CommandError

import six


class Diff(Command):
    """Prints a diff to the terminal."""

    name = 'diff'
    author = 'The Review Board Project'
    args = '[revisions]'
    option_list = [
        Command.server_options,
        Command.diff_options,
        Command.branch_options,
        Command.repository_options,
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

        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(tool, api_root=api_root)

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

        if self.options.no_renames and not tool.supports_no_renames:
            raise CommandError('The %s SCM tool does not support diffs '
                               'without renames.', tool.type)

        diff_info = tool.diff(
            revisions=revisions,
            include_files=self.options.include_files or [],
            exclude_patterns=self.options.exclude_patterns or [],
            no_renames=self.options.no_renames,
            extra_args=extra_args)

        diff = diff_info['diff']

        if diff:
            if six.PY2:
                print(diff)
            else:
                print(diff.decode('utf-8'))
