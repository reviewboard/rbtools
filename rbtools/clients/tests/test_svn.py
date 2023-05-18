# coding: utf-8
"""Unit tests for SubversionClient."""

import json
import os
import re
import sys
import unittest
from typing import List
from urllib.request import urlopen

import kgb

from rbtools.api.client import RBClient
from rbtools.api.tests.base import MockResponse
from rbtools.clients.base.scmclient import SCMClientDiffResult
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    TooManyRevisionsError)
from rbtools.clients.svn import SVNRepositoryInfo, SVNClient
from rbtools.clients.tests import FOO1, FOO2, FOO3, SCMClientTestCase
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_install
from rbtools.utils.process import (RunProcessResult,
                                   run_process,
                                   run_process_exec)
from rbtools.utils.repository import get_repository_resource


_MATCH_URL_BASE = 'http://localhost:8080/api/repositories/'
_MATCH_URL_TOOL = 'tool=Subversion'
_MATCH_URL_FIELDS = 'only-fields=id%2Cname%2Cmirror_path%2Cpath'


class SVNRepositoryMatchTests(SCMClientTestCase):
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
        (_MATCH_URL_BASE + '?' +
            _MATCH_URL_FIELDS +
            '&only-links=info&path=https%3A%2F%2Fsvn1.example.com%2F&' +
            _MATCH_URL_TOOL): {
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
                                'href': ('http://localhost:8080/api/'
                                         'repositories/1/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                ],
                'links': {
                },
                'total_results': 1,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE + '?' +
            _MATCH_URL_FIELDS +
            '&only-links=info&path=svn%2Bssh%3A%2F%2Fsvn2.example.com%2F&' +
            _MATCH_URL_TOOL): {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [
                    {
                        'id': 2,
                        'name': 'SVN Repo 2',
                        'path': 'https://svn2.example.com/',
                        'mirror_path': 'svn+ssh://svn2.example.com/',
                        'links': {
                            'info': {
                                'href': ('http://localhost:8080/api/'
                                         'repositories/1/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                ],
                'links': {
                },
                'total_results': 1,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE + '?' +
            _MATCH_URL_FIELDS +
            '&only-links=info&path=svn%2Bssh%3A%2F%2Fblargle%2F&' +
            _MATCH_URL_TOOL): {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [
                ],
                'links': {
                },
                'total_results': 0,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE + '?' +
            _MATCH_URL_FIELDS +
            '&only-links=&path=svn%2Bssh%3A%2F%2Fblargle%2F&' +
            _MATCH_URL_TOOL): {
            'mimetype': 'application/vnd.reviewboard.org.repositories+json',
            'rsp': {
                'repositories': [
                ],
                'links': {
                },
                'total_results': 0,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE + '?' +
            _MATCH_URL_FIELDS +
            '&only-links=info&' +
            _MATCH_URL_TOOL): {
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
                                'href': ('http://localhost:8080/api/'
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
                                'href': ('http://localhost:8080/api/'
                                         'repositories/2/info/'),
                                'method': 'GET',
                            },
                        },
                    },
                ],
                'links': {
                    'next': {
                        'href': ('http://localhost:8080/api/repositories/?'
                                 'only-links=info&tool=Subversion&'
                                 'only-fields=id%2Cname%2Cmirror_path%2Cpath&'
                                 'page=2'),
                        'method': 'GET',
                    },
                },
                'total_results': 3,
                'stat': 'ok',
            },
        },
        (_MATCH_URL_BASE + '?' +
            _MATCH_URL_FIELDS +
            '&only-links=info&page=2&' +
            _MATCH_URL_TOOL): {
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
                                'href': ('http://localhost:8080/api/'
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
        (_MATCH_URL_BASE + '1/info/'): {
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
        (_MATCH_URL_BASE + '2/info/'): {
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
        (_MATCH_URL_BASE + '3/info/'): {
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
        super(SVNRepositoryMatchTests, self).setUp()

        @self.spy_for(urlopen)
        def _urlopen(url, **kwargs):
            url = url.get_full_url()

            try:
                payload = self.payloads[url]
            except KeyError:
                print('Test requested unexpected URL "%s"' % url)

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

        self.api_client = RBClient('http://localhost:8080/')
        self.root_resource = self.api_client.get_root()

    def test_find_matching_server_repository_with_path_match(self):
        """Testing SVNClient.find_matching_server_repository with path
        match
        """
        url = 'https://svn1.example.com/'
        self.options.repository_url = url
        client = SVNClient(options=self.options)

        repository, info = get_repository_resource(
            self.root_resource,
            tool=client,
            repository_paths=url)
        self.assertEqual(repository.id, 1)

    def test_find_matching_server_repository_with_mirror_path_match(self):
        """Testing SVNClient.find_matching_server_repository with mirror_path
        match
        """
        url = 'svn+ssh://svn2.example.com/'
        self.options.repository_url = url
        client = SVNClient(options=self.options)

        repository, info = get_repository_resource(
            self.root_resource,
            tool=client,
            repository_paths=url)
        self.assertEqual(repository.id, 2)

    def test_find_matching_server_repository_with_uuid_match(self):
        """Testing SVNClient.find_matching_server_repository with UUID
        match
        """
        url = 'svn+ssh://blargle/'
        self.options.repository_url = url
        client = SVNClient(options=self.options)

        self.spy_on(client.svn_info, op=kgb.SpyOpReturn({
            'Repository UUID': 'UUID-3',
        }))

        repository, info = get_repository_resource(
            self.root_resource,
            tool=client,
            repository_paths=url)
        self.assertEqual(repository.id, 3)

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


class SVNClientTests(SCMClientTestCase):
    """Unit tests for SVNClient."""

    scmclient_cls = SVNClient

    default_scmclient_options = {
        'svn_show_copies_as_adds': None,
    }

    default_scmclient_caps = {
        'scmtools': {
            'svn': {
                'empty_files': True,
            },
        },
    }

    @classmethod
    def setup_checkout(cls, checkout_dir):
        """Populate a Subversion checkout.

        This will create a checkout of the sample Subversion repository stored
        in the :file:`testdata` directory.

        Args:
            checkout_dir (unicode):
                The top-level directory in which the checkout will be placed.

        Returns:
            The main checkout directory, or ``None`` if :command:`svn` isn't
            in the path.
        """
        client = SVNClient()

        if not client.has_dependencies():
            return None

        cls.svn_dir = os.path.join(cls.testdata_dir, 'svn-repo')
        cls.svn_repo_url = 'file://%s' % cls.svn_dir
        cls.clone_dir = os.path.join(checkout_dir, 'svn-repo')

        os.mkdir(checkout_dir, 0o700)
        os.chdir(checkout_dir)
        cls._run_svn(['co', cls.svn_repo_url, cls.clone_dir])

        svn_version = (
            cls._run_svn(['--version', '-q'])
            .stdout
            .read()
        )

        cls.svn_version = tuple(
            int(_v)
            for _v in svn_version.split('.')
        )

        if cls.svn_version >= (1, 9):
            # Subversion >= 1.9
            cls.new_file_diff_orig_version = b'nonexistent'
            cls.new_file_diff_modified_version = b'working copy'
        elif cls.svn_version >= (1, 7):
            # Subversion >= 1.7, < 1.9
            cls.new_file_diff_orig_version = b'revision 0'
            cls.new_file_diff_modified_version = b'working copy'
        else:
            # Subversion < 1.7
            cls.new_file_diff_orig_version = b'revision 0'
            cls.new_file_diff_modified_version = b'revision 0'

        return cls.clone_dir

    @classmethod
    def _run_svn(
        cls,
        command: List[str],
    ) -> RunProcessResult:
        """Run svn with the provided arguments.

        Args:
            command (list of str):
                The arguments to pass to :command:`svn`.

        Returns:
            rbtools.utils.process.RunProcessResult:
            The result of the :py:func:`~rbtools.utils.process.run_process`
            call.
        """
        return run_process(['svn'] + command)

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

    def test_check_dependencies_with_found(self):
        """Testing SVNClient.check_dependencies with hg found"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['svn', 'help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['svn', 'help'])

    def test_check_dependencies_with_missing(self):
        """Testing SVNClient.check_dependencies with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools ('svn') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['svn', 'help'])

    def test_get_local_path_with_deps_missing(self):
        """Testing SVNClient.get_local_path with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_local_path(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            local_path = client.get_local_path()

        self.assertIsNone(local_path)

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "svn help": skipping SVN')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['svn', 'help'])

    def test_get_local_path_with_deps_not_checked(self):
        """Testing SVNClient.get_local_path with dependencies not
        checked
        """
        # A False value is used just to ensure get_local_path() bails early,
        # and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either SVNClient.setup() or SVNClient.has_dependencies() must '
            'be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_local_path()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "svn help": skipping SVN')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['svn', 'help'])

    def test_get_repository_info_with_deps_missing(self):
        """Testing SVNClient.get_repository_info with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_repository_info(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            repository_info = client.get_repository_info()

        self.assertIsNone(repository_info)

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "svn help": skipping SVN')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['svn', 'help'])

    def test_get_repository_info_with_deps_not_checked(self):
        """Testing SVNClient.get_repository_info with dependencies not checked
        """
        # A False value is used just to ensure get_repository_info() bails
        # early, and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either SVNClient.setup() or SVNClient.has_dependencies() must '
            'be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_repository_info()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "svn help": skipping SVN')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['svn', 'help'])

    def test_is_remote_only_with_deps_missing(self):
        """Testing SVNClient.is_remote_only with dependencies missing"""
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # is_remote_only(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        with self.assertLogs(level='DEBUG') as ctx:
            remote_only = client.is_remote_only()

        self.assertFalse(remote_only)

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "svn help": skipping SVN')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['svn', 'help'])

    def test_is_remote_only_with_deps_not_checked(self):
        """Testing SVNClient.is_remote_only with dependencies not checked"""
        # A False value is used just to ensure is_remote_only() bails
        # early, and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either SVNClient.setup() or SVNClient.has_dependencies() must '
            'be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.is_remote_only()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "svn help": skipping SVN')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['svn', 'help'])

    def test_parse_revision_spec_no_args(self):
        """Testing SVNClient.parse_revision_spec with no specified revisions"""
        client = self.build_client()

        self.assertEqual(
            client.parse_revision_spec(),
            {
                'base': 'BASE',
                'tip': '--rbtools-working-copy',
            })

    def test_parse_revision_spec_one_revision(self):
        """Testing SVNClient.parse_revision_spec with one specified numeric
        revision
        """
        client = self.build_client()

        self.assertEqual(
            client.parse_revision_spec(['3']),
            {
                'base': 2,
                'tip': 3,
            })

    def test_parse_revision_spec_one_revision_changelist(self):
        """Testing SVNClient.parse_revision_spec with one specified changelist
        revision
        """
        client = self.build_client()

        self._svn_add_file('foo.txt', FOO3, 'my-change')

        self.assertEqual(
            client.parse_revision_spec(['my-change']),
            {
                'base': 'BASE',
                'tip': '%smy-change' % SVNClient.REVISION_CHANGELIST_PREFIX,
            })

    def test_parse_revision_spec_one_revision_nonexistant_changelist(self):
        """Testing SVNClient.parse_revision_spec with one specified invalid
        changelist revision
        """
        client = self.build_client()

        self._svn_add_file('foo.txt', FOO3, 'my-change')

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['not-my-change'])

    def test_parse_revision_spec_one_arg_two_revisions(self):
        """Testing SVNClient.parse_revision_spec with R1:R2 syntax"""
        client = self.build_client()

        self.assertEqual(
            client.parse_revision_spec(['1:3']),
            {
                'base': 1,
                'tip': 3,
            })

    def test_parse_revision_spec_two_arguments(self):
        """Testing SVNClient.parse_revision_spec with two revisions"""
        client = self.build_client()

        self.assertEqual(
            client.parse_revision_spec(['1', '3']),
            {
                'base': 1,
                'tip': 3,
            })

    def test_parse_revision_spec_one_revision_url(self):
        """Testing SVNClient.parse_revision_spec with one revision and a
        repository URL
        """
        client = self.build_client(options={
            'repository_url': ('http://svn.apache.org/repos/asf/'
                               'subversion/trunk'),
        })

        self.assertEqual(
            client.parse_revision_spec(['1549823']),
            {
                'base': 1549822,
                'tip': 1549823,
            })

    def test_parse_revision_spec_two_revisions_url(self):
        """Testing SVNClient.parse_revision_spec with R1:R2 syntax and a
        repository URL
        """
        client = self.build_client(options={
            'repository_url': ('http://svn.apache.org/repos/asf/'
                               'subversion/trunk'),
        })

        self.assertEqual(
            client.parse_revision_spec(['1549823:1550211']),
            {
                'base': 1549823,
                'tip': 1550211,
            })

    def test_parse_revision_spec_invalid_spec(self):
        """Testing SVNClient.parse_revision_spec with invalid specifications"""
        client = self.build_client()

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['aoeu'])

        with self.assertRaises(InvalidRevisionSpecError):
            client.parse_revision_spec(['aoeu', '1234'])

        with self.assertRaises(TooManyRevisionsError):
            client.parse_revision_spec(['1', '2', '3'])

    def test_parse_revision_spec_non_unicode_log(self):
        """Testing SVNClient.parse_revision_spec with a non-utf8 log entry"""
        client = self.build_client()

        # Note: the svn log entry for commit r2 contains one non-utf8 character
        self.assertEqual(
            client.parse_revision_spec(['2']),
            {
                'base': 1,
                'tip': 2,
            })

    def test_get_commit_message_working_copy(self):
        """Testing SVNClient.get_commit_message with a working copy change"""
        client = self.build_client()
        revisions = client.parse_revision_spec()

        self.assertIsNone(client.get_commit_message(revisions))

    def test_get_commit_message_committed_revision(self):
        """Testing SVNClient.get_commit_message with a single committed
        revision
        """
        client = self.build_client()
        revisions = client.parse_revision_spec(['2'])

        self.assertEqual(
            client.get_commit_message(revisions),
            {
                'description': 'Commit 2 -- a non-utf8 character: \xe9\n',
                'summary': 'Commit 2 -- a non-utf8 character: \xe9',
            })

    def test_get_commit_message_committed_revisions(self):
        """Testing SVNClient.get_commit_message with multiple committed
        revisions
        """
        client = self.build_client()
        revisions = client.parse_revision_spec(['1:3'])

        self.assertEqual(
            client.get_commit_message(revisions),
            {
                'description': 'Commit 3',
                'summary': 'Commit 2 -- a non-utf8 character: \xe9',
            })

    def test_diff_exclude(self):
        """Testing SVNClient diff with file exclude patterns"""
        client = self.build_client(needs_diff=True)

        self._svn_add_file('bar.txt', FOO1)
        self._svn_add_file('exclude.txt', FOO2)

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions, exclude_patterns=['exclude.txt']),
            {
                'diff': (
                    b'Index: /bar.txt\n'
                    b'===================================================='
                    b'===============\n'
                    b'--- /bar.txt\t(%s)\n'
                    b'+++ /bar.txt\t(%s)\n'
                    b'@@ -0,0 +1,9 @@\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+Italiam, fato profugus, Laviniaque venit\n'
                    b'+litora, multum ille et terris iactatus et alto\n'
                    b'+vi superum saevae memorem Iunonis ob iram;\n'
                    b'+multa quoque et bello passus, dum conderet urbem,\n'
                    b'+inferretque deos Latio, genus unde Latinum,\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Musa, mihi causas memora, quo numine laeso,\n'
                    b'+\n'
                ) % (self.new_file_diff_orig_version,
                     self.new_file_diff_modified_version),
            })

    def test_diff_exclude_in_subdir(self):
        """Testing SVNClient diff with exclude patterns in a subdir"""
        client = self.build_client(needs_diff=True)

        self._svn_add_file('foo.txt', FOO1)
        self._svn_add_dir('subdir')
        self._svn_add_file(os.path.join('subdir', 'exclude.txt'), FOO2)

        os.chdir('subdir')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions, exclude_patterns=['exclude.txt']),
            {
                'diff': b'',
            })

    def test_diff_exclude_root_pattern_in_subdir(self):
        """Testing SVNClient diff with repo exclude patterns in a subdir"""
        client = self.build_client(needs_diff=True)

        self._svn_add_file('exclude.txt', FOO1)
        self._svn_add_dir('subdir')

        os.chdir('subdir')

        revisions = client.parse_revision_spec([])
        exclude_patterns = [
            os.path.join(os.path.sep, 'exclude.txt'),
            '.',
        ]

        self.assertEqual(
            client.diff(revisions, exclude_patterns=exclude_patterns),
            {
                'diff': b'',
            })

    def test_same_diff_multiple_methods(self):
        """Testing SVNClient identical diff generated from root, subdirectory,
        and via target
        """
        client = self.build_client(needs_diff=True)

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
        revisions = client.parse_revision_spec()

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': (
                    b'Index: /dir1/A.txt\n'
                    b'============================================='
                    b'======================\n'
                    b'--- /dir1/A.txt\t(%s)\n'
                    b'+++ /dir1/A.txt\t(%s)\n'
                    b'@@ -0,0 +1,11 @@\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+Italiam, fato profugus, Laviniaque venit\n'
                    b'+litora, multum ille et terris iactatus et alto\n'
                    b'+vi superum saevae memorem Iunonis ob iram;\n'
                    b'+dum conderet urbem,\n'
                    b'+inferretque deos Latio, genus unde Latinum,\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Musa, mihi causas memora, quo numine laeso,\n'
                    b'+\n'
                ) % (self.new_file_diff_orig_version,
                     self.new_file_diff_modified_version),
            })

        # Case 2: Generate diff from dir1 subdirectory.
        os.chdir('dir1')

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': (
                    b'Index: /dir1/A.txt\n'
                    b'============================================='
                    b'======================\n'
                    b'--- /dir1/A.txt\t(nonexistent)\n'
                    b'+++ /dir1/A.txt\t(working copy)\n'
                    b'@@ -0,0 +1,11 @@\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+Italiam, fato profugus, Laviniaque venit\n'
                    b'+litora, multum ille et terris iactatus et alto\n'
                    b'+vi superum saevae memorem Iunonis ob iram;\n'
                    b'+dum conderet urbem,\n'
                    b'+inferretque deos Latio, genus unde Latinum,\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Musa, mihi causas memora, quo numine laeso,\n'
                    b'+\n'
                ),
            })

        # Case 3: Generate diff from dir2 subdirectory, but explicitly target
        # only ../dir1/A.txt.
        os.chdir('..')
        self._svn_add_dir('dir2')
        os.chdir('dir2')

        self.assertEqual(
            client.diff(revisions, include_files=['../dir1/A.txt']),
            {
                'diff': (
                    b'Index: /dir1/A.txt\n'
                    b'============================================='
                    b'======================\n'
                    b'--- /dir1/A.txt\t(nonexistent)\n'
                    b'+++ /dir1/A.txt\t(working copy)\n'
                    b'@@ -0,0 +1,11 @@\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+Italiam, fato profugus, Laviniaque venit\n'
                    b'+litora, multum ille et terris iactatus et alto\n'
                    b'+vi superum saevae memorem Iunonis ob iram;\n'
                    b'+dum conderet urbem,\n'
                    b'+inferretque deos Latio, genus unde Latinum,\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Musa, mihi causas memora, quo numine laeso,\n'
                    b'+\n'
                ),
            })

    def test_diff_non_unicode_characters(self):
        """Testing SVNClient diff with a non-utf8 file"""
        client = self.build_client(needs_diff=True)

        self._svn_add_file('A.txt', '\xe2'.encode('iso-8859-1'))
        self._run_svn(['propset', 'svn:mime-type', 'text/plain', 'A.txt'])

        revisions = client.parse_revision_spec()

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': (
                    b'Index: /A.txt\n'
                    b'=================================================='
                    b'=================\n'
                    b'--- /A.txt\t(%s)\n'
                    b'+++ /A.txt\t(%s)\n'
                    b'@@ -0,0 +1 @@\n'
                    b'+\xe2\n'
                    b'\\ No newline at end of file\n'
                    b'\n'
                    b'Property changes on: A.txt\n'
                    b'__________________________________________'
                    b'_________________________\n'
                    b'Added: svn:mime-type\n'
                    b'## -0,0 +1 ##\n'
                    b'+text/plain\n'
                    b'\\ No newline at end of property\n'
                ) % (self.new_file_diff_orig_version,
                     self.new_file_diff_modified_version),
            })

    def test_diff_non_unicode_filename_repository_url(self):
        """Testing SVNClient diff with a non-utf8 filename via repository_url
        option
        """
        client = self.build_client(
            needs_diff=True,
            options={
                'repository_url': self.svn_repo_url,
            })

        # Note: commit r4 adds one file with a non-utf8 character in both its
        # filename and content.
        revisions = client.parse_revision_spec(['4'])

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': (
                    b'Index: /\xc3\xa2.txt\n'
                    b'============================================='
                    b'======================\n'
                    b'--- /\xc3\xa2.txt\t(%s)\n'
                    b'+++ /\xc3\xa2.txt\t(revision 4)\n'
                    b'@@ -0,0 +1,2 @@\n'
                    b'+This file has a non-utf8 filename.\n'
                    b'+It also contains a non-utf8 character: \xc3\xa9.\n'
                ) % self.new_file_diff_orig_version,
            })

    def test_diff_with_empty_files(self):
        """Testing SVNClient.diff with empty files"""
        client = self.build_client(needs_diff=True)

        self._run_svn(['rm', 'empty-file'])
        self._svn_add_file(filename='new-empty-file',
                           data=b'')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': (
                    b'Index: /empty-file\t(deleted)\n'
                    b'======================================================='
                    b'============\n'
                    b'--- /empty-file\t(revision 6)\n'
                    b'+++ /empty-file\t(working copy)\n'
                    b'Index: /new-empty-file\t(added)\n'
                    b'======================================================='
                    b'============\n'
                    b'--- /new-empty-file\t(revision 0)\n'
                    b'+++ /new-empty-file\t(revision 0)\n'
                ),
            })

    def test_show_copies_as_adds_enabled(self):
        """Testing SVNClient with --show-copies-as-adds functionality
        enabled
        """
        self.check_show_copies_as_adds(
            state='y',
            expected_diff_result={
                'diff': (
                    b'Index: /dir1/foo.txt\n'
                    b'==========================================='
                    b'========================\n'
                    b'--- /foo.txt\t(%s)\n'
                    b'+++ /dir1/foo.txt\t(working copy)\n'
                    b'@@ -0,0 +1,11 @@\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+Italiam, fato profugus, Laviniaque venit\n'
                    b'+litora, multum ille et terris iactatus et alto\n'
                    b'+vi superum saevae memorem Iunonis ob iram;\n'
                    b'+dum conderet urbem,\n'
                    b'+inferretque deos Latio, genus unde Latinum,\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Albanique patres, atque altae moenia Romae.\n'
                    b'+Musa, mihi causas memora, quo numine laeso,\n'
                    b'+\n'
                ) % self.new_file_diff_orig_version,
            })

    def test_show_copies_as_adds_disabled(self):
        """Testing SVNClient with --show-copies-as-adds functionality
        disabled
        """
        if self.svn_version >= (1, 9):
            # Subversion >= 1.9
            diff = (
                b'Index: /dir1/foo.txt\t(added)\n'
                b'==========================================='
                b'========================\n'
                b'--- /dir1/foo.txt\t(revision 0)\n'
                b'+++ /dir1/foo.txt\t(revision 0)\n'
            )
        else:
            # Subversion < 1.9
            diff = b''

        self.check_show_copies_as_adds(
            state='n',
            expected_diff_result={
                'diff': diff,
            })

    def test_show_copies_as_adds_disabled_and_no_empty_files_cap(self):
        """Testing SVNClient with --show-copies-as-adds functionality
        disabled and no empty files capability
        """
        if self.svn_version >= (1, 9):
            # Subversion >= 1.9
            diff = (
                b'Index: /dir1/foo.txt\n'
                b'==========================================='
                b'========================\n'
            )
        else:
            # Subversion < 1.9
            diff = b''

        self.check_show_copies_as_adds(
            state='n',
            empty_files_cap=False,
            expected_diff_result={
                'diff': diff,
            })

    def check_show_copies_as_adds(
        self,
        state: str,
        expected_diff_result: SCMClientDiffResult,
        empty_files_cap: bool = True,
    ) -> None:
        """Helper function to evaluate --show-copies-as-adds.

        Args:
            state (unicode):
                The state to set for ``--show-copies-as-adds``.

            expected_diff_result (dict):
                The expected result of the diff call.

            empty_files_cap (bool, optional):
                The value to use for the Subversion ``empty_files``
                capability.

        Raises:
            AssertionError:
                One of the checks failed.
        """
        client = self.build_client(
            needs_diff=True,
            caps={
                'scmtools': {
                    'svn': {
                        'empty_files': empty_files_cap,
                    },
                },
            },
            options={
                'svn_show_copies_as_adds': state,
            })
        client.get_repository_info()

        # Ensure valid SVN client version.
        if (client.subversion_client_version <
            client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise unittest.SkipTest('Subversion client is too old to test '
                                    '--show-copies-as-adds.')

        self._svn_add_dir('dir1')
        self._svn_add_dir('dir2')
        self._run_svn(['copy', 'foo.txt', 'dir1'])

        # Generate identical diff via several methods:
        #  1) from checkout root
        #  2) via changelist
        #  3) from checkout root when all relevant files belong to a changelist
        #  4) via explicit include target

        revisions = client.parse_revision_spec()
        self.assertEqual(client.diff(revisions), expected_diff_result)

        self._run_svn(['changelist', 'cl1', 'dir1/foo.txt'])
        revisions = client.parse_revision_spec(['cl1'])
        self.assertEqual(client.diff(revisions), expected_diff_result)

        revisions = client.parse_revision_spec()
        self.assertEqual(client.diff(revisions), expected_diff_result)

        self._run_svn(['changelist', '--remove', 'dir1/foo.txt'])

        os.chdir('dir2')
        revisions = client.parse_revision_spec()
        self.assertEqual(client.diff(revisions, include_files=['../dir1']),
                         expected_diff_result)

    def test_history_scheduled_with_commit_nominal(self):
        """Testing SVNClient.history_scheduled_with_commit nominal cases"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        # Ensure valid SVN client version.
        if (client.subversion_client_version <
            client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise unittest.SkipTest('Subversion client is too old to test '
                                    'history_scheduled_with_commit().')

        self._svn_add_dir('dir1')
        self._svn_add_dir('dir2')
        self._run_svn(['copy', 'foo.txt', 'dir1'])

        # Squash stderr to prevent error message in test output.
        old_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')

        try:
            # Ensure SystemExit is raised when attempting to generate diff via
            # several methods:
            #
            #  1) from checkout root
            #  2) via changelist
            #  3) from checkout root when all relevant files belong to a
            #     changelist
            #  4) via explicit include target

            revisions = client.parse_revision_spec()

            with self.assertRaises(SystemExit):
                client.diff(revisions)

            self._run_svn(['changelist', 'cl1', 'dir1/foo.txt'])
            revisions = client.parse_revision_spec(['cl1'])

            with self.assertRaises(SystemExit):
                client.diff(revisions)

            revisions = client.parse_revision_spec()

            with self.assertRaises(SystemExit):
                client.diff(revisions)

            self._run_svn(['changelist', '--remove', 'dir1/foo.txt'])

            os.chdir('dir2')
            revisions = client.parse_revision_spec()

            with self.assertRaises(SystemExit):
                client.diff(revisions, include_files=['../dir1'])
        finally:
            sys.stderr = old_stderr

    def test_history_scheduled_with_commit_special_case_non_local_mods(self):
        """Testing SVNClient.history_scheduled_with_commit is bypassed when
        diff is not for local modifications in a working copy
        """
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        # Ensure valid SVN client version.
        if (client.subversion_client_version <
            client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise unittest.SkipTest('Subversion client is too old to test '
                                    'history_scheduled_with_commit().')

        # While within a working copy which contains a scheduled commit with
        # addition-with-history, ensure history_scheduled_with_commit() is not
        # executed when generating a diff between two revisions either
        # 1) locally or 2) via --reposistory-url option.

        self._run_svn(['copy', 'foo.txt', 'foo_copy.txt'])
        revisions = client.parse_revision_spec(['1:2'])

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': (
                    b'Index: /foo.txt\n'
                    b'================================================'
                    b'===================\n'
                    b'--- /foo.txt\t(revision 1)\n'
                    b'+++ /foo.txt\t(revision 2)\n'
                    b'@@ -1,4 +1,6 @@\n'
                    b' ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b' Italiam, fato profugus, Laviniaque venit\n'
                    b' litora, multum ille et terris iactatus et alto\n'
                    b' vi superum saevae memorem Iunonis ob iram;\n'
                    b'@@ -6,7 +8,4 @@\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
            })

        client = self.build_client(
            needs_diff=True,
            options={
                'repository_url': self.svn_repo_url,
            })
        client.get_repository_info()

        revisions = client.parse_revision_spec(['2'])

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': (
                    b'Index: /foo.txt\n'
                    b'================================================'
                    b'===================\n'
                    b'--- /foo.txt\t(revision 1)\n'
                    b'+++ /foo.txt\t(revision 2)\n'
                    b'@@ -1,4 +1,6 @@\n'
                    b' ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                    b' Italiam, fato profugus, Laviniaque venit\n'
                    b' litora, multum ille et terris iactatus et alto\n'
                    b' vi superum saevae memorem Iunonis ob iram;\n'
                    b'@@ -6,7 +8,4 @@\n'
                    b' inferretque deos Latio, genus unde Latinum,\n'
                    b' Albanique patres, atque altae moenia Romae.\n'
                    b' Musa, mihi causas memora, quo numine laeso,\n'
                    b'-quidve dolens, regina deum tot volvere casus\n'
                    b'-insignem pietate virum, tot adire labores\n'
                    b'-impulerit. Tantaene animis caelestibus irae?\n'
                    b' \n'
                ),
            })

    def test_history_scheduled_with_commit_special_case_exclude(self):
        """Testing SVNClient.history_scheduled_with_commit with exclude file"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        # Ensure valid SVN client version.
        if (client.subversion_client_version <
            client.SHOW_COPIES_AS_ADDS_MIN_VERSION):
            raise unittest.SkipTest('Subversion client is too old to test '
                                    'history_scheduled_with_commit().')

        # Lone file with history is also excluded.  In this case there should
        # be no SystemExit raised and an (empty) diff should be produced. Test
        # from checkout root and via changelist.

        self._run_svn(['copy', 'foo.txt', 'foo_copy.txt'])
        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions, exclude_patterns=['foo_copy.txt']),
            {
                'diff': b'',
            })

        self._run_svn(['changelist', 'cl1', 'foo_copy.txt'])
        revisions = client.parse_revision_spec(['cl1'])

        self.assertEqual(
            client.diff(revisions, exclude_patterns=['foo_copy.txt']),
            {
                'diff': b'',
            })

    def test_rename_diff_mangling_bug_4546(self):
        """Test diff with removal of lines that look like headers"""
        # If a file has lines that look like "-- XX (YY)", and one of those
        # files gets removed, our rename handling would filter them out. Test
        # that the bug is fixed.
        with open('bug-4546.txt', 'w') as f:
            f.write('-- test line1\n'
                    '-- test line2\n'
                    '-- test line (test2)\n')

        client = self.build_client(needs_diff=True)
        revisions = client.parse_revision_spec()

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': (
                    b'Index: /bug-4546.txt\n'
                    b'==========================================='
                    b'========================\n'
                    b'--- /bug-4546.txt\t(revision 6)\n'
                    b'+++ /bug-4546.txt\t(working copy)\n'
                    b'@@ -1,4 +1,3 @@\n'
                    b' -- test line1\n'
                    b'--- test line (test1)\n'
                    b' -- test line2\n'
                    b' -- test line (test2)\n'
                ),
            })

    def test_apply_patch(self):
        """Testing SVNClient.apply_patch"""
        client = self.build_client()
        repository_info = client.get_repository_info()

        self.spy_on(run_process_exec)

        with open('test.diff', 'wb') as fp:
            fp.write(
                b'Index: /\xc3\xa2.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /\xc3\xa2.txt\t(revision 5)\n'
                b'+++ /\xc3\xa2.txt\t(working copy)\n'
                b'@@ -1,2 +1,3 @@\n'
                b' This file has a non-utf8 filename.\n'
                b' It also contains a non-utf8 character: \xc3\xa9.\n'
                b'+And this! \xf0\x9f\xa5\xb9\n'
                b'Index: /foo.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /foo.txt\t(revision 5)\n'
                b'+++ /foo.txt\t(working copy)\n'
                b'@@ -6,6 +6,6 @@\n'
                b' dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'-Albanique patres, atque altae moenia Romae.\n'
                b'+Albanique patres, atque altae moenia Romae!\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'\n'
            )

        result = client.apply_patch(base_path=repository_info.base_path,
                                    base_dir='',
                                    patch_file='test.diff')

        self.assertSpyCalledWith(
            run_process_exec,
            [
                'svn', '--non-interactive', 'patch', '--strip=1', 'test.diff',
            ],
            redirect_stderr=True)

        self.assertTrue(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(
            result.patch_output,
            b'U         \xc3\xa2.txt\n'
            b'U         foo.txt\n')

    def test_apply_patch_with_p(self):
        """Testing SVNClient.apply_patch with p="""
        client = self.build_client()
        repository_info = client.get_repository_info()

        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        'svn', '--non-interactive', 'patch', '--strip=3',
                        'test.diff',
                    ],),
                    'kwargs': {
                        'redirect_stderr': True,
                    },
                },
            ]))

        with open('test.diff', 'wb') as fp:
            fp.write(
                b'Index: /a/b/\xc3\xa2.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /a/b/\xc3\xa2.txt\t(revision 5)\n'
                b'+++ /a/b/\xc3\xa2.txt\t(working copy)\n'
                b'@@ -1,2 +1,3 @@\n'
                b' This file has a non-utf8 filename.\n'
                b' It also contains a non-utf8 character: \xc3\xa9.\n'
                b'+And this! \xf0\x9f\xa5\xb9\n'
                b'Index: /a/b/foo.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /a/b/foo.txt\t(revision 5)\n'
                b'+++ /a/b/foo.txt\t(working copy)\n'
                b'@@ -6,6 +6,6 @@\n'
                b' dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'-Albanique patres, atque altae moenia Romae.\n'
                b'+Albanique patres, atque altae moenia Romae!\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'\n'
            )

        result = client.apply_patch(base_path=repository_info.base_path,
                                    base_dir='',
                                    patch_file='test.diff',
                                    p=3)

        self.assertSpyCalled(run_process_exec)

        self.assertTrue(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(
            result.patch_output,
            b'U         \xc3\xa2.txt\n'
            b'U         foo.txt\n')

    def test_apply_patch_with_revert(self):
        """Testing SVNClient.apply_patch with revert=True"""
        client = self.build_client()
        repository_info = client.get_repository_info()

        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        'svn', '--non-interactive', 'patch', '--strip=1',
                        '--reverse-diff', 'test.diff',
                    ],),
                    'kwargs': {
                        'redirect_stderr': True,
                    },
                },
            ]))

        with open('â.txt', 'ab') as fp:
            fp.write(b'And this! \xf0\x9f\xa5\xb9\n')

        with open('foo.txt', 'wb') as fp:
            fp.write(
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'ARMA virumque cano, Troiae qui primus ab oris\n'
                b'Italiam, fato profugus, Laviniaque venit\n'
                b'litora, multum ille et terris iactatus et alto\n'
                b'vi superum saevae memorem Iunonis ob iram;\n'
                b'dum conderet urbem,\n'
                b'inferretque deos Latio, genus unde Latinum,\n'
                b'Albanique patres, atque altae moenia Romae.\n'
                b'Albanique patres, atque altae moenia Romae!\n'
                b'Musa, mihi causas memora, quo numine laeso,\n'
                b'\n'
            )

        with open('test.diff', 'wb') as fp:
            fp.write(
                b'Index: /\xc3\xa2.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /\xc3\xa2.txt\t(revision 5)\n'
                b'+++ /\xc3\xa2.txt\t(working copy)\n'
                b'@@ -1,2 +1,3 @@\n'
                b' This file has a non-utf8 filename.\n'
                b' It also contains a non-utf8 character: \xc3\xa9.\n'
                b'+And this! \xf0\x9f\xa5\xb9\n'
                b'Index: /foo.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /foo.txt\t(revision 5)\n'
                b'+++ /foo.txt\t(working copy)\n'
                b'@@ -6,6 +6,6 @@\n'
                b' dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'-Albanique patres, atque altae moenia Romae.\n'
                b'+Albanique patres, atque altae moenia Romae!\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'\n'
            )

        result = client.apply_patch(base_path=repository_info.base_path,
                                    base_dir='',
                                    patch_file='test.diff',
                                    revert=True)

        self.assertSpyCalled(run_process_exec)

        self.assertTrue(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(
            result.patch_output,
            b'U         \xc3\xa2.txt\n'
            b'U         foo.txt\n')

    def test_apply_patch_with_empty_files(self):
        """Testing SVNClient.apply_patch with empty files"""
        client = self.build_client()
        repository_info = client.get_repository_info()

        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        'svn', '--non-interactive', 'patch', '--strip=1',
                        'test.diff',
                    ],),
                    'kwargs': {
                        'redirect_stderr': True,
                    },
                },
                {
                    'args': ([
                        'svn', '--non-interactive', 'add', '--force',
                        'new-empty-file-1', 'new-empty-file-2',
                    ],),
                },
                {
                    'args': ([
                        'svn', '--non-interactive', 'delete', '--force',
                        'empty-file',
                    ],),
                },
            ]))

        with open('test.diff', 'wb') as fp:
            fp.write(
                b'Index: empty-file\t(deleted)\n'
                b'================================================'
                b'===================\n'
                b'Index: new-empty-file-1\t(added)\n'
                b'================================================'
                b'===================\n'
                b'Index: new-empty-file-2\t(added)\n'
                b'================================================'
                b'===================\n'
            )

        result = client.apply_patch(base_path=repository_info.base_path,
                                    base_dir='',
                                    patch_file='test.diff')

        self.assertSpyCalled(run_process_exec)
        self.assertFalse(os.path.exists('empty-file'))
        self.assertTrue(os.path.exists('new-empty-file-1'))
        self.assertTrue(os.path.exists('new-empty-file-2'))

        with open('new-empty-file-1', 'rb') as fp:
            self.assertEqual(fp.read(), b'')

        with open('new-empty-file-2', 'rb') as fp:
            self.assertEqual(fp.read(), b'')

        self.assertTrue(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(result.patch_output, b'')

    def test_apply_patch_with_empty_files_revert(self):
        """Testing SVNClient.apply_patch with empty files and revert=True"""
        client = self.build_client()
        repository_info = client.get_repository_info()

        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        'svn', '--non-interactive', 'patch', '--strip=1',
                        '--reverse-diff', 'test.diff',
                    ],),
                    'kwargs': {
                        'redirect_stderr': True,
                    },
                },
                {
                    'args': ([
                        'svn', '--non-interactive', 'add', '--force',
                        'empty-file',
                    ],),
                },
                {
                    'args': ([
                        'svn', '--non-interactive', 'delete', '--force',
                        'new-empty-file-1', 'new-empty-file-2',
                    ],),
                },
            ]))

        with open('new-empty-file-1', 'wb'):
            pass

        with open('new-empty-file-2', 'wb'):
            pass

        with open('test.diff', 'wb') as fp:
            fp.write(
                b'Index: empty-file\t(deleted)\n'
                b'================================================'
                b'===================\n'
                b'Index: new-empty-file-1\t(added)\n'
                b'================================================'
                b'===================\n'
                b'Index: new-empty-file-2\t(added)\n'
                b'================================================'
                b'===================\n'
            )

        result = client.apply_patch(base_path=repository_info.base_path,
                                    base_dir='',
                                    patch_file='test.diff',
                                    revert=True)

        self.assertSpyCalled(run_process_exec)
        self.assertTrue(os.path.exists('empty-file'))
        self.assertFalse(os.path.exists('new-empty-file-1'))
        self.assertFalse(os.path.exists('new-empty-file-2'))

        self.assertTrue(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(result.patch_output, b'')

    def test_apply_patch_with_not_applied(self):
        """Testing SVNClient.apply_patch with not applied"""
        client = self.build_client()
        repository_info = client.get_repository_info()

        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        'svn', '--non-interactive', 'patch', '--strip=1',
                        'test.diff',
                    ],),
                    'kwargs': {
                        'redirect_stderr': True,
                    },
                },
            ]))

        with open('test.diff', 'wb') as fp:
            fp.write(
                b'Index: foorp.txt\n'
                b'================================================'
                b'===================\n'
            )

        result = client.apply_patch(base_path=repository_info.base_path,
                                    base_dir='',
                                    patch_file='test.diff')

        self.assertSpyCalled(run_process_exec)

        self.assertFalse(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(result.patch_output, b'')

    def test_apply_patch_with_conflicts(self):
        """Testing SVNClient.apply_patch with conflicts"""
        client = self.build_client()
        repository_info = client.get_repository_info()

        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        'svn', '--non-interactive', 'patch', '--strip=1',
                        'test.diff',
                    ],),
                    'kwargs': {
                        'redirect_stderr': True,
                    },
                },
            ]))

        with open('test.diff', 'wb') as fp:
            fp.write(
                b'Index: /\xc3\xa2.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /\xc3\xa2.txt\t(revision 5)\n'
                b'+++ /\xc3\xa2.txt\t(working copy)\n'
                b'@@ -1,1 +1,1 @@\n'
                b'-This is a bad line\n'
                b'+Oh hi! \xf0\x9f\xa5\xb9\n'
                b'Index: /foo.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /foo.txt\t(revision 5)\n'
                b'+++ /foo.txt\t(working copy)\n'
                b'@@ -6,6 +6,6 @@\n'
                b' dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'-foo\n'
                b'+Albanique patres, atque altae moenia Romae!\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'\n'
            )

        result = client.apply_patch(base_path=repository_info.base_path,
                                    base_dir='',
                                    patch_file='test.diff')

        self.assertSpyCalled(run_process_exec)

        self.assertFalse(result.applied)
        self.assertTrue(result.has_conflicts)
        self.assertEqual(
            result.conflicting_files,
            [
                'â.txt',
                'foo.txt',
            ])
        self.assertEqual(
            result.patch_output,
            b'C         \xc3\xa2.txt\n'
            b'>         rejected hunk @@ -1,1 +1,1 @@\n'
            b'C         foo.txt\n'
            b'>         rejected hunk @@ -6,6 +6,6 @@\n'
            b'Summary of conflicts:\n'
            b'  Text conflicts: 2\n')

    def test_apply_patch_with_applied_and_conflicts(self):
        """Testing SVNClient.apply_patch with applied and conflicts"""
        client = self.build_client()
        repository_info = client.get_repository_info()

        self.spy_on(
            run_process_exec,
            op=kgb.SpyOpMatchInOrder([
                {
                    'args': ([
                        'svn', '--non-interactive', 'patch', '--strip=1',
                        'test.diff',
                    ],),
                    'kwargs': {
                        'redirect_stderr': True,
                    },
                },
            ]))

        with open('test.diff', 'wb') as fp:
            fp.write(
                b'Index: /\xc3\xa2.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /\xc3\xa2.txt\t(revision 5)\n'
                b'+++ /\xc3\xa2.txt\t(working copy)\n'
                b'@@ -1,2 +1,3 @@\n'
                b' This file has a non-utf8 filename.\n'
                b' It also contains a non-utf8 character: \xc3\xa9.\n'
                b'+And this! \xf0\x9f\xa5\xb9\n'
                b'Index: /foo.txt\n'
                b'================================================'
                b'===================\n'
                b'--- /foo.txt\t(revision 5)\n'
                b'+++ /foo.txt\t(working copy)\n'
                b'@@ -6,6 +6,6 @@\n'
                b' dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'-foo\n'
                b'+Albanique patres, atque altae moenia Romae!\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'\n'
            )

        result = client.apply_patch(base_path=repository_info.base_path,
                                    base_dir='',
                                    patch_file='test.diff')

        self.assertSpyCalled(run_process_exec)

        self.assertTrue(result.applied)
        self.assertTrue(result.has_conflicts)
        self.assertEqual(result.conflicting_files, ['foo.txt'])
        self.assertEqual(
            result.patch_output,
            b'U         \xc3\xa2.txt\n'
            b'C         foo.txt\n'
            b'>         rejected hunk @@ -6,6 +6,6 @@\n'
            b'Summary of conflicts:\n'
            b'  Text conflicts: 1\n')
