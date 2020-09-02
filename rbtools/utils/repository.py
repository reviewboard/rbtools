"""Utility functions for working with repositories."""

from __future__ import unicode_literals


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
            An explicit repository name provided by local configuration. If
            this is not provided, :py:attr:`RepositoryInfo.name
            <rbtools.clients.RepositoryInfo.name>` will be used, if available.

    Returns:
        int:
        The ID of the repository, or ``None`` if not found.
    """
    if repository_name is None:
        repository_name = repository_info.name

    detected_paths = repository_info.path

    if not isinstance(detected_paths, list):
        detected_paths = [detected_paths]

    repositories = api_root.get_repositories(
        only_fields='id,name,mirror_path,path',
        only_links='')

    for repo in repositories.all_items:
        # NOTE: Versions of Review Board prior to 1.7.19 didn't include a
        #       'mirror_path' parameter, so we have to conditionally fetch it.
        if (repo.name == repository_name or
            repo.path in detected_paths or
            getattr(repo, 'mirror_path', None) in detected_paths):
            return repo.id

    return None
