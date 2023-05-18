"""Test for RBTools post command."""

from rbtools.clients import RepositoryInfo
from rbtools.clients.git import GitClient
from rbtools.commands import CommandError
from rbtools.commands.post import DiffHistory, Post, SquashedDiff
from rbtools.testing import CommandTestsMixin, TestCase


class BasePostCommandTests(CommandTestsMixin, TestCase):
    """Base class for rbt post tests.

    Version Added:
        3.1
    """

    command_cls = Post

    def _create_post_command(self, fields=None, args=None, **kwargs):
        """Create an argument parser with the given extra fields.

        Args:
            fields (list of unicode):
                A list of key-value pairs for the field argument.

                Each pair should be of the form key=value.

            args (list of unicode):
                A list of command line arguments to be passed to the parser.

                The command line will receive each item in the list.

        Returns:
            rbtools.commands.post.POST:
            A POST instance for communicating with the rbt server
        """
        command = self.create_command(args=args, **kwargs)

        if fields is not None:
            command.options.fields = fields

        return command


class PostCommandTests(BasePostCommandTests):
    """Tests for rbt post command."""

    command_cls = Post

    def test_post_one_extra_fields(self):
        """Testing rbt post --field <name>=<value>"""
        post = self.create_command(args=['--field', 'foo=bar'])
        post.post_process_options()

        self.assertEqual(
            post.options.extra_fields,
            {'extra_data.foo': 'bar'})

    def test_post_multiple_extra_fields(self):
        """Testing rbt post --field <name1>=<value> --field <name2>=<value>"""
        post = self.create_command(args=[
            '--field', 'foo=bar',
            '--field', 'desc=new',
        ])
        post.post_process_options()

        self.assertEqual(
            post.options.extra_fields,
            {
                'extra_data.foo': 'bar',
                'extra_data.desc': 'new',
            })

    def test_native_fields_through_extra_fields(self):
        """Testing rbt post --field with natively-supported field arguments"""
        post = self.create_command(args=[
            '--field', 'description=testing',
            '--field', 'summary=native testing',
            '--field', 'testing-done=No tests',
        ])
        post.post_process_options()

        self.assertEqual(post.options.description, 'testing')
        self.assertEqual(post.options.summary, 'native testing')
        self.assertEqual(post.options.testing_done, 'No tests')

    def test_wrong_argument_entry(self):
        """Testing rbt post --field <name> without value"""
        post = self.create_command(args=['--field', 'description'])

        message = (
            'The --field argument should be in the form of: '
            '--field name=value; got "description" instead.'
        )

        with self.assertRaisesMessage(CommandError, message):
            post.post_process_options()

    def test_multiple_delimiter(self):
        """Testing rbt post --field with "=" in values"""
        post = self.create_command(args=[
            '--field', 'myField=this=string=has=equals=signs',
        ])
        post.post_process_options()

        self.assertEqual(
            post.options.extra_fields,
            {'extra_data.myField': 'this=string=has=equals=signs'})

    def test_arg_field_set_again_by_custom_fields(self):
        """Testing rbt post --field with field name duplicating native
        argument
        """
        post = self.create_command(args=[
            '--field', 'description=test',
            '--description', 'test',
        ])

        message = (
            'The "description" field was provided by both --description= '
            'and --field description=. Please use --description instead.'
        )

        with self.assertRaisesMessage(CommandError, message):
            post.post_process_options()

    def test_post_setting_target_users(self):
        """Testing rbt post --target-people=<username>"""
        post = self.create_command(args=['--target-people', 'test_person'])
        post.post_process_options()

        self.assertEqual(post.options.target_people, 'test_person')

    def test_post_setting_target_groups(self):
        """Testing rbt post --target-groups=<group>"""
        post = self.create_command(args=['--target-groups', 'test_group'])
        post.post_process_options()

        self.assertEqual(post.options.target_groups, 'test_group')

    def test_post_setting_target_users_on_update(self):
        """Testing rbt post -r <id> --target-people=<username>"""
        post = self.create_command(args=[
            '--target-people', 'test_person',
            '--review-request-id', '12345',
        ])
        post.post_process_options()

        self.assertEqual(post.options.target_people, 'test_person')

    def test_post_setting_target_groups_on_update(self):
        """Testing rbt post -r <id> --target-groups=<group>"""
        post = self.create_command(args=[
            '--target-groups', 'test_group',
            '--review-request-id', '12345',
        ])
        post.post_process_options()

        self.assertEqual(post.options.target_groups, 'test_group')

    def test_post_default_target_users(self):
        """Testing rbt post with TARGET_PEOPLE= in .reviewboardrc"""
        with self.reviewboardrc({'TARGET_PEOPLE': 'test_person'}):
            post = self.create_command()
            post.post_process_options()

        self.assertEqual(post.options.target_people, 'test_person')

    def test_post_default_target_groups(self):
        """Testing rbt post with TARGET_GROUPS= in .reviewboardrc"""
        with self.reviewboardrc({'TARGET_GROUPS': 'test_group'}):
            post = self.create_command()
            post.post_process_options()

        self.assertEqual(post.options.target_groups, 'test_group')

    def test_post_no_default_target_users_update(self):
        """Testing rbt post -r <id> with TARGET_PEOPLE= in .reviewboardrc"""
        with self.reviewboardrc({'TARGET_PEOPLE': 'test_person'}):
            post = self.create_command(args=['--review-request-id', '12345'])
            post.post_process_options()

        self.assertIsNone(post.options.target_people)

    def test_post_no_default_target_groups_update(self):
        """Testing rbt post -r <id> with TARGET_GROUPS= in .reviewboardrc"""
        with self.reviewboardrc({'TARGET_GROUPS': 'test_group'}):
            post = self.create_command(args=['--review-request-id', '12345'])
            post.post_process_options()

        self.assertIsNone(post.options.target_groups)


