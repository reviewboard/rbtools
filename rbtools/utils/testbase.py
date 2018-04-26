from __future__ import unicode_literals

import contextlib
import os
import shutil
import sys
import tempfile
import uuid

import six
from six.moves import cStringIO as StringIO

from rbtools.utils.filesystem import cleanup_tempfiles, make_tempdir
from rbtools.testing import TestCase


class RBTestBase(TestCase):
    """Base class for RBTools tests.

    Its side effect in that it change home directory before test suit will
    run. This is because RBTools actively works with files and almost all
    tests employ file I/O operations."""
    def setUp(self):
        self._old_cwd = os.getcwd()
        self.old_home = os.environ['HOME']
        self.set_user_home_tmp()

    def tearDown(self):
        os.chdir(self._old_cwd)
        cleanup_tempfiles()

        if self.old_home:
            os.environ['HOME'] = self.old_home

    def chdir_tmp(self, dir=None):
        """Changes current directory to a temporary directory."""
        dirname = make_tempdir(parent=dir)
        os.chdir(dirname)
        return dirname

    def gen_uuid(self):
        """Generates UUID value which can be useful where some unique value
        is required."""
        return str(uuid.uuid4())

    def get_user_home(self):
        """Returns current user's home directory."""
        return os.environ['HOME']

    def reset_cl_args(self, values=[]):
        """Replaces command-line arguments with new ones.

        Useful for testing program's command-line options.
        """
        sys.argv = values

    def set_user_home(self, path):
        """Set home directory of current user."""
        os.environ['HOME'] = path

    def set_user_home_tmp(self):
        """Set temporary directory as current user's home."""
        self.set_user_home(make_tempdir())

    def catch_output(self, func):
        stdout = sys.stdout
        outbuf = StringIO()
        sys.stdout = outbuf
        func()
        sys.stdout = stdout
        return outbuf.getvalue()

    @contextlib.contextmanager
    def reviewboardrc(self, data, use_temp_dir=False):
        """Manage a temporary .reviewboardrc file.

        Args:
            data (dict)
                A dictionary of key-value pairs to write into the
                .reviewboardrc file.

                A best effort attempt will be made to convert the value into
                an appropriate string.

            use_temp_dir (boolean)
                A boolean that indicates if a temporary directory should be
                created and used as the working directory for the context.
        """
        if use_temp_dir:
            temp_dir = tempfile.mkdtemp()
            cwd = os.getcwd()
            os.chdir(temp_dir)

        with open('.reviewboardrc', 'w') as fp:
            for key, value in six.iteritems(data):
                fp.write('%s = %r\n' % (key, value))

        try:
            yield
        finally:
            if use_temp_dir:
                os.chdir(cwd)
                shutil.rmtree(temp_dir)
