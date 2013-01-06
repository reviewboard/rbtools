import os

from rbtools.api.errors import APIError
from rbtools.commands import Command, Option
from rbtools.utils.process import die


class Attach(Command):
    """Attach a file to a review request."""
    name = "attach"
    author = "The Review Board Project"
    option_list = [
        Option("--filename",
               dest="filename",
               default=None,
               help="custom filename for file attachment"),
        Option("--caption",
               dest="caption",
               default=None,
               help="caption for file attachment"),
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
