import getpass
import logging
import os
import socket
import subprocess
import sys
import tempfile

from tempfile import mkstemp

from rbtools.clients.clearcase import ClearCaseClient
from rbtools.clients.client import Client
from rbtools.clients.cvs import CVSClient
from rbtools.clients.git import GitClient
from rbtools.clients.mercurial import MercurialClient
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.svn import SVNClient


class RBUtilities(object):
    """A collection of utility functions

    A Utility class that performs such tasks as finding out environment
    information, making system calls, and raising warnings and errors
    """

    CLIENTS = (
    SVNClient(),
    CVSClient(),
    GitClient(),
    MercurialClient(),
    PerforceClient(),
    ClearCaseClient(),
    )

    ERR_NO = 1

    def __init__(self, log_file='rbproblems.log', log_level=logging.DEBUG):
        logging.basicConfig(filename=log_file, level=log_level)

    def get_client(self, url=None, types=CLIENTS):
        """Returns the source control manager client

        Determines the correct type of repository being used (using a list
        of possible types) in order to pass the correct client back.
        """

        client = None
        info = None

        if not url:
            type = 'missingRequiredParameter'
            message = 'get_client requires a url to be passed as a parameter'
            self.raise_error(type, message)

        for client in CLIENTS:
            client.set_url(url)

            info = client.get_info()

            if info:
                break

        if not info:
            client = None

            if url:
                type = 'repositoryNotFound'
                message = 'No repository could be accessed at: ' + url
                self.raise_error(type, message)

    def make_tempfile(self):
        """
        Creates a temporary file and returns the path. The path is stored
        in an array for later cleanup.
        """

        fd, tmpfile = mkstemp()
        os.close(fd)
        tempfiles.append(tmpfile)
        return tmpfile

    def check_install(self, command):
        """
        Try executing an external command and return a boolean indicating
        whether that command is installed or not.  The 'command' argument
        should be something that executes quickly, without hitting the network
        (for instance, 'svn help' or 'git --version').
        """
        try:
            p = subprocess.Popen(command.split(' '),
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            return True
        except OSError:
            return False

    def execute(self, command, env=None, split_lines=False, \
        ignore_errors=False, extra_ignore_errors=(), translate_newlines=True):
        """
        Utility function to execute a command and return the output.
        """

        if isinstance(command, list):
            self.output(subprocess.list2cmdline(command))
        else:
            self.output(command)

        if env:
            env.update(os.environ)
        else:
            env = os.environ.copy()

        env['LC_ALL'] = 'en_US.UTF-8'
        env['LANGUAGE'] = 'en_US.UTF-8'

        if sys.platform.startswith('win'):
            p = subprocess.Popen(command,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 shell=False,
                                 universal_newlines=translate_newlines,
                                 env=env)
        else:
            p = subprocess.Popen(command,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 shell=False,
                                 close_fds=True,
                                 universal_newlines=translate_newlines,
                                 env=env)
        if split_lines:
            data = p.stdout.readlines()
        else:
            data = p.stdout.read()

        rc = p.wait()

        if rc and not ignore_errors and rc not in extra_ignore_errors:
            self.die('Failed to execute command: %s\n%s' % (command, data))

        return data

    def die(msg=None):
        """
        Cleanly exits the program with an error message. Erases all remaining
        temporary files.
        """

        for tmpfile in tempfiles:

            try:
                os.unlink(tmpfile)
            except:
                pass

        if msg:
            self.output(msg)

        sys.exit(1)

    def output(self, text=''):
        """Outputs text

        This base implementation merely using the print command
        """

        print text

    def input(self, text='', secure=False):
        """Inputs text

        This base implementation merely uses raw_input (and getpass for
        secure inputs
        """

        if secure:
            return getpass.getpass(text)
        else:
            return raw_input(text)

    def raise_error(self, type='UnknownErrorType', message='No message'):
        """Raises an error

        Logs an error using logging, and then exits
        """

        logging.error(type + ': ' + message)
        sys.stderr(type + ': ' + message)
        exit(self.ERR_NO)

    def raise_warning(self, type='UnknownWarningType', message='No message'):
        """Raises a warning

        Logs a warning using logging
        """
        logging.warning(type + ': ' + message)
        self.output(type + ': ' + message)
