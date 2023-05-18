"""Unit tests for rbtools.utils.review_request."""

import kgb

from rbtools.api.errors import APIError
from rbtools.clients import BaseSCMClient
from rbtools.testing import TestCase
from rbtools.utils.errors import MatchReviewRequestsError
from rbtools.utils.review_request import (find_review_request_matches,
                                          get_pending_review_requests,
                                          guess_existing_review_request)


class FindReviewRequestMatchesTests(TestCase):
    """Unit tests for find_review_request_matches."""

    def test_with_empty(self):
        """Testing find_review_request_matches with empty list of review
        requests
        """
        self._run_test(review_request_infos=[],
                       expected_exact_id=None,
                       expected_fuzzy_ids=[])

    def test_without_options(self):
        """Testing find_review_request_matches with review requests and no
        match options
        """
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                },
                {
                    'review_request_id': 2,
                },
                {
                    'review_request_id': 3,
                },
            ],
            expected_exact_id=None,
            expected_fuzzy_ids=[])

    def test_with_commit_id_match(self):
        """Testing find_review_request_matches with commit_id match"""
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'commit_id': 'abc123',
                },
                {
                    'review_request_id': 2,
                    'commit_id': 'def456',
                },
                {
                    'review_request_id': 3,
                    'commit_id': 'ghi789',
                },
            ],
            match_kwargs={
                'commit_id': 'def456',
            },
            expected_exact_id=2)

    def test_with_commit_id_match_with_draft(self):
        """Testing find_review_request_matches with commit_id match and draft
        """
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'commit_id': 'abc123',
                },
                {
                    'review_request_id': 2,
                    'commit_id': 'def456',
                },
                {
                    'review_request_id': 3,
                    'commit_id': 'ghi789',
                },
            ],
            draft_infos=[
                {
                    'commit_id': '123abc',
                },
                {
                    'commit_id': '456def',
                },
                {
                    'commit_id': '789ghi',
                },
            ],
            match_kwargs={
                'commit_id': '456def',
            },
            expected_exact_id=2)

    def test_with_commit_id_no_match(self):
        """Testing find_review_request_matches with commit_id and no match
        """
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'commit_id': 'abc123',
                },
                {
                    'review_request_id': 2,
                    'commit_id': 'def456',
                },
                {
                    'review_request_id': 3,
                    'commit_id': 'ghi789',
                },
            ],
            match_kwargs={
                'commit_id': '1234567',
            })

    def test_with_scmclient_match_bool(self):
        """Testing find_review_request_matches with
        tool.get_tree_matches_review_request() returns boolean results
        """
        class MySCMClient(BaseSCMClient):
            def get_tree_matches_review_request(_self, review_request,
                                                revisions):
                return review_request.extra_data.get('key') == 'good'

        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'extra_data': {
                        'key': 'bad',
                    },
                },
                {
                    'review_request_id': 2,
                },
                {
                    'review_request_id': 3,
                    'extra_data': {
                        'key': 'good',
                    },
                },
            ],
            match_kwargs={
                'tool': MySCMClient(),
            },
            expected_exact_id=3)

    def test_with_scmclient_match_none(self):
        """Testing find_review_request_matches with
        tool.get_tree_matches_review_request() returns None
        """
        class MySCMClient(BaseSCMClient):
            def get_tree_matches_review_request(_self, review_request,
                                                revisions):
                return None

        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'extra_data': {
                        'key': 'bad',
                    },
                },
                {
                    'review_request_id': 2,
                },
                {
                    'review_request_id': 3,
                    'extra_data': {
                        'key': 'good',
                    },
                },
            ],
            match_kwargs={
                'tool': MySCMClient(),
            })

    def test_with_scmclient_match_bool_and_draft(self):
        """Testing find_review_request_matches with
        tool.get_tree_matches_review_request() returns boolean results and
        draft
        """
        class MySCMClient(BaseSCMClient):
            def get_tree_matches_review_request(_self, review_request,
                                                revisions):
                print(review_request)
                return review_request.extra_data.get('key') == 'good'

        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'extra_data': {
                        'key': 'bad',
                    },
                },
                {
                    'review_request_id': 2,
                },
                {
                    'review_request_id': 3,
                    'extra_data': {
                        'key': 'bad',
                    },
                },
            ],
            draft_infos=[
                {
                    'extra_data': {
                        'key': 'bad',
                    },
                },
                {},
                {
                    'extra_data': {
                        'key': 'good',
                    },
                },
            ],
            match_kwargs={
                'tool': MySCMClient(),
            },
            expected_exact_id=3)

    def test_with_summary_match(self):
        """Testing find_review_request_matches with summary match"""
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'summary': 'Test Summary ABC',
                },
                {
                    'review_request_id': 2,
                    'summary': 'Test Summary 2',
                },
                {
                    'review_request_id': 3,
                    'summary': 'Test Summary 3',
                },
            ],
            match_kwargs={
                'summary': 'Test Summary 2',
            },
            expected_fuzzy_ids=[2, 3, 1])

    def test_with_summary_match_and_draft(self):
        """Testing find_review_request_matches with summary match and draft"""
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'summary': 'Test Summary ABC',
                },
                {
                    'review_request_id': 2,
                    'summary': 'Test Summary 2',
                },
                {
                    'review_request_id': 3,
                    'summary': 'Test Summary 3',
                },
            ],
            draft_infos=[
                {
                    'summary': 'New Summary ABC',
                },
                {
                    'summary': 'New Summary 2',
                },
                {
                    'summary': 'New Summary 3',
                },
            ],
            match_kwargs={
                'summary': 'New Summary 2',
            },
            expected_fuzzy_ids=[2, 3, 1])

    def test_with_description_match(self):
        """Testing find_review_request_matches with description match"""
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'description': 'Test description ABC',
                },
                {
                    'review_request_id': 2,
                    'description': 'Test description 2',
                },
                {
                    'review_request_id': 3,
                    'description': 'Test description 3',
                },
            ],
            match_kwargs={
                'description': 'Test description 3',
                'commit_id': 'def456',
            },
            expected_fuzzy_ids=[3, 2, 1])

    def test_with_description_match_and_draft(self):
        """Testing find_review_request_matches with description match and
        draft
        """
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'description': 'Test description ABC',
                },
                {
                    'review_request_id': 2,
                    'description': 'Test description 2',
                },
                {
                    'review_request_id': 3,
                    'description': 'Test description 3',
                },
            ],
            draft_infos=[
                {
                    'description': 'New description ABC',
                },
                {
                    'description': 'New description 2',
                },
                {
                    'description': 'New description 3',
                },
            ],
            match_kwargs={
                'description': 'New description 3',
                'commit_id': 'def456',
            },
            expected_fuzzy_ids=[3, 2, 1])

    def test_with_summary_description_fuzzy_match(self):
        """Testing find_review_request_matches with summary and description
        fuzzy match
        """
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'summary': 'Test summary 1',
                    'description': 'Test description ABC',
                },
                {
                    'review_request_id': 2,
                    'summary': 'Test summary 2',
                    'description': 'Test description 2',
                },
                {
                    'review_request_id': 3,
                    'summary': 'Test summary 3',
                    'description': 'Test description 3',
                },
            ],
            match_kwargs={
                'summary': 'Test summary 2',
                'description': 'Test description',
                'commit_id': 'def456',
            },
            expected_fuzzy_ids=[2, 3, 1])

    def test_with_summary_description_fuzzy_match_and_draft(self):
        """Testing find_review_request_matches with summary and description
        fuzzy match and draft
        """
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'summary': 'Test summary 1',
                    'description': 'Test description ABC',
                },
                {
                    'review_request_id': 2,
                    'summary': 'Test summary 2',
                    'description': 'Test description 2',
                },
                {
                    'review_request_id': 3,
                    'summary': 'Test summary 3',
                    'description': 'Test description 3',
                },
            ],
            draft_infos=[
                {
                    'summary': 'New summary 1',
                    'description': 'New description ABC',
                },
                {
                    'summary': 'New summary 2',
                    'description': 'New description 2',
                },
                {
                    'summary': 'New summary 3',
                    'description': 'New description 3',
                },
            ],
            match_kwargs={
                'summary': 'New summary 2',
                'description': 'New description',
            },
            expected_fuzzy_ids=[2, 3, 1])

    def test_with_summary_description_exact_match(self):
        """Testing find_review_request_matches with summary and description
        exact match
        """
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'summary': 'Test summary 1',
                    'description': 'Test description ABC',
                },
                {
                    'review_request_id': 2,
                    'summary': 'Test summary 2',
                    'description': 'Test description 2',
                },
                {
                    'review_request_id': 3,
                    'summary': 'Test summary 3',
                    'description': 'Test description 3',
                },
            ],
            match_kwargs={
                'summary': 'Test summary 2',
                'description': 'Test description 2',
                'commit_id': 'def456',
            },
            expected_exact_id=2)

    def test_with_summary_description_exact_match_and_draft(self):
        """Testing find_review_request_matches with summary and description
        exact match and draft
        """
        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'summary': 'Test summary 1',
                    'description': 'Test description ABC',
                },
                {
                    'review_request_id': 2,
                    'summary': 'Test summary 2',
                    'description': 'Test description 2',
                },
                {
                    'review_request_id': 3,
                    'summary': 'Test summary 3',
                    'description': 'Test description 3',
                },
            ],
            draft_infos=[
                {
                    'summary': 'New summary 1',
                    'description': 'New description ABC',
                },
                {
                    'summary': 'New summary 2',
                    'description': 'New description 2',
                },
                {
                    'summary': 'New summary 3',
                    'description': 'New description 3',
                },
            ],
            match_kwargs={
                'summary': 'New summary 2',
                'description': 'New description 2',
                'commit_id': 'def456',
            },
            expected_exact_id=2)

    def test_with_multiple_exact_matches(self):
        """Testing find_review_request_matches with multiple exact matches"""
        class MySCMClient(BaseSCMClient):
            def get_tree_matches_review_request(_self, review_request,
                                                revisions):
                if 'key' in review_request.extra_data:
                    return review_request.extra_data.get('key') == 'good'

                return None

        self._run_test(
            review_request_infos=[
                {
                    'review_request_id': 1,
                    'summary': 'Test summary 1',
                    'description': 'Test description ABC',
                },
                {
                    'review_request_id': 2,
                    'summary': 'Test summary 2',
                    'description': 'Test description 2',
                    'extra_data': {
                        'key': 'good',
                    },
                },
                {
                    'review_request_id': 3,
                    'summary': 'Test summary 3',
                    'description': 'Test description 3',
                    'commit_id': 'abc123',
                },
                {
                    'review_request_id': 4,
                    'summary': 'Test summary 3A',
                    'description': 'Test description 3A',
                },
            ],
            match_kwargs={
                'commit_id': 'abc123',
                'description': 'Test description 1',
                'summary': 'Test summary 1',
                'tool': MySCMClient(),
            },
            expected_fuzzy_ids=[3, 2, 1, 4])

    def _run_test(self,
                  review_request_infos,
                  draft_infos=None,
                  match_kwargs={},
                  expected_exact_id=None,
                  expected_fuzzy_ids=[]):
        """Set up and run a test for find_review_request_matches.

        This will create all the URLs for the review requests and drafts,
        fetch the review requests, and compare them against the match criteria
        using :py:func:`~rbtools.utils.review_request.
        find_review_request_matches`.

        Args:
            review_request_infos (list of dict):
                A list of review request information to set in the registered
                payloads.

            draft_infos (list of dict, optional):
                An optional list of drafts to set, if expanding drafts.
                This must have one entry for each entry in
                ``review_request_infos``.

            match_kwargs (dict, optional):
                Keyword arguments to pass to :py:func:`~rbtools.utils.
                review_request.find_review_request_matches`.

            expected_exact_id (int, optional):
                The ID of the review request to expect as an exact match.

            expected_fuzzy_ids (list of int, optional):
                The list of IDs of the review request to expect as fuzzy
                matches, in order.

        Raises:
            AssertionError:
                The match state did not meet expectations.
        """
        client = self.create_rbclient()
        transport = self.get_rbclient_transport(client)
        urls = []
        url_querystring = ''

        for review_request_info in review_request_infos:
            url_info = transport.add_review_request_url(**review_request_info)
            urls.append(url_info['url'])

        if draft_infos:
            assert len(draft_infos) == len(review_request_infos)

            url_querystring = '?expand=draft'

            for review_request_info, draft_info in zip(review_request_infos,
                                                       draft_infos):
                review_request_id = review_request_info['review_request_id']

                transport.add_review_request_draft_url(
                    draft_id=review_request_id + 100,
                    review_request_id=review_request_id,
                    **draft_info)

        review_requests = [
            client.get_url(_url + url_querystring)
            for _url in urls
        ]

        result = find_review_request_matches(review_requests=review_requests,
                                             **match_kwargs)
        self.assertEqual(set(result.keys()), {'exact', 'fuzzy'})

        if expected_exact_id is not None:
            self.assertIsNotNone(result['exact'])
            self.assertEqual(result['exact'].id, expected_exact_id)
        else:
            self.assertIsNone(result['exact'])

        self.assertEqual(
            [
                _fuzzy['review_request'].id
                for _fuzzy in result['fuzzy']
            ],
            expected_fuzzy_ids)


