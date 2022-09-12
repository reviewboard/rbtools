"""Classes for representing source code repositories.

Version Added:
    4.0
"""

from typing import List, Optional, Union

from rbtools.api.resource import ItemResource
from rbtools.deprecation import (RemovedInRBTools50Warning,
                                 deprecate_non_keyword_only_args)


class RepositoryInfo:
    """A representation of a source code repository.

    Version Changed:
        4.0:
        * Moved from :py:mod:`rbtools.clients`. That module still provides
          compatibility imports.

        * Removed the deprecated :py:attr:`name`,
          :py:attr:`supports_changesets`, and
          :py:attr:`supports_parent_diffs` attributes.

        * Removed the deprecated :py:meth:`find_server_repository_info`
          method.
    """

    #: The path of the repository, or a list of possible paths.
    #:
    #: This may be empty.
    #:
    #: Type:
    #:     str or list of str
    path: Optional[Union[str, List[str]]]

    #: Relative path between the working directory and repository root.
    #:
    #: This is dependent on the type of SCM, and may be empty.
    #:
    #: Type:
    #:     str
    base_path: Optional[str]

    #: The local filesystem path for the repository.
    #:
    #: This can sometimes be the same as :py:attr:`path`, but may not be
    #: (since that can contain a remote repository path).
    #:
    #: Type:
    #:     str
    local_path: Optional[str]

    @deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
    def __init__(
        self,
        *,
        path: Optional[Union[str, List[str]]] = None,
        base_path: Optional[str] = None,
        local_path: Optional[str] = None,
    ) -> None:
        """Initialize the object.

        Version Changed:
            4.0:
            * The ``name``, ``supports_changesets``, and
              ``supports_parent_diffs`` arguments have been removed.

            * All arguments must be passed in as keyword arguments. This will
              be required in RBTools 5.

        Version Changed:
            3.0:
            * The ``name`` argument was deprecated. Clients which allow
              configuring the repository name in metadata should instead
              implement :py:meth:`get_repository_name`.

            * The ``supports_changesets`` and ``supports_parent_diffs``
              arguments were deprecated. Clients which need these should
              instead set :py:attr:`supports_changesets` and
              :py:attr:`supports_parent_diffs` on themselves.

        Args:
            path (str or list of str, optional):
                The path of the repository, or a list of possible paths
                (with the primary one appearing first).

                This can be empty by default, if the caller expects to later
                populate it with :py:meth:`update_from_remote`.

            base_path (str, optional):
                The relative path between the current working directory and the
                repository root.

            local_path (str, optional):
                The local filesystem path for the repository. This can
                sometimes be the same as ``path``, but may not be (since that
                can contain a remote repository path).

            name (str, optional):
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

    def __repr__(self) -> str:
        """Return a string representation of the repository info.

        Returns:
            str:
            The string representation.
        """
        return (
            '<%s(path=%r, base_path=%r, local_path=%r)>'
            % (type(self).__name__,
               self.path,
               self.base_path,
               self.local_path)
        )

    def __str__(self) -> str:
        """Return a human-readable representation of the repository info.

        Returns:
            str:
            The string representation.
        """
        return (
            'Path: %s, Base path: %s, Local path: %s'
            % (self.path, self.base_path, self.local_path)
        )

    def set_base_path(
        self,
        base_path: str,
    ) -> None:
        """Set the base path of the repository info.

        Args:
            base_path (str):
                The relative path between the current working directory and the
                repository root.
        """
        if not base_path.startswith('/'):
            base_path = '/%s' % base_path

        self.base_path = base_path

    def update_from_remote(
        self,
        repository: ItemResource,
        info: ItemResource,
    ) -> None:
        """Update the info from a remote repository.

        Subclasses may override this to fetch additional data from the server.

        By defaut, this simply sets the path based on the ``repository``.

        Args:
            repository (rbtools.api.resource.ItemResource):
                The repository resource.

            info (rbtools.api.resource.ItemResource, unused):
                The repository info resource.

                This is not used by default, but is available to callers.
        """
        self.path = repository.path
