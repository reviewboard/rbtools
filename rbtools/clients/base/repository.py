"""Classes for representing source code repositories.

Version Added:
    4.0
"""

from __future__ import unicode_literals

import logging

from rbtools.deprecation import RemovedInRBTools40Warning


class RepositoryInfo(object):
    """A representation of a source code repository.

    Version Changed:
        4.0:
        * Moved from :py:mod:`rbtools.clients`. That module still provides
          compatibility imports.
    """

    def __init__(self, path=None, base_path=None, local_path=None, name=None,
                 supports_changesets=False, supports_parent_diffs=False):
        """Initialize the object.

        Version Changed:
            3.0:
            The ``name`` argument was deprecated. Clients which allow
            configuring the repository name in metadata should instead
            implement :py:meth:`get_repository_name`.

            The ``supports_changesets`` and ``supports_parent_diffs`` arguments
            were deprecated. Clients which need these should instead set
            :py:attr:`supports_changesets` and :py:attr:`supports_parent_diffs`
            on themselves.

        Args:
            path (unicode or list of unicode, optional):
                The path of the repository, or a list of possible paths
                (with the primary one appearing first).

            base_path (unicode, optional):
                The relative path between the current working directory and the
                repository root.

            local_path (unicode, optional):
                The local filesystem path for the repository. This can
                sometimes be the same as ``path``, but may not be (since that
                can contain a remote repository path).

            name (unicode, optional):
                The name of the repository, as configured on Review Board.
                This might be available through some repository metadata.

            supports_changesets (bool, optional):
                Whether the repository type supports changesets that store
                their data server-side.

            supports_parent_diffs (bool, optional):
                Whether the repository type supports posting changes with
                parent diffs.
        """
        self.path = path
        self.base_path = base_path
        self.local_path = local_path
        self.supports_changesets = supports_changesets
        self.supports_parent_diffs = supports_parent_diffs
        logging.debug('Repository info: %s', self)

        if name is not None:
            RemovedInRBTools40Warning.warn(
                'The name argument to RepositoryInfo has been deprecated and '
                'will be removed in RBTools 4.0. Implement '
                'get_repository_name instead.')

        if supports_changesets:
            # We can't make this a soft deprecation so raise an error instead.
            # Users with custom SCMClient implementations will need to update
            # their code when moving to RBTools 3.0+.
            raise Exception(
                'The supports_changesets argument to RepositoryInfo has been '
                'deprecated and will be removed in RBTools 4.0. Clients which '
                'rely on this must instead set the supports_changesets '
                'attribute on the class.')

        if supports_parent_diffs:
            # We can't make this a soft deprecation so raise an error instead.
            # Users with custom SCMClient implementations will need to update
            # their code when moving to RBTools 3.0+.
            raise Exception(
                'The supports_changesets argument to RepositoryInfo has been '
                'deprecated and will be removed in RBTools 4.0. Clients which '
                'rely on this must instead set the supports_parent_diffs '
                'attribute on the class.')

    def __str__(self):
        """Return a string representation of the repository info.

        Returns:
            unicode:
            A loggable representation.
        """
        return 'Path: %s, Base path: %s' % (self.path, self.base_path)

    def set_base_path(self, base_path):
        """Set the base path of the repository info.

        Args:
            base_path (unicode):
                The relative path between the current working directory and the
                repository root.
        """
        if not base_path.startswith('/'):
            base_path = '/' + base_path

        logging.debug('changing repository info base_path from %s to %s',
                      self.base_path, base_path)
        self.base_path = base_path

    def update_from_remote(self, repository, info):
        """Update the info from a remote repository.

        Subclasses may override this to fetch additional data from the server.

        Args:
            repository (rbtools.api.resource.ItemResource):
                The repository resource.

            info (rbtools.api.resource.ItemResource):
                The repository info resource.
        """
        self.path = repository.path

    def find_server_repository_info(self, server):
        """Find the repository from the list of repositories on the server.

        For Subversion, this could be a repository with a different URL. For
        all other clients, this is a noop.

        Deprecated:
            3.0:
            Commands which need to use the remote repository, or need data from
            the remote repository such as the base path, should set
            :py:attr:`needs_repository`.

        Args:
            server (rbtools.api.resource.RootResource):
                The root resource for the Review Board server.

        Returns:
            RepositoryInfo:
            The server-side information for this repository.
        """
        RemovedInRBTools40Warning.warn(
            'The find_server_repository_info method is deprecated, and will '
            'be removed in RBTools 4.0. If you need to access the remote '
            'repository, set the needs_repository attribute on your Command '
            'subclass.')
        return self
