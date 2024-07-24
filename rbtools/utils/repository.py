"""Utility functions for working with repositories."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Union

from rbtools.api.errors import APIError

if TYPE_CHECKING:
    from rbtools.api.capabilities import Capabilities
    from rbtools.api.resource import ItemResource, RootResource
    from rbtools.clients.base.repository import RepositoryInfo
    from rbtools.clients.base.scmclient import BaseSCMClient


def get_repository_resource(
    api_root: RootResource,
    tool: Optional[BaseSCMClient] = None,
    repository_name: Optional[str] = None,
    repository_paths: Optional[Union[str, list[str]]] = None,
    capabilities: Optional[Capabilities] = None,
) -> tuple[Optional[ItemResource], Optional[ItemResource]]:
    """Return the API resource for the matching repository on the server.

    Version Added:
        3.0

    Version Changed:
        5.0.1:
        Added the ``capabilities`` argument.

    Args:
        api_root (rbtools.api.resource.RootResource):
            The root resource for the API.

        tool (rbtools.clients.base.BaseSCMClient, optional):
            The SCM client corresponding to the local working directory.

        repository_name (str, optional):
            An explicit repository name provided by the local configuration.

        repository_paths (list or str, optional):
            A list of potential paths to match for the repository.

        capabilities (rbtools.api.capabilities.Capabilities, optional):
            The capabilities fetched from the server.

    Returns:
        tuple of rbtools.api.resource.ItemResource:
        A 2-tuple of :py:class:`~rbtools.api.resource.ItemResource`. The first
        item is the matching repository, and the second is the repository info
        resource.
    """
    def _get_info(repository):
        # Many repository types don't implement the repository info
        # endpoint. In those cases we just want to return None.
        try:
            return repository.get_info()
        except APIError as e:
            if e.error_code != 209:
                raise

        return None

    query = {
        'only_fields': 'id,name,mirror_path,path',
        'only_links': 'info,diff_file_attachments',
    }

    if tool:
        server_tool_names = tool.get_server_tool_names(capabilities)

        if server_tool_names:
            query['tool'] = server_tool_names

    if repository_name:
        query['name'] = repository_name
    elif repository_paths:
        if not isinstance(repository_paths, list):
            repository_paths = [repository_paths]

        query['path'] = ','.join(repository_paths)

    repositories = api_root.get_repositories(**query)

    # Ideally filtering based on name or path returned us a single result. In
    # that case we can shortcut everything else.
    if repositories.total_results == 1:
        repository = repositories[0]
        return repository, _get_info(repository)

    # It's not uncommon with some SCMs for the server to have a different
    # configured path than the client. In that case, we want to try again
    # without filtering by path, and ask each tool to match based on other
    # conditions.
    if 'path' in query:
        query.pop('path', None)

        all_repositories = api_root.get_repositories(**query)
    else:
        all_repositories = repositories

    if all_repositories.total_results > 0 and tool:
        repository, info = tool.find_matching_server_repository(
            all_repositories)

        if repository:
            return repository, info

    # Now go back to the path-based query and see if there were multiple
    # matching repositories. In that case, return the first one and hope for
    # the best.
    if repositories.total_results > 1:
        repository = repositories[0]
        return repository, _get_info(repository)

    # If we reach this point, we really don't know. If the repository exists on
    # the server, nothing we tried to match with found it.
    return None, None


def get_repository_id(
    repository_info: RepositoryInfo,
    api_root: RootResource,
    repository_name: Optional[str] = None,
) -> Optional[int]:
    """Return the ID of a repository from the server.

    This will look up all accessible repositories on the server and try to
    find the ID of one that matches the provided repository information.

    Args:
        repository_info (rbtools.clients.base.repository.RepositoryInfo):
            The scanned repository information.

        api_root (rbtools.api.resource.RootResource):
            The root resource for the API.

        repository_name (str, optional):
            An explicit repository name provided by local configuration.

    Returns:
        int:
        The ID of the repository, or ``None`` if not found.
    """
    repository = get_repository_resource(
        api_root,
        tool=None,
        repository_name=repository_name,
        repository_paths=repository_info.path)[0]

    if repository:
        return repository.id

    return None
