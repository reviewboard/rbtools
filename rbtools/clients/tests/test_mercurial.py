"""Unit tests for MercurialClient."""

import os
import re
import shutil
import tempfile
import time
import unittest
from random import randint
from textwrap import dedent
from typing import List

import kgb

import rbtools.helpers
from rbtools.clients import PatchAuthor, RepositoryInfo
from rbtools.clients.errors import (CreateCommitError,
                                    MergeError,
                                    SCMClientDependencyError)
from rbtools.clients.mercurial import MercurialClient, MercurialRefType
from rbtools.clients.tests import (FOO, FOO1, FOO2, FOO3, FOO4, FOO5, FOO6,
                                   SCMClientTestCase)
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_install
from rbtools.utils.filesystem import (is_exe_in_path,
                                      load_config,
                                      make_tempdir)
from rbtools.utils.process import (RunProcessResult,
                                   run_process,
                                   run_process_exec)


hgext_path = os.path.abspath(os.path.join(rbtools.helpers.__file__, '..',
                                          'hgext.py'))


class MercurialTestCase(SCMClientTestCase):
    """Base class for all Mercurial unit tests."""

    @classmethod
    def run_hg(
        cls,
        command: List[str],
        **kwargs
    ) -> RunProcessResult:
        """Run a Mercurial command.

        Args:
            command (list of unicode):
                The command and arguments to pass to :program:`hg`.

            **kwargs (dict):
                Additional keyword arguments to pass to
                :py:func:`~rbtools.utils.process.run_process`.

        Returns:
            rbtools.utils.process.RunProcessResult:
            The result of :py:func:`~rbtools.utils.process.run_process`.
        """
        return run_process(
            ['hg'] + command,
            env={
                'HGPLAIN': '1',
            },
            **kwargs)

    def hg_add_file_commit(self, filename='test.txt', data=b'Test',
                           msg='Test commit', branch=None,
                           bookmark=None, tag=None, date=None):
        """Add a file to the repository and commit it.

        This can also optionally construct a branch for the commit.

        Args:
            filename (unicode, optional):
                The name of the file to write.

            data (bytes, optional):
                The data to write to the file.

            msg (unicode, optional):
                The commit message.

            branch (unicode, optional):
                The optional branch to create.

            bookmark (unicode, optional):
                The optional bookmark to create.

            tag (unicode, optional):
                The optional tag to create.

            date (unicode, optional):
                The optional date to set for the commit.

                Version Added:
                    4.0
        """
        if branch:
            self.run_hg(['branch', branch])

        if bookmark:
            self.run_hg(['bookmark', bookmark])

        with open(filename, 'wb') as f:
            f.write(data)

        commit_args = ['commit', '-A', '-m', msg]

        if date:
            commit_args += ['-d', date]

        commit_args.append(filename)

        self.run_hg(commit_args)

        if tag:
            self.run_hg(['tag', tag])


