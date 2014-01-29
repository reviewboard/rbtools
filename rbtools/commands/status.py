import logging

from rbtools.commands import Command, Option
from rbtools.utils.repository import get_repository_id
from rbtools.utils.users import get_user


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
        Option("--p4-client",
               dest="p4_client",
               config_key="P4_CLIENT",
               default=None,
               help="the Perforce client name that the review is in"),
        Option("--p4-port",
               dest="p4_port",
               config_key="P4_PORT",
               default=None,
               help="the Perforce servers IP address that the review is on"),
        Option("--p4-passwd",
               dest="p4_passwd",
               config_key="P4_PASSWD",
               default=None,
               help="the Perforce password or ticket of the user "
                    "in the P4USER environment variable"),
    ]

    def output_request(self, request):
        print "   r/%s - %s" % (request.id, request.summary)

    def output_draft(self, request, draft):
        print " * r/%s - %s" % (request.id, draft.summary)

    def main(self):
        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
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
