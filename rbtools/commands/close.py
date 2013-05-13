from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option


SUBMITTED = 'submitted'
DISCARDED = 'discarded'


class Close(Command):
    """Close a specific review request as discarded or submitted.

    By default, the command will change the status to submitted. The
    user can provide an optional description for this action.
    """
    name = "close"
    author = "The Review Board Project"
    args = "<review-request-id>"
    option_list = [
        Option("--close-type",
               dest="close_type",
               default=SUBMITTED,
               help="either submitted or discarded"),
        Option("--description",
               dest="description",
               default=None,
               help="optional description accompanied with change"),
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

    def get_review_request(self, request_id, api_root):
        """Returns the review request resource for the given ID."""
        try:
            request = api_root.get_review_request(review_request_id=request_id)
        except APIError, e:
            raise CommandError("Error getting review request: %s" % e)

        return request

    def check_valid_type(self, close_type):
        """Check if the user specificed a proper type.

        Type must either be 'discarded' or 'submitted'. If the type
        is wrong, the command will stop and alert the user.
        """
        if close_type not in (SUBMITTED, DISCARDED):
            raise CommandError("%s is not valid type. Try '%s' or '%s'" % (
                self.options.close_type, SUBMITTED, DISCARDED))

    def main(self, request_id):
        """Run the command."""
        close_type = self.options.close_type
        self.check_valid_type(close_type)
        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)
        request = self.get_review_request(request_id, api_root)

        if request.status == close_type:
            raise CommandError("Request request #%s is already %s." % (
                request_id, close_type))

        if self.options.description:
            request = request.update(status=close_type,
                                     description=self.options.description)
        else:
            request = request.update(status=close_type)

        print "Review request #%s is set to %s." % (request_id, request.status)
