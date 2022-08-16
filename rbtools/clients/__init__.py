"""Support for interfacing with source code management systems.

This provides support for creating, looking up, and registering SCM client
integrations, enabling RBTools to interact with local source code repositories
and communicate on their behalf to Review Board.

This particular module provides forwarding imports for:

.. autosummary::
   :nosignatures:

   ~rbtools.clients.base.patch.PatchAuthor
   ~rbtools.clients.base.patch.PatchResult
   ~rbtools.clients.base.repository.RepositoryInfo
   ~rbtools.clients.base.scmclient.BaseSCMClient

As well as some (soon to be legacy) utility functions and classes.

Version Changed:
    4.0:
    * Moved and renamed
      :py:class:`rbtools.clients.base.scmclient.BaseSCMClient` and added a
      forwarding import and temporary legacy class.

    * Moved :py:class:`~rbtools.clients.base.repository.RepositoryInfo` and
      added a forwarding import.
"""

from __future__ import unicode_literals

import logging
import os
import sys

import pkg_resources
import six

from rbtools.clients.base.patch import PatchAuthor, PatchResult
from rbtools.clients.base.repository import RepositoryInfo
from rbtools.clients.base.scmclient import BaseSCMClient
from rbtools.deprecation import RemovedInRBTools50Warning


# The clients are lazy loaded via load_scmclients()
SCMCLIENTS = None


class SCMClient(BaseSCMClient):
    """A base representation of an SCM tool.

    Deprecated:
        4.0:
        This has been moved to
        :py:class:`rbtools.clients.base.scmclient.BaseSCMClient`. Callers
        should updated to inherit from this.

        This legacy class will be removed in RBTools 5.0.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the client.

        Args:
            *args (tuple):
                Positional arguments to pass to the parent class.

            **kwargs (tuple):
                Keyword arguments to pass to the parent class.
        """
        RemovedInRBTools50Warning.warn(
            '%s should be updated to inherit from %s instead of %s. This '
            'will be required starting in RBTools 5.0.'
            % (type(self).__name__,
               BaseSCMClient.__name__,
               SCMClient.__name__))

        super(SCMClient, self).__init__(*args, **kwargs)


def load_scmclients(config, options):
    """Load the available SCM clients.

    Args:
        config (dict):
            The loaded user config.

        options (argparse.Namespace):
            The parsed command line arguments.
    """
    global SCMCLIENTS

    SCMCLIENTS = {}

    for ep in pkg_resources.iter_entry_points(group='rbtools_scm_clients'):
        try:
            client = ep.load()(config=config, options=options)
            client.entrypoint_name = ep.name
            SCMCLIENTS[ep.name] = client
        except Exception:
            logging.exception('Could not load SCM Client "%s"', ep.name)


def scan_usable_client(config, options, client_name=None):
    """Scan for a usable SCMClient.

    Args:
        config (dict):
            The loaded user config.

        options (argparse.Namespace):
            The parsed command line arguments.

        client_name (unicode, optional):
            A specific client name, which can come from the configuration. This
            can be used to disambiguate if there are nested repositories, or to
            speed up detection.

    Returns:
        tuple:
        A 2-tuple, containing the repository info structure and the tool
        instance.
    """
    repository_info = None
    tool = None

    # TODO: We should only load all of the scm clients if the client_name
    # isn't provided.
    if SCMCLIENTS is None:
        load_scmclients(config, options)

    if client_name:
        if client_name not in SCMCLIENTS:
            logging.error('The provided repository type "%s" is invalid.',
                          client_name)
            sys.exit(1)
        else:
            scmclients = {
                client_name: SCMCLIENTS[client_name]
            }
    else:
        scmclients = SCMCLIENTS

    # First go through and see if any repositories are configured in
    # remote-only mode. For example, SVN can post changes purely with a remote
    # URL and no working directory.
    for name, tool in six.iteritems(scmclients):
        if tool.is_remote_only():
            break
    else:
        tool = None

    candidate_tool_names = []

    # Now scan through the repositories to find any local working directories.
    # If there are multiple repositories which appear to be active in the CWD,
    # choose the deepest and emit a warning.
    if tool is None:
        candidate_repos = []

        for name, tool in six.iteritems(scmclients):
            candidate_tool_names.append(tool.name)

            logging.debug('Checking for a %s repository...', tool.name)
            local_path = tool.get_local_path()

            if local_path:
                candidate_repos.append((local_path, tool))

        if len(candidate_repos) == 1:
            tool = candidate_repos[0][1]
        elif candidate_repos:
            logging.debug('Finding deepest repository of multiple matching '
                          'repository types.')

            deepest_repo_len = 0
            deepest_repo_tool = None
            deepest_local_path = None
            found_multiple = False

            for local_path, tool in candidate_repos:
                if len(os.path.normpath(local_path)) > deepest_repo_len:
                    if deepest_repo_tool is not None:
                        found_multiple = True

                    deepest_repo_len = len(local_path)
                    deepest_repo_tool = tool
                    deepest_local_path = local_path

            if found_multiple:
                logging.warning('Multiple matching repositories were found. '
                                'Using %s repository at %s.',
                                tool.name, deepest_local_path)
                logging.warning('')
                logging.warning('Define REPOSITORY_TYPE in .reviewboardrc if '
                                'you wish to use a different repository.')

            tool = deepest_repo_tool
    else:
        candidate_tool_names.append(tool.name)

    repository_info = tool and tool.get_repository_info()

    if repository_info is None:
        if client_name:
            logging.error('A %s repository was not detected in the current '
                          'directory.',
                          client_name)
        else:
            repository_url = getattr(options, 'repository_url', None)

            if repository_url:
                logging.error('A supported repository was not found at %s',
                              repository_url)
            else:
                logging.error('A supported repository was not found in the '
                              'the current directory or any parent directory.')
                logging.error('')
                logging.error('The following types of repositories were '
                              'tried: %s',
                              ', '.join(sorted(candidate_tool_names)))

            logging.error('')
            logging.error('You may need to set up a .reviewboardrc file '
                          'with REPOSITORY_NAME, REPOSITORY_TYPE, and '
                          'REVIEWBOARD_URL, if one is not already set up. '
                          'This can be done by running `rbt setup-repo` and '
                          'following the instructions. This file should then '
                          'be committed to the repository for everyone to '
                          'use.')

        sys.exit(1)

    # Verify that options specific to an SCM Client have not been mis-used.
    if (getattr(options, 'change_only', False) and
        not tool.supports_changesets):
        logging.error('The --change-only option is not valid for the '
                      'current SCM client.\n')
        sys.exit(1)

    if (getattr(options, 'parent_branch', None) and
        not tool.supports_parent_diffs):
        logging.error('The --parent option is not valid for the '
                      'current SCM client.')
        sys.exit(1)

    from rbtools.clients.perforce import PerforceClient

    if (not isinstance(tool, PerforceClient) and
        (getattr(options, 'p4_client', None) or
         getattr(options, 'p4_port', None))):
        logging.error('The --p4-client and --p4-port options are not '
                      'valid for the current SCM client.\n')
        sys.exit(1)

    return repository_info, tool


__all__ = [
    'BaseSCMClient',
    'PatchAuthor',
    'PatchResult',
    'RepositoryInfo',
    'SCMCLIENTS',
    'SCMClient',
    'load_scmclients',
    'scan_usable_client',
]


__autodoc_excludes__ = [
    'BaseSCMClient',
    'PatchAuthor',
    'PatchResult',
    'RepositoryInfo',
]
