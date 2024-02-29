"""Utilities for matching review requests."""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from difflib import SequenceMatcher
from itertools import islice
from typing import Callable, Optional, TYPE_CHECKING

from housekeeping import deprecate_non_keyword_only_args

from rbtools.api.errors import APIError
from rbtools.api.resource import ListResource
from rbtools.clients.errors import InvalidRevisionSpecError
from rbtools.deprecation import RemovedInRBTools60Warning
from rbtools.utils.errors import MatchReviewRequestsError
from rbtools.utils.users import get_user

if TYPE_CHECKING:
    from rbtools.api.client import RBClient
    from rbtools.api.resource import ReviewRequestResource, RootResource
    from rbtools.clients.base.scmclient import (BaseSCMClient,
                                                SCMClientRevisionSpec)


def get_draft_or_current_value(field_name, review_request):
    """Returns the draft or current field value from a review request.

    If a draft exists for the supplied review request, return the draft's
    field value for the supplied field name, otherwise return the review
    request's field value for the supplied field name.
    """
    if review_request.draft:
        fields = review_request.draft[0]
    else:
        fields = review_request

    return fields[field_name]


def get_revisions(tool, cmd_args):
    """Returns the parsed revisions from the command line arguments.

    These revisions are used for diff generation and commit message
    extraction. They will be cached for future calls.
    """
    # Parse the provided revisions from the command line and generate
    # a spec or set of specialized extra arguments that the SCMClient
    # can use for diffing and commit lookups.
    try:
        revisions = tool.parse_revision_spec(cmd_args)
    except InvalidRevisionSpecError:
        if not tool.supports_diff_extra_args:
            raise

        revisions = None

    return revisions


def get_pending_review_requests(api_root,
                                username,
                                repository_id=None,
                                additional_fields=None):
    """Return pending review requests for a user.

    Each review request will contain a pre-fetched list of fields:

    * ``absolute_url``
    * ``bugs_closed``
    * ``commit_id``
    * ``description``
    * ``draft``
    * ``extra_data``
    * ``id``
    * ``public``
    * ``status``
    * ``summary``
    * ``url``

    If needed, additional fields can be requested by passing in
    ``additional_fields``.

    This requires a valid existing login session.

    Version Added:
        3.1

    Args:
        api_root (rbtools.api.resource.RootResource):
            The root resource of the Review Board server.

        username (unicode):
            The username owning the review requests.

            The authenticated user will need to have access to this user's
            pending review requests. For instance, it would need to be a
            superuser, a special user with the ``can_submit_as`` permission,
            or the user itself.

        repository_id (int, optional):
            The repository ID that all matching review requests must be
            posted against.

            If not provided, only review requests not backed by a repository
            will be matched.

        additional_fields (list of unicode, optional):
            Additional fields to fetch for the review request payload.
    """
    assert api_root is not None
    assert username

    only_fields = [
        'absolute_url',
        'bugs_closed',
        'commit_id',
        'description',
        'draft',
        'extra_data',
        'id',
        'public',
        'status',
        'summary',
        'url',
    ]

    if additional_fields:
        only_fields += additional_fields

    # Get only pending requests by the current user matching the provided
    # repository ID (or None).
    get_kwargs = {}

    if repository_id is not None:
        get_kwargs['repository'] = repository_id

    return api_root.get_review_requests(
        from_user=username,
        status='pending',
        expand='draft',
        only_fields=','.join(only_fields),
        only_links='diffs,draft',
        show_all_unpublished=True,
        **get_kwargs)