class GetPendingReviewRequestsTests(kgb.SpyAgency, TestCase):
    """Unit tests for get_pending_review_requests."""

    def test_standard(self):
        """Testing get_pending_review_requests"""
        client = self.create_rbclient()
        transport = self.get_rbclient_transport(client)
        api_root = client.get_root()

        transport.add_review_request_url(review_request_id=1)
        transport.add_review_request_draft_url(review_request_id=1,
                                               draft_id=1)

        transport.add_review_request_url(review_request_id=2)
        transport.add_review_request_draft_url(review_request_id=2,
                                               draft_id=2)

        self.spy_on(api_root.get_review_requests)

        pending_review_requests = get_pending_review_requests(
            api_root=api_root,
            username='test-user')

        self.assertSpyCalledWith(
            api_root.get_review_requests,
            from_user='test-user',
            status='pending',
            expand='draft',
            only_fields=(
                'absolute_url,bugs_closed,commit_id,description,draft,'
                'extra_data,id,public,status,summary,url'
            ),
            only_links='diffs,draft',
            show_all_unpublished=True)

        self.assertEqual(len(pending_review_requests), 2)
        self.assertEqual(pending_review_requests[0].id, 1)
        self.assertEqual(pending_review_requests[1].id, 2)

        self.assertTrue(hasattr(pending_review_requests[0], 'draft'))
        self.assertTrue(hasattr(pending_review_requests[1], 'draft'))

        self.assertEqual(pending_review_requests[0].draft[0].id, 1)
        self.assertEqual(pending_review_requests[1].draft[0].id, 2)

    def test_with_repository_id(self):
        """Testing get_pending_review_requests with repository_id="""
        client = self.create_rbclient()
        api_root = client.get_root()

        self.spy_on(api_root.get_review_requests)

        get_pending_review_requests(
            api_root=api_root,
            username='test-user',
            repository_id=123)

        self.assertSpyCalledWith(
            api_root.get_review_requests,
            from_user='test-user',
            status='pending',
            expand='draft',
            only_fields=(
                'absolute_url,bugs_closed,commit_id,description,draft,'
                'extra_data,id,public,status,summary,url'
            ),
            only_links='diffs,draft',
            repository=123,
            show_all_unpublished=True)

    def test_with_additional_fields(self):
        """Testing get_pending_review_requests with additional_fields="""
        client = self.create_rbclient()
        api_root = client.get_root()

        self.spy_on(api_root.get_review_requests)

        get_pending_review_requests(
            api_root=api_root,
            username='test-user',
            additional_fields=['testing_done', 'ship_it_count'])

        self.assertSpyCalledWith(
            api_root.get_review_requests,
            from_user='test-user',
            status='pending',
            expand='draft',
            only_fields=(
                'absolute_url,bugs_closed,commit_id,description,draft,'
                'extra_data,id,public,status,summary,url,testing_done,'
                'ship_it_count'
            ),
            only_links='diffs,draft',
            show_all_unpublished=True)


