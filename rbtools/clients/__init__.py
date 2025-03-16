"""Support for interfacing with source code management systems.

This provides support for creating, looking up, and registering SCM client
integrations, enabling RBTools to interact with local source code repositories
and communicate on their behalf to Review Board.

This particular module provides forwarding imports for:

.. autosummary::
   :nosignatures:

   rbtools.diffs.patches.PatchAuthor
   rbtools.diffs.patches.PatchResult
   rbtools.clients.base.registry.scmclient_registry
   rbtools.clients.base.repository.RepositoryInfo
   rbtools.clients.base.scmclient.BaseSCMClient

As well as some (soon to be legacy) utility functions and classes.

Version Changed:
    5.1:
    * :py:class:`~rbtools.diffs.patches.PatchAuthor` and `
      :py:class:`~rbtools.diffs.patches.PatchResult` should now be imported
      from :py:mod:`rbtools.diffs.patches`.

Version Changed:
    4.0:
    * Moved and renamed
      :py:class:`rbtools.clients.base.scmclient.BaseSCMClient` and added a
      forwarding import and temporary legacy class.

    * Moved :py:class:`~rbtools.clients.base.repository.RepositoryInfo` and
      added a forwarding import.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional, TYPE_CHECKING

from housekeeping import ClassMovedMixin

from rbtools.clients.base.registry import scmclient_registry
from rbtools.clients.base.repository import RepositoryInfo
from rbtools.clients.base.scmclient import BaseSCMClient
from rbtools.deprecation import RemovedInRBTools70Warning
from rbtools.diffs import patches

if TYPE_CHECKING:
    import argparse
    from rbtools.config import RBToolsConfig


# The clients are lazy loaded via load_scmclients()
SCMCLIENTS = None


class PatchAuthor(ClassMovedMixin,
                  patches.PatchAuthor,
                  warning_cls=RemovedInRBTools70Warning):
    """The author of a patch or commit.

    This has moved to :py:class:`rbtools.diffs.patches.PatchAuthor`. See that
    class for documentation.

    Deprecated:
        5.1:
        This will be removed in RBTools 7.
    """


class PatchResult(ClassMovedMixin,
                  patches.PatchResult,
                  warning_cls=RemovedInRBTools70Warning):
    """The result of a patch operation.

    This has moved to :py:class:`rbtools.diffs.patches.PatchResult`. See that
    class for documentation.

    Deprecated:
        5.1:
        This will be removed in RBTools 7.
    """


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

    for scmclient_cls in scmclient_registry:
        try:
            scmclient = scmclient_cls(config=config,
                                      options=options)
            SCMCLIENTS[scmclient_cls.scmclient_id] = scmclient
        except Exception:
            logging.exception('Could not load SCM Client "%s"',
                              scmclient_cls.scmclient_id)


def scan_usable_client(
    config: RBToolsConfig,
    options: argparse.Namespace,
    client_name: Optional[str] = None,
) -> tuple[Optional[RepositoryInfo], Optional[BaseSCMClient]]:
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
    from rbtools.utils.source_tree import scan_scmclients_for_path

    scmclient_ids = []

    if client_name:
        if client_name in scmclient_registry:
            scmclient_ids.append(client_name)
        else:
            logging.error('The provided repository type "%s" is invalid.',
                          client_name)
            sys.exit(1)

    repository_url = getattr(options, 'repository_url', None)
    scmclient_errors = {}

    # Now scan through the repositories to find any local working directories.
    # If there are multiple repositories which appear to be active in the CWD,
    # choose the deepest and emit a warning.
    scan_result = scan_scmclients_for_path(
        path=os.getcwd(),
        check_remote=bool(repository_url),
        scmclient_ids=scmclient_ids,
        scmclient_kwargs={
            'config': config,
            'options': options,
        })

    if scan_result.found:
        scmclient = scan_result.scmclient

        assert scmclient is not None
    else:
        dep_errors = scan_result.dependency_errors

        if client_name:
            if client_name in dep_errors:
                logging.error("The current %s repository can't be used. %s",
                              client_name, dep_errors[client_name])
                logging.error('')
                logging.error("Make sure they're installed and try again.")
            else:
                logging.error('A %s repository was not detected in the '
                              'current directory.',
                              client_name)
        else:
            scmclient_errors = scan_result.scmclient_errors
            candidate_scmclient_names: list[str] = [
                _candidate.scmclient.name or _candidate.scmclient.scmclient_id
                for _candidate in scan_result.candidates
            ]

            if repository_url:
                logging.error('A supported repository was not found at %s',
                              repository_url)
            else:
                logging.error('A supported repository was not found in the '
                              'the current directory or any parent directory.')

            if candidate_scmclient_names:
                logging.error('')
                logging.error('The following types of repositories were '
                              'tried: %s',
                              ', '.join(sorted(candidate_scmclient_names)))

            if dep_errors:
                logging.error('')
                logging.error("The following were missing dependencies:")
                logging.error('')

                for name, dep_error in sorted(dep_errors.items(),
                                              key=lambda pair: pair[0]):
                    logging.error('* %s: %s', name, dep_error)

            if scmclient_errors:
                logging.error('')
                logging.error('The following encountered unexpected '
                              'errors: %s',
                              ', '.join(sorted(scmclient_errors.keys())))

            logging.error('')
            logging.error('You may need to set up a .reviewboardrc file '
                          'with REPOSITORY_NAME, REPOSITORY_TYPE, and '
                          'REVIEWBOARD_URL, if one is not already set up. '
                          'This can be done by running `rbt setup-repo` and '
                          'following the instructions. This file should then '
                          'be committed to the repository for everyone to '
                          'use.')

        sys.exit(1)

    # Verify that options specific to an SCM Client have not been misused.
    if (getattr(options, 'change_only', False) and
        not scmclient.supports_changesets):
        logging.error('The --change-only option is not valid for the '
                      'current SCM client.\n')
        sys.exit(1)

    if (getattr(options, 'parent_branch', None) and
        not scmclient.supports_parent_diffs):
        logging.error('The --parent option is not valid for the '
                      'current SCM client.')
        sys.exit(1)

    from rbtools.clients.perforce import PerforceClient

    if (not isinstance(scmclient, PerforceClient) and
        (getattr(options, 'p4_client', None) or
         getattr(options, 'p4_port', None))):
        logging.error('The --p4-client and --p4-port options are not '
                      'valid for the current SCM client.\n')
        sys.exit(1)

    assert scan_result.repository_info is not None

    return scan_result.repository_info, scmclient


__all__ = [
    'BaseSCMClient',
    'PatchAuthor',
    'PatchResult',
    'RepositoryInfo',
    'SCMCLIENTS',
    'load_scmclients',
    'scan_usable_client',
    'scmclient_registry',
]


__autodoc_excludes__ = [
    'BaseSCMClient',
    'PatchAuthor',
    'PatchResult',
    'RepositoryInfo',
    'scmclient_registry',
]