@deprecate_non_keyword_only_args(RemovedInRBTools60Warning)
def find_review_request_by_change_id(
    *,
    api_client: RBClient,
    api_root: RootResource,
    revisions: SCMClientRevisionSpec,
    repository_id: Optional[int] = None,
) -> Optional[ReviewRequestResource]:
    """Ask Review Board for the review request ID for the tip revision.

    Note that this function calls the Review Board API with the ``only_fields``
    parameter, thus the returned review request will contain only the fields
    specified by the ``only_fields`` variable.

    If no review request is found, ``None`` will be returned instead.

    Version Changed:
        5.0:
        * Removed deprecated ``repository_info`` and ``repository_name``
          arguments.
        * Made all arguments keyword-only.

    Version Changed:
        3.0:
        The ``repository_info`` and ``repository_name`` arguments were
        deprecated in favor of adding the new ``repository_id`` argument.

    Args:
        api_client (rbtools.api.client.RBClient):
            The API client.

        api_root (rbtools.api.resource.RootResource):
            The root resource of the Review Board server.

        revisions (dict):
            The parsed revision information, including the ``tip`` key.

        repository_id (int, optional):
            The repository ID to use.

    Returns:
        rbtools.api.resource.ReviewRequestResource:
        The matching review request, if found.
    """
    assert api_client is not None
    assert api_root is not None
    assert revisions is not None

    only_fields = 'id,commit_id,changenum,status,url,absolute_url'
    change_id = revisions['tip']
    assert isinstance(change_id, str)

    logging.debug('Attempting to find review request from tip revision ID: %s',
                  change_id)
    # Strip off any prefix that might have been added by the SCM.
    change_id = change_id.split(':', 1)[1]

    optional_args = {}

    if change_id.isdigit():
        # Populate integer-only changenum field also for compatibility
        # with older API versions
        optional_args['changenum'] = int(change_id)

    user = get_user(api_client, api_root, auth_required=True)
    assert user is not None

    # Don't limit query to only pending requests because it's okay to stamp a
    # submitted review.
    review_requests = api_root.get_review_requests(repository=repository_id,
                                                   from_user=user.username,
                                                   commit_id=change_id,
                                                   only_links='self',
                                                   only_fields=only_fields,
                                                   **optional_args)

    if review_requests:
        count = review_requests.total_results

        # Only one review can be associated with a specific commit ID.
        if count > 0:
            assert count == 1, '%d review requests were returned' % count
            review_request = review_requests[0]
            logging.debug('Found review request %s with status %s',
                          review_request.id, review_request.status)

            if review_request.status != 'discarded':
                return review_request

    return None


def find_review_request_matches(review_requests,
                                tool=None,
                                revisions=None,
                                commit_id=None,
                                summary=None,
                                description=None,
                                max_review_requests=50):
    """Find review requests that match the provided criteria.

    This will iterate through a provided list of review request resources,
    comparing the contained information against the provided criteria in
    order to generate matches.

    There are two possible types of results: An exact match, or a list of
    fuzzy matches.

    If only one exact match is found, it will be in the results, and any fuzzy
    matches will be discarded.

    If more than one exact match is found, they'll be converted to fuzzy
    matches, with higher precedence than any actual fuzzy matches.

    If an exact match is not found, a list of fuzzy matches will be provided,
    each with a score (a floating point number between 0.0 and 1.0) indicating
    how close it matched the criteria.

    The following criteria is checked for a match:

    1. Matching ``commit_id``.

       This would be considered an exact match.

    2. Matching SCMClient-specific extra_data.

       A :py:class:`~rbtools.clients.base.BaseSCMClient` can provide its own
       matching logic, comparing state stored on a review request with
       information from the local clone/checkout. The result may be an exact
       match or a fuzzy match.

    3. Matching a summary/description, if provided.

       The provided summary/description will be compared against the review
       request. If the strings are both equal, then this will be an exact
       match. Otherwise, it's a fuzzy match.

    Version Added:
        3.1

    Args:
        review_requests (list or rbtools.api.resource.ListResource):
            Either a list resource for review requests (in which case all
            pages will be searched for matches), or a list of
            :py:class:`rbtools.api.resource.ReviewRequestResource` instances.

            Note:
                It's expected that these will all be backed by the same
                repository.  Otherwise, commit ID matching will not be
                reliable. This is the responsibility of the caller.

        tool (rbtools.clients.base.BaseSCMClient, optional):
            An optional client tool used to perform tool-specific matches.

        revisions (dict, optional):
            The parsed revisions from the tool.

        summary (unicode, optional):
            An optional summary to match against.

        description (unicode, optional):
            An optional description to match against.

        max_review_requests (int, optional):
            The maximum number of review requests to check. This avoids
            iterating through too many pages of review requests on the
            server.

    Returns:
        dict:
        A dictionary of results, containing:

        Keys:
            exact (rbtools.api.resource.ReviewRequestResource):
                An exact review request match. This may be ``None``.

            fuzzy (list of dict):
                A list of fuzzy matches. Each contains:

                Keys:
                    review_request (rbtools.api.resource.
                                    ReviewRequestResource):
                        The review request match candidate.

                    score (float):
                        The match score (between 0.0 and 1.0), indicating the
                        confidence of the match.
    """
    if isinstance(review_requests, ListResource):
        review_requests = review_requests.all_items

    # Avoid looping through too many review requests from the API.
    review_requests = list(islice(review_requests, max_review_requests))

    if revisions is None:
        revisions = {}

    exact_matches = OrderedDict()
    fuzzy_matches = []

    review_requests_details = []
    skips = set()

    for review_request in review_requests:
        if getattr(review_request, 'draft', None):
            details = review_request.draft[0]
        else:
            details = review_request

        review_requests_details.append(details)

    # Step 1: Check the commit ID.
    if commit_id:
        for review_request, details in zip(review_requests,
                                           review_requests_details):
            if commit_id == details.commit_id:
                # This is an exact match.
                exact_matches[review_request.id] = review_request

    if tool is not None:
        # Step 2: Check SCMClient-specific data.
        for review_request, details in zip(review_requests,
                                           review_requests_details):
            is_match = tool.get_tree_matches_review_request(
                review_request=details,
                revisions=revisions)

            # If is_match is a True or a False, we can make an explicit
            # decision. If it's None, we'll fall back to other logic.
            if is_match is True:
                # This is an exact match.
                exact_matches[review_request.id] = review_request
            elif is_match is False:
                # This is explicitly NOT the review request. Skip it.
                skips.add(review_request.id)
                exact_matches.pop(review_request.id, None)

    if summary or description:
        # Step 3: Check the summary/description.
        #
        # Only these will generate fuzzy results.
        for review_request, details in zip(review_requests,
                                           review_requests_details):
            # If we're skipping it from an above step, or it's already
            # considered an exact match, we can skip the summary/description
            # comparisons.
            if (review_request.id in skips or
                review_request.id in exact_matches):
                continue

            pairs = [
                (details.summary, summary or ''),
                (details.description, description or ''),
            ]

            # Compute a score based on a diff of the text fields. The score
            # will be 0.0 at the lowest, 1.0 at the highest. If either the
            # summary or description are missing, a 0.5 would be the highest
            # score achievable.
            score = sum(
                SequenceMatcher(a=_pair[0],
                                b=_pair[1]).ratio()
                for _pair in pairs
            ) / len(pairs)

            if score == 1.0:
                # This is an exact match for the content.
                exact_matches[review_request.id] = review_request
            else:
                # It wasn't an exact match, so record it as a fuzzy match for
                # later confirmation.
                fuzzy_matches.append({
                    'score': score,
                    'review_request': review_request,
                })

    if len(exact_matches) == 1:
        # We have an exact match, so the fuzzy matches aren't needed.
        # Discard them.
        exact_match = list(exact_matches.values())[0]
        fuzzy_matches = []
    else:
        exact_match = None

        # We're going to work with fuzzy matches. The first thing we want
        # to do is sort the ones we have, since they'll have non-0 scores.
        fuzzy_matches.sort(key=lambda _info: _info['score'],
                           reverse=True)

        if len(exact_matches) > 1:
            # We have multiple exact matches. We'll need to return them all.
            # Add them as fuzzy matches with a score of 1, in the order we
            # looked them up.
            fuzzy_matches = [
                {
                    'score': 1.0,
                    'review_request': _review_request
                }
                for _review_request in exact_matches.values()
            ] + fuzzy_matches

    return {
        'exact': exact_match,
        'fuzzy': fuzzy_matches,
    }


