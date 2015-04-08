from __future__ import unicode_literals


def get_repository_id(repository_info, api_root, repository_name=None):
    """Get the repository ID from the server.

    This will compare the paths returned by the SCM client
    with those on the server, and return the id of the first
    match.
    """
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
