from __future__ import unicode_literals

from difflib import SequenceMatcher


class Score(object):
    """Encapsulates ranking information for matching existing requests.

    This is currently used with 'rbt post -u' to match the new change with
    existing review requests. The 'get_match' method will return a new Score,
    and then multiple scores can be ranked against each other."""
    EXACT_MATCH_SCORE = 1.0

    def __init__(self, summary_score, description_score):
        self.summary_score = summary_score
        self.description_score = description_score

    def is_exact_match(self):
        return (self.summary_score == self.EXACT_MATCH_SCORE and
                self.description_score == self.EXACT_MATCH_SCORE)

    @staticmethod
    def get_match(summary_pair, description_pair):
        """Get a score based on a pair of summaries and a pair of descriptions.

        The scores for summary and description pairs are calculated
        independently using SequenceMatcher, and returned as part of a Score
        object.
        """
        if not summary_pair or not description_pair:
            return None

        summary_score = SequenceMatcher(
            None, summary_pair[0], summary_pair[1]).ratio()
        description_score = SequenceMatcher(
            None, description_pair[0], description_pair[1]).ratio()

        return Score(summary_score, description_score)