@deprecate_non_keyword_only_args(RemovedInRBTools60Warning)
def guess_existing_review_request(
    *,
    api_root: RootResource,
    api_client: Optional[RBClient] = None,
    tool: BaseSCMClient,
    revisions: SCMClientRevisionSpec,
    is_fuzzy_match_func: Optional[
        Callable[[ReviewRequestResource], bool]] = None,
    no_commit_error: Optional[Callable[[], None]] = None,
    submit_as: str,
    additional_fields: Optional[list[str]] = None,
    repository_id: Optional[int] = None,
    commit_id: Optional[str] = None,
) -> Optional[ReviewRequestResource]:
    """Try to guess the existing review request ID if it is available.

    The existing review request is guessed by comparing the existing
    summary and description to the current post's summary and description,
    respectively. The current post's summary and description are guessed if
    they are not provided.

    If the summary and description exactly match those of an existing
    review request, that request is immediately returned. Otherwise,
    the user is prompted to select from a list of potential matches,
    sorted by the highest ranked match first.

    Note that this function calls the ReviewBoard API with the only_fields
    parameter, thus the returned review request will contain only the fields
    specified by the only_fields variable.

    Version Changed:
        5.0:
        * Removed the deprecated ``repository_info``, ``repository_name``,
          ``guess_summary``, and ``guess_description`` arguments.
        * Made ``submit_as`` required.
        * Deprecated the ``api_client`` argument.
        * Made all arguments keyword-only.

    Version Changed:
        3.1:
        * Added the ``commit_id`` argument.
        * The ``guess_summary`` and ``guess_description`` arguments are
          deprecated and will be removed in RBTools 4.0.
        * ``submit_as`` should now be provided, and will be required in
          RBTools 4.0.

    Version Changed:
        3.0:
        The ``repository_info`` and ``repository_name`` arguments were
        deprecated in favor of adding the new ``repository_id`` argument.

    Args:
        api_root (rbtools.api.resource.RootResource):
            The root resource of the Review Board server.

        api_client (rbtools.api.client.RBClient):
            The API client.

        tool (rbtools.clients.base.BaseSCMClient):
            The SCM client.

        revisions (dict):
            The parsed revisions object.

        is_fuzzy_match_func (callable, optional):
            A function which can check if a review request is a match for the
            data being posted.

        no_commit_error (callable, optional):
            A function to be called when there's no local commit.

        submit_as (str):
            A username on the server which is used for posting review requests.
            If provided, review requests owned by this user will be matched.

            Version Changed:
                3.1:
                This will be required in RBTools 4.0.

        additional_fields (list of str, optional):
            A list of additional fields to include in the fetched review
            request resource.

        repository_id (int, optional):
            The ID of the repository to match.

        commit_id (str, optional):
            The ID of the commit to match.

            Version Added:
                3.1

    Returns:
        rbtools.api.resource.ReviewRequestResource:
        The resulting review request, if a match was made, or ``None`` if
        no review request could be matched.

    Raises:
        rbtools.utils.errors.MatchReviewRequestError:
            Error fetching the user session or review requests from the API.

            This will replace the :py:exc:`ValueError` exception for API
            issues in RBTools 4.0.

        ValueError:
            Error fetching review requests from the API.
    """
    assert tool is not None
    assert revisions is not None
    assert api_root is not None

    if api_client is not None:
        RemovedInRBTools60Warning.warn(
            'The api_client argument to guess_existing_review_request is '
            'deprecated and will be removed in RBTools 6.0.')

    # Fetch the pending review requests for this repository. These will be
    # the candidates for matching.
    try:
        review_requests = get_pending_review_requests(
            api_root=api_root,
            repository_id=repository_id,
            username=submit_as,
            additional_fields=additional_fields)
    except APIError as e:
        raise MatchReviewRequestsError(
            f'Error getting review requests for user "{submit_as}": {e}',
            api_error=e)

    summary = None
    description = None

    try:
        commit_message = tool.get_commit_message(revisions)

        if commit_message:
            summary = commit_message['summary']
            description = commit_message['description']
        elif callable(no_commit_error):
            # In a future version of RBTools, we'll want to deprecate this and
            # instead add a flag to require a commit message, raising an
            # exception if unavailable.
            no_commit_error()
    except NotImplementedError:
        pass

    # Find any review requests that match either exactly or partially.
    matches = find_review_request_matches(
        review_requests=review_requests,
        tool=tool,
        revisions=revisions,
        commit_id=commit_id,
        summary=summary,
        description=description)

    exact = matches['exact']

    if exact is not None:
        # We found an exact match. We're done.
        return exact

    # We don't have an exact match. We may have fuzzy matches that need to
    # be confirmed.
    #
    # In a future version of RBTools, we'll want to deprecate this
    # functionality and leave this sort of operation up to the caller. We can
    # use an opt-in flag to change the return type, and then make that
    # required in a future version, or just replace this method entirely with
    # a more tailored, future-proof version.
    if callable(is_fuzzy_match_func):
        # Allow the caller to decide what to do with any fuzzy matches.
        #
        # We'll only prompt up to 5 fuzzy matches (to stay consistent with
        # legacy behavior). Possible matches are in the order of highest
        # scores to least.
        for match_info in matches['fuzzy'][:5]:
            review_request = match_info['review_request']

            if is_fuzzy_match_func(review_request):
                return review_request

    return None


def parse_review_request_url(url):
    """Parse a review request URL and return its component parts.

    Args:
        url (unicode):
            The URL to parse.

    Returns:
        tuple:
        A 3-tuple consisting of the server URL, the review request ID, and the
        diff revision.
    """
    regex = (r'^(?P<server_url>https?:\/\/.*\/(?:\/s\/[^\/]+\/)?)'
             r'r\/(?P<review_request_id>\d+)'
             r'\/?(diff\/(?P<diff_id>\d+-?\d*))?\/?')
    match = re.match(regex, url)

    if match:
        server_url = match.group('server_url')
        request_id = match.group('review_request_id')
        diff_id = match.group('diff_id')
        return (server_url, request_id, diff_id)

    return (None, None, None)
