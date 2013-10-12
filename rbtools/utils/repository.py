def get_repository_id(repository_info, api_root, repository_name=None):
    """Get the repository ID from the server.

    This will compare the paths returned by the SCM client
    with those on the server, and return the id of the first
    match.
    """
    detected_paths = repository_info.path

    if not isinstance(detected_paths, list):
        detected_paths = [detected_paths]

    repositories = api_root.get_repositories()

    try:
        while True:
            for repo in repositories:
                if (repo.path in detected_paths or
                    repo.name == repository_name):
                    return repo.id

            repositories = repositories.get_next()
    except StopIteration:
        return None