class GuessExistingReviewRequestTests(kgb.SpyAgency, TestCase):
    """Unit tests for guess_existing_review_request."""

    def setUp(self):
        super(GuessExistingReviewRequestTests, self).setUp()

        client = self.create_rbclient()
        transport = self.get_rbclient_transport(client)

        self.api_root = client.get_root()
        self.transport = transport

        self.username = 'test-user'
        transport.add_user_url(username=self.username)
        transport.add_session_url(username=self.username)

    def test_with_defaults(self):
        """Testing guess_existing_review_request without match criteria"""
        class MySCMClient(BaseSCMClient):
            pass

        self._add_review_requests(1)

        self.assertIsNone(guess_existing_review_request(
            tool=MySCMClient(),
            revisions={
                'tip': 'abc123',
                'base': 'def456',
            },
            submit_as=self.username,
            api_root=self.api_root))

    def test_with_exact_match(self):
        """Testing guess_existing_review_request with exact match"""
        class MySCMClient(BaseSCMClient):
            def get_commit_message(_self, revisions):
                return {
                    'summary': 'Test summary 2',
                    'description': 'Test description 2',
                }

        self._add_review_requests(3)

        review_request = guess_existing_review_request(
            tool=MySCMClient(),
            revisions={
                'tip': 'abc123',
                'base': 'def456',
            },
            submit_as=self.username,
            api_root=self.api_root)

        self.assertIsNotNone(review_request)
        self.assertEqual(review_request.id, 2)

    def test_with_fuzzy_match_and_no_callback(self):
        """Testing guess_existing_review_request with fuzzy match and no
        is_fuzzy_match_func
        """
        class MySCMClient(BaseSCMClient):
            def get_commit_message(_self, revisions):
                return {
                    'summary': 'Test summary 2',
                    'description': 'Test description 2A',
                }

        self._add_review_requests(3)

        review_request = guess_existing_review_request(
            tool=MySCMClient(),
            revisions={
                'tip': 'abc123',
                'base': 'def456',
            },
            submit_as=self.username,
            api_root=self.api_root)

        self.assertIsNone(review_request)

    def test_with_fuzzy_match_and_callback_true(self):
        """Testing guess_existing_review_request with fuzzy match and
        is_fuzzy_match_func
        """
        class MySCMClient(BaseSCMClient):
            def get_commit_message(_self, revisions):
                return {
                    'summary': 'Test summary 2',
                    'description': 'Test description 2A',
                }

        candidate_ids = []

        def _is_fuzzy_match(review_request):
            candidate_ids.append(review_request.id)

            # Despite #2 being the likely match, we'll go with #1 (2nd in
            # the list of candidates).
            return review_request.id == 1

        self._add_review_requests(3)

        review_request = guess_existing_review_request(
            tool=MySCMClient(),
            revisions={
                'tip': 'abc123',
                'base': 'def456',
            },
            submit_as=self.username,
            is_fuzzy_match_func=_is_fuzzy_match,
            api_root=self.api_root)

        self.assertIsNotNone(review_request)
        self.assertEqual(review_request.id, 1)

        self.assertEqual(candidate_ids, [2, 1])

    def test_with_fuzzy_match_and_callback_false(self):
        """Testing guess_existing_review_request with fuzzy match and
        is_fuzzy_match_func returns False for all
        """
        class MySCMClient(BaseSCMClient):
            def get_commit_message(_self, revisions):
                return {
                    'summary': 'Test summary 2',
                    'description': 'Test description 2A',
                }

        candidate_ids = []

        def _is_fuzzy_match(review_request):
            candidate_ids.append(review_request.id)

            return False

        self._add_review_requests(10)

        review_request = guess_existing_review_request(
            tool=MySCMClient(),
            revisions={
                'tip': 'abc123',
                'base': 'def456',
            },
            submit_as=self.username,
            is_fuzzy_match_func=_is_fuzzy_match,
            api_root=self.api_root)

        self.assertIsNone(review_request)

        # There should only be 5 chances.
        self.assertEqual(candidate_ids, [2, 1, 3, 4, 5])

    def test_with_api_error(self):
        """Testing guess_existing_review_request with APIError when fetching
        review requests
        """
        class MySCMClient(BaseSCMClient):
            pass

        self.spy_on(get_pending_review_requests,
                    op=kgb.SpyOpRaise(APIError()))

        message = (
            'Error getting review requests for user "test-user": '
            'An error occurred when communicating with Review Board.'
        )

        with self.assertRaisesMessage(MatchReviewRequestsError,
                                      message):
            self.assertIsNone(guess_existing_review_request(
                tool=MySCMClient(),
                revisions={
                    'tip': 'abc123',
                    'base': 'def456',
                },
                submit_as=self.username,
                api_root=self.api_root))

    def _add_review_requests(self, count):
        """Add URLs for the specified number of review requests.

        Args:
            count (int):
                The number of review request URLs to add.
        """
        transport = self.transport

        for i in range(1, count + 1):
            transport.add_review_request_url(
                review_request_id=i,
                summary='Test summary %s' % i,
                description='Test description %s' % i,
                extra_data={
                    'key': 'value%s' % i,
                })
