from __future__ import print_function, unicode_literals

import difflib
import os
import textwrap

import six
from six.moves import input

from rbtools.commands import Command, CommandError
from rbtools.utils.console import confirm, confirm_select
from rbtools.utils.filesystem import CONFIG_FILE


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

    def prompt_rb_repository(self, tool_name, repository_info, api_root):
        """Interactively prompt to select a matching repository.

        The user is prompted to choose a matching repository found on the
        Review Board server.
        """
        # Go through each matching repo and prompt for a selection. If a
        # selection is made, immediately return the selected repo.
        repo_paths = {}
        for repository_page in api_root.get_repositories().all_pages:
            for repository in repository_page:
                if repository.tool != tool_name:
                    continue

                repo_paths[repository['path']] = repository

                if 'mirror_path' in repository:
                    repo_paths[repository['mirror_path']] = repository

        closest_paths = difflib.get_close_matches(repository_info.path,
                                                  six.iterkeys(repo_paths),
                                                  n=4, cutoff=0.4)

        if closest_paths:
            print()
            print(
                '%(num)s %(repo_type)s repositories found:'
                % {
                    'num': len(closest_paths),
                    'repo_type': tool_name,
                })
            self._display_rb_repositories(closest_paths, repo_paths)
            repo_chosen = confirm_select('Select a %s repository to use' %
                                         tool_name, len(closest_paths))

            if repo_chosen:
                repo_chosen = int(repo_chosen) - 1
                current_repo_index = closest_paths[repo_chosen]
                current_repo = repo_paths[current_repo_index]

                print()
                print('Selecting "%s" (%s)...' % (current_repo['name'],
                                                  current_repo['path']))
                print()

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

        print('%s creation successful! Config written to %s' % (CONFIG_FILE,
                                                                file_path))

    def main(self, *args):
        server = self.options.server
        api_client = None
        api_root = None

        if not server:
            print()
            print(textwrap.fill(
                'This command is intended to help users create a %s file in '
                'the current directory to connect a repository and Review '
                'Board server.')
                % CONFIG_FILE)
            print()
            print(textwrap.fill(
                'Repositories must currently exist on your server (either '
                'hosted internally or via RBCommons) to successfully '
                'generate this file.'))
            print(textwrap.fill(
                'Repositories can be added using the Admin Dashboard in '
                'Review Board or under your team administration settings in '
                'RBCommons.'))
            print()
            print(textwrap.fill(
                'Press CTRL + C anytime during this command to cancel '
                'generating your config file.'))
            print()

            while True:
                server = input('Enter the Review Board server URL: ')

                if server:
                    try:
                        # Validate the inputted server.
                        api_client, api_root = self.get_api(server)
                        break
                    except CommandError as e:
                        print()
                        print('%s' % e)
                        print('Please try again.')
                        print()

        repository_info, tool = self.initialize_scm_tool()

        # If we run the `--server` option or if we run `rbt setup-repo` with
        # a server URL already defined in our config file, neither `api_root`
        # nor `api_client` will be defined. We must re-validate our server
        # again.
        if not api_root and not api_client:
            api_client, api_root = self.get_api(server)

        self.setup_tool(tool, api_root=api_root)

        # Check if repository info on reviewboard server match local ones.
        repository_info = repository_info.find_server_repository_info(api_root)

        # While a repository is not chosen, keep the repository selection
        # prompt displayed until the prompt is cancelled.
        while True:
            print()
            print('Current server: %s' % server)
            selected_repo = self.prompt_rb_repository(
                tool.name, repository_info, api_root)

            if not selected_repo:
                print()
                print('No %s repository found for the Review Board server %s'
                      % (tool.name, server))
                print()
                print('Cancelling %s creation...' % CONFIG_FILE)
                print()
                print(textwrap.fill(
                    'Please make sure your repositories currently exist on '
                    'your server. Repositories can be configured using the '
                    'Review Board Admin Dashboard or under your team '
                    'administration settings in RBCommons. For more '
                    'information, see `rbt help setup-repo` or the official '
                    'docs at https://www.reviewboard.org/docs/.'))
                return

            config = [
                ('REVIEWBOARD_URL', server),
                ('REPOSITORY', selected_repo['name']),
                ('REPOSITORY_TYPE', tool.entrypoint_name),
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
            print(
                '%(num)d) "%(repo_name)s" (%(repo_url)s)'
                % {
                    'num': i + 1,
                    'repo_name': repo['name'],
                    'repo_url': repo_url,
                })
