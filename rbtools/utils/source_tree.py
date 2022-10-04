"""Utilities for scanning and working with source trees.

Version Added:
    4.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from typing_extensions import TypeAlias

from rbtools.clients import (BaseSCMClient,
                             RepositoryInfo,
                             scmclient_registry)
from rbtools.clients.errors import SCMClientDependencyError
from rbtools.utils.filesystem import chdir


logger = logging.getLogger(__name__)


@dataclass
class SCMClientScanCandidate:
    """A candidate found when scanning a source tree for SCMs.

    Version Added:
        4.0
    """

    #: The SCMClient that was matched.
    #:
    #: Type:
    #:     rbtools.clients.base.scmclient.BaseSCMClient
    scmclient: BaseSCMClient

    #: The local path on the filesystem for the match.
    #:
    #: This may be ``None``.
    #:
    #: Type:
    #:     str
    local_path: Optional[str] = None


@dataclass
class SCMClientScanResult:
    """The result of a scan for SCMs in a tree.

    Version Added:
        4.0
    """

    #: The matching SCMClient, if found.
    #:
    #: This will be ``None`` if no suitable SCMClient was found for the tree.
    #:
    #: Type:
    #:     rbtools.clients.base.scmclient.BaseSCMClient
    scmclient: Optional[BaseSCMClient]

    #: The matching local path on the filesystem, if found.
    #:
    #: This will be ``None`` if no suitable SCMClient was found for the tree,
    #: or if a repository was matched as remote-only.
    #:
    #: Type:
    #:     str
    local_path: Optional[str]

    #: The matching repository information, if found.
    #:
    #: This will be ``None`` if no suitable SCMClient was found for the tree.
    #:
    #: Type:
    #:     rbtools.clients.base.repository.RepositoryInfo
    repository_info: Optional[RepositoryInfo]

    #: A list of all possible candidates for the tree.
    #:
    #: The matching candidate will be a part of this list, if one was found.
    #:
    #: Type:
    #:     list of SCMClientScanCandidate
    candidates: SCMClientScanCandidateList

    #: SCMClient dependency errors encountered during the scan.
    #:
    #: Each key will correspond to the :py:attr:`BaseSCMClient.scmclient_id
    #: <rbtools.clients.base.scmclient.BaseSCMClient.scmclient_id>` of the
    #: erroring SCMClient, and each value will be a
    #: :py:class:`~rbtools.clients.errors.SCMClientDependencyError` containing
    #: further details.
    #:
    #: Type:
    #:     dict
    dependency_errors: SCMClientScanDependencyErrors

    #: Unexpected SCMClient errors encountered during the scan.
    #:
    #: Each key will correspond to the :py:attr:`BaseSCMClient.scmclient_id
    #: <rbtools.clients.base.scmclient.BaseSCMClient.scmclient_id>` of the
    #: erroring SCMClient, and each value will be an :py:exc:`Exception`
    #: subclass.
    #:
    #: Type:
    #:     dict
    scmclient_errors: SCMClientScanErrors

    @property
    def found(self) -> bool:
        """Whether a matching SCMClient was found.

        Type:
            bool
        """
        return self.scmclient is not None


def _get_or_create_scmclient_for_scan(
    *,
    scmclient_cls: type[BaseSCMClient],
    scmclient_kwargs: dict[str, Any],
    cache: _SCMClientCache,
    errors: SCMClientScanErrors,
    dep_errors: SCMClientScanDependencyErrors,
) -> Optional[BaseSCMClient]:
    """Return a SCMClient instance for an ID, utilizing a cache.

    This will return any existing instance from a cache, if one is found. If
    not found, a new one will be instantiated and returned.

    If there's an error instantiating a client, an error will be logged and
    the result (including the cached copy) will be ``None``.

    Version Added:
        4.0

    Args:
        scmclient_cls (type):
            The SCMClient class used to instantiate a copy.

        scmclient_kwargs (dict):
            Keyword arguments to pass to the SCMClient constructor.

        cache (dict):
            A dictionary used to cache instances. Each key is a SCMClient ID,
            and each value is an instance.

        errors (dict):
            A dictionary used to store unexpected errors encountered during
            instantiation.  Each key is a SCMClient ID, and each value is an
            exception.

        dep_errors (dict):
            A dictionary used to store dependency errors encountered during
            instantiation.  Each key is a SCMClient ID, and each value is
            a :py:class:`~rbtools.clients.errors.SCMClientDependencyError`
            exception.

    Returns:
        rbtools.clients.base.scmclient.BaseSCMClient:
        The SCMClient instance, or ``None`` if it failed to instantiate.
    """
    scmclient_id = scmclient_cls.scmclient_id

    try:
        scmclient = cache[scmclient_id]
    except KeyError:
        # Default this to None. If instantiation fails, we'll still cache it
        # to avoid a second attempt.
        scmclient = None

        try:
            scmclient = scmclient_cls(**scmclient_kwargs)
            scmclient.setup()
        except SCMClientDependencyError as e:
            logger.debug('[scan] Skipping %s: %s',
                         scmclient_cls.name, e)
            dep_errors[scmclient_id] = e
            scmclient = None
        except Exception as e:
            logger.exception('[scan] Unexpected error loading SCMClient '
                             '%s.%s: %s',
                             scmclient_cls.__module__,
                             scmclient_cls.__name__,
                             e)
            errors[scmclient_id] = e
            scmclient = None

        cache[scmclient_id] = scmclient

    return scmclient


def _get_scmclient_candidates(
    *,
    check_remote: bool,
    scmclient_classes: list[type[BaseSCMClient]],
    scmclient_kwargs: dict[str, Any],
) -> _SCMClientCandidatesResult:
    """Return SCMClient candidates and errors for the current directory.

    This will go through each registered SCMClient type, returning any that
    can provide information either in remote-only mode (where a local path
    does not come into play) or the current directory.

    If any provide information in a remote-only mode, then local directory
    checks will be skipped.

    Version Added:
        4.0

    Args:
        check_remote (bool):
            Whether to check in remote-only mode.

        scmclient_classes (list of type):
            The list of SCMClient classes to use for the scan.

        scmclient_kwargs (dict):
            Keyword arguments to pass to each SCMClient class constructor.

    Returns:
        tuple:
        A tuple containing:

        Tuple:
            0 (list of dict):
                The list of candidate matches.

            1 (dict):
                A dictionary mapping SCMClient IDs to exceptions raised
                during scan or initialization.

            2 (dict):
                A dictionary mapping SCMClient IDs to
                :py:class:`~rbtools.clients.errors.SCMClientDependencyError`
                exceptions raised during setup.
    """
    scmclient_cache: _SCMClientCache = {}
    candidates: SCMClientScanCandidateList = []
    errors: SCMClientScanErrors = {}
    dep_errors: SCMClientScanDependencyErrors = {}

    if check_remote:
        # First, go through and see if any repositories are configured in
        # remote-only mode. For example, SVN can post changes purely with a
        # remote URL and no working directory.
        for scmclient_cls in scmclient_classes:
            scmclient = _get_or_create_scmclient_for_scan(
                scmclient_cls=scmclient_cls,
                scmclient_kwargs=scmclient_kwargs,
                cache=scmclient_cache,
                errors=errors,
                dep_errors=dep_errors)

            if scmclient is not None:
                try:
                    is_remote_only = scmclient.is_remote_only()
                except Exception as e:
                    errors[scmclient.scmclient_id] = e
                    logger.exception('Unexpected error checking %s '
                                     'remote-only repository match for %s: %s',
                                     scmclient_cls.name, os.getcwd(), e)
                    is_remote_only = None

                if is_remote_only:
                    candidates.append(SCMClientScanCandidate(
                        local_path=None,
                        scmclient=scmclient))

    if not candidates:
        # Next, check against the local repositories.
        for scmclient_cls in scmclient_classes:
            scmclient = _get_or_create_scmclient_for_scan(
                scmclient_cls=scmclient_cls,
                scmclient_kwargs=scmclient_kwargs,
                cache=scmclient_cache,
                errors=errors,
                dep_errors=dep_errors)

            if scmclient is not None:
                logger.debug('[scan] Checking for a %s repository...',
                             scmclient.name)

                try:
                    local_path = scmclient.get_local_path()
                except Exception as e:
                    errors[scmclient.scmclient_id] = e
                    logger.exception('Unexpected error fetching %s local '
                                     'path information for %s: %s',
                                     scmclient_cls.name, os.getcwd(), e)
                    local_path = None

                if local_path:
                    candidates.append(SCMClientScanCandidate(
                        local_path=local_path,
                        scmclient=scmclient))

    return candidates, errors, dep_errors


def _get_preferred_candidate_for_scan(
    candidates: SCMClientScanCandidateList,
) -> Optional[SCMClientScanCandidate]:
    """Return a preferred candidate from a scanned list of candidates.

    If the provided list is empty, this will return ``None``.

    If there's only one candidate, it will be returned directly.

    If there are more, this will attempt to find the deepest candidate (the
    one closest to the working directory).

    Args:
        candidates (list of dict):
            The list of candidates.

    Returns:
        dict:
        The resulting candidate.
    """
    if not candidates:
        candidate = None
    if len(candidates) == 1:
        candidate = candidates[0]
    else:
        logger.debug('[scan] %s possible repositories were found. Trying to '
                     'find the deepest one...',
                     len(candidates))

        deepest_repo_len = 0
        deepest_candidate = None

        for candidate in candidates:
            local_path = candidate.local_path

            if (local_path and
                len(os.path.normpath(local_path)) > deepest_repo_len):
                deepest_repo_len = len(local_path)
                deepest_candidate = candidate

        candidate = deepest_candidate

    return candidate


def scan_scmclients_for_path(
    path: str,
    *,
    scmclient_kwargs: dict[str, Any],
    scmclient_ids: list[str] = [],
    check_remote: bool = True,
) -> SCMClientScanResult:
    """Scan and return information for SCMClients usable for a path.

    This looks for local source trees matching any supported SCMClient,
    starting at the provided path and working up toward the root of the
    filesystem. It will also by default check remote-only repositories, if
    the appropriate options are passed when instantiating each SCMClient.

    All candidates are recorded, which can be helpful with diagnosing a match
    (in the case of nested repositories). If there was at least one candidate
    found, the most likely match will be returned along with the candidates.

    Any errors encountered during matching will be logged and returned, to help
    with providing useful errors to the caller.

    Version Added:
        4.0

    Args:
        path (str):
            The starting path for the search.

        scmclient_kwargs (dict):
            Keyword arguments to pass when instantiating each SCMClient.

        scmclient_ids (list of str, optional):
            An explicit list of SCMClient IDs to try to use in the scan.

            If empty, this will try all registered SCMClients.

        check_remote (bool, optional):
            Whether to allow checking of remote repositories.

            This is dependent on support and logic within each SCMClient.

    Returns:
        SCMClientScanResult:
        The results of the SCMClient scan. This will never be ``None``.
    """
    logger.debug('[scan] Checking for available SCMs for %s...', path)

    if scmclient_ids:
        logger.debug('[scan] Only considering the following types of '
                     'repositories: %s',
                     ', '.join(sorted(scmclient_ids)))
    else:
        logger.debug('[scan] Considering all repository types')

    # Build the list of SCMClient classes to check.
    if scmclient_ids:
        scmclient_classes = [
            scmclient_registry.get(_scmclient_id)
            for _scmclient_id in scmclient_ids
        ]
    else:
        scmclient_classes = list(scmclient_registry)

    # Fetch the list of candidates.
    with chdir(path):
        candidates, scmclient_errors, dep_errors = _get_scmclient_candidates(
            check_remote=check_remote,
            scmclient_classes=scmclient_classes,
            scmclient_kwargs=scmclient_kwargs)

        # Try to find a single suitable candidate to return.
        candidate = _get_preferred_candidate_for_scan(candidates)

        scmclient = None
        local_path = None
        repository_info = None

        if candidate is not None:
            # We found a candidate. Make sure we can fetch repository
            # information from it.
            scmclient = candidate.scmclient
            local_path = candidate.local_path

            logger.debug('[scan] SCM scan complete. Found %s (%s)',
                         scmclient.scmclient_id, local_path)
            logger.debug('[scan] Verifying repository information...')

            try:
                repository_info = scmclient.get_repository_info()
            except Exception as e:
                scmclient_errors[scmclient.scmclient_id] = e
                logger.exception('Unexpected error fetching %s repository '
                                 'for %s: %s',
                                 scmclient.name, local_path, e)
                repository_info = None

            if repository_info is not None:
                # This is a successful result.
                logger.debug('[scan] Successfully found repository '
                             'information: %r',
                             repository_info)
            else:
                # We either didn't find repository information, or we failed
                # to fetch it. This is no longer a match.
                logger.debug('[scan] Repository information was not found.')
                candidate = None
        else:
            logger.debug('[scan] SCM scan complete. No candidate '
                         'repositories found.')

    if candidate is None:
        # We either didn't find anything, or we hit a problem looking up
        # information. Reset everything we'd return for successful results.
        scmclient = None
        local_path = None
        repository_info = None

    return SCMClientScanResult(scmclient=scmclient,
                               local_path=local_path,
                               repository_info=repository_info,
                               candidates=candidates,
                               dependency_errors=dep_errors,
                               scmclient_errors=scmclient_errors)


SCMClientScanCandidateList: TypeAlias = List[SCMClientScanCandidate]
SCMClientScanErrors: TypeAlias = Dict[str, Exception]
SCMClientScanDependencyErrors: TypeAlias = Dict[str, SCMClientDependencyError]

_SCMClientCache: TypeAlias = Dict[str, Optional[BaseSCMClient]]
_SCMClientKwargs: TypeAlias = Dict[str, Any]
_SCMClientCandidatesResult: TypeAlias = Tuple[SCMClientScanCandidateList,
                                              SCMClientScanErrors,
                                              SCMClientScanDependencyErrors]
