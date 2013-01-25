from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option


class Publish(Command):
    """Publish a specific review request from a draft."""
    name = "publish"
    author = "The Review Board Project"
    args = "<request-id>"
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

    def get_review_request(self, request_id, api_root):
        """Returns the review request resource for the given ID."""
        try:
            request = api_root.get_review_request(review_request_id=request_id)
        except APIError, e:
            raise CommandError("Error getting review request: %s" % e)

        return request

    def main(self, request_id):
        """Run the command."""
        repository_info, tool = self.initialize_scm_tool()
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)

        request = self.get_review_request(request_id, api_root)
        try:
            draft = request.get_draft()
            draft = draft.update(public=True)
        except APIError, e:
            raise CommandError("Error publishing review request (it may "
                               "already be published): %s" % e)

        print "Review request #%s is published." % (request_id)
