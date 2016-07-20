from __future__ import unicode_literals

import os
import sys
import uuid

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
        self.set_user_home_tmp()

    def tearDown(self):
        os.chdir(self._old_cwd)
        cleanup_tempfiles()

    def create_tmp_dir(self):
        """Creates and returns a temporary directory."""
        return make_tempdir()

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

    def is_exe_in_path(self, name):
        """Checks whether an executable is in the user's search path.

        This expects a name without any system-specific executable extension.
        It will append the proper extension as necessary. For example,
        use "myapp" and not "myapp.exe".

        This will return True if the app is in the path, or False otherwise.

        Taken from djblets.util.filesystem to avoid an extra dependency
        """

        if sys.platform == 'win32' and not name.endswith('.exe'):
            name += '.exe'

        for dir in os.environ['PATH'].split(os.pathsep):
            if os.path.exists(os.path.join(dir, name)):
                return True

        return False

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
