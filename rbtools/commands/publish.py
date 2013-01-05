from optparse import make_option

from rbtools.api.errors import APIError
from rbtools.commands import Command
from rbtools.utils.process import die


class Publish(Command):
    """Publish a specific review request from a draft."""
    name = "publish"
    author = "The Review Board Project"
    option_list = [
        make_option("--server",
                    dest="server",
                    metavar="SERVER",
                    help="specify a different Review Board server to use"),
        make_option("-d", "--debug",
                    action="store_true",
                    dest="debug",
                    help="display debug output"),
    ]

    def __init__(self):
        super(Publish, self).__init__()
        self.option_defaults = {
            'server': self.config.get('REVIEWBOARD_URL', None),
            'username': self.config.get('USERNAME', None),
            'password': self.config.get('PASSWORD', None),
            'debug': self.config.get('DEBUG', False),
        }

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
