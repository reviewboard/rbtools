import logging
import marshal
import os
import re
import socket
import stat
import subprocess

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    OptionsCheckError,
                                    TooManyRevisionsError)
from rbtools.utils.checks import check_gnu_diff, check_install
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import die, execute


class P4Wrapper(object):
    """A wrapper around p4 commands.

    All calls out to p4 go through an instance of this class. It keeps a
    separation between all the standard SCMClient logic and any parsing
    and handling of p4 invocation and results.
    """
    KEYVAL_RE = re.compile('^([^:]+): (.+)$')
    COUNTERS_RE = re.compile('^([^ ]+) = (.+)$')

    def is_supported(self):
        return check_install(['p4', 'help'])

    def counters(self):
        lines = self.run_p4(['counters'], split_lines=True)
        return self._parse_keyval_lines(lines, self.COUNTERS_RE)

    def change(self, changenum, password=None):
        return self.run_p4(['change', '-o', str(changenum)],
                           password=password, ignore_errors=True,
                           none_on_ignored_error=True,
                           marshalled=True)

    def files(self, path):
        return self.run_p4(['files', path], marshalled=True)

    def fstat(self, depot_path, fields=[]):
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
        lines = self.run_p4(['info'],
                            ignore_errors=True,
                            split_lines=True)

        return self._parse_keyval_lines(lines)

    def opened(self, changenum):
        return self.run_p4(['opened', '-c', str(changenum)],
                           marshalled=True)

    def print_file(self, depot_path, out_file=None):
        cmd = ['print']

        if out_file:
            cmd += ['-o', out_file]

        cmd += ['-q', depot_path]

        return self.run_p4(cmd)

    def where(self, depot_path):
        return self.run_p4(['where', depot_path], marshalled=True)

    def run_p4(self, p4_args, marshalled=False, password=None,
               *args, **kwargs):
        cmd = ['p4']

        if marshalled:
            cmd += ['-G']

        cmd += p4_args

        if password is not None:
            cmd += ['-P', password]

        if marshalled:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            result = []
            has_error = False

            while 1:
                try:
                    data = marshal.load(p.stdout)
                except EOFError:
                    break
                else:
                    result.append(data)
                    if data.get('code', None) == 'error':
                        has_error = True

            rc = p.wait()

            if rc or has_error:
                for record in result:
                    if 'data' in record:
                        print record['data']
                die('Failed to execute command: %s\n' % (cmd,))

            return result
        else:
            result = execute(cmd, *args, **kwargs)

        return result

    def _parse_keyval_lines(self, lines, regex=KEYVAL_RE):
        keyvals = {}

        for line in lines:
            m = regex.match(line)

            if m:
                key = m.groups()[0]
                value = m.groups()[1]
                keyvals[key] = value.strip()

        return keyvals


