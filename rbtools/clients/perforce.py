"""A client for Perforce."""

import io
import logging
import marshal
import os
import re
import socket
import stat
import string
import subprocess
import sys
from fnmatch import fnmatch
from typing import List, Optional, Tuple, Union

from rbtools.clients import RepositoryInfo
from rbtools.clients.base.scmclient import (BaseSCMClient,
                                            SCMClientDiffResult,
                                            SCMClientRevisionSpec)
from rbtools.clients.errors import (AmendError,
                                    EmptyChangeError,
                                    InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    SCMError,
                                    TooManyRevisionsError)
from rbtools.deprecation import (RemovedInRBTools50Warning,
                                 deprecate_non_keyword_only_args)
from rbtools.diffs.tools.base.diff_tool import BaseDiffTool
from rbtools.diffs.writers import UnifiedDiffWriter
from rbtools.utils.checks import check_install
from rbtools.utils.encoding import force_unicode
from rbtools.utils.filesystem import make_empty_files, make_tempfile
from rbtools.utils.process import execute


class P4Wrapper(object):
    """A wrapper around p4 commands.

    All calls out to p4 go through an instance of this class. It keeps a
    separation between all the standard SCMClient logic and any parsing
    and handling of p4 invocation and results.
    """

    KEYVAL_RE = re.compile('^([^:]+): (.+)$')
    COUNTERS_RE = re.compile('^([^ ]+) = (.+)$')

    def __init__(self, options):
        """Initialize the wrapper.

        Args:
            options (argparse.Namespace):
                The parsed command line options.
        """
        self.options = options

    def check_dependencies(self) -> None:
        """Check whether all base dependencies are available.

        This checks for the presence of :command:`p4` in the system path.

        Version Added:
            4.0:

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                A :command:`p4` tool could not be found.
        """
        if not self.is_supported():
            raise SCMClientDependencyError(missing_exes=['p4'])

    def is_supported(self):
        """Check whether the p4 command is usable.

        Returns:
            bool:
            ``True`` if there's an executable p4.
        """
        return check_install(['p4', 'help'])

    def counters(self):
        """Return the Perforce counters.

        Returns:
            dict:
            The parsed Perforce counters.
        """
        lines = self.run_p4(['counters'], split_lines=True)
        return self._parse_keyval_lines(lines, self.COUNTERS_RE)

    def change(self, changenum, marshalled=True):
        """Return the contents of a p4 change description.

        Args:
            changenum (int):
                The number of the changeset to list.

            marshalled (bool, optional):
                Whether to return the data in marshalled form.

        Returns:
            object:
            The contents of the change description, either as a unicode
            object or a list depending on the value of ``marshalled``.
        """
        return self.run_p4(['change', '-o', str(changenum)],
                           none_on_ignored_error=True,
                           marshalled=marshalled)

    def modify_change(
        self,
        new_change_spec: str,
        *,
        changenum: Optional[str] = None,
    ) -> None:
        """Modify a change description.

        Args:
            new_change_spec (unicode):
                The new changeset description. This must contain the changelist
                number.
        """
        args: List[str] = ['change', '-i']

        if changenum is not None:
            args.append(changenum)

        self.run_p4(args, input_string=new_change_spec)

    def files(self, path):
        """Return the opened files within the given path.

        Args:
            path (unicode):
                The Perforce path to check. This can be a mix of file paths
                (``//...``) and revisions (``...@X``).

        Returns:
            list:
            A list of the opened files.
        """
        return self.run_p4(['files', path], marshalled=True)

    def filelog(self, path):
        """Return a list of all the changed files within the given path.

        Args:
            path (unicode):
                The Perforce path to check. This is expected to be a path with
                two revision markers (``//...@X,Y``).

        Returns:
            list:
            A list of the various changed files and how they were changed.
        """
        return self.run_p4(['filelog', path], marshalled=True)

    def fstat(self, depot_path, fields=[]):
        """Run p4 fstat on a given depot path.

        Args:
            depot_path (unicode):
                The file path to stat.

            fields (list of unicode, optional):
                The fields to fetch.

        Returns:
            dict:
            The file stat info.
        """
        args = ['fstat']

        if fields:
            args += ['-T', ','.join(fields)]

        args.append(depot_path)

        lines = self.run_p4(args, split_lines=True)
        stat_info = {}

        for line in lines:
            line = line.strip()

            if line.startswith('... '):
                parts = line.split(' ', 2)
                stat_info[parts[1]] = parts[2]

        return stat_info

    def info(self):
        """Run p4 info and return the results.

        Returns:
            dict:
                The parsed output from :command:`p4 info`.
        """
        lines = self.run_p4(['info'],
                            ignore_errors=True,
                            split_lines=True)

        return self._parse_keyval_lines(lines)

    def opened(self, changenum):
        """Return the list of opened files in the given changeset.

        Args:
            changenum (int):
                The number of the changeset.

        Returns:
            list:
            A list of the opened files in the given changeset.
        """
        return self.run_p4(['opened', '-c', str(changenum)],
                           marshalled=True)

    def print_file(self, depot_path, out_file=None):
        """Print the contents of the given file.

        Args:
            depot_path (unicode):
                A Perforce path, including filename and revision.

            out_files (unicode, optional):
                A filename to write to. If not specified, the data will be
                returned.

        Returns:
            unicode:
            The output of the print operation.
        """
        cmd = ['print']

        if out_file:
            cmd += ['-o', out_file]

        cmd += ['-q', depot_path]

        return self.run_p4(cmd)

    def where(self, depot_path):
        """Return the local path for a depot path.

        Args:
            depot_path (unicode):
                A Perforce path to a file in the depot.

        Returns:
            list:
            A marshalled representation of the data showing where the file
            exists in the local client.
        """
        return self.run_p4(['where', depot_path], marshalled=True)

    def run_p4(self, p4_args, marshalled=False, ignore_errors=False,
               input_string=None, *args, **kwargs):
        """Invoke p4.

        In the current implementation, the arguments 'marshalled' and
        'input_string' cannot be used together, i.e. this command doesn't
        allow inputting and outputting at the same time.

        Args:
            p4_args (list):
                Additional arguments to pass to :command:`p4`.

            marshalled (bool, optional):
                Whether to return the data in marshalled format. This will
                return a more computer-readable version.

            ignore_errors (bool, optional):
                Whether to ignore return codes that typically indicate error
                conditions.

            input_string (unicode, optional):
                A string to pass to :command:`p4` on stdin.

            *args (list):
                Additional arguments to pass through to
                :py:func:`rbtools.utils.process.execute`.


            **kwargs (dict):
                Additional keyword arguments to pass through to
                :py:func:`rbtools.utils.process.execute`.

        Returns:
            object:
            If passing ``marshalled=True``, then this will be a list of
            dictionaries containing results from the command.

            If passing ``input_string``, this will always return ``None``.

            In all other cases, this will return the result of
            :py:func:`~rbtools.utils.process.execute`, depending on the
            arguments provided.

        Raises:
            rbtools.clients.errors.SCMError:
                There was an error with the call to Perforce. Details are in
                the error message.
        """
        cmd = ['p4']

        if marshalled:
            cmd += ['-G']

        if getattr(self.options, 'p4_client', None):
            cmd += ['-c', self.options.p4_client]

        if getattr(self.options, 'p4_port', None):
            cmd += ['-p', self.options.p4_port]

        if getattr(self.options, 'p4_passwd', None):
            cmd += ['-P', self.options.p4_passwd]

        cmd += p4_args

        if marshalled:
            logging.debug('Running: %s', subprocess.list2cmdline(cmd))
            p = subprocess.Popen(cmd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            result = []
            has_error = False

            while 1:
                try:
                    decoded_data = marshal.load(p.stdout)
                except EOFError:
                    break
                else:
                    # According to the Perforce documentation, we should always
                    # expect the decoded data to come back as a dictionary.
                    # Let's double-check this.
                    if not isinstance(decoded_data, dict):
                        logging.debug('Unexpected decoded data from Perforce '
                                      'command: %r',
                                      decoded_data)
                        raise SCMError('Expected a dictionary from Perforce, '
                                       'but got back a %s instead. Please '
                                       'file a bug about this.'
                                       % type(decoded_data))

                    # The dictionary data should consist of byte strings.
                    # We need to convert these over to Unicode.
                    data = {}

                    for key, value in decoded_data.items():
                        key = force_unicode(key)

                        # Values are typically strings, but error payloads
                        # contain integers as well.
                        if isinstance(value, bytes):
                            value = force_unicode(value)

                        data[key] = value

                    result.append(data)

                    if data.get('code') == 'error':
                        has_error = True

            rc = p.wait()

            try:
                stderr = p.stderr.read()
            except Exception as e:
                stderr = '<stderr exception: %r>' % e

            logging.debug('Command results = %r; stderr=%r',
                          result, stderr)

            if not ignore_errors and (rc or has_error):
                for record in result:
                    if 'data' in record:
                        print(record['data'])

                raise SCMError(
                    'Failed to execute command `%s`; payload=%r, stderr=%r'
                    % (subprocess.list2cmdline(cmd), result, stderr))

            return result
        elif input_string is not None:
            if not isinstance(input_string, bytes):
                input_string = input_string.encode('utf8')

            p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)

            try:
                stdout, stderr = p.communicate(input_string, timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
                stdout, stderr = p.communicate()

            if not ignore_errors and p.returncode != 0:
                raise SCMError('Failed to execute command: %s; stdout=%r; '
                               'stderr=%r'
                               % (cmd, stdout, stderr))

            return None
        else:
            result = execute(cmd, ignore_errors=ignore_errors, *args, **kwargs)

        return result

    def _parse_keyval_lines(self, lines, regex=KEYVAL_RE):
        """Parse a set of key:value lines into a dictionary.

        Args:
            lines (list of unicode):
                The set of lines to parse.

            regex (re.RegexObject, optional):
                A regular expression to use to parse each line.

        Returns:
            dict:
            The parsed key/value pairs.
        """
        keyvals = {}

        for line in lines:
            m = regex.match(line)

            if m:
                key = m.groups()[0]
                value = m.groups()[1]
                keyvals[key] = value.strip()

        return keyvals


class PerforceClient(BaseSCMClient):
    """A client for Perforce.

    This is a wrapper around the :command:`p4` executable that fetches
    repository information and generates compatible diffs.
    """

    scmclient_id = 'perforce'
    name = 'Perforce'
    server_tool_names = 'Perforce'

    requires_diff_tool = True

    can_amend_commit = True
    supports_changesets = True
    supports_diff_exclude_patterns = True
    supports_diff_extra_args = True
    supports_patch_revert = True

    DATE_RE = re.compile(br'(\w+)\s+(\w+)\s+(\d+)\s+(\d\d:\d\d:\d\d)\s+'
                         br'(\d\d\d\d)')
    ENCODED_COUNTER_URL_RE = re.compile(r'reviewboard.url\.(\S+)')

    REVISION_CURRENT_SYNC = '--rbtools-current-sync'
    REVISION_PENDING_CLN_PREFIX = '--rbtools-pending-cln:'
    REVISION_DEFAULT_CLN = 'default'

    ADDED_FILES_RE = re.compile(r'^==== //depot/(\S+)#\d+ ==A== \S+ ====$',
                                re.M)
    DELETED_FILES_RE = re.compile(r'^==== //depot/(\S+)#\d+ ==D== \S+ ====$',
                                  re.M)

    def __init__(self, p4_class=P4Wrapper, **kwargs):
        """Initialize the client.

        Args:
            p4_class (type, optional):
                The class type to use for the wrapper.

            **kwargs (dict):
                Keyword arguments to pass through to the superclass.
        """
        super(PerforceClient, self).__init__(**kwargs)
        self.p4 = p4_class(self.options)
        self._p4_info = None

    def check_dependencies(self) -> None:
        """Check whether all base dependencies are available.

        This checks for the presence of :command:`p4` in the system path.

        Version Added:
            4.0

        Raises:
            rbtools.clients.errors.SCMClientDependencyError:
                A :command:`hg` tool could not be found.
        """
        self.p4.check_dependencies()

    def get_local_path(self) -> Optional[str]:
        """Return the local path to the working tree.

        Returns:
            str:
            The filesystem path of the repository on the client system.
        """
        # NOTE: This can be removed once check_dependencies() is mandatory.
        if not self.has_dependencies(expect_checked=True):
            logging.debug('Unable to execute "p4 help": skipping Perforce')
            return None

        if self._p4_info is None:
            self._p4_info = self.p4.info()

        # Get the client root and see if we're currently within that root.
        # Since `p4 info` can return a result when we're nowhere near the
        # checkout directory, we need to do this in order to ensure we're not
        # going to be trying to build diffs in the wrong place.
        client_root = self._p4_info.get('Client root')

        # A 'null' client root is a valid configuration on Windows client,
        # so don't enforce the repository directory check.
        if (client_root and (client_root.lower() != 'null' or
                             not sys.platform.startswith('win'))):
            norm_cwd = os.path.normcase(os.path.realpath(os.getcwd()) +
                                        os.path.sep)
            local_path = os.path.normcase(os.path.realpath(client_root) +
                                          os.path.sep)

            # Only accept the repository if the current directory is inside
            # the root of the Perforce client.
            if norm_cwd.startswith(local_path):
                return local_path

        return None

    def get_repository_info(self) -> Optional[RepositoryInfo]:
        """Return repository information for the current working tree.

        Returns:
            rbtools.clients.base.repository.RepositoryInfo:
            The repository info structure.
        """
        local_path = self.get_local_path()

        if not local_path:
            return None

        p4_info = self._p4_info
        assert p4_info is not None

        # Check the server address. If we don't get something we expect here,
        # we'll want to bail early.
        server_version = p4_info.get('Server version')

        if not server_version:
            return None

        m = re.search(r'[^ ]*/([0-9]+)\.([0-9]+)/[0-9]+ .*$',
                      server_version, re.M)

        if not m:
            # Gracefully bail if we don't get a match.
            return None

        self.p4d_version = int(m.group(1)), int(m.group(2))

        # For the repository path, we first prefer p4 brokers, then the
        # upstream p4 server. If neither of those are found, just return None.
        server_address = p4_info.get('Broker address')

        if server_address:
            # We're connecting to a broker.
            encryption_state = p4_info.get('Broker encryption')
        else:
            # We're connecting directly to a server.
            server_address = p4_info.get('Server address')
            encryption_state = p4_info.get('Server encryption')

        if server_address is None:
            return None

        use_ssl = (encryption_state == 'encrypted')

        # Validate the repository path we got above to see if it's something
        # that makes sense.
        parts = server_address.split(':')
        hostname: Optional[str] = None
        port: Optional[str] = None

        if len(parts) == 3 and parts[0] == 'ssl':
            hostname = parts[1]
            port = parts[2]

            # We should have known above that SSL was an option, but in case,
            # force it here.
            use_ssl = True
        elif len(parts) == 2:
            hostname, port = parts

        if not hostname or not port:
            raise SCMError('Path %s is not a valid Perforce P4PORT'
                           % server_address)

        # Begin building the list of repository paths we want to try to look
        # up. We'll start with the parsed hostname, and then grab any aliases
        # (if we can).
        servers = [hostname]

        try:
            info = socket.gethostbyaddr(hostname)

            if info[0] != hostname:
                servers.append(info[0])

            if info[1]:
                servers += info[1]
        except (socket.gaierror, socket.herror):
            # We couldn't resolve it. This might be a temporary error, or
            # a network disconnect, or it might just be a unit test.
            pass

        # Build the final list of repository paths.
        repository_paths: List[str] = []

        for server in servers:
            repository_path = '%s:%s' % (server, port)

            # Prioritize SSL-based addresses.
            if use_ssl:
                repository_paths.append('ssl:%s' % repository_path)

            repository_paths.append(repository_path)

        # If there's only one repository path found, just simplify this to
        # a string. This doesn't have any impact on performance these days,
        # but the result is more consistent with other SCMs.
        if len(repository_paths) == 1:
            return RepositoryInfo(path=repository_paths[0],
                                  local_path=local_path)
        else:
            return RepositoryInfo(path=repository_paths,
                                  local_path=local_path)

    def get_repository_name(self):
        """Return any repository name configured in the repository.

        This is used as a fallback from the standard config options, for
        repository types that support configuring the name in repository
        metadata.

        Returns:
            unicode:
            The configured repository name, or None.
        """
        # Check if there's a counter available containing a repository name.
        counters = self.p4.counters()
        return counters.get('reviewboard.repository_name', None)

    def parse_revision_spec(
        self,
        revisions: List[str] = [],
    ) -> SCMClientRevisionSpec:
        """Parse the given revision spec.

        These will be used to generate the diffs to upload to Review Board
        (or print). The diff for review will include the changes in (base,
        tip].

        If zero revisions are passed in, this will return the current sync
        changelist as "tip", and the upstream branch as "base". The result
        may have special internal revisions or prefixes based on whether
        the changeset is submitted, pending, or shelved.

        If a single revision is passed in, this will return the parent of
        that revision for "base" and the passed-in revision for "tip".

        If two revisions are passed in, they need to both be submitted
        changesets.

        Args:
            revisions (list of str, optional):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use SCM-native syntaxes such as ``r1..r2`` or ``r1:r2``.
                SCMTool-specific overrides of this method are expected to deal
                with such syntaxes.

        Returns:
            dict:
            The parsed revision spec.

            See :py:class:`~rbtools.clients.base.scmclient.
            SCMClientRevisionSpec` for the format of this dictionary.

            This always populates the ``base`` and ``tip`` keys.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.
        """
        n_revs = len(revisions)

        if n_revs == 0:
            return {
                'base': self.REVISION_CURRENT_SYNC,
                'tip': (self.REVISION_PENDING_CLN_PREFIX +
                        self.REVISION_DEFAULT_CLN)
            }
        elif n_revs == 1:
            # A single specified CLN can be any of submitted, pending, or
            # shelved. These are stored with special prefixes and/or names
            # because the way that we get the contents of the files changes
            # based on which of these is in effect.
            status = self._get_changelist_status(revisions[0])

            # Both pending and shelved changes are treated as "pending",
            # through the same code path. This is because the documentation for
            # 'p4 change' tells a filthy lie, saying that shelved changes will
            # have their status listed as shelved. In fact, when you shelve
            # changes, it sticks the data up on the server, but leaves your
            # working copy intact, and the change is still marked as pending.
            # Even after reverting the working copy, the change won't have its
            # status as "shelved". That said, there's perhaps a way that it
            # could (perhaps from other clients?), so it's still handled in
            # this conditional.
            #
            # The diff routine will first look for opened files in the client,
            # and if that fails, it will then do the diff against the shelved
            # copy.
            if status in ('pending', 'shelved'):
                return {
                    'base': self.REVISION_CURRENT_SYNC,
                    'tip': self.REVISION_PENDING_CLN_PREFIX + revisions[0],
                }
            elif status == 'submitted':
                try:
                    cln = int(revisions[0])

                    return {
                        'base': str(cln - 1),
                        'tip': str(cln),
                    }
                except ValueError:
                    raise InvalidRevisionSpecError(
                        '%s does not appear to be a valid changelist' %
                        revisions[0])
            else:
                raise InvalidRevisionSpecError(
                    '%s does not appear to be a valid changelist' %
                    revisions[0])
        elif n_revs == 2:
            # The base revision must be a submitted CLN.
            status = self._get_changelist_status(revisions[0])

            if status in ('pending', 'shelved'):
                raise InvalidRevisionSpecError(
                    '%s cannot be used as the base CLN for a diff because '
                    'it is %s.' % (revisions[0], status))
            elif status != 'submitted':
                raise InvalidRevisionSpecError(
                    '%s does not appear to be a valid changelist' %
                    revisions[0])

            # Tip revision can be any of submitted, pending, or shelved CLNs.
            status = self._get_changelist_status(revisions[1])

            if status in ('pending', 'shelved'):
                raise InvalidRevisionSpecError(
                    '%s cannot be used for a revision range diff because it '
                    'is %s' % (revisions[1], status))
            elif status != 'submitted':
                raise InvalidRevisionSpecError(
                    '%s does not appear to be a valid changelist' %
                    revisions[1])

            return {
                'base': revisions[0],
                'tip': revisions[1],
            }
        else:
            raise TooManyRevisionsError

    def _get_changelist_status(self, changelist):
        """Return the status of a changelist.

        Args:
            changelist (int):
                The changelist to check.

        Returns:
            unicode:
            The current status of the changelist (such as "pending" or
            "submitted").
        """
        if changelist == self.REVISION_DEFAULT_CLN:
            return 'pending'
        else:
            change = self.p4.change(changelist)
            if len(change) == 1 and 'Status' in change[0]:
                return change[0]['Status']

        return None

    def scan_for_server(self, repository_info):
        """Find if a Review Board server has been defined in the p4 counters.

        This checks the Perforce counters to see if the Review Board server's
        URL is specified. Since Perforce only started supporting non-numeric
        counter values in server version 2008.1, we support both a normal
        counter ``reviewboard.url`` with a string value and embedding the URL
        in a counter name like
        ``reviewboard.url.http:||reviewboard.example.com``. Note that forward
        slashes aren't allowed in counter names, so pipe ('|') characters
        should be used. These should be safe because they should not be used
        unencoded in URLs.


        Args:
            repository_info (rbtools.clients.base.repository.RepositoryInfo):
                The repository information structure.

        Returns:
            unicode:
            The Review Board server URL, if available.
        """
        counters = self.p4.counters()

        # Try for a "reviewboard.url" counter first.
        url = counters.get('reviewboard.url', None)

        if url:
            return url

        # Next try for a counter of the form:
        # reviewboard_url.http:||reviewboard.example.com
        for key, value in counters.items():
            m = self.ENCODED_COUNTER_URL_RE.match(key)

            if m:
                return m.group(1).replace('|', '/')

        return None

    @deprecate_non_keyword_only_args(RemovedInRBTools50Warning)
    def diff(
        self,
        revisions: SCMClientRevisionSpec,
        *,
        include_files: List[str] = [],
        exclude_patterns: List[str] = [],
        extra_args: List[str] = [],
        **kwargs,
    ) -> SCMClientDiffResult:
        """Perform a diff using the given revisions.

        This goes through the hard work of generating a diff on Perforce in
        order to take into account adds/deletes and to provide the necessary
        revision information.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            include_files (list of unicode, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of unicode, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

            extra_args (list, unused):
                Additional arguments to be passed to the diff generation.
                Unused for git.

            **kwargs (dict, unused):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.

            ``changenum`` (:py:class:`unicode`):
                The number of the changeset being posted (if ``revisions``
                represents a single changeset).
        """
        diff_tool = self.get_diff_tool()
        assert diff_tool is not None

        exclude_patterns = self.normalize_exclude_patterns(exclude_patterns)

        if not revisions:
            # The "path posting" is still interesting enough to keep around. If
            # the given arguments don't parse as valid changelists, fall back
            # on that behavior.
            return self._path_diff(diff_tool=diff_tool,
                                   args=extra_args,
                                   exclude_patterns=exclude_patterns)

        # Support both //depot/... paths and local filenames. For the moment,
        # this does *not* support any of Perforce's traversal literals like ...
        depot_include_files = []
        local_include_files = []
        for filename in include_files:
            if filename.startswith('//'):
                depot_include_files.append(filename)
            else:
                # The way we determine files to include or not is via
                # 'p4 where', which gives us absolute paths.
                local_include_files.append(
                    os.path.realpath(os.path.abspath(filename)))

        base = revisions['base']
        tip = revisions['tip']

        assert isinstance(base, str)
        assert isinstance(tip, str)

        stream = io.BytesIO()
        diff_writer = UnifiedDiffWriter(stream)

        cl_is_pending = tip.startswith(self.REVISION_PENDING_CLN_PREFIX)
        cl_is_shelved = False

        if not cl_is_pending:
            # Submitted changes are handled by a different method
            logging.info('Generating diff for range of submitted changes: %s '
                         'to %s',
                         base, tip)
            self._compute_range_changes(
                diff_tool=diff_tool,
                diff_writer=diff_writer,
                base=base,
                tip=tip,
                depot_include_files=depot_include_files,
                local_include_files=local_include_files,
                exclude_patterns=exclude_patterns)

            return {
                'diff': stream.getvalue(),
            }

        # Strip off the prefix
        tip = tip.split(':', 1)[1]

        # Try to get the files out of the working directory first. If that
        # doesn't work, look at shelved files.
        opened_files = self.p4.opened(tip)
        if not opened_files:
            opened_files = self.p4.files('//...@=%s' % tip)
            cl_is_shelved = True

        if not opened_files:
            raise EmptyChangeError

        if cl_is_shelved:
            logging.info('Generating diff for shelved changeset %s', tip)
        else:
            logging.info('Generating diff for pending changeset %s', tip)

        action_mapping = {
            'edit': 'M',
            'integrate': 'M',
            'add': 'A',
            'branch': 'A',
            'import': 'A',
            'delete': 'D',
        }

        # XXX: Theoretically, shelved files should handle moves just fine--you
        # can shelve and unshelve changes containing moves. Unfortunately,
        # there doesn't seem to be any way to match up the added and removed
        # files when the changeset is shelved, because none of the usual
        # methods (fstat, filelog) provide the source move information when the
        # changeset is shelved.
        if self._supports_moves() and not cl_is_shelved:
            action_mapping['move/add'] = 'MV-a'
            action_mapping['move/delete'] = 'MV'
        else:
            # The Review Board server doesn't support moved files for
            # Perforce--create a diff that shows moved files as adds and
            # deletes.
            action_mapping['move/add'] = 'A'
            action_mapping['move/delete'] = 'D'

        for f in opened_files:
            depot_file = f['depotFile']
            local_file = self._depot_to_local(depot_file)
            new_depot_file = ''

            try:
                base_revision = int(f['rev'])
            except ValueError:
                # For actions like deletes, there won't be any "current
                # revision". Just pass through whatever was there before.
                base_revision = f['rev']

            action = f['action']

            if ((depot_include_files and
                 depot_file not in depot_include_files) or
                (local_include_files and
                 local_file not in local_include_files) or
                self._should_exclude_file(local_file, depot_file,
                                          exclude_patterns)):
                continue

            old_file = ''
            new_file = ''

            logging.debug('Processing %s of %s', action, depot_file)

            try:
                changetype_short = action_mapping[action]
            except KeyError:
                raise SCMError('Unsupported action type "%s" for %s'
                               % (action, depot_file))

            if changetype_short == 'M':
                assert tip is not None

                try:
                    old_file, new_file = self._extract_edit_files(
                        depot_file=depot_file,
                        local_file=local_file,
                        rev_a=base_revision,
                        rev_b=tip,
                        cl_is_shelved=cl_is_shelved)
                except ValueError as e:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: %s', depot_file, e)

                    continue
            elif changetype_short == 'A':
                # Perforce has a charming quirk where the revision listed for
                # a file is '1' in both the first submitted revision, as well
                # as before it's added. On the Review Board side, when we parse
                # the diff, we'll check to see if that revision exists, but
                # that only works for pending changes. If the change is shelved
                # or submitted, revision 1 will exist, which causes the
                # displayed diff to contain revision 1 twice.
                #
                # Setting the revision in the diff file to be '0' will avoid
                # problems with patches that add files.
                base_revision = 0

                try:
                    old_file, new_file = self._extract_add_files(
                        depot_file=depot_file,
                        local_file=local_file,
                        revision=tip,
                        cl_is_shelved=cl_is_shelved,
                        cl_is_pending=cl_is_pending)
                except ValueError as e:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: %s', depot_file, e)

                    continue

                if os.path.islink(new_file):
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping symlink %s', new_file)

                    continue
            elif changetype_short == 'D':
                try:
                    old_file, new_file = self._extract_delete_files(
                        depot_file=depot_file,
                        revision=base_revision)
                except ValueError as e:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s#%s: %s',
                                        depot_file, base_revision, e)

                    continue
            elif changetype_short == 'MV-a':
                # The server supports move information. We ignore this
                # particular entry, and handle the moves within the equivalent
                # 'move/delete' entry.
                continue
            elif changetype_short == 'MV':
                try:
                    old_file, new_file, new_depot_file = \
                        self._extract_move_files(
                            old_depot_file=depot_file,
                            tip=tip,
                            base_revision=base_revision,
                            cl_is_shelved=cl_is_shelved)
                except ValueError as e:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: %s', depot_file, e)

                    continue

            self._do_diff(diff_tool=diff_tool,
                          diff_writer=diff_writer,
                          old_file=old_file,
                          new_file=new_file,
                          depot_file=depot_file,
                          base_revision=base_revision,
                          new_depot_file=new_depot_file,
                          changetype_short=changetype_short,
                          ignore_unmodified=True)

        return {
            'diff': stream.getvalue(),
            'changenum': self.get_changenum(revisions),
        }

    def get_changenum(self, revisions):
        """Return the change number for the given revisions.

        This is only used when the client is supposed to send a change number
        to the server (such as with Perforce).

        Args:
            revisions (dict):
                A revisions dictionary as returned by ``parse_revision_spec``.

        Returns:
            unicode:
            The change number to send to the Review Board server.
        """
        # This is used to report the change number to the Review Board server
        # when posting pending changesets. By reporting the change number, we
        # extract the changeset description server-side. Ideally we'd change
        # this to remove the server-side implementation and just implement
        # --guess-summary and --guess-description, but that would likely
        # create a lot of unhappy users.
        if revisions is not None:
            tip = revisions['tip']

            if tip.startswith(self.REVISION_PENDING_CLN_PREFIX):
                tip = tip[len(self.REVISION_PENDING_CLN_PREFIX):]
                if tip != self.REVISION_DEFAULT_CLN:
                    return tip

        return None

    def _compute_range_changes(
        self,
        diff_tool: BaseDiffTool,
        diff_writer: UnifiedDiffWriter,
        base: str,
        tip: str,
        depot_include_files: List[str],
        local_include_files: List[str],
        exclude_patterns: List[str],
    ) -> None:
        """Compute the changes across files given a revision range.

        This will look at the history of all changes within the given range and
        compute the full set of changes contained therein. Just looking at the
        two trees isn't enough, since files may have moved around and we want
        to include that information.

        Args:
            diff_tool (rbtools.diffs.tools.base.diff_tool.BaseDiffTool):
                The diff tool used to generate diffs.

            diff_writer (rbtools.diffs.writers.UnifiedDiffWriter):
                The writer used to write diff content.

            base (str):
                The base of the revision range.

            tip (str):
                The tip of the revision range.

            depot_include_files (list of str):
                A list of depot paths to whitelist during diff generation.

            local_include_files (list of str):
                A list of local filesystem paths to whitelist during diff
                generation.

            exclude_patterns (list of str):
                A list of shell-style glob patterns to blacklist during diff
                generation.
        """
        # Start by looking at the filelog to get a history of all the changes
        # within the changeset range. This processing step is done because in
        # marshalled mode, the filelog doesn't sort its entries at all, and can
        # also include duplicate information, especially when files have moved
        # around.
        changesets = {}

        # We expect to generate a diff for (base, tip], but filelog gives us
        # [base, tip]. Increment the base to avoid this.
        real_base = str(int(base) + 1)

        file_log = self.p4.filelog('//...@%s,%s' % (real_base, tip)) or []

        for file_entry in file_log:
            cid = 0
            while True:
                change_key = 'change%d' % cid
                if change_key not in file_entry:
                    break

                action = file_entry['action%d' % cid]
                depot_file = file_entry['depotFile']

                try:
                    cln = int(file_entry[change_key])
                except ValueError:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: unable to parse '
                                        'change number "%s"',
                                        depot_file, file_entry[change_key])

                    break

                if action == 'integrate':
                    action = 'edit'
                elif action == 'branch':
                    action = 'add'

                if action not in ('edit', 'add', 'delete',
                                  'move/add', 'move/delete'):
                    raise Exception('Unsupported action type "%s" for %s' %
                                    (action, depot_file))

                rev_key = 'rev%d' % cid

                try:
                    rev = int(file_entry[rev_key])
                except ValueError:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: unable to parse '
                                        'revision number "%s"',
                                        depot_file, file_entry[rev_key])

                    break

                change = {
                    'rev': rev,
                    'action': action,
                }

                if action == 'move/add':
                    change['oldFilename'] = file_entry['file0,%d' % cid]
                elif action == 'move/delete':
                    change['newFilename'] = file_entry['file1,%d' % cid]

                cid += 1

                changesets.setdefault(cln, {})[depot_file] = change

        # Now run through the changesets in order and compute a change journal
        # for each file.
        files = []

        for cln in sorted(changesets.keys()):
            changeset = changesets[cln]

            for depot_file, change in changeset.items():
                action = change['action']

                # Moves will be handled in the 'move/delete' entry
                if action == 'move/add':
                    continue

                file_entry = None
                for f in files:
                    if f['depotFile'] == depot_file:
                        file_entry = f
                        break

                if file_entry is None:
                    file_entry = {
                        'initialDepotFile': depot_file,
                        'initialRev': change['rev'],
                        'newFile': action == 'add',
                        'rev': change['rev'],
                        'action': 'none',
                    }
                    files.append(file_entry)

                self._accumulate_range_change(file_entry, change)

        if not files:
            raise EmptyChangeError

        # Now generate the diff
        supports_moves = self._supports_moves()

        for f in files:
            action = f['action']
            depot_file = f['depotFile']

            try:
                local_file = self._depot_to_local(depot_file)
            except SCMError:
                if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                    logging.warning('Could not find local filename for "%s"',
                                    depot_file)

                local_file = None

            rev = f['rev']
            initial_depot_file = f['initialDepotFile']
            initial_rev = f['initialRev']

            if ((depot_include_files and
                 depot_file not in depot_include_files) or
                (local_include_files and local_file and
                 local_file not in local_include_files) or
                self._should_exclude_file(local_file, depot_file,
                                          exclude_patterns)):
                continue

            if action == 'add':
                assert local_file is not None

                try:
                    old_file, new_file = self._extract_add_files(
                        depot_file=depot_file,
                        local_file=local_file,
                        revision=rev)
                except ValueError as e:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: %s', depot_file, e)

                    continue

                self._do_diff(diff_tool=diff_tool,
                              diff_writer=diff_writer,
                              old_file=old_file,
                              new_file=new_file,
                              depot_file=depot_file,
                              base_revision=0,
                              new_depot_file='',
                              changetype_short='A',
                              ignore_unmodified=True)
            elif action == 'delete':
                try:
                    old_file, new_file = self._extract_delete_files(
                        depot_file=initial_depot_file,
                        revision=initial_rev)
                except ValueError as e:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: %s', depot_file, e)

                    continue

                self._do_diff(diff_tool=diff_tool,
                              diff_writer=diff_writer,
                              old_file=old_file,
                              new_file=new_file,
                              depot_file=initial_depot_file,
                              base_revision=initial_rev,
                              new_depot_file=depot_file,
                              changetype_short='D',
                              ignore_unmodified=True)
            elif action == 'edit':
                assert local_file is not None

                try:
                    old_file, new_file = self._extract_edit_files(
                        depot_file=depot_file,
                        local_file=local_file,
                        rev_a=initial_rev,
                        rev_b=rev,
                        cl_is_submitted=True)
                except ValueError as e:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: %s', depot_file, e)

                    continue

                self._do_diff(diff_tool=diff_tool,
                              diff_writer=diff_writer,
                              old_file=old_file,
                              new_file=new_file,
                              depot_file=initial_depot_file,
                              base_revision=initial_rev,
                              new_depot_file=depot_file,
                              changetype_short='M',
                              ignore_unmodified=True)
            elif action == 'move':
                assert local_file is not None

                try:
                    old_file_a, new_file_a = self._extract_add_files(
                        depot_file=depot_file,
                        local_file=local_file,
                        revision=rev)
                    old_file_b, new_file_b = self._extract_delete_files(
                        depot_file=initial_depot_file,
                        revision=initial_rev)
                except ValueError as e:
                    if not self.config.get('SUPPRESS_CLIENT_WARNINGS', False):
                        logging.warning('Skipping file %s: %s', depot_file, e)

                    continue

                if supports_moves:
                    # Show the change as a move
                    self._do_diff(diff_tool=diff_tool,
                                  diff_writer=diff_writer,
                                  old_file=old_file_a,
                                  new_file=new_file_b,
                                  depot_file=initial_depot_file,
                                  base_revision=initial_rev,
                                  new_depot_file=depot_file,
                                  changetype_short='MV',
                                  ignore_unmodified=True)
                else:
                    # Show the change as add and delete
                    self._do_diff(diff_tool=diff_tool,
                                  diff_writer=diff_writer,
                                  old_file=old_file_a,
                                  new_file=new_file_a,
                                  depot_file=depot_file,
                                  base_revision=0,
                                  new_depot_file='',
                                  changetype_short='A',
                                  ignore_unmodified=True)
                    self._do_diff(diff_tool=diff_tool,
                                  diff_writer=diff_writer,
                                  old_file=old_file_b,
                                  new_file=new_file_b,
                                  depot_file=initial_depot_file,
                                  base_revision=initial_rev,
                                  new_depot_file=depot_file,
                                  changetype_short='D',
                                  ignore_unmodified=True)
            elif action == 'skip':
                continue
            else:
                # We should never get here. The results of
                # self._accumulate_range_change should never be anything other
                # than add, delete, move, or edit.
                assert False

    def _accumulate_range_change(self, file_entry, change):
        """Compute the effects of a given change on a given file.

        Args:
            file_entry (dict):
                A dictionary containing information about the accumulated state
                of the given file. The results of this method will write the
                data back out to this dict.

            change (dict):
                A dictionary containing information about the new change to be
                applied to the given file.
        """
        old_action = file_entry['action']
        current_action = change['action']

        if old_action == 'none':
            # This is the first entry for this file.
            new_action = current_action
            file_entry['depotFile'] = file_entry['initialDepotFile']

            # If the first action was an edit or a delete, then the initial
            # revision (that we'll use to generate the diff) is n-1
            if current_action in ('edit', 'delete'):
                file_entry['initialRev'] -= 1
        elif current_action == 'add':
            # If we're adding a file that existed in the base changeset, it
            # means it was previously deleted and then added back. We
            # therefore want the operation to look like an edit. If it
            # didn't exist, then we added, deleted, and are now adding
            # again.
            if old_action == 'skip':
                new_action = 'add'
            else:
                new_action = 'edit'
        elif current_action == 'edit':
            # Edits don't affect the previous type of change
            # (edit+edit=edit, move+edit=move, add+edit=add).
            new_action = old_action
        elif current_action == 'delete':
            # If we're deleting a file which did not exist in the base
            # changeset, then we want to just skip it entirely (since it
            # means it's been added and then deleted). Otherwise, it's a
            # real delete.
            if file_entry['newFile']:
                new_action = 'skip'
            else:
                new_action = 'delete'
        elif current_action == 'move/delete':
            new_action = 'move'
            file_entry['depotFile'] = change['newFilename']

        file_entry['rev'] = change['rev']
        file_entry['action'] = new_action

    def _extract_edit_files(
        self,
        *,
        depot_file: str,
        local_file: str,
        rev_a: Union[int, str],
        rev_b: Union[int, str],
        cl_is_shelved: bool = False,
        cl_is_submitted: bool = False,
    ) -> Tuple[str, str]:
        """Extract the "old" and "new" files for an edit operation.

        Args:
            depot_file (str):
                The depot path of the file.

            local_file (str):
                The local filesystem path of the file.

            rev_a (int or str):
                The original revision of the file.

            rev_b (int or str):
                The new revision of the file.

            cl_is_shelved (bool, optional):
                Whether the containing changeset is shelved.

            cl_is_submitted (bool, optional):
                Whether the containing changeset is submitted.

        Returns:
            tuple:
            A 2-tuple containing:

            Tuple:
                0 (str):
                    The filename of the old version.

                1 (str):
                    The filename of the new version.

        Raises:
            ValueError:
                The file extraction failed.
        """
        # Get the old version out of Perforce
        old_filename = make_tempfile()
        self._write_file('%s#%s' % (depot_file, rev_a), old_filename)

        if cl_is_shelved:
            new_filename = make_tempfile()
            self._write_file('%s@=%s' % (depot_file, rev_b), new_filename)
        elif cl_is_submitted:
            new_filename = make_tempfile()
            self._write_file('%s#%s' % (depot_file, rev_b), new_filename)
        else:
            # Just reference the file within the client view
            new_filename = local_file

        return old_filename, new_filename

    def _extract_add_files(
        self,
        *,
        depot_file: str,
        local_file: str,
        revision: Union[int, str],
        cl_is_shelved: bool = False,
        cl_is_pending: bool = False,
    ) -> Tuple[str, str]:
        """Extract the "old" and "new" files for an add operation.

        Args:
            depot_file (str):
                The depot path of the file.

            local_file (str):
                The local filesystem path of the file.

            revision (int or str):
                The new revision of the file.

            cl_is_shelved (bool):
                Whether the containing changeset is shelved.

            cl_is_pending (bool):
                Whether the containing changeset is pending.

        Returns:
            tuple:
            A 2-tuple containing:

            Tuple:
                0 (str):
                    The filename of the old version.

                    Because this is an add operation, this will represent an
                    empty file.

                1 (str):
                    The filename of the new version.

        Raises:
            ValueError:
                The file extraction failed.
        """
        # Make an empty tempfile for the old file
        old_filename = make_tempfile()

        if cl_is_shelved:
            new_filename = make_tempfile()
            self._write_file('%s@=%s' % (depot_file, revision), new_filename)
        elif cl_is_pending:
            # Just reference the file within the client view
            new_filename = local_file
        else:
            new_filename = make_tempfile()
            self._write_file('%s#%s' % (depot_file, revision), new_filename)

        return old_filename, new_filename

    def _extract_delete_files(
        self,
        *,
        depot_file: str,
        revision: Union[int, str],
    ) -> Tuple[str, str]:
        """Extract the "old" and "new" files for a delete operation.

        Returns a tuple of (old filename, new filename). This can raise a
        ValueError if extraction fails.

        Args:
            depot_file (str):
                The depot path of the file.

            revision (int or str):
                The old revision of the file.

        Returns:
            tuple:
            A 2-tuple containing:

            Tuple:
                0 (str):
                    The filename of the old version.

                1 (str):
                    The filename of the new version.

                    Because this is a delete operation, this will represent an
                    empty file.

        Raises:
            ValueError:
                The file extraction failed.
        """
        # Get the old version out of Perforce
        old_filename = make_tempfile()
        self._write_file('%s#%s' % (depot_file, revision), old_filename)

        # Make an empty tempfile for the new file
        new_filename = make_tempfile()

        return old_filename, new_filename

    def _extract_move_files(
        self,
        *,
        old_depot_file: str,
        tip: Union[int, str],
        base_revision: Union[int, str],
        cl_is_shelved: bool = False,
    ) -> Tuple[str, str, str]:
        """Extract the "old" and "new" files for a move operation.

        Returns a tuple of (old filename, new filename, new depot path). This
        can raise a ValueError if extraction fails.

        Args:
            old_depot_file (str):
                The depot path of the old version of the file.

            tip (int or str):
                The new revision of the file.

            base_revision (int or str):
                The old revision of the file.

            cl_is_shelved (bool, optional):
                Whether the containing changeset is shelved.

        Returns:
            tuple:
            A 2-tuple containing:

            Tuple:
                0 (str):
                    The filename of the old version.

                    Because this is an add operation, this will represent an
                    empty file.

                1 (str):
                    The filename of the new version.

                2 (str):
                    The depot path of the new version.

        Raises:
            ValueError:
                The file extraction failed.
        """
        # XXX: fstat *ought* to work, but Perforce doesn't supply the movedFile
        # field in fstat (or apparently anywhere else) when a change is
        # shelved. For now, _diff_pending will avoid calling this method at all
        # for shelved changes, and instead treat them as deletes and adds.
        assert not cl_is_shelved

        # if cl_is_shelved:
        #     fstat_path = '%s@=%s' % (depot_file, tip)
        # else:
        fstat_path = old_depot_file

        stat_info = self.p4.fstat(fstat_path,
                                  ['clientFile', 'movedFile'])
        if 'clientFile' not in stat_info or 'movedFile' not in stat_info:
            raise ValueError('Unable to get moved file information')

        old_filename = make_tempfile()
        self._write_file('%s#%s' % (old_depot_file, base_revision),
                         old_filename)

        # if cl_is_shelved:
        #     fstat_path = '%s@=%s' % (stat_info['movedFile'], tip)
        # else:
        fstat_path = stat_info['movedFile']

        stat_info = self.p4.fstat(fstat_path,
                                  ['clientFile', 'depotFile'])
        if 'clientFile' not in stat_info or 'depotFile' not in stat_info:
            raise ValueError('Unable to get moved file information')

        # Grab the new depot path (to include in the diff index)
        new_depot_file = stat_info['depotFile']

        # Reference the new file directly in the client view
        new_filename = stat_info['clientFile']

        return old_filename, new_filename, new_depot_file

    def _path_diff(
        self,
        diff_tool: BaseDiffTool,
        args: List[str],
        exclude_patterns: List[str],
    ) -> SCMClientDiffResult:
        """Process a path-style diff.

        This allows people to post individual files in various ways.

        Args:
            diff_tool (rbtools.diffs.tools.base.diff_tool.BaseDiffTool):
                The diff tool being used to generate diffs.

            args (list of str):
                A list of paths to add. The path styles supported are:

                ``//path/to/file``:
                    Upload file as a "new" file.

                ``//path/to/dir/...``:
                    Upload all files as "new" files.

                ``//path/to/file[@#]rev``:
                    Upload file from that rev as a "new" file.

                ``//path/to/file[@#]rev,[@#]rev``:
                    Upload a diff between revs.

                ``//path/to/dir/...[@#]rev,[@#]rev``:
                    Upload a diff of all files between revs in that directory.

            exclude_patterns (list of str):
                A list of shell-style glob patterns to blacklist during diff
                generation.

        Returns:
            dict:
            A dictionary containing a ``diff`` key.
        """
        stream = io.BytesIO()
        diff_writer = UnifiedDiffWriter(stream)

        r_revision_range = re.compile(r'^(?P<path>//[^@#]+)' +
                                      r'(?P<revision1>[#@][^,]+)?' +
                                      r'(?P<revision2>,[#@][^,]+)?$')

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        for path in args:
            m = r_revision_range.match(path)

            if not m:
                raise SCMError('Path %s does not match a valid Perforce path.'
                               % path)
            revision1 = m.group('revision1')
            revision2 = m.group('revision2')
            first_rev_path = m.group('path')

            if revision1:
                first_rev_path += revision1
            records = self.p4.files(first_rev_path)

            # Make a map for convenience.
            files = {}

            # Records are:
            # 'rev': '1'
            # 'func': '...'
            # 'time': '1214418871'
            # 'action': 'edit'
            # 'type': 'ktext'
            # 'depotFile': '...'
            # 'change': '123456'
            for record in records:
                if record['action'] not in ('delete', 'move/delete'):
                    if revision2:
                        files[record['depotFile']] = [record, None]
                    else:
                        files[record['depotFile']] = [None, record]

            if revision2:
                # [1:] to skip the comma.
                second_rev_path = m.group('path') + revision2[1:]
                records = self.p4.files(second_rev_path)
                for record in records:
                    if record['action'] not in ('delete', 'move/delete'):
                        try:
                            m = files[record['depotFile']]
                            m[1] = record
                        except KeyError:
                            files[record['depotFile']] = [None, record]

            old_file = new_file = empty_filename
            changetype_short = None

            for depot_path, (first_record, second_record) in files.items():
                old_file = new_file = empty_filename
                if first_record is None:
                    new_path = '%s#%s' % (depot_path, second_record['rev'])
                    self._write_file(new_path, tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                    changetype_short = 'A'
                    base_revision = 0
                elif second_record is None:
                    old_path = '%s#%s' % (depot_path, first_record['rev'])
                    self._write_file(old_path, tmp_diff_from_filename)
                    old_file = tmp_diff_from_filename
                    changetype_short = 'D'
                    base_revision = int(first_record['rev'])
                elif first_record['rev'] == second_record['rev']:
                    # We when we know the revisions are the same, we don't need
                    # to do any diffing. This speeds up large revision-range
                    # diffs quite a bit.
                    continue
                else:
                    old_path = '%s#%s' % (depot_path, first_record['rev'])
                    new_path = '%s#%s' % (depot_path, second_record['rev'])
                    self._write_file(old_path, tmp_diff_from_filename)
                    self._write_file(new_path, tmp_diff_to_filename)
                    new_file = tmp_diff_to_filename
                    old_file = tmp_diff_from_filename
                    changetype_short = 'M'
                    base_revision = int(first_record['rev'])

                local_path = self._depot_to_local(depot_path)
                if self._should_exclude_file(local_path, depot_path,
                                             exclude_patterns):
                    continue

                # TODO: We're passing new_depot_file='' here just to make
                # things work like they did before the moved file change was
                # added (58ccae27). This section of code needs to be updated
                # to properly work with moved files.
                self._do_diff(diff_tool=diff_tool,
                              diff_writer=diff_writer,
                              old_file=old_file,
                              new_file=new_file,
                              depot_file=depot_path,
                              base_revision=base_revision,
                              new_depot_file='',
                              changetype_short=changetype_short,
                              ignore_unmodified=True)

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)

        return {
            'diff': stream.getvalue(),
        }

    def _do_diff(
        self,
        diff_tool: BaseDiffTool,
        diff_writer: UnifiedDiffWriter,
        old_file: str,
        new_file: str,
        depot_file: str,
        base_revision: int,
        new_depot_file: str,
        changetype_short: str,
        ignore_unmodified: bool = False,
    ) -> None:
        """Create a diff of a single file.

        Args:
            diff_tool (rbtools.diffs.tools.base.diff_tool.BaseDiffTool):
                The diff tool being used to generate diffs.

            old_file (str):
                The absolute path of the "old" file.

            new_file (str):
                The absolute path of the "new" file.

            depot_file (str):
                The depot path in Perforce for this file.

            base_revision (int):
                The base Perforce revision number of the old file.

            new_depot_file (str):
                The depot path in Perforce for the new location of this ifle.
                Only used if the file was moved.

            changetype_short (str):
                The change type provided by Perforce.

            ignore_unmodified (bool, optional):
                Whether to return an empty list if the file was not changed.
        """
        # Perform the diff on the files.
        diff_result = diff_tool.run_diff_file(orig_path=old_file,
                                              modified_path=new_file,
                                              show_hunk_context=True)

        cwd = os.getcwd()

        if depot_file.startswith(cwd):
            local_path = depot_file[len(cwd) + 1:]
        else:
            local_path = depot_file

        if changetype_short == 'MV':
            is_move = True

            if new_depot_file.startswith(cwd):
                new_local_path = new_depot_file[len(cwd) + 1:]
            else:
                new_local_path = new_depot_file
        else:
            is_move = False
            new_local_path = local_path

        if not diff_result.has_text_differences or diff_result.is_binary:
            is_empty_and_changed = (self.supports_empty_files() and
                                    changetype_short in ('A', 'D'))

            if ((not diff_result.has_text_differences and
                 (is_move or is_empty_and_changed)) or
                diff_result.is_binary):
                diff_writer.write_line(
                    '==== %s#%d ==%s== %s ===='
                    % (depot_file,
                       base_revision,
                       changetype_short,
                       new_local_path))
                diff_writer.write_diff_file_result_hunks(diff_result)
                diff_writer.write_line(b'')
            else:
                if ignore_unmodified:
                    return
                else:
                    print('Warning: %s in your changeset is unmodified' %
                          local_path)
        else:
            modified_header = diff_result.parsed_modified_file_header
            modified_header_extra: bytes
            timestamp: str = ''

            if modified_header:
                modified_header_extra = modified_header['extra']

                m = re.search(br'(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)',
                              modified_header_extra)

                if m:
                    timestamp = m.group(1).decode('utf-8')
                else:
                    # Thu Sep  3 11:24:48 2007
                    m = self.DATE_RE.search(modified_header_extra)

                    if m:
                        month_map = {
                            b'Jan': b'01',
                            b'Feb': b'02',
                            b'Mar': b'03',
                            b'Apr': b'04',
                            b'May': b'05',
                            b'Jun': b'06',
                            b'Jul': b'07',
                            b'Aug': b'08',
                            b'Sep': b'09',
                            b'Oct': b'10',
                            b'Nov': b'11',
                            b'Dec': b'12',
                        }
                        month = month_map[m.group(2)]
                        day = m.group(3)
                        timestamp_raw = m.group(4)
                        year = m.group(5)

                        timestamp = (
                            b'%s-%s-%s %s' % (year, month, day, timestamp_raw)
                        ).decode('utf-8')

            if not timestamp:
                raise SCMError('Unable to parse diff header: %s'
                               % diff_result.parsed_modified_file_header)

            if is_move:
                diff_writer.write_line('Moved from: %s' % depot_file)
                diff_writer.write_line('Moved to: %s' % new_depot_file)

            diff_writer.write_file_headers(
                orig_path=local_path,
                orig_extra='%s#%d' % (depot_file, base_revision),
                modified_path=new_local_path,
                modified_extra=timestamp)
            diff_writer.write_diff_file_result_hunks(diff_result)

    def _write_file(self, depot_path, tmpfile):
        """Grab a file from Perforce and writes it to a temp file.

        Args:
            depot_path (unicode):
                The depot path (including revision) of the file to write.

            tmpfile (unicode):
                The name of a temporary file to write to.
        """
        logging.debug('Writing "%s" to "%s"', depot_path, tmpfile)
        self.p4.print_file(depot_path, out_file=tmpfile)

        # The output of 'p4 print' will be a symlink if that's what version
        # control contains. There's a few reasons to skip these files...
        #
        # * Relative symlinks will likely be broken, causing an unexpected
        #   OSError.
        # * File that's symlinked to isn't necessarily in version control.
        # * Users expect that this will only process files under version
        #   control. If I can replace a file they opened with a symlink to
        #   private keys in '~/.ssh', then they'd probably be none too happy
        #   when rbt uses their credentials to publish its contents.

        if os.path.islink(tmpfile):
            raise ValueError('"%s" is a symlink' % depot_path)
        else:
            # p4 print sets the file readonly and that causes a later call to
            # unlink fail. Change permissions so we can delete it when we're
            # done.
            os.chmod(tmpfile, stat.S_IREAD | stat.S_IWRITE)

    def _depot_to_local(self, depot_path):
        """Convert a depot path to a local path.

        Given a path in the depot return the path on the local filesystem to
        the same file.  If there are multiple results, take only the last
        result from the where command.

        Args:
            depot_path (unicode):
                The path of a file within the Perforce depot.

        Returns:
            unicode:
            The location of that same file within the local client, if
            available.
        """
        where_output = self.p4.where(depot_path)

        try:
            return where_output[-1]['path']
        except KeyError:
            # XXX: This breaks on filenames with spaces.
            return where_output[-1]['data'].split(' ')[2].strip()

    def get_raw_commit_message(self, revisions):
        """Extract the commit message based on the provided revision range.

        Since local changelists in Perforce are not ordered with respect to
        one another, this implementation looks at only the tip revision.

        Args:
            revisions (dict):
                A dictionary containing ``base`` and ``tip`` keys.

        Returns:
            unicode:
            The commit messages of all commits between (base, tip].
        """
        changelist = revisions['tip']

        # The parsed revision spec may include a prefix indicating that it is
        # pending. This prefix, which is delimited by a colon, must be
        # stripped in order to run p4 change on the actual changelist number.
        if ':' in changelist:
            changelist = changelist.split(':', 1)[1]

        if changelist == self.REVISION_DEFAULT_CLN:
            # The default changelist has no description and couldn't be
            # accessed from p4 change anyway
            return ''

        logging.debug('Fetching description for changelist %s', changelist)
        change = self.p4.change(changelist)

        if len(change) == 1 and 'Description' in change[0]:
            return change[0]['Description']
        else:
            return ''

    def apply_patch_for_empty_files(self, patch, p_num, revert=False):
        """Return whether any empty files in the patch are applied.

        Args:
            patch (bytes):
                The contents of the patch.

            p_num (unicode):
                The prefix level of the diff.

            revert (bool, optional):
                Whether the patch should be reverted rather than applied.

        Returns:
            ``True`` if there are empty files in the patch. ``False`` if there
            were no empty files, or if an error occurred while applying the
            patch.
        """
        patched_empty_files = False

        if revert:
            added_files = self.DELETED_FILES_RE.findall(patch)
            deleted_files = self.ADDED_FILES_RE.findall(patch)
        else:
            added_files = self.ADDED_FILES_RE.findall(patch)
            deleted_files = self.DELETED_FILES_RE.findall(patch)

        # Prepend the root of the Perforce client to each file name.
        p4_info = self.p4.info()
        client_root = p4_info.get('Client root')
        added_files = ['%s/%s' % (client_root, f) for f in added_files]
        deleted_files = ['%s/%s' % (client_root, f) for f in deleted_files]

        if added_files:
            make_empty_files(added_files)
            result = execute(['p4', 'add'] + added_files, ignore_errors=True,
                             none_on_ignored_error=True)

            if result is None:
                logging.error('Unable to execute "p4 add" on: %s',
                              ', '.join(added_files))
            else:
                patched_empty_files = True

        if deleted_files:
            result = execute(['p4', 'delete'] + deleted_files,
                             ignore_errors=True, none_on_ignored_error=True)

            if result is None:
                logging.error('Unable to execute "p4 delete" on: %s',
                              ', '.join(deleted_files))
            else:
                patched_empty_files = True

        return patched_empty_files

    def _supports_moves(self):
        """Return whether the Review Board server supports moved files.

        Returns:
            bool:
            ``True`` if the Review Board server can support showing moves.
        """
        return (self.capabilities and
                self.capabilities.has_capability('scmtools', 'perforce',
                                                 'moved_files'))

    def _supports_empty_files(self):
        """Return whether the Review Board server supports empty files.

        Returns:
            bool:
            ``True`` if the Review Board server can support showing empty
            files.
        """
        return (self.capabilities and
                self.capabilities.has_capability('scmtools', 'perforce',
                                                 'empty_files'))

    def _should_exclude_file(self, local_file, depot_file, exclude_patterns):
        """Determine if a file should be excluded from a diff.

        Check if the file identified by (local_file, depot_file) should be
        excluded from the diff. If a pattern beings with '//', then it will be
        matched against the depot_file. Otherwise, it will be matched against
        the local file.

        Args:
            local_file (unicode):
                The local filename of the file.

            depot_file (unicode):
                The Perforce path of the file.

            exclude_patterns (list of unicode):
                A list of shell-style glob patterns to blacklist during diff
                generation. This is expected to have already been normalized.

        Returns:
            bool:
            ``True`` if the given file should be excluded.
        """
        for pattern in exclude_patterns:
            if pattern.startswith('//'):
                if fnmatch(depot_file, pattern):
                    return True
            elif local_file and fnmatch(local_file, pattern):
                return True

        return False

    def normalize_exclude_patterns(self, patterns):
        """Normalize the set of patterns so all non-depot paths are absolute.

        A path with a leading // is interpreted as a depot pattern and remains
        unchanged. A path with a leading path separator is interpreted as being
        relative to the Perforce client root. All other paths are interpreted
        as being relative to the current working directory. Non-depot paths are
        transformed into absolute paths.

        Args:
            patterns (list of unicode):
                A list of shell-style glob patterns to blacklist during diff
                generation.

        Returns:
            list of unicode:
            The normalized patterns.
        """
        cwd = os.getcwd()
        base_dir = self.p4.info().get('Client root')

        def normalize(p):
            if p.startswith('//'):
                # Absolute depot patterns remain unchanged.
                return p
            elif p.startswith(os.path.sep):
                # Patterns beginning with the operating system's path separator
                # are relative to the repository root.
                assert base_dir is not None
                p = os.path.join(base_dir, p[1:])
            else:
                # All other patterns are considered to be relative to the
                # current working directory.
                p = os.path.join(cwd, p)

            return os.path.normpath(p)

        return [normalize(pattern) for pattern in patterns]

    def _replace_changeset_description(
        self,
        old_spec: str,
        new_description: str,
    ) -> str:
        """Replace the description in the given changelist spec.

        Args:
            old_spec (str):
                The p4 changelist spec string (the raw output from p4 change).

            new_description (str):
                The new description text to use.

        Returns:
            str:
            The new changelist spec.
        """
        new_lines: List[str] = []
        key = 'Description:'
        skipping_to_next_field: bool = False

        for line in old_spec.splitlines(True):
            if skipping_to_next_field:
                # Ignore the content in the current field until we find another
                # key. We'll skip anything that starts with whitespace, which
                # would indicate content within the current field.
                if not line[0].isspace():
                    # There's content here, so we're in a field again.
                    # Mark it, and make sure to add a leading newline to
                    # separate this field from the previously-injected
                    # content.
                    skipping_to_next_field = False
                    new_lines.append(f'\n{line}')
            elif line.startswith(key):
                # Insert the new description. Don't include the first line
                # of the old one if it happens to be on the same line as
                # the key.
                new_lines.append(f'{key}\n')
                new_lines += [
                    f'\t{_line}\n'
                    for _line in new_description.splitlines()
                ]
                skipping_to_next_field = True
            else:
                new_lines.append(line)

        return ''.join(new_lines)

    def amend_commit_description(self, message, revisions):
        """Update a commit message to the given string.

        Since local changelists on Perforce have no ordering with respect to
        each other, the revisions argument is mandatory.

        Args:
            message (unicode):
                The commit message to use when amending the commit.

            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

        Raises:
            rbtools.clients.errors.AmendError:
                The given changelist could not be amended.
        """
        # Get the changelist number from the tip revision, removing the prefix
        # if necessary. Don't allow amending submitted or default changelists.
        changelist_id = revisions['tip']
        logging.debug('Preparing to amend change %s', changelist_id)

        if not changelist_id.startswith(self.REVISION_PENDING_CLN_PREFIX):
            raise AmendError('Cannot modify submitted changelist %s'
                             % changelist_id)

        changelist_num = changelist_id.split(':', 1)[1]

        if changelist_num == self.REVISION_DEFAULT_CLN:
            raise AmendError('Cannot modify the default changelist')
        elif not changelist_num.isdigit():
            raise AmendError('%s is an invalid changelist ID' % changelist_num)

        # Get the current changelist description and insert the new message.
        # Since p4 change -i doesn't take in marshalled objects, we get the
        # description as raw text and manually edit it.
        change = self.p4.change(changelist_num, marshalled=False)
        new_change = self._replace_changeset_description(change, message)

        self.p4.modify_change(new_change)
