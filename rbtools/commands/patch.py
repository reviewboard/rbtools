from optparse import make_option
import os

from rbtools.api.errors import APIError
from rbtools.commands import Command
from rbtools.utils.filesystem import make_tempfile


class Patch(Command):
    """Applies a specific patch from a RB server.

    The patch file indicated by the request id is downloaded from the
    server and then applied locally."""
    name = "patch"
    author = "John Sintal"
    option_list = [
        make_option("--diff-revision",
                    dest="diff_revision",
                    default=None,
                    help="revision id of diff to be used as patch"),
        make_option("--px",
                    dest="px",
                    default=None,
                    help="numerical pX argument for patch"),
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
        super(Patch, self).__init__()
        self.option_defaults = {
            'server': self.config.get('REVIEWBOARD_URL', None),
            'username': self.config.get('USERNAME', None),
            'password': self.config.get('PASSWORD', None),
            'debug': self.config.get('DEBUG', False),
        }

    def get_patch(self, request_id, diff_revision=None):
        """Given a review request ID and a diff revision,
        return the diff as a string, the used diff revision,
        and its basedir.

        If a diff revision is not specified, then this will
        look at the most recent diff.
        """
        try:
            diffs = self.root_resource \
                .get_review_requests() \
                .get_item(request_id) \
                .get_diffs()
        except APIError, e:
            die("Error getting diffs: %s" % (e))

        # Use the latest diff if a diff revision was not given.
        # Since diff revisions start a 1, increment by one, and
        # never skip a number, the latest diff revisions number
        # should be equal to the number of diffs.
        if diff_revision is None:
            diff_revision = diffs.total_results

        try:
            diff = diffs.get_item(diff_revision)
            diff_body = diff.get_patch().diff
            base_dir = diff.basedir
        except APIError:
            die('The specified diff revision does not exist.')

        return diff_body, diff_revision, base_dir

    def apply_patch(self, request_id, diff_revision, diff_file_path, base_dir):
        """Apply patch patch_file and display results to user."""
        print "Patch is being applied from request %s with diff revision" \
              " %s." % (request_id, diff_revision)
        self.tool.apply_patch(diff_file_path, self.repository_info.base_path,
                              base_dir, self.options.px)

    def main(self, request_id, *args):
        """Run the command."""
        self.repository_info, self.tool = self.initialize_scm_tool()
        server_url = self.get_server_url(self.repository_info, self.tool)
        self.root_resource = self.get_root(server_url)

        # Get the patch, the used patch ID and base dir for the diff
        diff_body, diff_revision, base_dir = self.get_patch(
            request_id,
            self.options.diff_revision)

        tmp_patch_file = make_tempfile(diff_body)

        self.apply_patch(request_id, diff_revision, tmp_patch_file, base_dir)

        os.remove(tmp_patch_file)
