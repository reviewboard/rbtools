from rbtools.api.errors import APIError
from rbtools.clients.errors import InvalidRevisionSpecError
from rbtools.commands import CommandError
from rbtools.utils.match_score import Score
from rbtools.utils.repository import get_repository_id
from rbtools.utils.users import get_user


def get_commit_message(tool, cmd_args):
    """Returns the commit message for the parsed revisions.

    If the SCMClient supports getting a commit message, this will fetch
    and store the message for future lookups.

    This is used for guessing the summary and description fields, and
    updating exising review requests using -u.
    """
    return tool.get_commit_message(get_revisions(tool, cmd_args))


def get_raw_commit_message(tool, cmd_args):
    """Returns the raw commit message for the parsed revisions.

    If the SCMClient supports getting a commit message, this will fetch
    and store the message for future lookups.
    """
    return tool.get_raw_commit_message(get_revisions(tool, cmd_args))


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


def get_possible_matches(review_requests, summary, description, limit=5):
    """Returns a sorted list of tuples of score and review request.

    Each review request is given a score based on the summary and
    description provided. The result is a sorted list of tuples containing
    the score and the corresponding review request, sorted by the highest
    scoring review request first.
    """
    candidates = []

    # Get all potential matches.
    try:
        while True:
            for review_request in review_requests:
                summary_pair = (
                    get_draft_or_current_value(
                        'summary', review_request),
                    summary)
                description_pair = (
                    get_draft_or_current_value(
                        'description', review_request),
                    description)
                score = Score.get_match(summary_pair, description_pair)
                candidates.append((score, review_request))

            review_requests = review_requests.get_next()
    except StopIteration:
        pass

    # Sort by summary and description on descending rank.
    sorted_candidates = sorted(
        candidates,
        key=lambda m: (m[0].summary_score, m[0].description_score),
        reverse=True
    )

    return sorted_candidates[:limit]


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


def guess_existing_review_request_id(repository_info, repository_name,
                                     api_root, api_client, tool, cmd_args,
                                     guess_summary, guess_description,
                                     is_fuzzy_match_func=None,
                                     no_commit_error=None):
    """Try to guess the existing review request ID if it is available.

    The existing review request is guessed by comparing the existing
    summary and description to the current post's summary and description,
    respectively. The current post's summary and description are guessed if
    they are not provided.

    If the summary and description exactly match those of an existing
    review request, the ID for which is immediately returned. Otherwise,
    the user is prompted to select from a list of potential matches,
    sorted by the highest ranked match first.
    """
    user = get_user(api_client, api_root, auth_required=True)
    repository_id = get_repository_id(
        repository_info, api_root, repository_name)

    try:
        # Get only pending requests by the current user for this
        # repository.
        review_requests = api_root.get_review_requests(
            repository=repository_id, from_user=user.username,
            status='pending', expand='draft')

        if not review_requests:
            raise CommandError('No existing review requests to update for '
                               'user %s.'
                               % user.username)
    except APIError as e:
        raise CommandError('Error getting review requests for user '
                           '%s: %s' % (user.username, e))

    if not guess_summary or not guess_description:
        try:
            commit_message = get_commit_message(tool, cmd_args)

            if commit_message:
                if not guess_summary:
                    summary = commit_message['summary']

                if not guess_description:
                    description = commit_message['description']
            elif callable(no_commit_error):
                no_commit_error()
        except NotImplementedError:
            raise CommandError('--summary and --description are required.')

    possible_matches = get_possible_matches(review_requests, summary,
                                            description)
    exact_match_count = num_exact_matches(possible_matches)

    for score, review_request in possible_matches:
        # If the score is the only exact match, return the review request
        # ID without confirmation, otherwise prompt.
        if ((score.is_exact_match() and exact_match_count == 1) or
            (callable(is_fuzzy_match_func) and
             is_fuzzy_match_func(review_request))):
            return review_request.id

    return None


def num_exact_matches(possible_matches):
    """Returns the number of exact matches in the possible match list."""
    count = 0

    for score, request in possible_matches:
        if score.is_exact_match():
            count += 1

    return count
