"""Base test cases for RBTools unit tests."""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from typing import Iterator, Optional, Sequence, TYPE_CHECKING, Union

import kgb

from rbtools.api.client import RBClient
from rbtools.testing.api.transport import URLMapTransport
from rbtools.utils.filesystem import (cleanup_tempfiles,
                                      make_tempdir,
                                      make_tempfile)

if TYPE_CHECKING:
    from unittest.case import _AssertRaisesContext

    from rbtools.api.transport import Transport


class TestCase(unittest.TestCase):
    """The base class for RBTools test cases.

    This provides helpful utility functions, environment management, and
    better docstrings to help craft unit tests for RBTools functionality.
    All RBTools unit tests should use this this class or a subclass of it
    as the base class.
    """

    #: Regex for matching consecutive whitespace characters.
    ws_re = re.compile(r'\s+')

    maxDiff = None

    #: The default text editor to use for tests.
    #:
    #: By default, this will use a fake editor that's bundled with the test
    #: suite.
    default_text_editor: str = '%s %s' % (
        sys.executable,
        os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     'scripts', 'editor.py'))
    )

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
    needs_temp_home: bool = False

    ######################
    # Instance variables #
    ######################

    #: The current directory before any tests are run.
    _cls_old_cwd: str

    #: The current directory before the current test was run.
    _old_cwd: str

    #: The home directory before the current test was run.
    old_home: str

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the test suite.

        This will store some state that can be restored once all tests in the
        class have been run.
        """
        super().setUpClass()

        cls._cls_old_cwd = os.getcwd()

    @classmethod
    def tearDownClass(cls) -> None:
        """Tear down the test suite.

        This will restore the current directory to what was set prior to
        the test runs, and then call any parent tear-down logic.
        """
        os.chdir(cls._cls_old_cwd)

        super().tearDownClass()

    def setUp(self) -> None:
        """Set up a single test.

        This will store some initial state for tests and optionally create a
        new current HOME directory to run the tests within.
        """
        super().setUp()

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

        os.environ['RBTOOLS_EDITOR'] = self.default_text_editor

    def tearDown(self) -> None:
        """Tear down a single test.

        This will clean up any temporary files and directories, and restore
        the current directory and HOME direcotry.
        """
        super().tearDown()

        os.chdir(self._old_cwd)
        cleanup_tempfiles()

        if self.old_home:
            self.set_user_home(self.old_home)

    def shortDescription(self) -> str:
        """Returns the description of the current test.

        This changes the default behavior to replace all newlines with spaces,
        allowing a test description to span lines. It should still be kept
        short, though.

        Returns:
            str:
            The descriptive text for the current unit test.
        """
        doc = self._testMethodDoc

        if doc is not None:
            doc = doc.split('\n\n', 1)[0]
            doc = self.ws_re.sub(' ', doc).strip()

        return doc

    def get_user_home(self) -> str:
        """Return the user's current home directory.

        Version Added:
            3.0

        Returns:
            str:
            The current home directory.
        """
        return os.environ['HOME']

    def set_user_home(
        self,
        path: str,
    ) -> None:
        """Set the user's current home directory.

        This will be unset when the unit test has finished.

        Version Added:
            3.0

        Args:
            path (str):
                The new home directory.
        """
        os.environ['HOME'] = path

    def chdir_tmp(self) -> str:
        """Create a temporary directory and set it as the working directory.

        The directory will be deleted after the test has finished.

        Version Added:
            3.0

        Returns:
            str:
            The path to the temp directory.
        """
        dirname = make_tempdir()
        os.chdir(dirname)

        return dirname

    @contextmanager
    def env(
        self,
        env: dict[str, Optional[str]],
    ) -> Iterator[None]:
        """Run code with custom environment variables temporarily set.

        This will set environment variables to the provided values (or
        erase them from the environment if set to ``None``) before executing
        the code in the context.

        Once executed, the old environment will be restored.

        Version Added:
            5.0

        Args:
            env (dict):
                The environment variables to set/remove.

        Context:
            Code will execute with the new environment set.
        """
        old_env: dict[str, Optional[str]] = {}

        for key, value in env.items():
            old_env[key] = os.environ.get(key)

            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        try:
            yield
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def precreate_tempfiles(
        self,
        count: int,
    ) -> Sequence[str]:
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

        Returns:
            list of str:
            The list of temporary file paths.

        Raises:
            AssertionError:
                The test suite class did not mix in :py:class:`kgb.SpyAgency`.
        """
        spy_for = getattr(self, 'spy_for', None)

        assert spy_for, (
            '%r must mix in kgb.SpyAgency in order to call this method.'
            % self.__class__)

        tmpfiles: list[str] = [
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

    def precreate_tempdirs(
        self,
        count: int,
    ) -> Sequence[str]:
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

        Returns:
            list of str:
            The list of temporary directory paths.

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

    def assertDiffEqual(
        self,
        diff: bytes,
        expected_diff: bytes,
    ) -> None:
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

    def assertRaisesMessage(
        self,
        expected_exception: type[Exception],
        expected_message: str,
    ) -> _AssertRaisesContext[Exception]:
        """Assert that a call raises an exception with the given message.

        Args:
            expected_exception (type):
                The type of exception that's expected to be raised.

            expected_message (str):
                The expected exception message.

        Raises:
            AssertionError:
                The assertion failure, if the exception and message isn't
                raised.
        """
        return self.assertRaisesRegex(expected_exception,
                                      re.escape(expected_message))

    def create_rbclient(self) -> RBClient:
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

    def get_rbclient_transport(
        self,
        client: RBClient,
    ) -> Transport:
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

    def write_reviewboardrc(
        self,
        config: Union[str, dict[str, object]] = {},
        *,
        parent_dir: Optional[str] = None,
        filename: str = '.reviewboardrc',
    ) -> str:
        """Write a .reviewboardrc file to a directory.

        This allows for control over where the file is written, what it's
        named, and the serialization of the contents of the file.

        Version Added:
            5.0

        Args:
            config (dict or str):
                A dictionary of settings to write, or a string payload for
                the entire file.

            parent_dir (str, optional):
                The directory where the configuration file should go.

                This will default to the current directory.

            filename (str, optional):
                The name of the configuration file.

                This defaults to :file:`.reviewboardrc`.

        Returns:
            str:
            The resulting path to the configuration file.
        """
        if not parent_dir:
            parent_dir = os.getcwd()

        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir, 0o700)

        full_path = os.path.realpath(os.path.join(parent_dir, filename))

        with open(full_path, 'w') as fp:
            if isinstance(config, str):
                fp.write(config)
            else:
                for key, value in config.items():
                    fp.write('%s = %r\n' % (key, value))

        return full_path

    @contextmanager
    def reviewboardrc(
        self,
        config: Union[str, dict[str, object]],
        use_temp_dir: bool = False,
    ) -> Iterator[None]:
        """Populate a temporary .reviewboardrc file.

        This will create a :file:`.reviewboardrc` file, either in the current
        directory or in a new temporary directory (if ``use_temp_dir`` is set).
        The file will contain the provided configuration.

        Version Added:
            3.0

        Args:
            config (dict or str):
                A dictionary of key-value pairs to write into the
                :file:`.reviewboardrc` file, or the string contents of the
                file.

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
        else:
            # Avoid unbound errors. We won't be using these below.
            temp_dir = ''
            cwd = ''

        self.write_reviewboardrc(config)

        try:
            yield
        finally:
            if use_temp_dir:
                os.chdir(cwd)
                shutil.rmtree(temp_dir)
