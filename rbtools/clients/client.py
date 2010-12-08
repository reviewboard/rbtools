import os
import re
import socket
import sys
import urllib

from rbtools.api.utilities import RBUtilities


class Client(object):
    """Base Client class

    Client is responsible for dealing with local repositories. It collects
    and stores info about the repository (location, SCM type, etc.), as well as
    creating diffs.
    """

    url = None

    def __init__(self, url=None, util=RBUtilities()):
        self.url = url
        self.util = util

    def set_url(self, url=None):
        self.url = url

    def get_info(self):
        """Returns information about the repository

        This is the base version, and doesn't return anything
        """
        return None

    def diff(self, args):
        """Returns the generated diff and optional parent diff for this
        repository.

        The returned tuple is (diff_string, parent_diff_string)
        """
        return (None, None)


class Repository(object):
    """A representation of a source code repository."""

    def __init__(self, path=None, base_path=None, supports_changesets=False,
                 supports_parent_diffs=False):
        self.path = path
        self.base_path = base_path
        self.supports_changesets = supports_changesets
        self.supports_parent_diffs = supports_parent_diffs

    def __str__(self):
        return "Path: %s, Base path: %s, Supports changesets: %s" % \
            (self.path, self.base_path, self.supports_changesets)

    def set_base_path(self, base_path):

        if not base_path.startswith('/'):
            base_path = '/' + base_path
        self.base_path = base_path

    def find_server_repository_info(self, server):
        """
        Try to find the repository from the list of repositories on the server.
        For Subversion, this could be a repository with a different URL. For
        all other clients, this is a noop.
        """
        return self
