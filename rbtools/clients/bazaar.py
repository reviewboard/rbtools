import os
import re

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.utils.checks import check_install
from rbtools.utils.process import execute


class BazaarClient(SCMClient):
    """
    Bazaar client wrapper that fetches repository information and generates
    compatible diffs.

    The :class:`RepositoryInfo` object reports whether the repository supports
    parent diffs (every branch with a parent supports them).
    """

    name = 'Bazaar'

    # Regular expression that matches the path to the current branch.
    #
    # For branches with shared repositories, Bazaar reports
    # "repository branch: /foo", but for standalone branches it reports
    # "branch root: /foo".
    BRANCH_REGEX = (r'\w*(repository branch|branch root|checkout root): '
                    r'(?P<branch_path>.+)$')

    def get_repository_info(self):
        """
        Find out information about the current Bazaar branch (if any) and
        return it.
        """
        if not check_install("bzr help"):
            return None

        bzr_info = execute(["bzr", "info"], ignore_errors=True)

        if "ERROR: Not a branch:" in bzr_info:
            # This is not a branch:
            repository_info = None
        else:
            # This is a branch, let's get its attributes:
            branch_match = re.search(self.BRANCH_REGEX, bzr_info, re.MULTILINE)

            path = branch_match.group("branch_path")
            if path == ".":
                path = os.getcwd()

            repository_info = RepositoryInfo(
                path=path,
                base_path="/",    # Diffs are always relative to the root.
                supports_parent_diffs=True)

        return repository_info

    def diff(self, files):
        """
        Return the diff of this branch with respect to its parent and set
        the summary and description is required.
        """
        files = files or []

        if self.options.parent_branch:
            revision_range = "ancestor:%s.." % self.options.parent_branch
        else:
            revision_range = "submit:.."

        # Getting the diff for the changes in the current branch:
        diff = self._get_range_diff(revision_range, files)
        self._set_summary("-1")
        self._set_description(revision_range)

        return {
            'diff': diff,
        }

    def diff_between_revisions(self, revision_range, files, repository_info):
        """
        Return the diff for the two revisions in ``revision_range`` and set
        the summary and description is required.
        """
        diff = self._get_range_diff(revision_range, files)

        # Revision ranges in Bazaar and separated with dots, not colons:
        last_revision = revision_range.split("..")[1]
        self._set_summary(last_revision)
        self._set_description(revision_range)

        return {
            'diff': diff,
        }

    def _get_range_diff(self, revision_range, files):
        """
        Return the diff for the two revisions in ``revision_range``.
        """
        diff_cmd = ["bzr", "diff", "-q", "-r", revision_range] + files
        diff = execute(diff_cmd, ignore_errors=True)
        diff = diff or None

        return diff

    def _set_summary(self, revision):
        """
        Set the summary to the message of ``revision`` if asked to guess it.
        """
        if self.options.guess_summary and not self.options.summary:
            self.options.summary = self._extract_summary(revision)

    def _set_description(self, revision_range=None):
        """
        Set the description to the changelog of ``revision_range`` if asked to
        guess it.
        """
        if self.options.guess_description and not self.options.description:
            self.options.description = self._extract_description(
                revision_range)

    def _extract_summary(self, revision):
        """Return the commit message for ``revision``."""
        # `bzr log --line' returns the log in the format:
        #   {revision-number}: {committer-name} {commit-date} {commit-message}
        # So we should ignore everything after the date (YYYY-MM-DD).
        log_message = execute(
            ["bzr", "log", "-r", revision, "--line"]).rstrip()
        log_message_match = re.search(r"\d{4}-\d{2}-\d{2}", log_message)
        truncated_characters = log_message_match.end() + 1

        summary = log_message[truncated_characters:]

        return summary

    def _extract_description(self, revision_range=None):
        command = ["bzr"]

        # If there is no revision range specified, that means we need the logs
        # of all the outgoing changes:
        if revision_range:
            command.extend(["log", "-r", revision_range])
        else:
            command.extend(["missing", "-q", "--mine-only"])

        # We want to use the "short" output format, where all the logs are
        # separated with hyphens:
        command.append("--short")

        changelog = execute(command, ignore_errors=True).rstrip()

        return changelog
