from rbtools.api.errors import APIError
from rbtools.commands import Command, Option
from rbtools.utils.process import die


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
        Option("-d", "--debug",
               action="store_true",
               dest="debug",
               config_key="DEBUG",
               default=False,
               help="display debug output"),
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

    def get_review_request(self, request_id):
        """Return the review request resource for the given ID."""
        try:
            request = \
                self.root_resource.get_review_requests().get_item(request_id)
        except APIError, e:
            die("Error getting review request: %s" % e)

        return request

    def main(self, request_id, *args):
        """Run the command."""
        repository_info, tool = self.initialize_scm_tool()
        server_url = self.get_server_url(repository_info, tool)
        self.root_resource = self.get_root(server_url)

        request = self.get_review_request(request_id)
        try:
            draft = request.get_draft()
            draft = draft.update(data={'public': True})
        except APIError, e:
            die("Error publishing review request (it may already be"
                "publish): %s" % e)

        print "Review request #%s is published." % (request_id)
