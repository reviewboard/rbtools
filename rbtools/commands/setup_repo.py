from __future__ import print_function, unicode_literals

import difflib
import os

import six
from six.moves import input

from rbtools.commands import Command, CommandError
from rbtools.utils.console import confirm
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
    description = ('Configure a repository to point to a Review Board server '
                   'by generating the configuration file %s'
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
        for repository_page in api_root.get_repositories().all_pages:
            repo_paths = {}

            for repository in repository_page:
                if repository.tool != tool_name:
                    continue

                repo_paths[repository['path']] = repository

                if 'mirror_path' in repository:
                    repo_paths[repository['mirror_path']] = repository

            closest_path = difflib.get_close_matches(repository_info.path,
                                                     six.iterkeys(repo_paths),
                                                     n=4, cutoff=0.4)

            for path in closest_path:
                repo = repo_paths[path]
                question = ('Use the %s repository "%s" (%s)?'
                            % (tool_name, repo['name'], repo['path']))

                if confirm(question):
                    return repo

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

        print('Config written to %s' % file_path)

    def main(self, *args):
        server = self.options.server

        if not server:
            server = input('Enter the Review Board server URL: ')

        repository_info, tool = self.initialize_scm_tool()
        api_client, api_root = self.get_api(server)
        self.setup_tool(tool, api_root=api_root)

        # Check if repository info on reviewboard server match local ones.
        repository_info = repository_info.find_server_repository_info(api_root)

        selected_repo = self.prompt_rb_repository(
            tool.name, repository_info, api_root)

        if not selected_repo:
            print('No %s repository found or selected for %s. %s not created.'
                  % (tool.name, server, CONFIG_FILE))
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
            question = ('"%s" exists. Overwrite with the following?\n\n%s\n'
                        % (outfile_path, output))

        if not confirm(question):
            return

        self.generate_config_file(outfile_path, config)
