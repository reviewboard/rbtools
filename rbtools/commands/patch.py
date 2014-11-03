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
                    "from the review request (Git/Mercurial only)."),
        Option("-C", "--commit-no-edit",
               dest="commit_no_edit",
               action="store_true",
               default=False,
               help="Commit using information fetched "
                    "from the review request (Git/Mercurial only). "
                    "This differs from -c by not invoking the editor "
                    "to modify the commit message."),
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
        Command.server_options,
        Command.repository_options,
    ]

    def get_patch(self, request_id, api_root, diff_revision=None):
        """Return the diff as a string, the used diff revision and its basedir.

        If a diff revision is not specified, then this will look at the most
        recent diff.
        """
        try:
            diffs = api_root.get_diffs(review_request_id=request_id)
        except APIError as e:
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
            base_dir = getattr(diff, 'basedir', None) or ''
        except APIError:
            raise CommandError('The specified diff revision does not exist.')

        return diff_body, diff_revision, base_dir

    def apply_patch(self, repository_info, tool, request_id, diff_revision,
                    diff_file_path, base_dir):
        """Apply patch patch_file and display results to user."""
        print ("Patch is being applied from request %s with diff revision "
               "%s." % (request_id, diff_revision))

        result = tool.apply_patch(diff_file_path, repository_info.base_path,
                                  base_dir, self.options.px)

        if result.patch_output:
            print
            print result.patch_output.strip()
            print

        if not result.applied:
            raise CommandError(
                'Unable to apply the patch. The patch may be invalid, or '
                'there may be conflicts that could not be resolvd.')

        if result.has_conflicts:
            if result.conflicting_files:
                print ('The patch was partially applied, but there were '
                       'conflicts in:')
                print

                for filename in result.conflicting_files:
                    print '    %s' % filename

                print
            else:
                print ('The patch was partially applied, but there were '
                       'conflicts.')

            return False
        else:
            print 'Successfully applied patch.'

            return True

    def _extract_commit_message(self, review_request):
        """Returns a commit message based on the review request.

        The commit message returned contains the Summary, Description, Bugs,
        and Testing Done fields from the review request, if available.
        """
        info = []

        summary = review_request.summary
        description = review_request.description
        testing_done = review_request.testing_done

        if not description.startswith(summary):
            info.append(summary)

        info.append(description)

        if testing_done:
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
        self.setup_tool(tool, api_root=api_root)

        # Check if repository info on reviewboard server match local ones.
        repository_info = repository_info.find_server_repository_info(api_root)

        # Get the patch, the used patch ID and base dir for the diff
        diff_body, diff_revision, base_dir = self.get_patch(
            request_id,
            api_root,
            self.options.diff_revision)

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

            tmp_patch_file = make_tempfile(diff_body)
            success = self.apply_patch(repository_info, tool, request_id,
                                       diff_revision, tmp_patch_file, base_dir)

            if success and (self.options.commit or
                            self.options.commit_no_edit):
                try:
                    review_request = api_root.get_review_request(
                        review_request_id=request_id,
                        force_text_type='plain')
                except APIError as e:
                    raise CommandError('Error getting review request %s: %s'
                                       % (request_id, e))

                message = self._extract_commit_message(review_request)
                author = review_request.get_submitter()

                try:
                    tool.create_commit(message, author,
                                       not self.options.commit_no_edit)
                    print('Changes committed to current branch.')
                except NotImplementedError:
                    raise CommandError('--commit is not supported with %s'
                                       % tool.name)
