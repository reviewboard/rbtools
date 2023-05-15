"""Base test cases for RBTools unit tests."""

import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from typing import List

import kgb

from rbtools.api.client import RBClient
from rbtools.testing.api.transport import URLMapTransport
from rbtools.utils.filesystem import (cleanup_tempfiles,
                                      make_tempdir,
                                      make_tempfile)


class TestCase(unittest.TestCase):
    """The base class for RBTools test cases.

    This provides helpful utility functions, environment management, and
    better docstrings to help craft unit tests for RBTools functionality.
    All RBTools unit tests should use this this class or a subclass of it
    as the base class.
    """

    ws_re = re.compile(r'\s+')

    default_text_editor = '%s %s' % (
        sys.executable,
        os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     'scripts', 'editor.py'))
    )

    maxDiff = 10000

    #: A sample test URL for a Review Board server.
    #:
    #: Version Added:
    #:     3.1
    TEST_SERVER_URL = 'https://reviews.example.com/'

    #: Whether individual unit tests need a new temporary HOME directory.
    #:
    #: If set, a directory will be created at test startup, and will be
    #: set as the home directory.
    #:
    #: Version Added:
    #:     3.0
    needs_temp_home = False

    @classmethod
    def setUpClass(cls):
        super(TestCase, cls).setUpClass()

        cls._cls_old_cwd = os.getcwd()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._cls_old_cwd)

        super(TestCase, cls).tearDownClass()

    def setUp(self):
        super(TestCase, self).setUp()

        self._old_cwd = os.getcwd()
        self.old_home = self.get_user_home()

        if self.needs_temp_home:
            home_dir = make_tempdir()
            self.set_user_home(home_dir)

            # Since the tests need a safer HOME setup, it stands to reason
            # that we should also not operate within the tree, as it could
            # result in RBTools's .reviewboardrc being picked up. We'll
            # instead default to running within the new home directory.
            os.chdir(home_dir)

        os.environ[str('RBTOOLS_EDITOR')] = str(self.default_text_editor)

    def tearDown(self):
        super(TestCase, self).tearDown()

        os.chdir(self._old_cwd)
        cleanup_tempfiles()

        if self.old_home:
            self.set_user_home(self.old_home)

    def shortDescription(self):
        """Returns the description of the current test.

        This changes the default behavior to replace all newlines with spaces,
        allowing a test description to span lines. It should still be kept
        short, though.

        Returns:
            unicode:
            The descriptive text for the current unit test.
        """
        doc = self._testMethodDoc

        if doc is not None:
            doc = doc.split('\n\n', 1)[0]
            doc = self.ws_re.sub(' ', doc).strip()

        return doc

    def get_user_home(self):
        """Return the user's current home directory.

        Version Added:
            3.0

        Returns:
            unicode:
            The current home directory.
        """
        return os.environ['HOME']

    def set_user_home(self, path):
        """Set the user's current home directory.

        This will be unset when the unit test has finished.

        Version Added:
            3.0

        Args:
            path (unicode):
                The new home directory.
        """
        os.environ['HOME'] = path

    def chdir_tmp(self):
        """Create a temporary directory and set it as the working directory.

        The directory will be deleted after the test has finished.

        Version Added:
            3.0

        Returns:
            unicode:
            The path to the temp directory.
        """
        dirname = make_tempdir()
        os.chdir(dirname)

        return dirname

    def precreate_tempfiles(self, count):
        """Pre-create a specific number of temporary files.

        This will call :py:func:`~rbtools.utils.filesystem.make_tempfile`
        the specified number of times, returning the list of generated temp
        file paths, and will then spy that function to return those temp
        files.

        Once each pre-created temp file is used up, any further calls to
        :py:func:`~rbtools.utils.filesystem.make_tempfile` will result in
        an error, failing the test.

        This is useful in unit tests that need to script a series of
        expected calls using :py:mod:`kgb` (such as through
        :py:class:`kgb.ops.SpyOpMatchInOrder`) that need to know the names
        of temporary filenames up-front.

        Unit test suites that use this must mix in :py:class:`kgb.SpyAgency`.

        Version Added:
            3.0

        Args:
            count (int):
                The number of temporary filenames to pre-create.

        Raises:
            AssertionError:
                The test suite class did not mix in :py:class:`kgb.SpyAgency`.
        """
        spy_for = getattr(self, 'spy_for', None)

        assert spy_for, (
            '%r must mix in kgb.SpyAgency in order to call this method.'
            % self.__class__)

        tmpfiles: List[str] = [
            make_tempfile()
            for i in range(count)
        ]

        tmpfiles_iter = iter(tmpfiles)

        @spy_for(make_tempfile)
        def _return_next_tempfile(*args, **kwargs) -> str:
            try:
                tmpfile = next(tmpfiles_iter)
            except StopIteration:
                self.fail('Too many calls to make_tempfile(). Expected %s, '
                          'got %s.'
                          % (count, count + 1))

            content = kwargs.get('content')

            if content:
                with open(tmpfile, 'wb') as fp:
                    fp.write(content)

            return tmpfile

        return tmpfiles

    def precreate_tempdirs(self, count):
        """Pre-create a specific number of temporary directories.

        This will call :py:func:`~rbtools.utils.filesystem.make_tempdir`
        the specified number of times, returning the list of generated temp
        paths, and will then spy that function to return those temp paths.

        Once each pre-created temp path is used up, any further calls to
        :py:func:`~rbtools.utils.filesystem.make_tempdir` will result in
        an error, failing the test.

        This is useful in unit tests that need to script a series of
        expected calls using :py:mod:`kgb` (such as through
        :py:class:`kgb.ops.SpyOpMatchInOrder`) that need to know the names
        of temporary filenames up-front.

        Unit test suites that use this must mix in :py:class:`kgb.SpyAgency`.

        Version Added:
            3.0

        Args:
            count (int):
                The number of temporary directories to pre-create.

        Raises:
            AssertionError:
                The test suite class did not mix in :py:class:`kgb.SpyAgency`.
        """
        assert hasattr(self, 'spy_on'), (
            '%r must mix in kgb.SpyAgency in order to call this method.'
            % self.__class__)

        tmpdirs = [
            make_tempdir()
            for i in range(count)
        ]

        self.spy_on(make_tempdir, op=kgb.SpyOpReturnInOrder(tmpdirs))

        return tmpdirs

    def assertDiffEqual(self, diff, expected_diff):
        """Assert that two diffs are equal.

        Args:
            diff (bytes):
                The generated diff.

            expected_diff (bytes):
                The expected diff.

        Raises:
            AssertionError:
                The diffs aren't equal or of the right type.
        """
        self.assertIsInstance(diff, bytes)
        self.assertIsInstance(expected_diff, bytes)

        self.assertEqual(diff.splitlines(), expected_diff.splitlines())

    def assertRaisesMessage(self, expected_exception, expected_message):
        """Assert that a call raises an exception with the given message.

        Args:
            expected_exception (type):
                The type of exception that's expected to be raised.

            expected_message (unicode):
                The expected exception message.

        Raises:
            AssertionError:
                The assertion failure, if the exception and message isn't
                raised.
        """
        # This explicitly uses the old name, as opposed to assertRaisesRegex,
        # because we still need Python 2.7 support. Once we move to Python 3,
        # we can fix this.
        return self.assertRaisesRegexp(expected_exception,
                                       re.escape(expected_message))

    def create_rbclient(self):
        """Return a RBClient for testing.

        This will set up a :py:class:`~rbtools.testing.api.transport.
        URLMapTransport`. It's recommended that the caller access it via
        :py:meth:`get_rbclient_transport`.

        Version Added:
            3.1

        Args:
            transport (rbtools.api.transport.Transport, optional):
                An explicit transport instance to use

        Returns:
            rbtools.api.client.RBClient:
            The client for testing purposes.
        """
        return RBClient(url=self.TEST_SERVER_URL,
                        transport_cls=URLMapTransport)

    def get_rbclient_transport(self, client):
        """Return the transport associated with a RBClient.

        This allows tests to avoid reaching into
        :py:class:`~rbtools.api.client.RBClient` internals in order to get
        the transport.

        Version Added:
            3.1

        Args:
            client (rbtools.api.client.RBClient):
                The client instance.

        Returns:
            rbtools.api.transport.Transport:
            The client's transport.
        """
        return client._transport

    @contextmanager
    def reviewboardrc(self, config, use_temp_dir=False):
        """Populate a temporary .reviewboardrc file.

        This will create a :file:`.reviewboardrc` file, either in the current
        directory or in a new temporary directory (if ``use_temp_dir`` is set).
        The file will contain the provided configuration.

        Version Added:
            3.0

        Args:
            config (dict):
                A dictionary of key-value pairs to write into the
                :file:`.reviewboardrc` file.

                A best effort attempt will be made to write each configuration
                to the file.

            use_temp_dir (bool, optional):
                Whether a temporary directory should be created and set as
                the current directory. If set, the file will be written there,
                and the directory will be removed after the context manager
                finishes.

        Context:
            The code being run will have a :file:`.reviewboardrc` in the
            current directory.
        """
        if use_temp_dir:
            temp_dir = tempfile.mkdtemp()
            cwd = os.getcwd()
            os.chdir(temp_dir)

        with open('.reviewboardrc', 'w') as fp:
            for key, value in config.items():
                fp.write('%s = %r\n' % (key, value))

        try:
            yield
        finally:
            if use_temp_dir:
                os.chdir(cwd)
                shutil.rmtree(temp_dir)
