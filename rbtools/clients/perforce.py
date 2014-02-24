import logging
import marshal
import os
import re
import socket
import stat
import subprocess

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import (EmptyChangeError,
                                    InvalidRevisionSpecError,
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

    def __init__(self, options):
        self.options = options

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

    def filelog(self, path):
        return self.run_p4(['filelog', path], marshalled=True)

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

        if self.options.p4_client:
            cmd += ['-c', self.options.p4_client]

        if self.options.p4_port:
            cmd += ['-p', self.options.p4_port]

        if self.options.p4_passwd:
            cmd += ['-P', self.options.p4_passwd]

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

    supports_diff_extra_args = True
    supports_update_without_summary_and_description = True

    DATE_RE = re.compile(r'(\w+)\s+(\w+)\s+(\d+)\s+(\d\d:\d\d:\d\d)\s+'
                         '(\d\d\d\d)')
    ENCODED_COUNTER_URL_RE = re.compile('reviewboard.url\.(\S+)')

    REVISION_CURRENT_SYNC = '--rbtools-current-sync'
    REVISION_PENDING_CLN_PREFIX = '--rbtools-pending-cln:'

    def __init__(self, p4_class=P4Wrapper, **kwargs):
        super(PerforceClient, self).__init__(**kwargs)
        self.p4 = p4_class(self.options)

    def get_repository_info(self):
        if not self.p4.is_supported():
            return None

        p4_info = self.p4.info()

        # For the repository path, we first prefer p4 brokers, then the
        # upstream p4 server. If neither of those are found, just return None.
        repository_path = (p4_info.get('Broker address') or
                           p4_info.get('Server address'))

        if repository_path is None:
            return None

        client_root = p4_info.get('Client root')

        if client_root is None:
            return None

        norm_cwd = os.path.normcase(os.path.realpath(os.getcwd()) +
                                    os.path.sep)
        norm_client_root = os.path.normcase(os.path.realpath(client_root) +
                                            os.path.sep)

        # Don't accept the repository if the current directory is outside the
        # root of the Perforce client.
        if not norm_cwd.startswith(norm_client_root):
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
        
    def match_existing_review_request(self, review_requests, revisions):
        """Scan the given review_requests for one that matches the given 
        revisions and return it.  If an exact match is not found, return 
        ``None``.
        """
        tip = revisions['tip']
        changenum = int(tip.replace(self.REVISION_PENDING_CLN_PREFIX, ''))
        for review_request in review_requests:
            if changenum == review_request.changenum:
                return review_request
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

    def diff(self, revisions, files=[], extra_args=[]):
        """
        Goes through the hard work of generating a diff on Perforce in order
        to take into account adds/deletes and to provide the necessary
        revision information.
        """
        if not revisions:
            # The "path posting" is still interesting enough to keep around. If
            # the given arguments don't parse as valid changelists, fall back
            # on that behavior.
            return self._path_diff(extra_args)

        # Support both //depot/... paths and local filenames. For the moment,
        # this does *not* support any of perforce's traversal literals like ...
        depot_include_files = []
        local_include_files = []
        for filename in files:
            if filename.startswith('//'):
                depot_include_files.append(filename)
            else:
                # The way we determine files to include or not is via
                # 'p4 where', which gives us absolute paths.
                local_include_files.append(
                    os.path.realpath(os.path.abspath(filename)))

        base = revisions['base']
        tip = revisions['tip']

        cl_is_pending = tip.startswith(self.REVISION_PENDING_CLN_PREFIX)
        cl_is_shelved = False

        if not cl_is_pending:
            # Submitted changes are handled by a different method
            logging.info('Generating diff for range of submitted changes: %s '
                         'to %s',
                         base, tip)
            return self._compute_range_changes(
                base, tip, depot_include_files, local_include_files)

        # Strip off the prefix
        tip = tip[len(self.REVISION_PENDING_CLN_PREFIX):]

        # Try to get the files out of the working directory first. If that
        # doesn't work, look at shelved files.
        opened_files = self.p4.opened(tip)
        if not opened_files:
            opened_files = self.p4.files('//...@=%s' % tip)
            cl_is_shelved = True

        if not opened_files:
            raise EmptyChangeError

        if cl_is_shelved:
            logging.info('Generating diff for shelved changeset %s' % tip)
        else:
            logging.info('Generating diff for pending changeset %s' % tip)

        diff_lines = []

        action_mapping = {
            'edit': 'M',
            'integrate': 'M',
            'add': 'A',
            'branch': 'A',
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
            # perforce--create a diff that shows moved files as adds and
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
                 local_file not in local_include_files)):
                continue

            old_file = ''
            new_file = ''

            logging.debug('Processing %s of %s', action, depot_file)

            try:
                changetype_short = action_mapping[action]
            except KeyError:
                die('Unsupported action type "%s" for %s' % (action, depot_file))

            if changetype_short == 'M':
                try:
                    old_file, new_file = self._extract_edit_files(
                        depot_file, local_file, base_revision, tip,
                        cl_is_shelved, False)
                except ValueError, e:
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
                        depot_file, local_file, tip, cl_is_shelved,
                        cl_is_pending)
                except ValueError, e:
                    logging.warning('Skipping file %s: %s', depot_file, e)
                    continue

                if os.path.islink(new_file):
                    logging.warning('Skipping symlink %s', new_file)
                    continue
            elif changetype_short == 'D':
                try:
                    old_file, new_file = self._extract_delete_files(
                        depot_file, base_revision)
                except ValueError, e:
                    logging.warning('Skipping file %s#%s: %s', depot_file, e)
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
                            depot_file, tip, base_revision, cl_is_shelved)
                except ValueError, e:
                    logging.warning('Skipping file %s: %s', depot_file, e)
                    continue

            dl = self._do_diff(old_file, new_file, depot_file, base_revision,
                               new_depot_file, changetype_short,
                               ignore_unmodified=True)
            diff_lines += dl

        # For pending changesets, report the change number to the reviewboard
        # server when posting. This is used to extract the changeset
        # description server-side. Ideally we'd change this to remove the
        # server-side implementation and just implement --guess-summary and
        # --guess-description, but that would create a lot of unhappy users.
        if cl_is_pending and tip != 'default':
            changenum = str(tip)
        else:
            changenum = None

        return {
            'diff': ''.join(diff_lines),
            'changenum': changenum,
        }

    def _compute_range_changes(self, base, tip, depot_include_files,
                               local_include_files):
        """Compute the changes across files given a revision range.

        This will look at the history of all changes within the given range and
        compute the full set of changes contained therein. Just looking at the
        two trees isn't enough, since files may have moved around and we want
        to include that information.
        """
        # Start by looking at the filelog to get a history of all the changes
        # within the changeset range. This processing step is done because in
        # marshalled mode, the filelog doesn't sort its entries at all, and can
        # also include duplicate information, especially when files have moved
        # around.
        changesets = {}
        for file_entry in self.p4.filelog('//...@%s,%s' % (base, tip)):
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
                    logging.warning('Skipping file %s: unable to parse '
                                    'change number "%s"',
                                    depot_file, file_entry[change_key])
                    break

                if action not in ('edit', 'integrate', 'add', 'delete',
                                  'move/add', 'move/delete'):
                    raise Exception('Unsupported action type "%s" for %s' %
                                    (action, depot_file))

                if action == 'integrate':
                    action = 'edit'
                elif action == 'branch':
                    action = 'add'

                try:
                    rev_key = 'rev%d' % cid
                    rev = int(file_entry[rev_key])
                except ValueError:
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
            for depot_file, change in changeset.iteritems():
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
        diff_lines = []
        for f in files:
            action = f['action']
            depot_file = f['depotFile']
            local_file = self._depot_to_local(depot_file)
            rev = f['rev']
            initial_depot_file = f['initialDepotFile']
            initial_rev = f['initialRev']

            if ((depot_include_files and
                 depot_file not in depot_include_files) or
                (local_include_files and
                 local_file not in local_include_files)):
                continue

            if action == 'add':
                try:
                    old_file, new_file = self._extract_add_files(
                        depot_file, local_file, rev, False, False)
                except ValueError, e:
                    logging.warning('Skipping file %s: %s', depot_file, e)
                    continue

                diff_lines += self._do_diff(
                    old_file, new_file, depot_file, 0, '', 'A',
                    ignore_unmodified=True)
            elif action == 'delete':
                try:
                    old_file, new_file = self._extract_delete_files(
                        initial_depot_file, initial_rev)
                except ValueError:
                    logging.warning('Skipping file %s: %s', depot_file, e)
                    continue

                diff_lines += self._do_diff(
                    old_file, new_file, initial_depot_file, initial_rev,
                    depot_file, 'D', ignore_unmodified=True)
            elif action == 'edit':
                try:
                    old_file, new_file = self._extract_edit_files(
                        depot_file, local_file, initial_rev, rev, False, True)
                except ValueError:
                    logging.warning('Skipping file %s: %s', depot_file, e)
                    continue
            elif action == 'move':
                try:
                    old_file_a, new_file_a = self._extract_add_files(
                        depot_file, local_file, rev, False, False)
                    old_file_b, new_file_b = self._extract_delete_files(
                        initial_depot_file, initial_rev)
                except ValueError:
                    logging.warning('Skipping file %s: %s', depot_file, e)
                    continue

                if supports_moves:
                    # Show the change as a move
                    diff_lines += self._do_diff(
                        old_file_a, new_file_b, initial_depot_file,
                        initial_rev, depot_file, 'MV', ignore_unmodified=True)
                else:
                    # Show the change as add and delete
                    diff_lines += self._do_diff(
                        old_file_a, new_file_a, depot_file, 0, '', 'A',
                        ignore_unmodified=True)
                    diff_lines += self._do_diff(
                        old_file_b, new_file_b, initial_depot_file, initial_rev,
                        depot_file, 'D', ignore_unmodified=True)
            elif action == 'skip':
                continue
            else:
                # We should never get here. The results of
                # self._accumulate_range_change should never be anything other
                # than add, delete, move, or edit.
                assert False

        return {
            'diff': ''.join(diff_lines)
        }

    def _accumulate_range_change(self, file_entry, change):
        """Compute the effects of a given change on a given file"""
        old_action = file_entry['action']
        current_action = change['action']

        if old_action == 'none':
            # This is the first entry for this file.
            new_action = current_action
            file_entry['depotFile'] = file_entry['initialDepotFile']

            # If the first action was an edit, then the initial revision
            # (that we'll use to generate the diff) is n-1
            if current_action == 'edit':
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

    def _extract_edit_files(self, depot_file, local_file, rev_a, rev_b,
                            cl_is_shelved, cl_is_submitted):
        """Extract the 'old' and 'new' files for an edit operation.

        Returns a tuple of (old filename, new filename). This can raise a
        ValueError if the extraction fails.
        """
        # Get the old version out of perforce
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

    def _extract_add_files(self, depot_file, local_file, revision,
                           cl_is_shelved, cl_is_pending):
        """Extract the 'old' and 'new' files for an add operation.

        Returns a tuple of (old filename, new filename). This can raise a
        ValueError if the extraction fails.
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

    def _extract_delete_files(self, depot_file, revision):
        """Extract the 'old' and 'new' files for a delete operation.

        Returns a tuple of (old filename, new filename). This can raise a
        ValueError if extraction fails.
        """
        # Get the old version out of perforce
        old_filename = make_tempfile()
        self._write_file('%s#%s' % (depot_file, revision), old_filename)

        # Make an empty tempfile for the new file
        new_filename = make_tempfile()

        return old_filename, new_filename

    def _extract_move_files(self, old_depot_file, tip, base_revision,
                            cl_is_shelved):
        """Extract the 'old' and 'new' files for a move operation.

        Returns a tuple of (old filename, new filename, new depot path). This
        can raise a ValueError if extraction fails.
        """
        # XXX: fstat *ought* to work, but perforce doesn't supply the movedFile
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

                # TODO: We're passing new_depot_file='' here just to make
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

    def _do_diff(self, old_file, new_file, depot_file, base_revision,
                 new_depot_file, changetype_short, ignore_unmodified=False):
        """
        Do the work of producing a diff for Perforce.

        old_file - The absolute path to the "old" file.
        new_file - The absolute path to the "new" file.
        depot_file - The depot path in Perforce for this file.
        base_revision - The base perforce revision number of the old file as
            an integer.
        new_depot_file - Location of the new file. Only used for moved files.
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
                      (depot_file, base_revision, changetype_short,
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

            dl[0] = "--- %s\t%s#%s\n" % (local_path, depot_file, base_revision)
            dl[1] = "+++ %s\t%s\n" % (new_local_path, timestamp)

            if is_move:
                dl.insert(0, 'Moved to: %s\n' % new_depot_file)
                dl.insert(0, 'Moved from: %s\n' % depot_file)

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
        #   when rbt uses their credentials to publish its contents.

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

    def _supports_moves(self):
        return (self.capabilities and
                self.capabilities.has_capability('scmtools', 'perforce',
                                                 'moved_files'))
