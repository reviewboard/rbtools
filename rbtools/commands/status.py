import logging

from rbtools.commands import Command, Option
from rbtools.utils.users import get_user


def get_repository_id(repository_info, api_root, repository_name=None):
    """Get the repository ID from the server.

    This will compare the paths returned by the SCM client
    with those on the server, and return the id of the first
    match.
    """
    detected_paths = repository_info.path

    if not isinstance(detected_paths, list):
        detected_paths = [detected_paths]

    repositories = api_root.get_repositories()

    try:
        while True:
            for repo in repositories:
                if (repo.path in detected_paths or
                    repo.name == repository_name):
                    return repo.id

            repositories = repositories.get_next()
    except StopIteration:
        return None


class Status(Command):
    """Display review requests for the current repository."""
    name = "status"
    author = "The Review Board Project"
    description = "Output a list of your pending review requests."
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
        Option("--all",
               dest="all_repositories",
               action="store_true",
               default=False,
               help="Show review requests for all repositories instead "
                    "of the detected repository."),
    ]

    def output_request(self, request):
        print "   r/%s - %s" % (request.id, request.summary)

    def output_draft(self, request, draft):
        print " * r/%s - %s" % (request.id, draft.summary)

    def main(self):
        repository_info, tool = self.initialize_scm_tool()
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)
        self.setup_tool(tool, api_root=api_root)
        user = get_user(api_client, api_root, auth_required=True)

        query_args = {
            'from_user': user.username,
            'status': 'pending',
            'expand': 'draft',
        }

        if not self.options.all_repositories:
            repo_id = get_repository_id(
                repository_info,
                api_root,
                repository_name=self.config.get('REPOSITORY', None))

            if repo_id:
                query_args['repository'] = repo_id
            else:
                logging.warning('The repository detected in the current '
                                'directory was not found on\n'
                                'the Review Board server. Displaying review '
                                'requests from all repositories.')

        requests = api_root.get_review_requests(**query_args)

        try:
            while True:
                for request in requests:
                    if request.draft:
                        self.output_draft(request, request.draft[0])
                    else:
                        self.output_request(request)

                requests = requests.get_next(**query_args)
        except StopIteration:
            pass
