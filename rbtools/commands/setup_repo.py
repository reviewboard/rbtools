import os

from rbtools.commands import Command, CommandError, Option
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
    name = "setup-repo"
    author = "The Review Board Project"
    description = ("Configure a repository to point to a Review Board server "
                   "by generating the configuration file %s"
                   % CONFIG_FILE)
    args = ""
    option_list = [
        Option("--server",
               dest="server",
               metavar="SERVER",
               config_key="REVIEWBOARD_URL",
               default=None,
               help="specify a different Review Board server to use"),
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
    ]

    def prompt_rb_repository(self, tool_name, repository_info, api_root):
        """Interactively prompt to select a matching repository.

        The user is prompted to choose a matching repository found on the
        Review Board server.
        """
        repositories = api_root.get_repositories()

        # Go through each matching repo and prompt for a selection. If a
        # selection is made, immediately return the selected repo.
        try:
            while True:
                for repo in repositories:
                    is_match = (
                        tool_name == repo.tool and
                        repository_info.path in
                        (repo['path'], getattr(repo, 'mirror_path', '')))

                    if is_match:
                        question = (
                            "Use the %s repository '%s' (%s)?"
                            % (tool_name, repo['name'], repo['path']))

                        if confirm(question):
                            return repo

                repositories = repositories.get_next()
        except StopIteration:
            pass

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
            outfile = open(file_path, "w")
            output = self._get_output(config)
            outfile.write(output)
            outfile.close()
        except IOError as e:
            raise CommandError('I/O error generating config file (%s): %s'
                               % e.errno, e.strerror)

        print "Config written to %s" % file_path

    def main(self, *args):
        server = self.options.server

        if not server:
            server = raw_input('Enter the Review Board server URL: ')

        repository_info, tool = self.initialize_scm_tool()
        api_client, api_root = self.get_api(server)
        self.setup_tool(tool, api_root=api_root)

        selected_repo = self.prompt_rb_repository(
            tool.name, repository_info, api_root)

        if not selected_repo:
            print ("No %s repository found or selected for %s. %s not created."
                   % (tool.name, server, CONFIG_FILE))
            return

        config = [
            ('REVIEWBOARD_URL', server),
            ('REPOSITORY', selected_repo['name'])
        ]

        try:
            branch = tool.get_current_branch()
            config.append(('BRANCH', branch))
        except NotImplementedError:
            pass

        outfile_path = os.path.join(os.getcwd(), CONFIG_FILE)
        output = self._get_output(config)

        if not os.path.exists(outfile_path):
            question = ("Create '%s' with the following?\n\n%s\n"
                        % (outfile_path, output))
        else:
            question = ("'%s' exists. Overwrite with the following?\n\n%s\n"
                        % (outfile_path, output))

        if not confirm(question):
            return

        self.generate_config_file(outfile_path, config)
