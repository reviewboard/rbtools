import cookielib
import difflib
import getpass
import marshal
import mimetools
import ntpath
import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
import urllib
import urllib2

from optparse import OptionParser
from tempfile import mkstemp
from urlparse import urljoin, urlparse

import Repository

class RBUtilities(object):
    """A collection of utility functions

    A Utility class that performs such tasks as finding out environment
    information, making system calls, and raising warnings and errors
    """

    ERR_NO = 1

    log_file = None

    def __init__(self, log_file='rbproblems.log'):

        self.log_file = log_file

    def get_repository(self, url=None, repo_types=['svn', 'cvs', 'git', \
                        'hg', 'perforce', 'clearcase'], additional_repos=[]):
        """Returns the repository
        
        TODO make this not suck
        
        Using a list of repositories provided by the user, attempts to find
        the type of repository being used by the user
        """

        if not url:
            self.raise_error("missingRequiredParameter", \
                    "get_repository requires url to be passed as a parameter")

        possible_repos = additional_repos

        #TODO: use a dictionary
        """HINT on how
        It would be better to have a lookup map somewhere outside the function, like:

        repository_types = {
            'svn': Repository.SVNRepository,
            'cvs': Repository.CVSRepository,
        }

        Then you can do:

        if type in repository_types:
            possible_repos.append(repository_types[tpe](url, self))
        else:
            self.raise_warning(...)
        """
        for type in repo_types:
            type = type.lower()

            if type == 'svn':
                possible_repos.append(Repository.SVNRepository(url, self))
            elif type == 'cvs':
                possible_repos.append(Repository.CVSRepository(url, self))
            elif type == 'git':
                possible_repos.append(Repository.GitRepository(url, self))
            elif type == 'hg' or type == 'mercurial':
                possible_repos.append(Repository.MercurialRepository(url, \
                                                                    self))
            elif type == 'perforce':
                possible_repos.append(Repository.PerforceRepository(url, \
                                                                    self))
            elif type == 'clearcase' or type == 'clear case':
                possible_repos.append(Repository.ClearCaseRepository(url, \
                                                                    self))
            else:
                self.raise_warning("UnreckognizedType", type + "is not a \
recognized type. If it is a Repository type, create it yourself and pass it \
in using additional_repos")

        repo = None

        for rep in possible_repos:

            if rep.get_info():
                repo = rep
                break

        return repo

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

 #       if isinstance(command, list):
 #           debug(subprocess.list2cmdline(command))
 #       else:
 #           debug(command)

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

    def check_gnu_diff():
        """
        Checks if GNU diff is installed, and informs the user if it's not.
        """
        has_gnu_diff = False

        try:
            result = execute(['diff', '--version'], ignore_errors=True)
            has_gnu_diff = 'GNU diffutils' in result
        except OSError:
            pass

        if not has_gnu_diff:
            sys.stderr.write('\n')
            sys.stderr.write('GNU diff is required for Subversion '
                             'repositories. Make sure it is installed\n')
            sys.stderr.write('and in the path.\n')
            sys.stderr.write('\n')

            if os.name == 'nt':
                sys.stderr.write('On Windows, you can install this from:\n')
                sys.stderr.write(GNU_DIFF_WIN32_URL)
                sys.stderr.write('\n')

            self.die()

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

    def raise_error(self, errorType='UnknownErrorType', \
                          errorMessage='No message', logError=True):
        """Raises an error
        
        In the base implementation, this logs the error, prints it using
        output, and then exits
        """

        self.output('Error-' + errorType + ': ' + errorMessage)

        if logError:
            file = open(self.log_file, 'a')

            if not file:
                self.output('Further Error, could not open logfile (located \
at "' + self.log_file + '").')

            file.write('Error,' + errorType + ',' + errorMessage)

            file.close()

        exit(self.ERR_NO)

    def raise_warning(self, warningType='UnknownWarningType', \
                            warningMessage='No message', logWarning=True):
        """Raises a warning
        
        In this base implementation, this logs the warning, and prints it
        using output. This function only differs from raise_error by the
        fact that raise_warning does not exit afterwardl
        """

        self.output('Warning-' + warningType + ': ' + warningMessage)

        if logWarning:
            file = open(self.log_file, 'a')

            if not file:
                self.output('Error, could not open logfile (located at "' + \
                                                    self.log_file + '").')
                exit(ERR_NO)

            file.write('Error,' + warningType + ',' + warningMessage)
            file.close()