class PostBuildNewReviewRequestDataTests(BasePostCommandTests):
    """Unit tests for Post._build_new_review_request_data."""

    def test_defaults(self):
        """Testing Post._build_new_review_request_data"""
        self._run_test(expected_request_data={
            'create_with_history': True,
            'repository': 1,
        })

    def test_with_can_bookmark(self):
        """Testing Post._build_new_review_request_data with
        SCMClient.can_bookmark=True
        """
        self._run_test(
            bookmark='my-bookmark',
            expected_request_data={
                'create_with_history': True,
                'extra_data_json': {
                    'local_bookmark': 'my-bookmark',
                },
                'repository': 1,
            })

    def test_with_can_bookmark_and_no_json_patching_cap(self):
        """Testing Post._build_new_review_request_data with
        SCMClient.can_bookmark=True and no json_patching capability
        """
        self._run_test(
            bookmark='my-bookmark',
            cap_json_patching=False,
            expected_request_data={
                'create_with_history': True,
                'extra_data__local_bookmark': 'my-bookmark',
                'repository': 1,
            })

    def test_with_can_branch(self):
        """Testing Post._build_new_review_request_data with
        SCMClient.can_branch=True
        """
        self._run_test(
            branch='my-branch',
            expected_request_data={
                'create_with_history': True,
                'extra_data_json': {
                    'local_branch': 'my-branch',
                },
                'repository': 1,
            })

    def test_with_can_branch_and_no_json_patching_cap(self):
        """Testing Post._build_new_review_request_data with
        SCMClient.can_branch=True and no json_patching capability
        """
        self._run_test(
            branch='my-branch',
            cap_json_patching=False,
            expected_request_data={
                'create_with_history': True,
                'extra_data__local_branch': 'my-branch',
                'repository': 1,
            })

    def test_with_squashed_diff_changeunm(self):
        """Testing Post._build_new_review_request_data with squashed diff with
        changenum
        """
        self._run_test(
            squashed_diff=SquashedDiff(diff=b'',
                                       parent_diff=None,
                                       base_commit_id=None,
                                       base_dir=None,
                                       commit_id=None,
                                       changenum=123,
                                       review_request_extra_data={}),
            expected_request_data={
                'changenum': 123,
                'repository': 1,
            })

    def test_with_squashed_diff_commit_id(self):
        """Testing Post._build_new_review_request_data with squashed diff with
        commit_id
        """
        self._run_test(
            squashed_diff=SquashedDiff(diff=b'',
                                       parent_diff=None,
                                       base_commit_id=None,
                                       base_dir=None,
                                       commit_id='abc1234',
                                       changenum=None,
                                       review_request_extra_data={}),
            expected_request_data={
                'commit_id': 'abc1234',
                'repository': 1,
            })

    def test_with_squashed_diff_commit_id_no_capability(self):
        """Testing Post._build_new_review_request_data with squashed diff with
        commit_id and capability review_requests.commit_ids=False
        """
        self._run_test(
            cap_commit_ids=False,
            squashed_diff=SquashedDiff(diff=b'',
                                       parent_diff=None,
                                       base_commit_id=None,
                                       base_dir=None,
                                       commit_id='abc1234',
                                       changenum=None,
                                       review_request_extra_data={}),
            expected_request_data={
                'repository': 1,
            })

    def test_with_squashed_diff_extra_data(self):
        """Testing Post._build_new_review_request_data with squashed diff
        containing review_request_extra_data
        """
        self._run_test(
            squashed_diff=SquashedDiff(
                diff=b'',
                parent_diff=None,
                base_commit_id=None,
                base_dir=None,
                commit_id=None,
                changenum=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={
                'extra_data_json': {
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                },
                'repository': 1,
            })

    def test_with_squashed_diff_extra_data_no_json_patching_cap(self):
        """Testing Post._build_new_review_request_data with squashed diff
        containing review_request_extra_data and no json_patching capability
        """
        self._run_test(
            cap_json_patching=False,
            squashed_diff=SquashedDiff(
                diff=b'',
                parent_diff=None,
                base_commit_id=None,
                base_dir=None,
                commit_id=None,
                changenum=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={
                'repository': 1,
            })

    def test_with_diff_history_extra_data(self):
        """Testing Post._build_new_review_request_data with squashed diff
        containing review_request_extra_data
        """
        self._run_test(
            diff_history=DiffHistory(
                entries=[],
                parent_diff=None,
                base_commit_id=None,
                validation_info=None,
                cumulative_diff=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={
                'create_with_history': True,
                'extra_data_json': {
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                },
                'repository': 1,
            })

    def test_with_diff_history_extra_data_no_json_patching_cap(self):
        """Testing Post._build_new_review_request_data with squashed diff
        containing review_request_extra_data and no json_patching capability
        """
        self._run_test(
            cap_json_patching=False,
            diff_history=DiffHistory(
                entries=[],
                parent_diff=None,
                base_commit_id=None,
                validation_info=None,
                cumulative_diff=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={
                'create_with_history': True,
                'repository': 1,
            })

    def test_with_submit_as(self):
        """Testing Post._build_new_review_request_data with submit_as"""
        self._run_test(
            cap_commit_ids=False,
            submit_as='some-user',
            expected_request_data={
                'create_with_history': True,
                'repository': 1,
                'submit_as': 'some-user',
            })

    def _run_test(self,
                  expected_request_data,
                  bookmark=None,
                  branch=None,
                  squashed_diff=None,
                  diff_history=None,
                  submit_as=None,
                  cap_commit_ids=True,
                  cap_json_patching=True):
        """Run a test with the provided and expected data.

        Args:
            expected_request_data (dict):
                The expected data to be returned by the function.

            bookmark (unicode, optional):
                An optional bookmark to simulate being returned by the tool.

            branch (unicode, optional):
                An optional branch to simulate being returned by the tool.

            squashed_diff (rbtools.commands.post.SquashedDiff, optional):
                An optional squashed diff to set.

            diff_history (rbtools.commands.post.SquashedDiff, optional):
                An optional diff history to set.

            submit_as (unicode, optional):
                An optional username to simulate posting as.

            cap_commit_ids (bool, optional):
                The value of the ``commit_ids`` capability to use.

            cap_json_patching (bool, optional):
                The value of the ``json_patching`` capability to use.

        Raises:
            AssertionError:
                An expectation failed.
        """
        class MyTool(GitClient):
            name = 'my-tool'
            can_bookmark = (bookmark is not None)
            can_branch = (branch is not None)

            def get_current_bookmark(self):
                return bookmark

            def get_current_branch(self):
                return branch

        def setup_transport(transport):
            transport.capabilities['extra_data']['json_patching'] = \
                cap_json_patching
            transport.capabilities['review_requests']['commit_ids'] = \
                cap_commit_ids

            transport.add_repository_urls(path=repo_info.path,
                                          tool=tool.name)

        repo_info = RepositoryInfo(path='/path')
        tool = MyTool()

        post = self.create_command(
            repository_info=repo_info,
            tool=tool,
            setup_transport_func=setup_transport,
            initialize=True)

        request_data = post._build_new_review_request_data(
            squashed_diff=squashed_diff,
            diff_history=diff_history,
            submit_as=submit_as)

        self.assertEqual(request_data, expected_request_data)


class BuildReviewRequestDraftDataTests(BasePostCommandTests):
    """Unit tests for Post._build_review_request_draft_data."""

    def test_defaults(self):
        """Testing Post._build_review_request_draft_data"""
        self._run_test(expected_request_data={})

    def test_with_publish(self):
        """Testing Post._build_review_request_draft_data with --publish"""
        self._run_test(
            args=['--publish'],
            expected_request_data={
                'public': True,
            })

    def test_with_trivial_publish(self):
        """Testing Post._build_review_request_draft_data with
        --trivial-publish
        """
        self._run_test(
            args=['--trivial-publish'],
            expected_request_data={
                'public': True,
                'trivial': True,
            })

    def test_with_trivial_publish_no_cap(self):
        """Testing Post._build_review_request_draft_data with
        --trivial-publish and no capability
        """
        self._run_test(
            args=['--trivial-publish'],
            cap_trivial_publish=False,
            expected_request_data={
                'public': True,
            })

    def test_with_markdown(self):
        """Testing Post._build_review_request_draft_data with --markdown and
        no other fields
        """
        self._run_test(
            args=['--markdown'],
            expected_request_data={})

    def test_with_native_field_args(self):
        """Testing Post._build_review_request_draft_data with native
        --<field> arguments
        """
        self._run_test(
            args=[
                '--branch=new-branch',
                '--bugs-closed=123,  456  789',
                '--depends-on=1,2,3',
                '--description=New Description',
                '--summary=New Summary',
                '--target-groups=group1,group2',
                '--target-people=user1,user2',
                '--testing-done=New Testing Done',
            ],
            expected_request_data={
                'branch': 'new-branch',
                'bugs_closed': '123,456,789',
                'depends_on': '1,2,3',
                'description': 'New Description',
                'summary': 'New Summary',
                'target_groups': 'group1,group2',
                'target_people': 'user1,user2',
                'testing_done': 'New Testing Done',
                'text_type': 'plain',
            })

    def test_with_native_field_args_and_diff_only(self):
        """Testing Post._build_review_request_draft_data with native
        --<field> arguments and --diff-only
        """
        self._run_test(
            args=[
                '--branch=new-branch',
                '--depends-on=1,2,3',
                '--description=New Description',
                '--summary=New Summary',
                '--target-groups=group1,group2',
                '--target-people=user1,user2',
                '--testing-done=New Testing Done',
                '--diff-only',
            ],
            expected_request_data={})

    def test_with_native_field_args_and_markdown(self):
        """Testing Post._build_review_request_draft_data with native
        --<field> arguments and --markdown
        """
        self._run_test(
            args=[
                '--branch=new-branch',
                '--depends-on=1,2,3',
                '--description=New Description',
                '--summary=New Summary',
                '--target-groups=group1,group2',
                '--target-people=user1,user2',
                '--testing-done=New Testing Done',
                '--markdown',
            ],
            expected_request_data={
                'branch': 'new-branch',
                'depends_on': '1,2,3',
                'description': 'New Description',
                'summary': 'New Summary',
                'target_groups': 'group1,group2',
                'target_people': 'user1,user2',
                'testing_done': 'New Testing Done',
                'text_type': 'markdown',
            })

    def test_with_change_description(self):
        """Testing Post._build_review_request_draft_data with
        --change-description
        """
        self._run_test(
            args=[
                '--change-description=New Change Description',
            ],
            expected_request_data={
                'changedescription': 'New Change Description',
                'changedescription_text_type': 'plain',
            })

    def test_with_change_description_and_markdown(self):
        """Testing Post._build_review_request_draft_data with
        --change-description and --markdown
        """
        self._run_test(
            args=[
                '--change-description=New Change Description',
                '--markdown',
            ],
            expected_request_data={
                'changedescription': 'New Change Description',
                'changedescription_text_type': 'markdown',
            })

    def test_with_can_bookmark(self):
        """Testing Post._build_review_request_draft_data with
        SCMClient.can_bookmark=True
        """
        self._run_test(
            bookmark='my-bookmark',
            expected_request_data={
                'extra_data_json': {
                    'local_bookmark': 'my-bookmark',
                },
            })

    def test_with_can_bookmark_and_no_json_patching_cap(self):
        """Testing Post._build_review_request_draft_data with
        SCMClient.can_bookmark=True and no json_patching capability
        """
        self._run_test(
            bookmark='my-bookmark',
            cap_json_patching=False,
            expected_request_data={
                'extra_data__local_bookmark': 'my-bookmark',
            })

    def test_with_can_bookmark_and_review_request_is_new(self):
        """Testing Post._build_review_request_draft_data with
        SCMClient.can_bookmark=True and review request is newly-created
        """
        self._run_test(
            bookmark='my-bookmark',
            review_request_is_new=True,
            expected_request_data={})

    def test_with_can_branch(self):
        """Testing Post._build_review_request_draft_data with
        SCMClient.can_branch=True
        """
        self._run_test(
            branch='my-branch',
            expected_request_data={
                'extra_data_json': {
                    'local_branch': 'my-branch',
                },
            })

    def test_with_can_branch_and_no_json_patching_cap(self):
        """Testing Post._build_review_request_draft_data with
        SCMClient.can_branch=True and no json_patching capability
        """
        self._run_test(
            branch='my-branch',
            cap_json_patching=False,
            expected_request_data={
                'extra_data__local_branch': 'my-branch',
            })

    def test_with_can_branch_and_review_request_is_new(self):
        """Testing Post._build_review_request_draft_data with
        SCMClient.can_branch=True and review request is newly-created
        """
        self._run_test(
            branch='my-branch',
            review_request_is_new=True,
            expected_request_data={})

    def test_with_squashed_diff(self):
        """Testing Post._build_review_request_draft_data with squashed diff"""
        self._run_test(
            squashed_diff=SquashedDiff(diff=b'',
                                       parent_diff=None,
                                       base_commit_id=None,
                                       base_dir=None,
                                       commit_id=None,
                                       changenum=None,
                                       review_request_extra_data={}),
            expected_request_data={})

    def test_with_squashed_diff_and_commit_id(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        with commit_id
        """
        self._run_test(
            squashed_diff=SquashedDiff(diff=b'',
                                       parent_diff=None,
                                       base_commit_id=None,
                                       base_dir=None,
                                       commit_id='abc123',
                                       changenum=None,
                                       review_request_extra_data={}),
            expected_request_data={
                'commit_id': 'abc123',
            })

    def test_with_squashed_diff_and_commit_id_no_change(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        with commit_id not changing from draft
        """
        self._run_test(
            cap_commit_ids=False,
            draft_commit_id='abc123',
            squashed_diff=SquashedDiff(diff=b'',
                                       parent_diff=None,
                                       base_commit_id=None,
                                       base_dir=None,
                                       commit_id='def456',
                                       changenum=None,
                                       review_request_extra_data={}),
            expected_request_data={})

    def test_with_squashed_diff_and_commit_id_no_cap(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        with commit_id and no capability
        """
        self._run_test(
            cap_commit_ids=False,
            squashed_diff=SquashedDiff(diff=b'',
                                       parent_diff=None,
                                       base_commit_id=None,
                                       base_dir=None,
                                       commit_id='abc123',
                                       changenum=None,
                                       review_request_extra_data={}),
            expected_request_data={})

    def test_with_squashed_diff_extra_data(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        containing review_request_extra_data
        """
        self._run_test(
            squashed_diff=SquashedDiff(
                diff=b'',
                parent_diff=None,
                base_commit_id=None,
                base_dir=None,
                commit_id=None,
                changenum=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={
                'extra_data_json': {
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                },
            })

    def test_with_squashed_diff_extra_data_no_json_patching_cap(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        containing review_request_extra_data and no json_patching capability
        """
        self._run_test(
            cap_json_patching=False,
            squashed_diff=SquashedDiff(
                diff=b'',
                parent_diff=None,
                base_commit_id=None,
                base_dir=None,
                commit_id=None,
                changenum=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={})

    def test_with_squashed_diff_extra_data_and_review_requst_is_new(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        containing review_request_extra_data and review request is
        newly-created
        """
        self._run_test(
            review_request_is_new=True,
            squashed_diff=SquashedDiff(
                diff=b'',
                parent_diff=None,
                base_commit_id=None,
                base_dir=None,
                commit_id=None,
                changenum=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={})

    def test_with_diff_history_extra_data(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        containing review_request_extra_data
        """
        self._run_test(
            diff_history=DiffHistory(
                entries=[],
                parent_diff=None,
                base_commit_id=None,
                validation_info=None,
                cumulative_diff=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={
                'extra_data_json': {
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                },
            })

    def test_with_diff_history_extra_data_no_json_patching_cap(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        containing review_request_extra_data and no json_patching capability
        """
        self._run_test(
            cap_json_patching=False,
            diff_history=DiffHistory(
                entries=[],
                parent_diff=None,
                base_commit_id=None,
                validation_info=None,
                cumulative_diff=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={})

    def test_with_diff_history_extra_data_and_review_requst_is_new(self):
        """Testing Post._build_review_request_draft_data with squashed diff
        containing review_request_extra_data and review request is
        newly-created
        """
        self._run_test(
            review_request_is_new=True,
            diff_history=DiffHistory(
                entries=[],
                parent_diff=None,
                base_commit_id=None,
                validation_info=None,
                cumulative_diff=None,
                review_request_extra_data={
                    'new_key1': 'new_value',
                    'new_key2': {
                        'new_subkey': [1, 2, 3],
                    },
                }),
            expected_request_data={})

    def test_with_guess_no(self):
        """Testing Post._build_review_request_draft_data with
        --guess-fields=no
        """
        self._run_test(
            args=['--guess-fields=no'],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={})

    def test_with_guess_yes_and_review_request_id(self):
        """Testing Post._build_review_request_draft_data with
        --guess-fields=yes and --review-request-id=<ID>
        """
        self._run_test(
            args=[
                '--review-request-id=123',
                '--guess-fields=yes',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'description': 'This is the multi-line\ndescription.',
                'summary': 'This is the summary.',
                'text_type': 'plain',
            })

    def test_with_guess_yes_and_update(self):
        """Testing Post._build_review_request_draft_data with
        --guess-fields=yes and --update
        """
        self._run_test(
            args=[
                '--update',
                '--guess-fields=yes',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'description': 'This is the multi-line\ndescription.',
                'summary': 'This is the summary.',
                'text_type': 'plain',
            })

    def test_with_guess_auto(self):
        """Testing Post._build_review_request_draft_data with
        --guess-fields=auto
        """
        self._run_test(
            args=['--guess-fields=auto'],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'description': 'This is the multi-line\ndescription.',
                'summary': 'This is the summary.',
                'text_type': 'plain',
            })

    def test_with_guess_auto_and_review_request_id(self):
        """Testing Post._build_review_request_draft_data with
        --guess-fields=auto and --review-request-id=<id>
        """
        self._run_test(
            args=[
                '--review-request-id=123',
                '--guess-fields=auto',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={})

    def test_with_guess_auto_and_update(self):
        """Testing Post._build_review_request_draft_data with
        --guess-fields=auto and --update
        """
        self._run_test(
            args=[
                '--update',
                '--guess-fields=auto',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={})

    def test_with_guess_summary_no(self):
        """Testing Post._build_review_request_draft_data with
        --guess-summary=no
        """
        # Note that --guess-description=auto by default, hence these results.
        self._run_test(
            args=['--guess-summary=no'],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'description': (
                    'This is the summary.\n'
                    '\n'
                    'This is the multi-line\n'
                    'description.'
                ),
                'text_type': 'plain',
            })

    def test_with_guess_summary_yes_and_review_request_id(self):
        """Testing Post._build_review_request_draft_data with
        --guess-summary=yes and --review-request-id=<ID>
        """
        self._run_test(
            args=[
                '--review-request-id=123',
                '--guess-summary=yes',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'summary': 'This is the summary.',
            })

    def test_with_guess_summary_yes_and_update(self):
        """Testing Post._build_review_request_draft_data with
        --guess-summary=yes and --update
        """
        self._run_test(
            args=[
                '--update',
                '--guess-summary=yes',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'summary': 'This is the summary.',
            })

    def test_with_guess_summary_auto(self):
        """Testing Post._build_review_request_draft_data with
        --guess-summary=auto
        """
        # Note that --guess-description=auto by default, hence these results.
        self._run_test(
            args=['--guess-summary=auto'],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
                'summary': 'This is the summary.',
                'text_type': 'plain',
            })

    def test_with_guess_summary_auto_and_review_request_id(self):
        """Testing Post._build_review_request_draft_data with
        --guess-summary=auto and --review-request-id=<id>
        """
        self._run_test(
            args=[
                '--review-request-id=123',
                '--guess-summary=auto',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={})

    def test_with_guess_summary_auto_and_update(self):
        """Testing Post._build_review_request_draft_data with
        --guess-summary=auto and --update
        """
        self._run_test(
            args=[
                '--update',
                '--guess-summary=auto',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={})

    def test_with_guess_description_no(self):
        """Testing Post._build_review_request_draft_data with
        --guess-description=no
        """
        # Note that --guess-summary=auto by default, hence these results.
        self._run_test(
            args=['--guess-description=no'],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'summary': 'This is the summary.',
            })

    def test_with_guess_description_yes_and_review_request_id(self):
        """Testing Post._build_review_request_draft_data with
        --guess-description=yes and --review-request-id=<ID>
        """
        self._run_test(
            args=[
                '--review-request-id=123',
                '--guess-description=yes',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'description': (
                    'This is the summary.\n'
                    '\n'
                    'This is the multi-line\n'
                    'description.'
                ),
                'text_type': 'plain',
            })

    def test_with_guess_description_yes_and_update(self):
        """Testing Post._build_review_request_draft_data with
        --guess-description=yes and --update
        """
        self._run_test(
            args=[
                '--update',
                '--guess-description=yes',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'description': (
                    'This is the summary.\n'
                    '\n'
                    'This is the multi-line\n'
                    'description.'
                ),
                'text_type': 'plain',
            })

    def test_with_guess_description_auto(self):
        """Testing Post._build_review_request_draft_data with
        --guess-description=auto
        """
        # Note that --guess-summary=auto by default, hence these results.
        self._run_test(
            args=['--guess-description=auto'],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
                'summary': 'This is the summary.',
                'text_type': 'plain',
            })

    def test_with_guess_description_auto_and_review_request_id(self):
        """Testing Post._build_review_request_draft_data with
        --guess-description=auto and --review-request-id=<id>
        """
        self._run_test(
            args=[
                '--review-request-id=123',
                '--guess-description=auto',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={})

    def test_with_guess_description_auto_and_update(self):
        """Testing Post._build_review_request_draft_data with
        --guess-description=auto and --update
        """
        self._run_test(
            args=[
                '--update',
                '--guess-description=auto',
            ],
            commit_message={
                'summary': 'This is the summary.',
                'description': (
                    'This is the multi-line\n'
                    'description.'
                ),
            },
            expected_request_data={})

    def _run_test(self,
                  expected_request_data,
                  args=[],
                  squashed_diff=None,
                  diff_history=None,
                  draft_commit_id=None,
                  review_request_is_new=False,
                  bookmark=None, branch=None,
                  commit_message=None,
                  cap_trivial_publish=True,
                  cap_commit_ids=True,
                  cap_json_patching=True):
        """Run a test with the provided and expected data.

        Args:
            expected_request_data (dict):
                The expected data to be returned by the function.

            args (list of unicode):
                Arguments to pass to the command.

            squashed_diff (rbtools.commands.post.SquashedDiff, optional):
                An optional squashed diff to set.

            diff_history (rbtools.commands.post.SquashedDiff, optional):
                An optional diff history to set.

            draft_commit_id (unicode, optional):
                An optional commit ID to set.

            review_request_is_new (bool, optional):
                Whether to simulate that the review request has just been
                created.

            bookmark (unicode, optional):
                An optional bookmark to simulate being returned by the tool.

            branch (unicode, optional):
                An optional branch to simulate being returned by the tool.

            commit_message (dict, optional):
                An optional commit message result dictionary.

            cap_trivial_publish (bool, optional):
                The value of the ``trivial_publish`` capability to use.

            cap_commit_ids (bool, optional):
                The value of the ``commit_ids`` capability to use.

            cap_json_patching (bool, optional):
                The value of the ``json_patching`` capability to use.

        Raises:
            AssertionError:
                An expectation failed.
        """
        class MyTool(GitClient):
            name = 'my-tool'
            can_bookmark = (bookmark is not None)
            can_branch = (branch is not None)

            def get_current_bookmark(self):
                return bookmark

            def get_current_branch(self):
                return branch

            def get_commit_message(self, revisions):
                return commit_message

        def setup_transport(transport):
            transport.capabilities['extra_data']['json_patching'] = \
                cap_json_patching
            transport.capabilities['review_requests'].update({
                'commit_ids': cap_commit_ids,
                'trivial_publish': cap_trivial_publish,
            })

            transport.add_review_request_url(
                review_request_id=review_request_id)
            transport.add_review_request_draft_url(
                review_request_id=review_request_id,
                draft_id=130,
                commit_id=draft_commit_id)
            transport.add_repository_urls(path=repo_info.path,
                                          tool=tool.name)

        review_request_id = 123

        repo_info = RepositoryInfo(path='/path')
        tool = MyTool()

        post = self.create_command(
            args=args,
            repository_info=repo_info,
            tool=tool,
            setup_transport_func=setup_transport,
            initialize=True)
        post.revisions = {
            'base': 'def456',
            'tip': 'abc123',
        }
        post.post_process_options()

        api_root = post.api_root

        request_data = post._build_review_request_draft_data(
            review_request_is_new=review_request_is_new,
            review_request=api_root.get_review_request(
                review_request_id=review_request_id),
            draft=api_root.get_draft(review_request_id=review_request_id),
            squashed_diff=squashed_diff,
            diff_history=diff_history)

        self.assertEqual(request_data, expected_request_data)
