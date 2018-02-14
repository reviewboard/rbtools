"""Test for RBTools post command."""

from __future__ import unicode_literals

from rbtools.commands import CommandError
from rbtools.commands.post import Post
from rbtools.utils.testbase import RBTestBase


class PostCommandTests(RBTestBase):
    """Tests for rbt post command."""

    def test_post_one_extra_fields(self):
        """Testing one extra field argument with rbt post --field foo=bar"""
        post = self._create_post_command(['foo=bar'])
        post.post_process_options()
        self.assertEqual(
            post.options.extra_fields,
            {'extra_data.foo': 'bar'})

    def test_post_multiple_extra_fields(self):
        """Testing multiple extra field arguments with rbt post --field
        foo=bar --field desc=new
        """
        post = self._create_post_command(['foo=bar', 'desc=new'])
        post.post_process_options()
        self.assertEqual(
            post.options.extra_fields,
            {
                'extra_data.foo': 'bar',
                'extra_data.desc': 'new',
            })

    def test_native_fields_through_extra_fields(self):
        """Testing built-in fields through extra_fields with rbt post --field
        description=testing --field summary='native testing' --field
        testing-done='No tests'
        """
        post = self._create_post_command([
            'description=testing',
            'summary=native testing',
            'testing-done=No tests',
        ])
        post.post_process_options()
        self.assertEqual(post.options.description, 'testing')
        self.assertEqual(post.options.summary, 'native testing')
        self.assertEqual(post.options.testing_done, 'No tests')

    def test_wrong_argument_entry(self):
        """Testing built-in fields through extra_fields with rbt post --field
        description and rbt post --field testing_done='No tests'
        """
        post = self._create_post_command(['testing_done=No tests'])
        self.assertEqual(post.options.testing_done, None)
        post = self._create_post_command(['description'])

        self.assertRaises(CommandError, post.post_process_options)

    def test_multiple_delimiter(self):
        """Testing multiple delimiters with rbt post --field
        myField=this=string=has=equals=signs
        """
        post = self._create_post_command(
            ['myField=this=string=has=equals=signs'])
        post.post_process_options()
        self.assertEqual(
            post.options.extra_fields,
            {'extra_data.myField': 'this=string=has=equals=signs'})

    def test_arg_field_set_again_by_custom_fields(self):
        """Testing argument duplication with rbt post --field
        myField=test --description test
        """
        post = self._create_post_command(['description=test'])
        post.options.description = 'test'

        self.assertRaises(CommandError, post.post_process_options)

    def test_post_setting_target_users(self):
        """Testing setting the target person with rbt post
        --target-people=test_person
        """
        post = self._create_post_command(args=['--target-people',
                                               'test_person'])
        post.post_process_options()
        self.assertEqual(post.options.target_people, 'test_person')

    def test_post_setting_target_groups(self):
        """Testing setting the target group with rbt post
        --target-groups=test_group
        """
        post = self._create_post_command(args=['--target-groups',
                                               'test_group'])
        post.post_process_options()
        self.assertEqual(post.options.target_groups, 'test_group')

    def test_post_setting_target_users_on_update(self):
        """Testing setting the target person on an update with rbt post
        --target-people=test_person --review-request-id=12345
        """
        post = self._create_post_command(args=['--target-people',
                                               'test_person',
                                               '--review-request-id', '12345'])
        post.post_process_options()
        self.assertEqual(post.options.target_people, 'test_person')

    def test_post_setting_target_groups_on_update(self):
        """Testing setting the target group on an update with rbt post
        --target-groups=test_group --review-request-id=12345
        """
        post = self._create_post_command(args=['--target-groups', 'test_group',
                                               '--review-request-id', '12345'])
        post.post_process_options()
        self.assertEqual(post.options.target_groups, 'test_group')

    def test_post_default_target_users(self):
        """Testing setting target person via config file with rbt post
        """
        with self.reviewboardrc({'TARGET_PEOPLE': 'test_person'},
                                use_temp_dir=True):
            post = self._create_post_command()
            post.post_process_options()
            self.assertEqual(post.options.target_people, 'test_person')

    def test_post_default_target_groups(self):
        """Testing setting target group via config file with rbt post
        """
        with self.reviewboardrc({'TARGET_GROUPS': 'test_group'},
                                use_temp_dir=True):
            post = self._create_post_command()
            post.post_process_options()
            self.assertEqual(post.options.target_groups, 'test_group')

    def test_post_no_default_target_users_update(self):
        """Testing setting target person on update via config file
        with rbt post --review-request-id=12345
        """
        with self.reviewboardrc({'TARGET_PEOPLE': 'test_person'},
                                use_temp_dir=True):
            post = self._create_post_command(args=['--review-request-id',
                                                   '12345'])
            post.post_process_options()
            self.assertEqual(post.options.target_people, None)

    def test_post_no_default_target_groups_update(self):
        """Testing setting target group on update via config file
        with rbt post --review-request-id=12345
        """
        with self.reviewboardrc({'TARGET_GROUPS': 'test_group'},
                                use_temp_dir=True):
            post = self._create_post_command(args=['--review-request-id',
                                                   '12345'])
            post.post_process_options()
            self.assertEqual(post.options.target_groups, None)

    def _create_post_command(self, fields=None, args=None):
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
        post = Post()
        argv = ['rbt', 'post']

        if args is not None:
            argv.extend(args)

        parser = post.create_arg_parser(argv)
        post.options = parser.parse_args(argv[2:])

        if fields is not None:
            post.options.fields = fields

        return post
