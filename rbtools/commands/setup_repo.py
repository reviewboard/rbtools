"""Implementation of rbt setup-repo."""

import difflib
import os
import textwrap

from rbtools.commands import Command, CommandError
from rbtools.utils.console import confirm, confirm_select
from rbtools.utils.filesystem import CONFIG_FILE
from rbtools.utils.repository import get_repository_resource


class SetupRepo(Command):
    """Configure a repository to point to a Review Board server.

    Interactively creates the configuration file .reviewboardrc in the current
    working directory.

    The user is prompted for the Review Board server url if it's not supplied
    as an option. Upon a successful server connection, an attempt is made to
    match the local repository to a repository on the Review Board server.
    If no match is found or if the user declines the match, the user is
    prompted to choose from other repositories on the Review Board server.

    If the client supports it, it attempts to guess the branch name on the
    server.
    """

    name = 'setup-repo'
    author = 'The Review Board Project'
    description = ('Configure an existing repository to point to a Review '
                   'Board server by generating the configuration file %s'
                   % CONFIG_FILE)
    args = ''
    option_list = [
        Command.server_options,
        Command.perforce_options,
        Command.tfs_options,
    ]

    def prompt_rb_repository(self, local_tool_name, server_tool_names,
                             repository_paths, api_root):
        """Interactively prompt to select a matching repository.

        The user is prompted to choose a matching repository found on the
        Review Board server.

        Args:
            local_tool_name (unicode):
                The local name of the detected tool.

            server_tool_names (unicode):
                A comma-separated list of potentially matching SCMTool names in
                the Review Board server.

            repository_paths (list or unicode, optional):
                A list of potential paths to match for the repository.

            api_root (rbtools.api.resource.RootResource):
                The root resource for the Review Board server.

        Returns:
            rbtools.api.resource.ItemResource:
            The selected repository resource.
        """
        # Go through each matching repo and prompt for a selection. If a
        # selection is made, immediately return the selected repo.
        repo_paths = {}

        repositories = api_root.get_repositories(tool=server_tool_names)

        for repository in repositories.all_items:
            repo_paths[repository['path']] = repository

            if 'mirror_path' in repository:
                repo_paths[repository['mirror_path']] = repository

        closest_paths = difflib.get_close_matches(repository_paths,
                                                  repo_paths.keys(),
                                                  n=4,
                                                  cutoff=0.4)

        if closest_paths:
            self.stdout.new_line()
            self.stdout.write(
                '%(num)s matching %(repo_type)s repositories found:'
                % {
                    'num': len(closest_paths),
                    'repo_type': local_tool_name,
                })
            self._display_rb_repositories(closest_paths, repo_paths)
            repo_chosen = confirm_select('Select a %s repository to use' %
                                         local_tool_name, len(closest_paths))

            if repo_chosen:
                repo_chosen = int(repo_chosen) - 1
                current_repo_index = closest_paths[repo_chosen]
                current_repo = repo_paths[current_repo_index]

                self.stdout.new_line()
                self.stdout.write('Selecting "%s" (%s)...'
                                  % (current_repo['name'],
                                     current_repo['path']))
                self.stdout.new_line()

                return current_repo

        return None

    def _get_output(self, config):
        """Returns a string output based on the the provided config."""
        settings = []

        for setting, value in config:
            settings.append('%s = "%s"' % (setting, value))

        settings.append('')

        return '\n'.join(settings)

    def generate_config_file(self, file_path, config):
        """Generates the config file in the current working directory."""
        try:
            with open(file_path, 'w') as outfile:
                output = self._get_output(config)
                outfile.write(output)
        except IOError as e:
            raise CommandError('I/O error generating config file (%s): %s'
                               % (e.errno, e.strerror))

        self.stdout.write('%s creation successful! Config written to %s'
                          % (CONFIG_FILE, file_path))

    def main(self, *args):
        server = self.options.server
        api_client = None
        api_root = None

        self.stdout.new_line()
        self.stdout.write(textwrap.fill(
            'This command is intended to help users create a %s file in '
            'the current directory to connect a repository and Review '
            'Board server.')
            % CONFIG_FILE)
        self.stdout.new_line()
        self.stdout.write(textwrap.fill(
            'Repositories must currently exist on your server (either '
            'hosted internally or via RBCommons) to successfully '
            'generate this file.'))
        self.stdout.write(textwrap.fill(
            'Repositories can be added using the Admin Dashboard in '
            'Review Board or under your team administration settings in '
            'RBCommons.'))
        self.stdout.new_line()
        self.stdout.write(textwrap.fill(
            'Press CTRL + C anytime during this command to cancel '
            'generating your config file.'))
        self.stdout.new_line()

        while True:
            if server:
                try:
                    # Validate the inputted server.
                    api_client, api_root = self.get_api(server)
                    break
                except CommandError as e:
                    self.stdout.new_line()
                    self.stdout.write('%s' % e)
                    self.stdout.write('Please try again.')
                    self.stdout.new_line()

            server = input('Enter the Review Board server URL: ')

        repository_info, tool = self.initialize_scm_tool()

        self.capabilities = self.get_capabilities(api_root)
        tool.capabilities = self.capabilities

        # Go through standard detection mechanism first. If we find a match
        # this way, we'll set the local repository_info path to be the same as
        # the remote, which will improve matching.
        repository, info = get_repository_resource(
            api_root,
            tool=tool,
            repository_paths=repository_info.path)

        if repository:
            repository_info.update_from_remote(repository, info)

        # While a repository is not chosen, keep the repository selection
        # prompt displayed until the prompt is cancelled.
        while True:
            self.stdout.new_line()
            self.stdout.write('Current server: %s' % server)
            selected_repo = self.prompt_rb_repository(
                local_tool_name=tool.name,
                server_tool_names=tool.server_tool_names,
                repository_paths=repository_info.path,
                api_root=api_root)

            if not selected_repo:
                self.stdout.new_line()
                self.stdout.write('No %s repository found for the Review '
                                  'Board server %s'
                                  % (tool.name, server))
                self.stdout.new_line()
                self.stdout.write('Cancelling %s creation...' % CONFIG_FILE)
                self.stdout.new_line()
                self.stdout.write(textwrap.fill(
                    'Please make sure your repositories '
                    'currently exist on your server. '
                    'Repositories can be configured using the '
                    'Review Board Admin Dashboard or under your '
                    'team administration settings in RBCommons. '
                    'For more information, see `rbt help '
                    'setup-repo` or the official docs at '
                    'https://www.reviewboard.org/docs/.'))
                return

            config = [
                ('REVIEWBOARD_URL', server),
                ('REPOSITORY', selected_repo['name']),
                ('REPOSITORY_TYPE', tool.scmclient_id),
            ]

            try:
                branch = tool.get_current_branch()
                config.append(('BRANCH', branch))
                config.append(('LAND_DEST_BRANCH', branch))
            except NotImplementedError:
                pass

            outfile_path = os.path.join(os.getcwd(), CONFIG_FILE)
            output = self._get_output(config)

            if not os.path.exists(outfile_path):
                question = ('Create "%s" with the following?\n\n%s\n'
                            % (outfile_path, output))
            else:
                question = (
                    '"%s" exists. Overwrite with the following?\n\n%s\n'
                    % (outfile_path, output)
                )

            if confirm(question):
                break

        self.generate_config_file(outfile_path, config)

    def _display_rb_repositories(self, closest_paths, repo_paths):
        """Display all repositories found for a Review Board server.

        Args:
            closest_paths (list of unicode)
                A list of best-matching repositories from a valid
                Review Board server.

            repo_paths (dict)
                A dictionary containing repository metadata.
        """
        for i, repo_url in enumerate(closest_paths):
            repo = repo_paths[repo_url]
            self.stdout.write(
                '%(num)d) "%(repo_name)s" (%(repo_url)s)'
                % {
                    'num': i + 1,
                    'repo_name': repo['name'],
                    'repo_url': repo_url,
                })
