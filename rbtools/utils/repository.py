"""Utility functions for working with repositories."""

from __future__ import unicode_literals

from rbtools.api.errors import APIError


def get_repository_resource(api_root,
                            tool=None,
                            repository_name=None,
                            repository_paths=None):
    """Return the API resource for the matching repository on the server.

    Version Added:
        3.0

    Args:
        api_root (rbtools.api.resource.RootResource):
            The root resource for the API.

        tool (rbtools.clients.SCMClient, optional):
            The SCM client corresponding to the local working directory.

        repository_name (unicode, optional):
            An explicit repository name provided by the local configuration.

        repository_paths (list or unicode, optional):
            A list of potential paths to match for the repository.

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
        'only_links': 'info',
    }

    if tool and tool.server_tool_names:
        query['tool'] = tool.server_tool_names

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
    query.pop('path', None)

    all_repositories = api_root.get_repositories(**query)

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


def get_repository_id(repository_info, api_root, repository_name=None):
    """Return the ID of a repostiory from the server.

    This will look up all accessible repositories on the server and try to
    find the ID of one that matches the provided repository information.

    Args:
        repository_info (rbtools.clients.RepositoryInfo):
            The scanned repository information.

        api_root (rbtools.api.resource.RootResource):
            The root resource for the API.

        repository_name (unicode, optional):
            An explicit repository name provided by local configuration.

    Returns:
        int:
        The ID of the repository, or ``None`` if not found.
    """
    repository, info = get_repository_resource(
        api_root,
        tool=None,
        repository_name=repository_name,
        repository_paths=repository_info.path)

    if repository:
        return repository.id

    return None