class MercurialClientTests(MercurialTestCase):
    """Unit tests for MercurialClient."""

    scmclient_cls = MercurialClient

    TESTSERVER = 'http://127.0.0.1:8080'
    CLONE_HGRC = dedent("""
        [ui]
        username = test user <user at example.com>

        [paths]
        default = %(hg_dir)s
        cloned = %(clone_dir)s

        [reviewboard]
        url = %(test_server)s

        [diff]
        git = true
    """).rstrip()

    AUTHOR = PatchAuthor(full_name='name',
                         email='email')

    @classmethod
    def setup_checkout(cls, checkout_dir):
        """Populate a Mercurial clone.

        This will create a clone of the sample Mercurial repository stored in
        the :file:`testdata` directory.

        Args:
            checkout_dir (unicode):
                The top-level directory in which the clone will be placed.

        Returns:
            str:
            The main clone directory, or ``None`` if :command:`hg` isn't
            in the path.
        """
        client = MercurialClient()

        if not client.has_dependencies():
            return None

        cls.hg_dir = os.path.join(cls.testdata_dir, 'hg-repo')
        cls.run_hg(['clone', '--stream', cls.hg_dir, checkout_dir])

        return checkout_dir

    def setUp(self):
        super(MercurialClientTests, self).setUp()

        self.clone_dir = self.checkout_dir

        if self.clone_dir is not None:
            self.clone_hgrc_path = os.path.join(self.clone_dir, '.hg', 'hgrc')

            with open(self.clone_hgrc_path, 'w') as fp:
                fp.write(self.CLONE_HGRC % {
                    'hg_dir': self.hg_dir,
                    'clone_dir': self.clone_dir,
                    'test_server': self.TESTSERVER,
                })
        else:
            self.clone_dir = None

    def test_check_dependencies_with_found(self):
        """Testing MercurialClient.check_dependencies with hg found"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['hg', '--help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['hg', '--help'])

    def test_check_dependencies_with_missing(self):
        """Testing MercurialClient.check_dependencies with dependencies
        missing
        """
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = "Command line tools ('hg') are missing."

        with self.assertRaisesMessage(SCMClientDependencyError, message):
            client.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['hg', '--help'])

    def test_get_local_path_with_deps_missing(self):
        """Testing MercurialClient.get_local_path with dependencies missing"""
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
                         'Unable to execute "hg --help": skipping Mercurial')
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['hg', '--help'])

    def test_get_local_path_with_deps_not_checked(self):
        """Testing MercurialClient.get_local_path with dependencies not
        checked
        """
        # A False value is used just to ensure get_local_path() bails early,
        # and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either MercurialClient.setup() or '
            'MercurialClient.has_dependencies() must be called before other '
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_local_path()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "hg --help": skipping Mercurial')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['hg', '--help'])

    def test_get_repository_info(self):
        """Testing MercurialClient.get_repository_info"""
        client = self.build_client()
        ri = client.get_repository_info()

        self.assertIsInstance(ri, RepositoryInfo)
        self.assertEqual(ri.base_path, '')

        hgpath = ri.path

        if os.path.basename(hgpath) == '.hg':
            hgpath = os.path.dirname(hgpath)

        self.assertEqual(self.hg_dir, hgpath)

    def test_get_repository_info_with_deps_missing(self):
        """Testing MercurialClient.get_repository_info with dependencies
        missing
        """
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
                         'Unable to execute "hg --help": skipping Mercurial')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['hg', '--help'])

    def test_get_repository_info_with_deps_not_checked(self):
        """Testing MercurialClient.get_repository_info with dependencies
        not checked
        """
        # A False value is used just to ensure get_repository_info() bails
        # early, and to minimize side-effects.
        self.spy_on(check_install, op=kgb.SpyOpReturn(False))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either MercurialClient.setup() or '
            'MercurialClient.has_dependencies() must be called before other '
            'functions are used. This will be required starting in '
            'RBTools 5.0.'
        )

        with self.assertLogs(level='DEBUG') as ctx:
            with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
                client.get_repository_info()

        self.assertEqual(ctx.records[0].msg,
                         'Unable to execute "hg --help": skipping Mercurial')

        self.assertSpyCallCount(check_install, 1)
        self.assertSpyCalledWith(check_install, ['hg', '--help'])

    def test_scan_for_server(self):
        """Testing MercurialClient.scan_for_server"""
        client = self.build_client()
        client.hgrc = {}

        assert self.clone_dir is not None
        os.rename(self.clone_hgrc_path,
                  os.path.join(self.clone_dir, '._disabled_hgrc'))

        client._load_hgrc()

        ri = client.get_repository_info()

        self.assertIsNone(client.scan_for_server(ri))

    def test_scan_for_server_when_present_in_hgrc(self):
        """Testing MercurialClient.scan_for_server when present in hgrc"""
        client = self.build_client()
        ri = client.get_repository_info()

        self.assertEqual(client.scan_for_server(ri),
                         self.TESTSERVER)

    def test_scan_for_server_reviewboardrc(self):
        """Testing MercurialClient.scan_for_server when in .reviewboardrc"""
        client = self.build_client()

        with self.reviewboardrc({'REVIEWBOARD_URL': self.TESTSERVER}):
            client.config = load_config()
            ri = client.get_repository_info()

            self.assertEqual(client.scan_for_server(ri),
                             self.TESTSERVER)

    def test_diff(self):
        """Testing MercurialClient.diff"""
        client = self.build_client(needs_diff=True)

        base_commit_id = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='delete and modify stuff')
        commit_id = self._hg_get_tip()

        revisions = client.parse_revision_spec([])

        spy = self.spy_on(client._execute)
        result = client.diff(revisions)

        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', base_commit_id, '-r', commit_id],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertIsInstance(result, dict)
        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': commit_id,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -6,7 +6,4 @@\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id.encode('utf-8'),
            },
            'parent_diff': None,
        })

    def test_diff_with_multiple_commits(self):
        """Testing MercurialClient.diff with multiple commits"""
        client = self.build_client(needs_diff=True)

        base_commit_id = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO3,
                                msg='commit 3')
        commit_id = self._hg_get_tip()

        revisions = client.parse_revision_spec([])

        spy = self.spy_on(client._execute)
        result = client.diff(revisions)

        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', base_commit_id, '-r', commit_id],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': commit_id,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -1,12 +1,11 @@\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' Italiam, fato profugus, Laviniaque venit\n'
                b' litora, multum ille et terris iactatus et alto\n'
                b' vi superum saevae memorem Iunonis ob iram;\n'
                b'-multa quoque et bello passus, dum conderet urbem,\n'
                b'+dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'+Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id.encode('utf-8'),
            },
            'parent_diff': None,
        })

    def test_diff_with_exclude_patterns(self):
        """Testing MercurialClient.diff with exclude_patterns"""
        client = self.build_client(needs_diff=True)

        base_commit_id = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')
        self.hg_add_file_commit(filename='exclude.txt',
                                data=FOO2,
                                msg='commit 2')
        commit_id = self._hg_get_tip()

        revisions = client.parse_revision_spec([])

        spy = self.spy_on(client._execute)
        result = client.diff(revisions, exclude_patterns=['exclude.txt'])

        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-X', 'exclude.txt', '-r', base_commit_id, '-r', commit_id],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': commit_id,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -6,7 +6,4 @@\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id.encode('utf-8'),
            },
            'parent_diff': None,
        })

    def test_diff_with_exclude_patterns_with_empty_file(self):
        """Testing MercurialClient.diff with exclude_patterns matching empty
        file
        """
        client = self.build_client(needs_diff=True)

        base_commit_id = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')
        self.hg_add_file_commit(filename='empty.txt',
                                data=b'',
                                msg='commit 2')
        commit_id = self._hg_get_tip()

        revisions = client.parse_revision_spec([])

        spy = self.spy_on(client._execute)
        result = client.diff(revisions, exclude_patterns=['empty.txt'])

        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-X', 'empty.txt', '-r', base_commit_id, '-r', commit_id],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': commit_id,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -6,7 +6,4 @@\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id.encode('utf-8'),
            },
            'parent_diff': None,
        })

    def test_diff_with_diverged_branch(self):
        """Testing MercurialClient.diff with diverged branch"""
        client = self.build_client(needs_diff=True)

        base_commit_id = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')
        commit_id1 = self._hg_get_tip()

        # Create a "diverged" branch and make a commit there. We'll start by
        # generating a diff for this commit.
        self.run_hg(['branch', 'diverged'])
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')
        commit_id2 = self._hg_get_tip()

        revisions = client.parse_revision_spec([])

        spy = self.spy_on(client._execute)
        result = client.diff(revisions)

        self.assertEqual(len(spy.calls), 2)
        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', base_commit_id, '-r', commit_id1],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)
        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', commit_id1, '-r', commit_id2],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': commit_id2,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -1,3 +1,5 @@\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' Italiam, fato profugus, Laviniaque venit\n'
                b' litora, multum ille et terris iactatus et alto\n'
            ) % {
                b'base_commit_id': commit_id1.encode('utf-8'),
                b'commit_id': commit_id2.encode('utf-8'),
            },
            'parent_diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -6,7 +6,4 @@\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id1.encode('utf-8'),
            },
        })

        # Switch back to the default branch.
        self.run_hg(['update', '-C', 'default'])
        self.assertEqual(commit_id1, self._hg_get_tip())

        revisions = client.parse_revision_spec([])

        spy.reset_calls()
        result = client.diff(revisions)

        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', base_commit_id, '-r', commit_id1],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertEqual(len(spy.calls), 1)
        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': commit_id1,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -6,7 +6,4 @@\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id1.encode('utf-8'),
            },
            'parent_diff': None,
        })

    def test_diff_with_parent_diff(self):
        """Testing MercurialClient.diff with parent diffs"""
        client = self.build_client(needs_diff=True)

        base_commit_id = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')
        commit_id2 = self._hg_get_tip()

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO3,
                                msg='commit 3')
        commit_id3 = self._hg_get_tip()

        revisions = client.parse_revision_spec(['2', '3'])

        spy = self.spy_on(client._execute)
        result = client.diff(revisions)

        self.assertEqual(len(spy.calls), 2)
        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', commit_id2, '-r', commit_id3],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)
        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', base_commit_id, '-r', commit_id2],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': None,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -1,11 +1,11 @@\n'
                b'-ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' Italiam, fato profugus, Laviniaque venit\n'
                b' litora, multum ille et terris iactatus et alto\n'
                b' vi superum saevae memorem Iunonis ob iram;\n'
                b'-multa quoque et bello passus, dum conderet urbem,\n'
                b'+dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'+Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b' \n'
            ) % {
                b'base_commit_id': commit_id2.encode('utf-8'),
                b'commit_id': commit_id3.encode('utf-8'),
            },
            'parent_diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -1,3 +1,5 @@\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' Italiam, fato profugus, Laviniaque venit\n'
                b' litora, multum ille et terris iactatus et alto\n'
                b'@@ -6,7 +8,4 @@\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id2.encode('utf-8'),
            },
        })

    def test_diff_with_parent_diff_and_diverged_branch(self):
        """Testing MercurialClient.diff with parent diffs and diverged branch
        """
        # This test is very similar to test_diff_with_parent_diff except we
        # throw a branch into the mix.
        client = self.build_client(needs_diff=True)

        base_commit_id = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')

        self.run_hg(['branch', 'diverged'])
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')
        commit_id2 = self._hg_get_tip()

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO3,
                                msg='commit 3')
        commit_id3 = self._hg_get_tip()

        revisions = client.parse_revision_spec(['2', '3'])

        spy = self.spy_on(client._execute)
        result = client.diff(revisions)

        self.assertEqual(len(spy.calls), 2)
        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', commit_id2, '-r', commit_id3],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)
        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', base_commit_id, '-r', commit_id2],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': None,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -1,11 +1,11 @@\n'
                b'-ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' Italiam, fato profugus, Laviniaque venit\n'
                b' litora, multum ille et terris iactatus et alto\n'
                b' vi superum saevae memorem Iunonis ob iram;\n'
                b'-multa quoque et bello passus, dum conderet urbem,\n'
                b'+dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'+Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b' \n'
            ) % {
                b'base_commit_id': commit_id2.encode('utf-8'),
                b'commit_id': commit_id3.encode('utf-8'),
            },
            'parent_diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -1,3 +1,5 @@\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' Italiam, fato profugus, Laviniaque venit\n'
                b' litora, multum ille et terris iactatus et alto\n'
                b'@@ -6,7 +8,4 @@\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id2.encode('utf-8'),
            },
        })

    def test_diff_with_parent_diff_using_option(self):
        """Testing MercurialClient.diff with parent diffs using --parent"""
        # This test is very similar to test_diff_with_parent_diff except we
        # use the --parent option to post without explicit revisions
        client = self.build_client(
            needs_diff=True,
            options={
                'parent_branch': '2',
            })

        base_commit_id = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')
        commit_id2 = self._hg_get_tip()

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO3,
                                msg='commit 3')
        commit_id3 = self._hg_get_tip()

        revisions = client.parse_revision_spec([])

        spy = self.spy_on(client._execute)
        result = client.diff(revisions)

        self.assertEqual(len(spy.calls), 2)
        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', commit_id2, '-r', commit_id3],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)
        self.assertSpyCalledWith(
            spy,
            ['hg', 'diff', '--hidden', '--nodates', '-g',
             '-r', base_commit_id, '-r', commit_id2],
            env={
                'HGPLAIN': '1',
            },
            log_output_on_error=False,
            results_unicode=False)

        self.assertEqual(result, {
            'base_commit_id': base_commit_id,
            'commit_id': commit_id3,
            'diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -1,11 +1,11 @@\n'
                b'-ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' Italiam, fato profugus, Laviniaque venit\n'
                b' litora, multum ille et terris iactatus et alto\n'
                b' vi superum saevae memorem Iunonis ob iram;\n'
                b'-multa quoque et bello passus, dum conderet urbem,\n'
                b'+dum conderet urbem,\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b'+Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b' \n'
            ) % {
                b'base_commit_id': commit_id2.encode('utf-8'),
                b'commit_id': commit_id3.encode('utf-8'),
            },
            'parent_diff': (
                b'# HG changeset patch\n'
                b'# Node ID %(commit_id)s\n'
                b'# Parent  %(base_commit_id)s\n'
                b'diff --git a/foo.txt b/foo.txt\n'
                b'--- a/foo.txt\n'
                b'+++ b/foo.txt\n'
                b'@@ -1,3 +1,5 @@\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b'+ARMA virumque cano, Troiae qui primus ab oris\n'
                b' ARMA virumque cano, Troiae qui primus ab oris\n'
                b' Italiam, fato profugus, Laviniaque venit\n'
                b' litora, multum ille et terris iactatus et alto\n'
                b'@@ -6,7 +8,4 @@\n'
                b' inferretque deos Latio, genus unde Latinum,\n'
                b' Albanique patres, atque altae moenia Romae.\n'
                b' Musa, mihi causas memora, quo numine laeso,\n'
                b'-quidve dolens, regina deum tot volvere casus\n'
                b'-insignem pietate virum, tot adire labores\n'
                b'-impulerit. Tantaene animis caelestibus irae?\n'
                b' \n'
            ) % {
                b'base_commit_id': base_commit_id.encode('utf-8'),
                b'commit_id': commit_id2.encode('utf-8'),
            },
        })

    def test_parse_revision_spec_with_no_args(self):
        """Testing MercurialClient.parse_revision_spec with no arguments"""
        client = self.build_client()

        base = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')

        tip = self._hg_get_tip()

        self.assertEqual(
            client.parse_revision_spec([]),
            {
                'base': base,
                'commit_id': tip,
                'tip': tip,
            })

    def test_parse_revision_spec_with_one_arg_periods(self):
        """Testing MercurialClient.parse_revision_spec with r1..r2 syntax"""
        client = self.build_client()

        base = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')

        tip = self._hg_get_tip()

        self.assertEqual(
            client.parse_revision_spec(['0..1']),
            {
                'base': base,
                'tip': tip,
            })

    def test_parse_revision_spec_with_one_arg_colons(self):
        """Testing MercurialClient.parse_revision_spec with r1::r2 syntax"""
        client = self.build_client()

        base = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')

        tip = self._hg_get_tip()

        self.assertEqual(
            client.parse_revision_spec(['0..1']),
            {
                'base': base,
                'tip': tip,
            })

    def test_parse_revision_spec_with_one_arg(self):
        """Testing MercurialClient.parse_revision_spec with one revision"""
        client = self.build_client()

        base = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')
        tip = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')

        self.assertEqual(
            client.parse_revision_spec(['1']),
            {
                'base': base,
                'commit_id': tip,
                'tip': tip,
            })

    def test_parse_revision_spec_with_two_args(self):
        """Testing MercurialClient.parse_revision_spec with two revisions"""
        client = self.build_client()

        base = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')
        tip = self._hg_get_tip()

        self.assertEqual(
            client.parse_revision_spec(['0', '2']),
            {
                'base': base,
                'tip': tip,
            })

    def test_parse_revision_spec_with_parent_base(self):
        """Testing MercurialClient.parse_revision_spec with parent base"""
        client = self.build_client()

        start_base = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')
        commit1 = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2')
        commit2 = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO3,
                                msg='commit 3')
        commit3 = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO4,
                                msg='commit 4')
        commit4 = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO5,
                                msg='commit 5')

        self.assertEqual(
            client.parse_revision_spec(['1', '2']),
            {
                'base': commit1,
                'tip': commit2,
                'parent_base': start_base,
            })

        self.assertEqual(
            client.parse_revision_spec(['4']),
            {
                'base': commit3,
                'tip': commit4,
                'parent_base': start_base,
                'commit_id': commit4,
            })

        self.assertEqual(
            client.parse_revision_spec(['2', '4']),
            {
                'base': commit2,
                'tip': commit4,
                'parent_base': start_base,
            })

    def test_get_hg_ref_type(self):
        """Testing MercurialClient.get_hg_ref_type"""
        client = self.build_client()

        self.hg_add_file_commit(branch='test-branch',
                                bookmark='test-bookmark',
                                tag='test-tag')
        tip = self._hg_get_tip()

        self.assertEqual(client.get_hg_ref_type('test-branch'),
                         MercurialRefType.BRANCH)
        self.assertEqual(client.get_hg_ref_type('test-bookmark'),
                         MercurialRefType.BOOKMARK)
        self.assertEqual(client.get_hg_ref_type('test-tag'),
                         MercurialRefType.TAG)
        self.assertEqual(client.get_hg_ref_type(tip),
                         MercurialRefType.REVISION)
        self.assertEqual(client.get_hg_ref_type('something-invalid'),
                         MercurialRefType.UNKNOWN)

    def test_get_commit_message_with_one_commit_in_range(self):
        """Testing MercurialClient.get_commit_message with range containing
        only one commit
        """
        client = self.build_client(options={
            'guess_description': True,
            'guess_summary': True,
        })

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.get_commit_message(revisions),
            {
                'description': 'commit 1',
                'summary': 'commit 1',
            })

    def test_get_commit_message_with_commit_range(self):
        """Testing MercurialClient.get_commit_message with commit range"""
        client = self.build_client(options={
            'guess_description': True,
            'guess_summary': True,
        })

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1\n\ndesc1')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2\n\ndesc2')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO3,
                                msg='commit 3\n\ndesc3')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.get_commit_message(revisions),
            {
                'description': (
                    'desc1\n'
                    '\n'
                    'commit 2\n'
                    '\n'
                    'desc2\n'
                    '\n'
                    'commit 3\n'
                    '\n'
                    'desc3'
                ),
                'summary': 'commit 1',
            })

    def test_get_commit_message_with_specific_commit(self):
        """Testing MercurialClient.get_commit_message with specific commit"""
        client = self.build_client(options={
            'guess_description': True,
            'guess_summary': True,
        })

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1\n\ndesc1')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2\n\ndesc2')
        tip = self._hg_get_tip()
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO3,
                                msg='commit 3\n\ndesc3')

        revisions = client.parse_revision_spec([tip])

        self.assertEqual(
            client.get_commit_message(revisions),
            {
                'description': 'desc2',
                'summary': 'commit 2',
            })

    def test_commit_history(self):
        """Testing MercurialClient.get_commit_history"""
        client = self.build_client()

        base_commit_id = self._hg_get_tip(full=True)

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO1,
                                msg='commit 1\n\ndesc1',
                                date='2022-08-04T11:00:00-07:00')
        commit_id1 = self._hg_get_tip(full=True)

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO2,
                                msg='commit 2\n\ndesc2',
                                date='2022-08-05T12:00:00-07:00')
        commit_id2 = self._hg_get_tip(full=True)

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO3,
                                msg='commit 3\n\ndesc3',
                                date='2022-08-06T13:00:00-07:00')
        commit_id3 = self._hg_get_tip(full=True)

        revisions = client.parse_revision_spec([])
        commit_history = client.get_commit_history(revisions)

        self.assertEqual(
            commit_history,
            [
                {
                    'author_date': '2022-08-04T11:00:00-07:00',
                    'author_email': 'user at example.com',
                    'author_name': 'test user <user at example.com>',
                    'commit_id': commit_id1,
                    'commit_message': 'commit 1\n\ndesc1',
                    'parent_id': base_commit_id,
                },
                {
                    'author_date': '2022-08-05T12:00:00-07:00',
                    'author_email': 'user at example.com',
                    'author_name': 'test user <user at example.com>',
                    'commit_id': commit_id2,
                    'commit_message': 'commit 2\n\ndesc2',
                    'parent_id': commit_id1,
                },
                {
                    'author_date': '2022-08-06T13:00:00-07:00',
                    'author_email': 'user at example.com',
                    'author_name': 'test user <user at example.com>',
                    'commit_id': commit_id3,
                    'commit_message': 'commit 3\n\ndesc3',
                    'parent_id': commit_id2,
                },
            ])

    def test_create_commit_with_run_editor_true(self):
        """Testing MercurialClient.create_commit with run_editor set to True"""
        client = self.build_client()
        self.spy_on(client._execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='Test commit message.',
                             author=self.AUTHOR,
                             run_editor=True,
                             files=['foo.txt'])

        self.assertSpyLastCalledWith(
            client._execute,
            ['hg', 'commit', '-m', 'TEST COMMIT MESSAGE.', '-u',
             'name <email>', 'foo.txt'])

    def test_create_commit_with_run_editor_false(self):
        """Testing MercurialClient.create_commit with run_editor set to False
        """
        client = self.build_client()
        self.spy_on(client._execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='Test commit message.',
                             author=self.AUTHOR,
                             run_editor=False,
                             files=['foo.txt'])

        self.assertSpyLastCalledWith(
            client._execute,
            ['hg', 'commit', '-m', 'Test commit message.', '-u',
             'name <email>', 'foo.txt'])

    def test_create_commit_with_all_files_true(self):
        """Testing MercurialClient.create_commit with all_files set to True"""
        client = self.build_client()
        self.spy_on(client._execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='message',
                             author=self.AUTHOR,
                             run_editor=False,
                             files=[],
                             all_files=True)

        self.assertSpyLastCalledWith(
            client._execute,
            ['hg', 'commit', '-m', 'message', '-u', 'name <email>', '-A'])

    def test_create_commit_with_all_files_false(self):
        """Testing MercurialClient.create_commit with all_files set to False"""
        client = self.build_client()
        self.spy_on(client._execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='message',
                             author=self.AUTHOR,
                             run_editor=False,
                             files=['foo.txt'],
                             all_files=False)

        self.assertSpyLastCalledWith(
            client._execute,
            ['hg', 'commit', '-m', 'message', '-u', 'name <email>',
             'foo.txt'])

    def test_create_commit_with_empty_commit_message(self):
        """Testing MercurialClient.create_commit with empty commit message"""
        client = self.build_client()

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        message = (
            "A commit message wasn't provided. The patched files are in "
            "your tree but haven't been committed."
        )

        with self.assertRaisesMessage(CreateCommitError, message):
            client.create_commit(message='',
                                 author=self.AUTHOR,
                                 run_editor=True,
                                 files=['foo.txt'])

    def test_create_commit_without_author(self):
        """Testing MercurialClient.create_commit without author information"""
        client = self.build_client()
        self.spy_on(client._execute)

        with open('foo.txt', 'w') as fp:
            fp.write('change')

        client.create_commit(message='Test commit message.',
                             author=None,
                             run_editor=True,
                             files=['foo.txt'])

        self.assertSpyLastCalledWith(
            client._execute,
            ['hg', 'commit', '-m', 'TEST COMMIT MESSAGE.', 'foo.txt'])

    def test_merge_with_branch_and_close_branch_false(self):
        """Testing MercurialClient.merge with target branch and
        close_branch=False
        """
        client = self.build_client()

        self.hg_add_file_commit(branch='test-branch')

        self.spy_on(client._execute)
        client.merge(target='test-branch',
                     destination='default',
                     message='My merge commit',
                     author=self.AUTHOR,
                     close_branch=False)

        calls = client._execute.calls
        self.assertSpyCallCount(client._execute, 5)
        self.assertSpyCalledWith(calls[0], ['hg', 'log', '-ql1', '-r',
                                            'bookmark(test-branch)'])
        self.assertSpyCalledWith(calls[1], ['hg', 'branches', '-q'])
        self.assertSpyCalledWith(calls[2], ['hg', 'update', 'default'])
        self.assertSpyCalledWith(calls[3], ['hg', 'merge', 'test-branch'])
        self.assertSpyCalledWith(calls[4], ['hg', 'commit', '-m',
                                            'My merge commit',
                                            '-u', 'name <email>'])

    def test_merge_with_branch_and_close_branch_true(self):
        """Testing MercurialClient.merge with target branch and
        close_branch=True
        """
        client = self.build_client()

        self.hg_add_file_commit(branch='test-branch')

        self.spy_on(client._execute)
        client.merge(target='test-branch',
                     destination='default',
                     message='My merge commit',
                     author=self.AUTHOR,
                     close_branch=True)

        calls = client._execute.calls
        self.assertSpyCallCount(client._execute, 7)
        self.assertSpyCalledWith(calls[0], ['hg', 'log', '-ql1', '-r',
                                            'bookmark(test-branch)'])
        self.assertSpyCalledWith(calls[1], ['hg', 'branches', '-q'])
        self.assertSpyCalledWith(calls[2], ['hg', 'update', 'test-branch'])
        self.assertSpyCalledWith(calls[3], ['hg', 'commit', '-m',
                                            'My merge commit',
                                            '--close-branch'])
        self.assertSpyCalledWith(calls[4], ['hg', 'update', 'default'])
        self.assertSpyCalledWith(calls[5], ['hg', 'merge', 'test-branch'])
        self.assertSpyCalledWith(calls[6], ['hg', 'commit', '-m',
                                            'My merge commit',
                                            '-u', 'name <email>'])

    def test_merge_with_bookmark_and_close_branch_false(self):
        """Testing MercurialClient.merge with target bookmark and
        close_branch=False
        """
        client = self.build_client()

        self.run_hg(['branch', 'feature-work'])
        self.hg_add_file_commit(bookmark='test-bookmark')

        self.spy_on(client._execute)
        client.merge(target='test-bookmark',
                     destination='default',
                     message='My merge commit',
                     author=self.AUTHOR,
                     close_branch=False)

        calls = client._execute.calls
        self.assertSpyCallCount(client._execute, 4)
        self.assertSpyCalledWith(calls[0], ['hg', 'log', '-ql1', '-r',
                                            'bookmark(test-bookmark)'])
        self.assertSpyCalledWith(calls[1], ['hg', 'update', 'default'])
        self.assertSpyCalledWith(calls[2], ['hg', 'merge', 'test-bookmark'])
        self.assertSpyCalledWith(calls[3], ['hg', 'commit', '-m',
                                            'My merge commit',
                                            '-u', 'name <email>'])

    def test_merge_with_bookmark_and_close_branch_true(self):
        """Testing MercurialClient.merge with target bookmark and
        close_branch=True
        """
        client = self.build_client()

        self.run_hg(['branch', 'feature-work'])
        self.hg_add_file_commit(bookmark='test-bookmark')

        self.spy_on(client._execute)
        client.merge(target='test-bookmark',
                     destination='default',
                     message='My merge commit',
                     author=self.AUTHOR,
                     close_branch=True)

        calls = client._execute.calls
        self.assertSpyCallCount(client._execute, 5)
        self.assertSpyCalledWith(calls[0], ['hg', 'log', '-ql1', '-r',
                                            'bookmark(test-bookmark)'])
        self.assertSpyCalledWith(calls[1], ['hg', 'update', 'default'])
        self.assertSpyCalledWith(calls[2], ['hg', 'merge', 'test-bookmark'])
        self.assertSpyCalledWith(calls[3], ['hg', 'commit', '-m',
                                            'My merge commit',
                                            '-u', 'name <email>'])
        self.assertSpyCalledWith(calls[4], ['hg', 'bookmark', '-d',
                                            'test-bookmark'])

    def test_merge_with_tag(self):
        """Testing MercurialClient.merge with target tag"""
        client = self.build_client()

        self.run_hg(['branch', 'feature-work'])
        self.hg_add_file_commit(tag='test-tag')

        self.spy_on(client._execute)
        client.merge(target='test-tag',
                     destination='default',
                     message='My merge commit',
                     author=self.AUTHOR,
                     close_branch=True)

        calls = client._execute.calls
        self.assertSpyCallCount(client._execute, 6)
        self.assertSpyCalledWith(calls[0], ['hg', 'log', '-ql1', '-r',
                                            'bookmark(test-tag)'])
        self.assertSpyCalledWith(calls[1], ['hg', 'branches', '-q'])
        self.assertSpyCalledWith(calls[2], ['hg', 'log', '-ql1', '-r',
                                            'tag(test-tag)'])
        self.assertSpyCalledWith(calls[3], ['hg', 'update', 'default'])
        self.assertSpyCalledWith(calls[4], ['hg', 'merge', 'test-tag'])
        self.assertSpyCalledWith(calls[5], ['hg', 'commit', '-m',
                                            'My merge commit',
                                            '-u', 'name <email>'])

    def test_merge_with_revision(self):
        """Testing MercurialClient.merge with target revision"""
        client = self.build_client()

        self.run_hg(['branch', 'feature-work'])
        self.hg_add_file_commit()
        tip = self._hg_get_tip()

        self.spy_on(client._execute)
        client.merge(target=tip,
                     destination='default',
                     message='My merge commit',
                     author=self.AUTHOR,
                     close_branch=True)

        calls = client._execute.calls
        self.assertSpyCallCount(client._execute, 7)
        self.assertSpyCalledWith(calls[0], ['hg', 'log', '-ql1', '-r',
                                            'bookmark(%s)' % tip])
        self.assertSpyCalledWith(calls[1], ['hg', 'branches', '-q'])
        self.assertSpyCalledWith(calls[2], ['hg', 'log', '-ql1', '-r',
                                            'tag(%s)' % tip])
        self.assertSpyCalledWith(calls[3], ['hg', 'identify', '-r', tip])
        self.assertSpyCalledWith(calls[4], ['hg', 'update', 'default'])
        self.assertSpyCalledWith(calls[5], ['hg', 'merge', tip])
        self.assertSpyCalledWith(calls[6], ['hg', 'commit', '-m',
                                            'My merge commit',
                                            '-u', 'name <email>'])

    def test_merge_with_invalid_target(self):
        """Testing MercurialClient.merge with an invalid target"""
        client = self.build_client()

        expected_message = (
            'Could not find a valid branch, tag, bookmark, or revision called '
            '"invalid".'
        )

        with self.assertRaisesMessage(MergeError, expected_message):
            client.merge(target='invalid',
                         destination='default',
                         message='commit message',
                         author=self.AUTHOR)

    def test_merge_with_invalid_destination(self):
        """Testing MercurialClient.merge with an invalid destination branch"""
        client = self.build_client()

        expected_message = 'Could not switch to branch "non-existent-branch".'

        with self.assertRaisesMessage(MergeError, expected_message):
            client.merge(target='default',
                         destination='non-existent-branch',
                         message='commit message',
                         author=self.AUTHOR)

    def test_apply_patch(self):
        """Testing MercurialClient.apply_patch"""
        client = self.build_client()

        self.spy_on(run_process_exec,
                    op=kgb.SpyOpReturn((0, b'test', b'')))

        result = client.apply_patch(patch_file='test.diff')

        self.assertSpyCalledWith(
            run_process_exec,
            [
                'hg', 'patch', '--no-commit', 'test.diff',
                '--config', 'extensions.rbtoolsnormalize=%s' % hgext_path,
            ])

        self.assertTrue(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(result.patch_output, b'test')

    def test_apply_patch_with_p(self):
        """Testing MercurialClient.apply_patch with p="""
        client = self.build_client()

        self.spy_on(run_process_exec,
                    op=kgb.SpyOpReturn((0, b'test', b'')))

        result = client.apply_patch(patch_file='test.diff',
                                    p='1')

        self.assertSpyCalledWith(
            run_process_exec,
            [
                'hg', 'patch', '--no-commit', '-p', '1', 'test.diff',
                '--config', 'extensions.rbtoolsnormalize=%s' % hgext_path,
            ])

        self.assertTrue(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(result.patch_output, b'test')

    def test_apply_patch_with_error(self):
        """Testing MercurialClient.apply_patch with error"""
        client = self.build_client()

        self.spy_on(run_process_exec,
                    op=kgb.SpyOpReturn((1, b'bad', b'')))

        result = client.apply_patch(patch_file='test.diff')

        self.assertSpyCalledWith(
            run_process_exec,
            [
                'hg', 'patch', '--no-commit', 'test.diff',
                '--config', 'extensions.rbtoolsnormalize=%s' % hgext_path,
            ],
            redirect_stderr=True)

        self.assertFalse(result.applied)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.conflicting_files, [])
        self.assertEqual(result.patch_output, b'bad')

    def _hg_get_tip(self, full=False):
        """Return the revision at the tip of the branch.

        Args:
            full (bool, optional):
                Whether to return a full ID. By default, a shortened ID is
                returned.

                Version Added:
                    4.0

        Returns:
            unicode:
            The tip revision.
        """
        cmdline = ['identify']

        if full:
            # This is currently the most cross-Mercurial way of getting a
            # full ID.
            cmdline.append('--debug')

        return (
            self.run_hg(cmdline)
            .stdout
            .read()
            .split()[0]
        )


class MercurialSubversionClientTests(MercurialTestCase):
    """Unit tests for hgsubversion."""

    TESTSERVER = 'http://127.0.0.1:8080'

    SVNSERVE_MAX_RETRIES = 12

    _svnserve_pid = None
    _svn_temp_base_path = None
    _skip_reason = None

    @classmethod
    def setUpClass(cls):
        for exe in ('svnadmin', 'svnserve', 'svn'):
            if not is_exe_in_path(exe):
                cls._skip_reason = '%s is not available on the system.' % exe
                break
        else:
            has_hgsubversion = False

            try:
                output = (
                    run_process(
                        [
                            'hg', '--config', 'extensions.hgsubversion=',
                            'svn', '--help',
                        ],
                        ignore_errors=True)
                    .stdout
                    .read()
                )

                has_hgsubversion = \
                    not re.search('unknown command [\'"]svn[\'"]',
                                  output, re.I)
            except OSError:
                has_hgsubversion = False

            if not has_hgsubversion:
                cls._skip_reason = \
                    'hgsubversion is not available or cannot be used.'

        super(MercurialSubversionClientTests, cls).setUpClass()

        # Don't do any of the following expensive stuff if we know we're just
        # going to skip all the tests.
        if cls._skip_reason:
            return

        # Create the repository that we'll be populating and later cloning.
        temp_base_path = tempfile.mkdtemp(prefix='rbtools.')
        cls._svn_temp_base_path = temp_base_path

        svn_repo_path = os.path.join(temp_base_path, 'svnrepo')
        run_process(['svnadmin', 'create', svn_repo_path])

        # Fill it with content. First, though, we have to clone it.
        svn_checkout_path = os.path.join(temp_base_path, 'checkout.svn')
        run_process(['svn', 'checkout', 'file://%s' % svn_repo_path,
                     svn_checkout_path])
        os.chdir(svn_checkout_path)

        run_process(['svn', 'propset', 'reviewboard:url', cls.TESTSERVER,
                     svn_checkout_path])
        run_process(['svn', 'mkdir', 'trunk', 'branches', 'tags'])
        run_process(['svn', 'commit', '-m', 'Initial commit.'])
        os.chdir(os.path.join(svn_checkout_path, 'trunk'))

        for i, data in enumerate([FOO, FOO1, FOO2]):
            cls.svn_add_file_commit(filename='foo.txt',
                                    data=data,
                                    msg='Test commit %s' % i,
                                    add_file=(i == 0))

        # Launch svnserve so Mercurial can pull from it.
        svnserve_port = (os.environ.get('SVNSERVE_PORT') or
                         str(randint(30000, 40000)))

        pid_file = os.path.join(temp_base_path, 'svnserve.pid')

        run_process([
            'svnserve', '--single-thread', '--pid-file', pid_file, '-d',
            '--listen-port', svnserve_port, '-r', temp_base_path,
        ])

        for i in range(0, cls.SVNSERVE_MAX_RETRIES):
            try:
                cls._svnserve_pid = int(open(pid_file).read().strip())
            except (IOError, OSError):
                # Wait to see if svnserve has launched yet.
                time.sleep(0.25)

        if not cls._svnserve_pid:
            raise cls.failureException('Unable to launch svnserve on port %s'
                                       % svnserve_port)

        cls.svn_checkout_url = 'svn://127.0.0.1:%s/svnrepo' % svnserve_port

    @classmethod
    def tearDownClass(cls):
        if cls._svnserve_pid:
            os.kill(cls._svnserve_pid, 9)

        if cls._svn_temp_base_path:
            shutil.rmtree(cls._svn_temp_base_path, ignore_errors=True)

        super(MercurialSubversionClientTests, cls).tearDownClass()

    def setUp(self):
        super(MercurialSubversionClientTests, self).setUp()

        if self._skip_reason:
            raise unittest.SkipTest(self._skip_reason)

        home_dir = make_tempdir()
        self.set_user_home(home_dir)
        hgrc_path = os.path.join(home_dir, '.hgrc')

        # Make sure hgsubversion is enabled.
        #
        # This will modify the .hgrc in the temp home directory created for
        # these tests.
        #
        # The "hgsubversion =" tells Mercurial to check for hgsubversion in
        # the default PYTHONPATH
        with open(hgrc_path, 'w') as fp:
            fp.write('[extensions]\n')
            fp.write('hgsubversion =\n')

        try:
            self.clone_dir = os.path.join(home_dir, 'checkout.hg')
            self.run_hg(['clone', '--stream', self.svn_checkout_url,
                         self.clone_dir])
        except Exception as e:
            raise unittest.SkipTest(
                'Unable to clone Subversion repository: %s' % e)

        os.chdir(self.clone_dir)

    @classmethod
    def svn_add_file_commit(cls, filename, data, msg, add_file=True):
        with open(filename, 'wb') as fp:
            fp.write(data)

        if add_file:
            run_process(['svn', 'add', filename], ignore_errors=True)

        run_process(['svn', 'commit', '-m', msg])

    def test_get_repository_info(self):
        """Testing MercurialClient.get_repository_info with SVN"""
        client = self.build_client()
        ri = client.get_repository_info()

        self.assertEqual(client._type, 'svn')
        self.assertEqual(ri.base_path, '/trunk')
        self.assertEqual(ri.path, self.svn_checkout_url)

    def test_calculate_repository_info(self):
        """Testing MercurialClient._calculate_hgsubversion_repository_info
        with SVN determines repository and base paths
        """
        client = self.build_client()

        repo_info = client._calculate_hgsubversion_repository_info(
            'URL: svn+ssh://testuser@svn.example.net/repo/trunk\n'
            'Repository Root: svn+ssh://testuser@svn.example.net/repo\n'
            'Repository UUID: bfddb570-5023-0410-9bc8-bc1659bf7c01\n'
            'Revision: 9999\n'
            'Node Kind: directory\n'
            'Last Changed Author: user\n'
            'Last Changed Rev: 9999\n'
            'Last Changed Date: 2012-09-05 18:04:28 +0000 (Wed, 05 Sep 2012)'
        )

        self.assertEqual(repo_info.path, 'svn+ssh://svn.example.net/repo')
        self.assertEqual(repo_info.base_path, '/trunk')

    def test_scan_for_server_with_reviewboardrc(self):
        """Testing MercurialClient.scan_for_server with SVN and configured
        .reviewboardrc
        """
        client = self.build_client()

        with self.reviewboardrc({'REVIEWBOARD_URL': 'https://example.com/'}):
            client.config = load_config()
            ri = client.get_repository_info()

            self.assertEqual(client.scan_for_server(ri),
                             'https://example.com/')

    def test_scan_for_server_with_property(self):
        """Testing MercurialClient.scan_for_server with SVN and reviewboard:url
        property
        """
        client = self.build_client()
        ri = client.get_repository_info()

        self.assertEqual(client.scan_for_server(ri), self.TESTSERVER)

    def test_diff(self):
        """Testing MercurialClient.diff with SVN"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO4,
                                msg='edit 4')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': '',
                'parent_diff': None,
            })

    def test_diff_with_multiple_commits(self):
        """Testing MercurialClient.diff with SVN and multiple commits"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO4,
                                msg='edit 4')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO5,
                                msg='edit 5')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO6,
                                msg='edit 6')

        revisions = client.parse_revision_spec([])

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': '',
                'parent_diff': None,
            })

    def test_diff_with_revision(self):
        """Testing MercurialClient.diff with SVN and specific revision"""
        client = self.build_client(needs_diff=True)
        client.get_repository_info()

        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO4,
                                msg='edit 4',
                                branch='b')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO5,
                                msg='edit 5',
                                branch='b')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO6,
                                msg='edit 6',
                                branch='b')
        self.hg_add_file_commit(filename='foo.txt',
                                data=FOO4,
                                msg='edit 7',
                                branch='b')

        revisions = client.parse_revision_spec(['3'])

        self.assertEqual(
            client.diff(revisions),
            {
                'diff': '',
                'parent_diff': None,
            })
