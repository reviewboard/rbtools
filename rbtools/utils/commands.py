from rbtools.api.errors import APIError
from rbtools.commands import CommandError


def get_review_request(review_request_id, api_root):
    """Returns the review request resource for the given ID."""
    try:
        review_request = api_root.get_review_request(
            review_request_id=review_request_id)
    except APIError, e:
        raise CommandError("Error getting review request %s: %s"
                           % (review_request_id, e))

    return review_request
