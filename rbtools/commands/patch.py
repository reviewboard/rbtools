import re

from rbtools.api.errors import APIError
from rbtools.commands import Command, CommandError, Option
from rbtools.utils.filesystem import make_tempfile


# MARKDOWN_ESCAPED_CHARS comes from markdown.Markdown.ESCAPED_CHARS. We don't
# want to have a dependency on markdown for rbtools, so we just copy it into
# here.
MARKDOWN_ESCAPED_CHARS = ['\\', '`', '*', '_', '{', '}', '[', ']',
                          '(', ')', '>', '#', '+', '-', '.', '!']
MARKDOWN_SPECIAL_CHARS = re.escape(r''.join(MARKDOWN_ESCAPED_CHARS))
UNESCAPE_CHARS_RE = re.compile(r'\\([%s])' % MARKDOWN_SPECIAL_CHARS)


class Patch(Command):
    """Applies a specific patch from a RB server.

    The patch file indicated by the request id is downloaded from the
    server and then applied locally."""
    name = "patch"
    author = "The Review Board Project"
    args = "<review-request-id>"
    option_list = [
        Option("-c", "--commit",
               dest="commit",
               action="store_true",
               default=False,
               help="Commit using information fetched "
                    "from the review request (Git only)."),
        Option("--diff-revision",
               dest="diff_revision",
               default=None,
               help="revision id of diff to be used as patch"),
        Option("--px",
               dest="px",
               default=None,
               help="numerical pX argument for patch"),
        Option("--print",
               dest="patch_stdout",
               action="store_true",
               default=False,
               help="print patch to stdout instead of applying"),
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

    def get_patch(self, request_id, api_root, diff_revision=None):
        """Return the diff as a string, the used diff revision and its basedir.

        If a diff revision is not specified, then this will look at the most
        recent diff.
        """
        try:
            diffs = api_root.get_diffs(review_request_id=request_id)
        except APIError, e:
            raise CommandError("Error getting diffs: %s" % e)

        # Use the latest diff if a diff revision was not given.
        # Since diff revisions start a 1, increment by one, and
        # never skip a number, the latest diff revisions number
        # should be equal to the number of diffs.
        if diff_revision is None:
            diff_revision = diffs.total_results

        try:
            diff = diffs.get_item(diff_revision)
            diff_body = diff.get_patch().data
            base_dir = diff.basedir
        except APIError:
            raise CommandError('The specified diff revision does not exist.')

        return diff_body, diff_revision, base_dir

    def apply_patch(self, repository_info, tool, request_id, diff_revision,
                    diff_file_path, base_dir):
        """Apply patch patch_file and display results to user."""
        print ("Patch is being applied from request %s with diff revision "
               " %s." % (request_id, diff_revision))
        tool.apply_patch(diff_file_path, repository_info.base_path,
                         base_dir, self.options.px)

    def _unescape_markdown(self, text):
        return UNESCAPE_CHARS_RE.sub(r'\1', text)

    def _extract_commit_message(self, review_request):
        """Returns a commit message based on the review request.

        The commit message returned contains the Summary, Description, Bugs,
        and Testing Done fields from the review request, if available.
        """
        info = []

        summary = review_request.summary

        description = review_request.description
        if review_request.rich_text:
            description = self._unescape_markdown(description)

        if not description.startswith(summary):
            info.append(summary)

        info.append(description)

        testing_done = review_request.testing_done
        if testing_done:
            if review_request.rich_text:
                testing_done = self._unescape_markdown(testing_done)

            info.append('Testing Done:\n%s' % testing_done)

        if review_request.bugs_closed:
            info.append('Bugs closed: %s'
                        % ', '.join(review_request.bugs_closed))

        info.append('Reviewed at %s' % review_request.absolute_url)

        return '\n\n'.join(info)

    def main(self, request_id):
        """Run the command."""
        repository_info, tool = self.initialize_scm_tool(
            client_name=self.options.repository_type)
        server_url = self.get_server_url(repository_info, tool)
        api_client, api_root = self.get_api(server_url)

        # Get the patch, the used patch ID and base dir for the diff
        diff_body, diff_revision, base_dir = self.get_patch(
            request_id,
            api_root,
            self.options.diff_revision)

        tmp_patch_file = make_tempfile(diff_body)
        if self.options.patch_stdout:
            print diff_body
        else:
            try:
                if tool.has_pending_changes():
                    message = 'Working directory is not clean.'

                    if not self.options.commit:
                        print 'Warning: %s' % message
                    else:
                        raise CommandError(message)
            except NotImplementedError:
                pass

            self.apply_patch(repository_info, tool, request_id, diff_revision,
                             tmp_patch_file, base_dir)

            if self.options.commit:
                try:
                    review_request = api_root.get_review_request(
                        review_request_id=request_id)
                except APIError, e:
                    raise CommandError('Error getting review request %s: %s'
                                       % (request_id, e))

                message = self._extract_commit_message(review_request)
                author = review_request.get_submitter()

                try:
                    tool.create_commmit(message, author)
                    print('Changes committed to current branch.')
                except NotImplementedError:
                    raise CommandError('--commit is not supported with %s'
                                       % tool.name)
