"""Unit tests for SubversionClient."""

from __future__ import unicode_literals

import json
import os
import sys
from functools import wraps
from hashlib import md5

from kgb import SpyAgency
from nose import SkipTest
from six.moves.urllib.request import urlopen

from rbtools.api.client import RBClient
from rbtools.api.tests import MockResponse
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError)
from rbtools.clients.svn import SVNRepositoryInfo, SVNClient
from rbtools.clients.tests import FOO1, FOO2, FOO3, SCMClientTests
from rbtools.utils.checks import is_valid_version
from rbtools.utils.filesystem import is_exe_in_path
from rbtools.utils.process import execute


def svn_version_set_hash(svn16_hash, svn17_hash, svn19_hash):
    """Pass the appropriate hash to the wrapped function.

    SVN 1.6, 1.7/1.8, and 1.9+ will generate slightly different output for
    ``svn diff`` when generating the diff with a working copy. This works
    around that by checking the installed SVN version and passing the
    appropriate hash.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(self):
            self.client.get_repository_info()

            version = self.client.subversion_client_version

            if version < (1, 7):
                return f(self, svn16_hash)
            elif version < (1, 9):
                return f(self, svn17_hash)
            else:
                return f(self, svn19_hash)

        return wrapped
    return decorator


class SVNRepositoryInfoTests(SpyAgency, SCMClientTests):
    """Unit tests for rbtools.clients.svn.SVNRepositoryInfo."""

    payloads = {
        'http://localhost:8080/api/': {
            'mimetype': 'application/vnd.reviewboard.org.root+json',
            'rsp': {
                'uri_templates': {},
                'links': {
                    'self': {
                        'href': 'http://localhost:8080/api/',
                        'method': 'GET',
                    },
                    'repositories': {
                        'href': 'http://localhost:8080/api/repositories/',
                        'method': 'GET',
                    },
                },
                'stat': 'ok',
            },
        },
        'http://localhost:8080/api/repositories/?tool=Subversion': {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [
                    {
                        # This one doesn't have a mirror_path, to emulate
                        # Review Board 1.6.
                        'id': 1,
                        'name': 'SVN Repo 1',
                        'path': 'https://svn1.example.com/',
                        'links': {
                            'info': {
                                'href': ('https://localhost:8080/api/'
                                         'repositories/1/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                    {
                        'id': 2,
                        'name': 'SVN Repo 2',
                        'path': 'https://svn2.example.com/',
                        'mirror_path': 'svn+ssh://svn2.example.com/',
                        'links': {
                            'info': {
                                'href': ('https://localhost:8080/api/'
                                         'repositories/2/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                ],
                'links': {
                    'next': {
                        'href': ('http://localhost:8080/api/repositories/'
                                 '?tool=Subversion&page=2'),
                        'method': 'GET',
                    },
                },
                'total_results': 3,
                'stat': 'ok',
            },
        },
        'http://localhost:8080/api/repositories/?tool=Subversion&page=2': {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [
                    {
                        'id': 3,
                        'name': 'SVN Repo 3',
                        'path': 'https://svn3.example.com/',
                        'mirror_path': 'svn+ssh://svn3.example.com/',
                        'links': {
                            'info': {
                                'href': ('https://localhost:8080/api/'
                                         'repositories/3/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                ],
                'total_results': 3,
                'stat': 'ok',
            },
        },
        'https://localhost:8080/api/repositories/1/info/': {
            'mimetype': 'application/vnd.reviewboard.org.repository-info+json',
            'rsp': {
                'info': {
                    'uuid': 'UUID-1',
                    'url': 'https://svn1.example.com/',
                    'root_url': 'https://svn1.example.com/',
                },
                'stat': 'ok',
            },
        },
        'https://localhost:8080/api/repositories/2/info/': {
            'mimetype': 'application/vnd.reviewboard.org.repository-info+json',
            'rsp': {
                'info': {
                    'uuid': 'UUID-2',
                    'url': 'https://svn2.example.com/',
                    'root_url': 'https://svn2.example.com/',
                },
                'stat': 'ok',
            },
        },
        'https://localhost:8080/api/repositories/3/info/': {
            'mimetype': 'application/vnd.reviewboard.org.repository-info+json',
            'rsp': {
                'info': {
                    'uuid': 'UUID-3',
                    'url': 'https://svn3.example.com/',
                    'root_url': 'https://svn3.example.com/',
                },
                'stat': 'ok',
            },
        },
    }

    def setUp(self):
        super(SVNRepositoryInfoTests, self).setUp()

        def _urlopen(url, **kwargs):
            url = url.get_full_url()

            try:
                payload = self.payloads[url]
            except KeyError:
                return MockResponse(404, {}, json.dumps({
                    'rsp': {
                        'stat': 'fail',
                        'err': {
                            'code': 100,
                            'msg': 'Object does not exist',
                        },
                    },
                }))

            return MockResponse(
                200,
                {
                    'Content-Type': payload['mimetype'],
                },
                json.dumps(payload['rsp']))

        self.spy_on(urlopen, call_fake=_urlopen)

        self.api_client = RBClient('http://localhost:8080/')
        self.root_resource = self.api_client.get_root()

    def test_find_server_repository_info_with_path_match(self):
        """Testing SVNRepositoryInfo.find_server_repository_info with
        path matching
        """
        info = SVNRepositoryInfo('https://svn1.example.com/', '/', '')

        repo_info = info.find_server_repository_info(self.root_resource)
        self.assertEqual(repo_info, info)
        self.assertEqual(repo_info.repository_id, 1)

    def test_find_server_repository_info_with_mirror_path_match(self):
        """Testing SVNRepositoryInfo.find_server_repository_info with
        mirror_path matching
        """
        info = SVNRepositoryInfo('svn+ssh://svn2.example.com/', '/', '')

        repo_info = info.find_server_repository_info(self.root_resource)
        self.assertEqual(repo_info, info)
        self.assertEqual(repo_info.repository_id, 2)

    def test_find_server_repository_info_with_uuid_match(self):
        """Testing SVNRepositoryInfo.find_server_repository_info with
        UUID matching
        """
        info = SVNRepositoryInfo('svn+ssh://blargle/', '/', 'UUID-3')

        repo_info = info.find_server_repository_info(self.root_resource)
        self.assertNotEqual(repo_info, info)
        self.assertEqual(repo_info.repository_id, 3)

    def test_relative_paths(self):
        """Testing SVNRepositoryInfo._get_relative_path"""
        info = SVNRepositoryInfo('http://svn.example.com/svn/', '/', '')
        self.assertEqual(info._get_relative_path('/foo', '/bar'), None)
        self.assertEqual(info._get_relative_path('/', '/trunk/myproject'),
                         None)
        self.assertEqual(info._get_relative_path('/trunk/myproject', '/'),
                         '/trunk/myproject')
        self.assertEqual(
            info._get_relative_path('/trunk/myproject', ''),
            '/trunk/myproject')
        self.assertEqual(
            info._get_relative_path('/trunk/myproject', '/trunk'),
            '/myproject')
        self.assertEqual(
            info._get_relative_path('/trunk/myproject', '/trunk/myproject'),
            '/')


class SVNClientTests(SCMClientTests):
    def setUp(self):
        super(SVNClientTests, self).setUp()

        if not is_exe_in_path('svn'):
            raise SkipTest('svn not found in path')

        self.svn_dir = os.path.join(self.testdata_dir, 'svn-repo')
        self.clone_dir = self.chdir_tmp()
        self.svn_repo_url = 'file://' + self.svn_dir
        self._run_svn(['co', self.svn_repo_url, 'svn-repo'])
        os.chdir(os.path.join(self.clone_dir, 'svn-repo'))

        self.client = SVNClient(options=self.options)
        self.options.svn_show_copies_as_adds = None

    def _run_svn(self, command):
        return execute(['svn'] + command, env=None, split_lines=False,
                       ignore_errors=False, extra_ignore_errors=())

    def _svn_add_file(self, filename, data, changelist=None):
        """Add a file to the test repo."""
        is_new = not os.path.exists(filename)

        with open(filename, 'wb') as f:
            f.write(data)

        if is_new:
            self._run_svn(['add', filename])

        if changelist:
            self._run_svn(['changelist', changelist, filename])

    def _svn_add_dir(self, dirname):
        """Add a directory to the test repo."""
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        self._run_svn(['add', dirname])

    def test_parse_revision_spec_no_args(self):
        """Testing SVNClient.parse_revision_spec with no specified revisions"""
        revisions = self.client.parse_revision_spec()
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 'BASE')
        self.assertEqual(revisions['tip'], '--rbtools-working-copy')

    def test_parse_revision_spec_one_revision(self):
        """Testing SVNClient.parse_revision_spec with one specified numeric
        revision"""
        revisions = self.client.parse_revision_spec(['3'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 2)
        self.assertEqual(revisions['tip'], 3)

    def test_parse_revision_spec_one_revision_changelist(self):
        """Testing SVNClient.parse_revision_spec with one specified changelist
        revision"""
        self._svn_add_file('foo.txt', FOO3, 'my-change')

        revisions = self.client.parse_revision_spec(['my-change'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 'BASE')
        self.assertEqual(revisions['tip'],
                         SVNClient.REVISION_CHANGELIST_PREFIX + 'my-change')

    def test_parse_revision_spec_one_revision_nonexistant_changelist(self):
        """Testing SVNClient.parse_revision_spec with one specified invalid
        changelist revision"""
        self._svn_add_file('foo.txt', FOO3, 'my-change')

        self.assertRaises(
            InvalidRevisionSpecError,
            lambda: self.client.parse_revision_spec(['not-my-change']))

    def test_parse_revision_spec_one_arg_two_revisions(self):
        """Testing SVNClient.parse_revision_spec with R1:R2 syntax"""
        revisions = self.client.parse_revision_spec(['1:3'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1)
        self.assertEqual(revisions['tip'], 3)

    def test_parse_revision_spec_two_arguments(self):
        """Testing SVNClient.parse_revision_spec with two revisions"""
        revisions = self.client.parse_revision_spec(['1', '3'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1)
        self.assertEqual(revisions['tip'], 3)

    def test_parse_revision_spec_one_revision_url(self):
        """Testing SVNClient.parse_revision_spec with one revision and a
        repository URL"""
        self.options.repository_url = \
            'http://svn.apache.org/repos/asf/subversion/trunk'

        revisions = self.client.parse_revision_spec(['1549823'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1549822)
        self.assertEqual(revisions['tip'], 1549823)

    def test_parse_revision_spec_two_revisions_url(self):
        """Testing SVNClient.parse_revision_spec with R1:R2 syntax and a
        repository URL"""
        self.options.repository_url = \
            'http://svn.apache.org/repos/asf/subversion/trunk'

        revisions = self.client.parse_revision_spec(['1549823:1550211'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1549823)
        self.assertEqual(revisions['tip'], 1550211)

    def test_parse_revision_spec_invalid_spec(self):
        """Testing SVNClient.parse_revision_spec with invalid specifications"""
        self.assertRaises(InvalidRevisionSpecError,
                          self.client.parse_revision_spec,
                          ['aoeu'])
        self.assertRaises(InvalidRevisionSpecError,
                          self.client.parse_revision_spec,
                          ['aoeu', '1234'])
        self.assertRaises(TooManyRevisionsError,
                          self.client.parse_revision_spec,
                          ['1', '2', '3'])

    def test_parse_revision_spec_non_unicode_log(self):
        """Testing SVNClient.parse_revision_spec with a non-utf8 log entry"""
        # Note: the svn log entry for commit r2 contains one non-utf8 character
        revisions = self.client.parse_revision_spec(['2'])
        self.assertTrue(isinstance(revisions, dict))
        self.assertTrue('base' in revisions)
        self.assertTrue('tip' in revisions)
        self.assertTrue('parent_base' not in revisions)
        self.assertEqual(revisions['base'], 1)
        self.assertEqual(revisions['tip'], 2)

    def test_get_commit_message_working_copy(self):
        """Testing SVNClient.get_commit_message with a working copy change"""
        revisions = self.client.parse_revision_spec()
        message = self.client.get_commit_message(revisions)
        self.assertIsNone(message)

    def test_get_commit_message_committed_revision(self):
        """Testing SVNClient.get_commit_message with a single committed
        revision
        """
        revisions = self.client.parse_revision_spec(['2'])
        message = self.client.get_commit_message(revisions)

        self.assertTrue('summary' in message)
        self.assertTrue('description' in message)

        self.assertEqual(message['summary'],
                         'Commit 2 -- a non-utf8 character: \xe9')
        self.assertEqual(message['description'],
                         'Commit 2 -- a non-utf8 character: \xe9\n')

    def test_get_commit_message_committed_revisions(self):
        """Testing SVNClient.get_commit_message with multiple committed
        revisions
        """
        revisions = self.client.parse_revision_spec(['1:3'])
        message = self.client.get_commit_message(revisions)

        self.assertTrue('summary' in message)
        self.assertTrue('description' in message)

        self.assertEqual(message['summary'],
                         'Commit 2 -- a non-utf8 character: \xe9')
        self.assertEqual(message['description'], 'Commit 3')

    @svn_version_set_hash('6613644d417f7c90f83f3a2d16b1dad5',
                          '7630ea80056a7340d93a556e9af60c63',
                          '6a5339da19e60c7706e44aeebfa4da5f')
    def test_diff_exclude(self, md5sum):
        """Testing SVNClient diff with file exclude patterns"""
        self._svn_add_file('bar.txt', FOO1)
        self._svn_add_file('exclude.txt', FOO2)

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions,
                                  exclude_patterns=['exclude.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self.assertEqual(md5(result['diff']).hexdigest(), md5sum)

    def test_diff_exclude_in_subdir(self):
        """Testing SVNClient diff with exclude patterns in a subdir"""
        self._svn_add_file('foo.txt', FOO1)
        self._svn_add_dir('subdir')
        self._svn_add_file(os.path.join('subdir', 'exclude.txt'), FOO2)

        os.chdir('subdir')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(
            revisions,
            exclude_patterns=['exclude.txt'])

        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self.assertEqual(result['diff'], b'')

    def test_diff_exclude_root_pattern_in_subdir(self):
        """Testing SVNClient diff with repo exclude patterns in a subdir"""
        self._svn_add_file('exclude.txt', FOO1)
        self._svn_add_dir('subdir')

        os.chdir('subdir')

        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(
            revisions,
            exclude_patterns=[os.path.join(os.path.sep, 'exclude.txt'),
                              '.'])

        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)

        self.assertEqual(result['diff'], b'')

    @svn_version_set_hash('043befc507b8177a0f010dc2cecc4205',
                          '1b68063237c584d38a9a3ddbdf1f72a2',
                          '466f7c2092e085354f5b24b91d48dd80')
    def test_same_diff_multiple_methods(self, md5_sum):
        """Testing SVNClient identical diff generated from root, subdirectory,
        and via target"""

        # Test diff generation for a single file, where 'svn diff' is invoked
        # from three different locations.  This should result in an identical
        # diff for all three cases.  Add a new subdirectory and file
        # (dir1/A.txt) which will be the lone change captured in the diff.
        # Cases:
        #  1) Invoke 'svn diff' from checkout root.
        #  2) Invoke 'svn diff' from dir1/ subdirectory.
        #  3) Create dir2/ subdirectory parallel to dir1/.  Invoke 'svn diff'
        #     from dir2/ where '../dir1/A.txt' is provided as a specific
        #     target.
        #
        # This test is inspired by #3749 which broke cases 2 and 3.

        self._svn_add_dir('dir1')
        self._svn_add_file('dir1/A.txt', FOO3)

        # Case 1: Generate diff from checkout root.
        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

        # Case 2: Generate diff from dir1 subdirectory.
        os.chdir('dir1')
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

        # Case 3: Generate diff from dir2 subdirectory, but explicitly target
        # only ../dir1/A.txt.
        os.chdir('..')
        self._svn_add_dir('dir2')
        os.chdir('dir2')
        result = self.client.diff(revisions, ['../dir1/A.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

    @svn_version_set_hash('902d662a110400f7470294b2d9e72d36',
                          '13803373ded9af750384a4601d5173ce',
                          'f11dfbe58925871c5f64b6ca647a8d3c')
    def test_diff_non_unicode_characters(self, md5_sum):
        """Testing SVNClient diff with a non-utf8 file"""
        self._svn_add_file('A.txt', '\xe2'.encode('iso-8859-1'))
        self._run_svn(['propset', 'svn:mime-type', 'text/plain', 'A.txt'])

        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5_sum)

    @svn_version_set_hash('60c4d21f4d414da947f4e7273e6d1326',
                          '60c4d21f4d414da947f4e7273e6d1326',
                          '571e47c456698bad35bca06523473008')
    def test_diff_non_unicode_filename_repository_url(self, md5sum):
        """Testing SVNClient diff with a non-utf8 filename via repository_url
        option"""
        self.options.repository_url = self.svn_repo_url

        # Note: commit r4 adds one file with a non-utf8 character in both its
        # filename and content.
        revisions = self.client.parse_revision_spec(['4'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5sum)

    @svn_version_set_hash('ac1835240ec86ee14ddccf1f2236c442',
                          'ac1835240ec86ee14ddccf1f2236c442',
                          '610f5506e670dc55a2464a6ad9af015c')
    def test_show_copies_as_adds_enabled(self, md5sum):
        """Testing SVNClient with --show-copies-as-adds functionality
        enabled"""
        self.check_show_copies_as_adds('y', md5sum)

    @svn_version_set_hash('d41d8cd98f00b204e9800998ecf8427e',
                          'd41d8cd98f00b204e9800998ecf8427e',
                          'b656e2f9b70ade256c3fe855c13ee52c')
    def test_show_copies_as_adds_disabled(self, md5sum):
        """Testing SVNClient with --show-copies-as-adds functionality
        disabled"""
        self.check_show_copies_as_adds('n', md5sum)

    def check_show_copies_as_adds(self, state, md5sum):
        """Helper function to evaluate --show-copies-as-adds"""
        self.client.get_repository_info()

        # Ensure valid SVN client version.
        if not is_valid_version(self.client.subversion_client_version,
                                self.client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise SkipTest('Subversion client is too old to test '
                           '--show-copies-as-adds.')

        self.options.svn_show_copies_as_adds = state

        self._svn_add_dir('dir1')
        self._svn_add_dir('dir2')
        self._run_svn(['copy', 'foo.txt', 'dir1'])

        # Generate identical diff via several methods:
        #  1) from checkout root
        #  2) via changelist
        #  3) from checkout root when all relevant files belong to a changelist
        #  4) via explicit include target

        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5sum)

        self._run_svn(['changelist', 'cl1', 'dir1/foo.txt'])
        revisions = self.client.parse_revision_spec(['cl1'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5sum)

        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5sum)

        self._run_svn(['changelist', '--remove', 'dir1/foo.txt'])

        os.chdir('dir2')
        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions, ['../dir1'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(), md5sum)

    def test_history_scheduled_with_commit_nominal(self):
        """Testing SVNClient.history_scheduled_with_commit nominal cases"""
        self.client.get_repository_info()

        # Ensure valid SVN client version.
        if not is_valid_version(self.client.subversion_client_version,
                                self.client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise SkipTest('Subversion client is too old to test '
                           'history_scheduled_with_commit().')

        self._svn_add_dir('dir1')
        self._svn_add_dir('dir2')
        self._run_svn(['copy', 'foo.txt', 'dir1'])

        # Squash stderr to prevent error message in test output.
        sys.stderr = open(os.devnull, 'w')

        # Ensure SystemExit is raised when attempting to generate diff via
        # several methods:
        #  1) from checkout root
        #  2) via changelist
        #  3) from checkout root when all relevant files belong to a changelist
        #  4) via explicit include target

        revisions = self.client.parse_revision_spec()
        self.assertRaises(SystemExit, self.client.diff, revisions)

        self._run_svn(['changelist', 'cl1', 'dir1/foo.txt'])
        revisions = self.client.parse_revision_spec(['cl1'])
        self.assertRaises(SystemExit, self.client.diff, revisions)

        revisions = self.client.parse_revision_spec()
        self.assertRaises(SystemExit, self.client.diff, revisions)

        self._run_svn(['changelist', '--remove', 'dir1/foo.txt'])

        os.chdir('dir2')
        revisions = self.client.parse_revision_spec()
        self.assertRaises(SystemExit, self.client.diff, revisions, ['../dir1'])

    def test_history_scheduled_with_commit_special_case_non_local_mods(self):
        """Testing SVNClient.history_scheduled_with_commit is bypassed when
        diff is not for local modifications in a working copy"""
        self.client.get_repository_info()

        # Ensure valid SVN client version.
        if not is_valid_version(self.client.subversion_client_version,
                                self.client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise SkipTest('Subversion client is too old to test '
                           'history_scheduled_with_commit().')

        # While within a working copy which contains a scheduled commit with
        # addition-with-history, ensure history_scheduled_with_commit() is not
        # executed when generating a diff between two revisions either
        # 1) locally or 2) via --reposistory-url option.

        self._run_svn(['copy', 'foo.txt', 'foo_copy.txt'])
        revisions = self.client.parse_revision_spec(['1:2'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'ed154720a7459c2649cab4d2fa34fa93')

        self.options.repository_url = self.svn_repo_url
        revisions = self.client.parse_revision_spec(['2'])
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'ed154720a7459c2649cab4d2fa34fa93')

    def test_history_scheduled_with_commit_special_case_exclude(self):
        """Testing SVNClient.history_scheduled_with_commit with exclude file"""
        self.client.get_repository_info()

        # Ensure valid SVN client version.
        if not is_valid_version(self.client.subversion_client_version,
                                self.client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise SkipTest('Subversion client is too old to test '
                           'history_scheduled_with_commit().')

        # Lone file with history is also excluded.  In this case there should
        # be no SystemExit raised and an (empty) diff should be produced. Test
        # from checkout root and via changelist.

        self._run_svn(['copy', 'foo.txt', 'foo_copy.txt'])
        revisions = self.client.parse_revision_spec([])
        result = self.client.diff(revisions, [], ['foo_copy.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'd41d8cd98f00b204e9800998ecf8427e')

        self._run_svn(['changelist', 'cl1', 'foo_copy.txt'])
        revisions = self.client.parse_revision_spec(['cl1'])
        result = self.client.diff(revisions, [], ['foo_copy.txt'])
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertEqual(md5(result['diff']).hexdigest(),
                         'd41d8cd98f00b204e9800998ecf8427e')

    def test_rename_diff_mangling_bug_4546(self):
        """Test diff with removal of lines that look like headers"""
        # If a file has lines that look like "-- XX (YY)", and one of those
        # files gets removed, our rename handling would filter them out. Test
        # that the bug is fixed.
        with open('bug-4546.txt', 'w') as f:
            f.write('-- test line1\n'
                    '-- test line2\n'
                    '-- test line (test2)\n')

        revisions = self.client.parse_revision_spec()
        result = self.client.diff(revisions)
        self.assertTrue(isinstance(result, dict))
        self.assertTrue('diff' in result)
        self.assertTrue(b'--- test line (test1)' in result['diff'])