class PerforceClient(SCMClient):
    """
    A wrapper around the p4 Perforce tool that fetches repository information
    and generates compatible diffs.
    """
    name = 'Perforce'

    DATE_RE = re.compile(r'(\w+)\s+(\w+)\s+(\d+)\s+(\d\d:\d\d:\d\d)\s+'
                         '(\d\d\d\d)')
    ENCODED_COUNTER_URL_RE = re.compile('reviewboard.url\.(\S+)')

    REVISION_CURRENT_SYNC = '--rbtools-current-sync'
    REVISION_SHELVE_PARENT = '--rbtools-shelved-cln-parent'
    REVISION_SHELVED_CLN_PREFIX = '--rbtools-shelved-cln:'
    REVISION_PENDING_CLN_PREFIX = '--rbtools-pending-cln:'

    def __init__(self, p4_class=P4Wrapper, **kwargs):
        super(PerforceClient, self).__init__(**kwargs)
        self.p4 = p4_class()

    def get_repository_info(self):
        if not self.p4.is_supported():
            return None

        p4_info = self.p4.info()

        # For the repository path, we first prefer p4 brokers, then the
        # upstream p4 server. If neither of those are found, just return None.
        repository_path = p4_info.get('Broker address', None)

        if repository_path is None:
            repository_path = p4_info.get('Server address', None)

        if repository_path is None:
            return None

        try:
            parts = repository_path.split(':')
            hostname = None

            if len(parts) == 3 and parts[0] == 'ssl':
                hostname = parts[1]
                port = parts[2]
            elif len(parts) == 2:
                hostname, port = parts

            if not hostname:
                die('Path %s is not a valid Perforce P4PORT' % repository_path)

            info = socket.gethostbyaddr(hostname)

            # Build the list of repository paths we want to tr to look up.
            servers = [hostname]

            if info[0] != hostname:
                servers.append(info[0])

            # If aliases exist for hostname, create a list of alias:port
            # strings for repository_path.
            if info[1]:
                servers += info[1]

            repository_path = ["%s:%s" % (server, port)
                               for server in servers]

            # If there's only one repository path found, then we don't
            # need to do a more expensive lookup of all registered
            # paths. We can look up just this path directly.
            if len(repository_path) == 1:
                repository_path = repository_path[0]
        except (socket.gaierror, socket.herror):
            pass

        server_version = p4_info.get('Server version', None)

        if not server_version:
            return None

        m = re.search(r'[^ ]*/([0-9]+)\.([0-9]+)/[0-9]+ .*$',
                      server_version, re.M)
        if m:
            self.p4d_version = int(m.group(1)), int(m.group(2))
        else:
            # Gracefully bail if we don't get a match
            return None

        # Now that we know it's Perforce, make sure we have GNU diff
        # installed, and error out if we don't.
        check_gnu_diff()

        return RepositoryInfo(path=repository_path, supports_changesets=True)

    def parse_revision_spec(self, revisions=[]):
        """Parses the given revision spec.

        The 'revisions' argument is a list of revisions as specified by the
        user. Items in the list do not necessarily represent a single revision,
        since the user can use SCM-native syntaxes such as "r1..r2" or "r1:r2".
        SCMTool-specific overrides of this method are expected to deal with
        such syntaxes.

        This will return a dictionary with the following keys:
            'base':        A revision to use as the base of the resulting diff.
            'tip':         A revision to use as the tip of the resulting diff.

        These will be used to generate the diffs to upload to Review Board (or
        print). The diff for review will include the changes in (base, tip].

        If zero revisions are passed in, this will return the 'default'
        changelist.

        If a single revision is passed in, this will return the parent of that
        revision for 'base' and the passed-in revision for 'tip'. The result
        may have special internal revisions or prefixes based on whether the
        changeset is submitted, pending, or shelved.

        If two revisions are passed in, they need to both be submitted
        changesets.
        """
        n_revs = len(revisions)

        if n_revs == 0:
            return {
                'base': self.REVISION_CURRENT_SYNC,
                'tip': self.REVISION_PENDING_CLN_PREFIX + 'default',
            }
        elif n_revs == 1:
            # A single specified CLN can be any of submitted, pending, or
            # shelved. These are stored with special prefixes and/or names
            # because the way that we get the contents of the files changes
            # based on which of these is in effect.
            status = self._get_changelist_status(revisions[0])

            if status == 'pending':
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
            elif status == 'shelved':
                return {
                    'base': self.REVISION_SHELVE_PARENT,
                    'tip': self.REVISION_SHELVED_CLN_PREFIX + revisions[0],
                }
            else:
                raise InvalidRevisionSpecError(
                    '%s does not appear to be a valid changelist' %
                    revisions[0])
        elif n_revs == 2:
            result = {}

            # The base revision must be a submitted CLN
            status = self._get_changelist_status(revisions[0])
            if status == 'submitted':
                result['base'] = revisions[0]
            elif status in ('pending', 'shelved'):
                raise InvalidRevisionSpecError(
                    '%s cannot be used as the base CLN for a diff because '
                    'it is %s.' % (revisions[0], status))
            else:
                raise InvalidRevisionSpecError(
                    '%s does not appear to be a valid changelist' %
                    revisions[0])

            # Tip revision can be any of submitted, pending, or shelved CLNs
            status = self._get_changelist_status(revisions[1])
            if status == 'submitted':
                result['tip'] = revisions[1]
            elif status in ('pending', 'shelved'):
                raise InvalidRevisionSpecError(
                    '%s cannot be used for a revision range diff because it '
                    'is %s' % (revisions[1], status))
            else:
                raise InvalidRevisionSpecError(
                    '%s does not appear to be a valid changelist' %
                    revisions[1])

            return result
        else:
            raise TooManyRevisionsError

    def _get_changelist_status(self, changelist):
        if changelist == 'default':
            return 'pending'
        else:
            change = self.p4.change(changelist)
            assert len(change) == 1
            if 'Status' in change[0]:
                return change[0]['Status']

        return None

    def scan_for_server(self, repository_info):
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = \
            super(PerforceClient, self).scan_for_server(repository_info)

        if server_url:
            return server_url

        return self.scan_for_server_counter(repository_info)

    def scan_for_server_counter(self, repository_info):
        """
        Checks the Perforce counters to see if the Review Board server's url
        is specified. Since Perforce only started supporting non-numeric
        counter values in server version 2008.1, we support both a normal
        counter 'reviewboard.url' with a string value and embedding the url in
        a counter name like 'reviewboard.url.http:||reviewboard.example.com'.
        Note that forward slashes aren't allowed in counter names, so
        pipe ('|') characters should be used. These should be safe because they
        should not be used unencoded in urls.
        """
        counters = self.p4.counters()

        # Try for a "reviewboard.url" counter first.
        url = counters.get('reviewboard.url', None)

        if url:
            return url

        # Next try for a counter of the form:
        # reviewboard_url.http:||reviewboard.example.com
        for key, value in counters.iteritems():
            m = self.ENCODED_COUNTER_URL_RE.match(key)

            if m:
                return m.group(1).replace('|', '/')

        return None

    def get_changenum(self, args):
        if len(args) == 0:
            return "default"
        elif len(args) == 1:
            if args[0] == "default":
                return "default"

            try:
                return str(int(args[0]))
            except ValueError:
                # (if it isn't a number, it can't be a cln)
                return None
        # there are multiple args (not a cln)
        else:
            return None

    def diff(self, args):
        """
        Goes through the hard work of generating a diff on Perforce in order
        to take into account adds/deletes and to provide the necessary
        revision information.
        """
        # set the P4 enviroment:
        if self.options.p4_client:
            os.environ['P4CLIENT'] = self.options.p4_client

        if self.options.p4_port:
            os.environ['P4PORT'] = self.options.p4_port

        if self.options.p4_passwd:
            os.environ['P4PASSWD'] = self.options.p4_passwd

        try:
            revisions = self.parse_revision_spec(args)
        except InvalidRevisionSpecError:
            return self._path_diff(args)

        base = revisions['base']
        tip = revisions['tip']
        if tip.startswith(self.REVISION_PENDING_CLN_PREFIX):
            # Post a pending changeset
            return self._diff_pending(
                tip[len(self.REVISION_PENDING_CLN_PREFIX):])
        elif tip.startswith(self.REVISION_SHELVED_CLN_PREFIX):
            # Post a shelved changeset
            pass
        else:
            # Post a diff between two submitted changesets.
            pass

    def _diff_pending(self, changenum):
        logging.info('Generating diff for pending changeset %s' % changenum)

        opened_files = self.p4.opened(changenum)

        if not opened_files:
            die("Couldn't find any affected files for this change.")

        diff_lines = []

        action_mapping = {
            'edit': 'M',
            'integrate': 'M',
            'add': 'A',
            'branch': 'A',
            'delete': 'D',
        }

        if (self.capabilities and
            self.capabilities.has_capability('scmtools', 'perforce',
                                             'moved_files')):
            action_mapping['move/add'] = 'MV-a'
            action_mapping['move/delete'] = 'MV'
        else:
            # The Review Board server doesn't support moved files for
            # perforce--create a diff that shows moved files as adds and
            # deletes.
            action_mapping['move/add'] = 'A'
            action_mapping['move/delete'] = 'D'

        for f in opened_files:
            depot_path = f['depotFile']
            new_depot_path = ''
            try:
                base_revision = int(f['rev'])
            except ValueError:
                # For actions like deletes, there won't be any "current
                # revision". Just pass through whatever was there before
                base_revision = f['rev']
            action = f['action']

            empty_file = make_tempfile()
            old_file = make_tempfile()

            logging.debug('Processing %s of %s', action, depot_path)

            try:
                changetype_short = action_mapping[action]
            except KeyError:
                die('Unknown action type "%s" for %s' % (action, depot_path))

            if changetype_short == 'M':
                # Get the old version out of perforce and stick it in
                # 'old_file'
                try:
                    old_depot_path = '%s#%s' % (depot_path, base_revision)
                    self._write_file(old_depot_path, old_file)
                except ValueError, e:
                    logging.warning('Skipping file %s: %s', old_depot_path, e)
                    continue

                # Just reference the file within the client view for the new
                # file
                new_file = self._depot_to_local(depot_path)
            elif changetype_short == 'A':
                # Just reference the file within the client view for the new
                # file
                new_file = self._depot_to_local(depot_path)

                if os.path.islink(new_file):
                    logging.warning('Skipping symlink %s', new_file)
                    continue
            elif changetype_short == 'D':
                # Get the old version out of perforce and stick it in
                # 'old_file'
                try:
                    old_depot_path = '%s#%s' % (depot_path, base_revision)
                    self._write_file(old_depot_path, old_file)
                except ValueError, e:
                    logging.warning('Skipping file %s#%s: %s', old_depot_path, e)
                    continue

                # Use a completely empty file for the new one
                new_file = empty_file
            elif changetype_short == 'MV-a':
                # The server supports move information. We ignore this
                # particular entry, and handle the moves within the equivalent
                # 'move/delete' entry.
                continue
            elif changetype_short == 'MV':
                # A moved file. Figure out where it moved to and represent that
                # information.
                stat_info = self.p4.fstat(depot_path,
                                          ['clientFile', 'movedFile'])
                if ('clientFile' not in stat_info or
                    'movedFile' not in stat_info):
                    die('Unable to get moved file information for %s' %
                        depot_path)

                try:
                    old_depot_path = '%s#%s' % (depot_path, base_revision)
                    self._write_file(old_depot_path, old_file)
                except ValueError, e:
                    logging.warning('Skipping file %s#%s: %s', old_depot_path, e)
                    continue

                # Get information on the new file
                moved_stat_info = self.p4.fstat(stat_info['movedFile'],
                                                ['clientFile', 'depotFile'])
                if ('clientFile' not in moved_stat_info or
                    'depotFile' not in moved_stat_info):
                    die('Unable to get moved file information for %s' %
                        stat_info['movedFile'])

                # Access the new file directly in the client view
                new_file = moved_stat_info['clientFile']
                new_depot_path = moved_stat_info['depotFile']

            dl = self._do_diff(old_file, new_file, depot_path, base_revision,
                               new_depot_path, changetype_short,
                               ignore_unmodified=True)
            diff_lines += dl

            os.unlink(old_file)
            os.unlink(empty_file)

        return {
            'diff': ''.join(diff_lines),
        }

    def check_options(self):
        if self.options.revision_range:
            raise OptionsCheckError(
                "The --revision-range option is not supported for Perforce "
                "repositories. Please use the Perforce range path syntax "
                "instead.\n\n"
                "See: http://www.reviewboard.org/docs/manual/dev/users/tools/"
                "post-review/#posting-paths")

    def _path_diff(self, args):
        """
        Process a path-style diff. This allows people to post individual files
        in various ways.

        Multiple paths may be specified in `args`.  The path styles supported
        are:

        //path/to/file
        Upload file as a "new" file.

        //path/to/dir/...
        Upload all files as "new" files.

        //path/to/file[@#]rev
        Upload file from that rev as a "new" file.

        //path/to/file[@#]rev,[@#]rev
        Upload a diff between revs.

        //path/to/dir/...[@#]rev,[@#]rev
        Upload a diff of all files between revs in that directory.
        """
        r_revision_range = re.compile(r'^(?P<path>//[^@#]+)' +
                                      r'(?P<revision1>[#@][^,]+)?' +
                                      r'(?P<revision2>,[#@][^,]+)?$')

        empty_filename = make_tempfile()
        tmp_diff_from_filename = make_tempfile()
        tmp_diff_to_filename = make_tempfile()

        diff_lines = []

        for path in args:
            m = r_revision_range.match(path)

            if not m:
                die('Path %r does not match a valid Perforce path.' % (path,))
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
                    self._write_file(new_path, tmp_diff_from_filename)
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

                # TODO: We're passing new_depot_path='' here just to make
                # things work like they did before the moved file change was
                # added (58ccae27). This section of code needs to be updated
                # to properly work with moved files.
                dl = self._do_diff(old_file, new_file, depot_path,
                                   base_revision, '', changetype_short,
                                   ignore_unmodified=True)
                diff_lines += dl

        os.unlink(empty_filename)
        os.unlink(tmp_diff_from_filename)
        os.unlink(tmp_diff_to_filename)

        return {
            'diff': ''.join(diff_lines),
        }

    def sanitize_changenum(self, changenum):
        """
        Return a "sanitized" change number for submission to the Review Board
        server. For default changelists, this is always None. Otherwise, use
        the changelist number for submitted changelists, or if the p4d is
        2002.2 or newer.

        This is because p4d < 2002.2 does not return enough information about
        pending changelists in 'p4 describe' for Review Board to make use of
        them (specifically, the list of files is missing). This would result
        in the diffs being rejected.
        """
        if changenum == "default":
            return None
        else:
            v = self.p4d_version

            if v[0] < 2002 or (v[0] == "2002" and v[1] < 2):
                description = self.p4.description(
                    changenum=changenum,
                    password=self.options.p4_passwd)

                if '*pending*' in description[0]:
                    return None

        return changenum

    def _do_diff(self, old_file, new_file, depot_path, base_revision,
                 new_depot_path, changetype_short, ignore_unmodified=False):
        """
        Do the work of producing a diff for Perforce.

        old_file - The absolute path to the "old" file.
        new_file - The absolute path to the "new" file.
        depot_path - The depot path in Perforce for this file.
        base_revision - The base perforce revision number of the old file as
            an integer.
        new_depot_path - Location of the new file. Only used for moved files.
        changetype_short - The change type as a short string.
        ignore_unmodified - If True, will return an empty list if the file
            is not changed.

        Returns a list of strings of diff lines.
        """
        if hasattr(os, 'uname') and os.uname()[0] == 'SunOS':
            diff_cmd = ["gdiff", "-urNp", old_file, new_file]
        else:
            diff_cmd = ["diff", "-urNp", old_file, new_file]

        # Diff returns "1" if differences were found.
        dl = execute(diff_cmd, extra_ignore_errors=(1, 2),
                     translate_newlines=False)

        # If the input file has ^M characters at end of line, lets ignore them.
        dl = dl.replace('\r\r\n', '\r\n')
        dl = dl.splitlines(True)

        cwd = os.getcwd()

        if depot_path.startswith(cwd):
            local_path = depot_path[len(cwd) + 1:]
        else:
            local_path = depot_path

        if changetype_short == 'MV':
            is_move = True

            if new_depot_path.startswith(cwd):
                new_local_path = new_depot_path[len(cwd) + 1:]
            else:
                new_local_path = new_depot_path
        else:
            is_move = False
            new_local_path = local_path

        # Special handling for the output of the diff tool on binary files:
        #     diff outputs "Files a and b differ"
        # and the code below expects the output to start with
        #     "Binary files "
        if (len(dl) == 1 and
            dl[0].startswith('Files %s and %s differ' %
                            (old_file, new_file))):
            dl = ['Binary files %s and %s differ\n' % (old_file, new_file)]

        if dl == [] or dl[0].startswith("Binary files "):
            if dl == [] and not is_move:
                if ignore_unmodified:
                    return []
                else:
                    print "Warning: %s in your changeset is unmodified" % \
                          local_path

            dl.insert(0, "==== %s#%s ==%s== %s ====\n" %
                      (depot_path, base_revision, changetype_short,
                       new_local_path))
            dl.append('\n')
        elif len(dl) > 1:
            m = re.search(r'(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)', dl[1])
            if m:
                timestamp = m.group(1)
            else:
                # Thu Sep  3 11:24:48 2007
                m = self.DATE_RE.search(dl[1])
                if not m:
                    die("Unable to parse diff header: %s" % dl[1])

                month_map = {
                    "Jan": "01",
                    "Feb": "02",
                    "Mar": "03",
                    "Apr": "04",
                    "May": "05",
                    "Jun": "06",
                    "Jul": "07",
                    "Aug": "08",
                    "Sep": "09",
                    "Oct": "10",
                    "Nov": "11",
                    "Dec": "12",
                }
                month = month_map[m.group(2)]
                day = m.group(3)
                timestamp = m.group(4)
                year = m.group(5)

                timestamp = "%s-%s-%s %s" % (year, month, day, timestamp)

            dl[0] = "--- %s\t%s#%s\n" % (local_path, depot_path, base_revision)
            dl[1] = "+++ %s\t%s\n" % (new_local_path, timestamp)

            if is_move:
                dl.insert(0, 'Moved to: %s\n' % new_depot_path)
                dl.insert(0, 'Moved from: %s\n' % depot_path)

            # Not everybody has files that end in a newline (ugh). This ensures
            # that the resulting diff file isn't broken.
            if dl[-1][-1] != '\n':
                dl.append('\n')
        else:
            die("ERROR, no valid diffs: %s" % dl[0])

        return dl

    def _write_file(self, depot_path, tmpfile):
        """
        Grabs a file from Perforce and writes it to a temp file. p4 print sets
        the file readonly and that causes a later call to unlink fail. So we
        make the file read/write.
        """
        logging.debug('Writing "%s" to "%s"' % (depot_path, tmpfile))
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
        #   when post-review uses their credentials to publish its contents.

        if os.path.islink(tmpfile):
            raise ValueError("'%s' is a symlink" % depot_path)
        else:
            os.chmod(tmpfile, stat.S_IREAD | stat.S_IWRITE)

    def _depot_to_local(self, depot_path):
        """
        Given a path in the depot return the path on the local filesystem to
        the same file.  If there are multiple results, take only the last
        result from the where command.
        """
        where_output = self.p4.where(depot_path)

        try:
            return where_output[-1]['path']
        except:
            # XXX: This breaks on filenames with spaces.
            return where_output[-1]['data'].split(' ')[2].strip()
