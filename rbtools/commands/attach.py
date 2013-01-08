import os
from optparse import make_option

from rbtools.api.errors import APIError
from rbtools.commands import Command
from rbtools.utils.process import die


class Attach(Command):
    """Attach a file to a review request."""
    name = "attach"
    author = "John Sintal"
    option_list = [
        make_option("--filename",
                    dest="filename",
                    default=None,
                    help="custom filename for file attachment"),
        make_option("--caption",
                    dest="caption",
                    default=None,
                    help="caption for file attachment"),
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
        super(Attach, self).__init__()
        self.option_defaults = {
            'server': self.config.get('REVIEWBOARD_URL', None),
            'username': self.config.get('USERNAME', None),
            'password': self.config.get('PASSWORD', None),
            'debug': self.config.get('DEBUG', False),
        }

    def get_review_request(self, request_id):
        """Returns the review request resource for the given ID."""
        try:
            request = \
                self.root_resource.get_review_requests().get_item(request_id)
        except APIError:
            die('The specified review request does not exist.')

        return request

    def main(self, request_id, path_to_file, *args):
        """Run the command."""
        self.repository_info, self.tool = self.initialize_scm_tool()
        server_url = self.get_server_url(self.repository_info, self.tool)
        self.root_resource = self.get_root(server_url)

        request = self.get_review_request(request_id)

        try:
            f = open(path_to_file, 'r')
            content = f.read()
            f.close()
        except IOError:
            die("%s is not a valid file." % (path_to_file))

        # Check if the user specified a custom filename, otherwise
        # use the original filename.
        filename = self.options.filename or os.path.basename(path_to_file)

        try:
            request.get_file_attachments() \
                .upload_attachment(filename, content, self.options.caption)
        except APIError, e:
            die("Error uploading file: %s" % (e))

        print "Uploaded %s to review request %s." % (path_to_file, request_id)
