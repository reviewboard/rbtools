"""Test for RBTools post command."""

from __future__ import unicode_literals

from rbtools.commands import CommandError
from rbtools.commands.post import Post
from rbtools.utils.testbase import RBTestBase


class PostCommandTests(RBTestBase):
    """Tests for rbt post command."""

    def _create_post_command(self, fields):
        """Create an argument parser with the given extra fields.

        Args:
            fields (list of unicode):
                A list of key-value pairs for the field argument.

                Each pair should be of the form key=value.

        Returns:
            argparse.ArgumentParser:
            Argument parser for commandline arguments
        """
        post = Post()
        argv = ['rbt', 'post']
        parser = post.create_arg_parser(argv)
        post.options = parser.parse_args(argv[2:])
        post.options.fields = fields

        return post

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
