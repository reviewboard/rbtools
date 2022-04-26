"""Test for RBTools post command."""

from __future__ import unicode_literals

from rbtools.commands import CommandError
from rbtools.commands.post import Post
from rbtools.testing import CommandTestsMixin, TestCase


class PostCommandTests(CommandTestsMixin, TestCase):
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
