"""Unit tests for rbtools.config.loader.

Version Added:
    5.0
"""

from __future__ import annotations

import os
import sys

from rbtools.config.errors import ConfigSyntaxError
from rbtools.config.loader import (get_config_paths,
                                   load_config,
                                   parse_config_file)
from rbtools.utils.filesystem import make_tempdir
from rbtools.testing import TestCase


class GetConfigPathsTests(TestCase):
    """Unit tests for get_config_paths.

    Version Added:
        5.0
    """

    needs_temp_home = True

    def test_with_no_files(self) -> None:
        """Testing get_config_paths with no .reviewboardrc files found"""
        self.assertEqual(get_config_paths(), [])

    def test_with_home_dir_only(self) -> None:
        """Testing get_config_paths with .reviewboardrc in home directory
        only
        """
        repo_dir = make_tempdir()
        os.chdir(repo_dir)

        config_file = self.write_reviewboardrc(
            parent_dir=self.get_user_home())

        self.assertEqual(get_config_paths(), [config_file])

    def test_with_home_and_repo_dir(self) -> None:
        """Testing get_config_paths with repository-provided .reviewboardrc
        files
        """
        repo_dir = make_tempdir()
        subdir = os.path.join(repo_dir, 'subdir')

        config_file1 = self.write_reviewboardrc(parent_dir=subdir)
        config_file2 = self.write_reviewboardrc(parent_dir=repo_dir)
        config_file3 = self.write_reviewboardrc(
            parent_dir=self.get_user_home())

        os.chdir(subdir)

        self.assertEqual(
            get_config_paths(),
            [
                config_file1,
                config_file2,
                config_file3,
            ])

    def test_with_rbtools_config_path(self) -> None:
        """Testing get_config_paths with RBTOOLS_CONFIG_PATH= environment
        variables
        """
        repo_dir = make_tempdir()
        subdir = os.path.join(repo_dir, 'subdir')

        tempdir1 = make_tempdir()
        tempdir2 = make_tempdir()

        config_file1 = self.write_reviewboardrc(parent_dir=tempdir1)
        config_file2 = self.write_reviewboardrc(parent_dir=tempdir2)
        config_file3 = self.write_reviewboardrc(parent_dir=subdir)
        config_file4 = self.write_reviewboardrc(parent_dir=repo_dir)
        config_file5 = self.write_reviewboardrc(
            parent_dir=self.get_user_home())

        os.chdir(subdir)

        os.environ['RBTOOLS_CONFIG_PATH'] = os.pathsep.join([
            tempdir1,
            tempdir2,
            '/badXXX',
        ])

        try:
            config_paths = get_config_paths()
        finally:
            os.environ.pop('RBTOOLS_CONFIG_PATH')

        self.assertEqual(
            config_paths,
            [
                config_file1,
                config_file2,
                config_file3,
                config_file4,
                config_file5,
            ])


class ParseConfigFileTests(TestCase):
    """Unit tests for parse_config_file.

    Version Added:
        5.0
    """

    needs_temp_home = True

    def test_with_valid_config(self) -> None:
        """Testing parse_config_file with valid configuration"""
        config_file = self.write_reviewboardrc({
            'BRANCH': 'my-branch',
            'CUSTOM1': 'value1',
            'REVIEWBOARD_URL': 'https://reviews.example.com/',
        })

        config = parse_config_file(config_file)

        self.assertEqual(config.BRANCH, 'my-branch')
        self.assertEqual(config.CUSTOM1, 'value1')
        self.assertEqual(config.REVIEWBOARD_URL,
                         'https://reviews.example.com/')

    def test_with_syntax_error(self) -> None:
        """Testing parse_config_file with syntax error"""
        config_file = self.write_reviewboardrc('BRANCH1 = "my-branch\n')

        message = (
            f'Syntax error in RBTools configuration file "{config_file}" '
            f'at line 1'
        )

        with self.assertRaisesMessage(ConfigSyntaxError, message) as ctx:
            parse_config_file(config_file)

        e = ctx.exception
        self.assertEqual(e.filename, config_file)
        self.assertEqual(e.line, 1)

        if sys.version_info[:2] >= (3, 10):
            self.assertEqual(e.column, 11)
        else:
            self.assertEqual(e.column, 21)


class LoadConfigTests(TestCase):
    """Unit tests for load_config.

    Version Added:
        5.0
    """

    needs_temp_home = True

    def test_with_files(self) -> None:
        """Testing load_config"""
        repo_dir = make_tempdir()
        subdir = os.path.join(repo_dir, 'subdir')

        tempdir1 = make_tempdir()
        tempdir2 = make_tempdir()

        self.write_reviewboardrc(
            'BRANCH = "my-branch"\n',
            parent_dir=tempdir1)
        self.write_reviewboardrc(
            'SUMMARY = "my summary"\n'
            'CUSTOM1 = 123\n',
            parent_dir=tempdir2)
        self.write_reviewboardrc(
            'REVIEWBOARD_URL = "https://reviews.example.com/"',
            parent_dir=subdir)
        self.write_reviewboardrc(
            'CUSTOM2 = [1, 2, 3]\n',
            parent_dir=repo_dir)
        self.write_reviewboardrc(
            'ALIASES = {"my-alias": "my-command"}\n',
            parent_dir=self.get_user_home())

        os.chdir(subdir)

        os.environ['RBTOOLS_CONFIG_PATH'] = os.pathsep.join([
            tempdir1,
            tempdir2,
            '/badXXX',
        ])

        try:
            config = load_config()
        finally:
            os.environ.pop('RBTOOLS_CONFIG_PATH')

        self.assertEqual(config.ALIASES, {
            'my-alias': 'my-command',
        })
        self.assertEqual(config.BRANCH, 'my-branch')
        self.assertEqual(config.CUSTOM1, 123)
        self.assertEqual(config.CUSTOM2, [1, 2, 3])
        self.assertEqual(config.REVIEWBOARD_URL,
                         'https://reviews.example.com/')
        self.assertEqual(config.SUMMARY, 'my summary')
        self.assertEqual(config._raw_config, {
            'ALIASES': {
                'my-alias': 'my-command',
            },
            'BRANCH': 'my-branch',
            'CUSTOM1': 123,
            'CUSTOM2': [1, 2, 3],
            'REVIEWBOARD_URL': 'https://reviews.example.com/',
            'SUMMARY': 'my summary',
        })

    def test_with_no_files(self) -> None:
        """Testing load_config with no files found"""
        config = load_config()

        self.assertEqual(config._raw_config, {})
