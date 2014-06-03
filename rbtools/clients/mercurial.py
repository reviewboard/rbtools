import logging
import os
import re
import uuid

from urlparse import urlsplit, urlunparse

from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    TooManyRevisionsError)
from rbtools.clients.svn import SVNClient
from rbtools.utils.checks import check_install
from rbtools.utils.process import die, execute


class MercurialClient(SCMClient):
    """
    A wrapper around the hg Mercurial tool that fetches repository
    information and generates compatible diffs.
    """
    name = 'Mercurial'

    PRE_CREATION = '/dev/null'
    PRE_CREATION_DATE = 'Thu Jan 01 00:00:00 1970 +0000'

    def __init__(self, **kwargs):
        super(MercurialClient, self).__init__(**kwargs)

        self.hgrc = {}
        self._type = 'hg'
        self._remote_path = ()
        self._initted = False
        self._hg_env = {
            'HGPLAIN': '1',
        }

        self._hgext_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            '..', 'helpers', 'hgext.py'))

        # `self._remote_path_candidates` is an ordered set of hgrc
        # paths that are checked if `tracking` option is not given
        # explicitly.  The first candidate found to exist will be used,
        # falling back to `default` (the last member.)
        self._remote_path_candidates = ['reviewboard', 'origin', 'parent',
                                        'default']

    @property
    def hidden_changesets_supported(self):
        """Whether the repository supports hidden changesets.

        Mercurial 1.9 and above support hidden changesets. These are changesets
        that have been hidden from regular repository view. They still exist
        and are accessible, but only if the --hidden command argument is
        specified.

        Since we may encounter hidden changesets (e.g. the user specifies
        hidden changesets as part of the revision spec), we need to be aware
        of hidden changesets.
        """
        if not hasattr(self, '_hidden_changesets_supported'):
            # The choice of command is arbitrary. parents for the initial
            # revision should be fast.
            result = execute(['hg', 'parents', '--hidden', '-r', '0'],
                             ignore_errors=True,
                             with_errors=False,
                             none_on_ignored_error=True)
            self._hidden_changesets_supported = result is not None

        return self._hidden_changesets_supported

    @property
    def hg_root(self):
        """The root of the working directory.

        This will return the root directory of the current repository. If the
        current working directory is not inside a mercurial repository, this
        returns None.
        """
        if not hasattr(self, '_hg_root'):
            root = execute(['hg', 'root'], env=self._hg_env,
                           ignore_errors=True)

            if not root.startswith('abort:'):
                self._hg_root = root.strip()
            else:
                self._hg_root = None

        return self._hg_root

    def _init(self):
        """Initialize the client."""
        if self._initted or not self.hg_root:
            return

        self._load_hgrc()

        svn_info = execute(["hg", "svn", "info"], ignore_errors=True)
        if (not svn_info.startswith('abort:') and
                not svn_info.startswith("hg: unknown command") and
                not svn_info.lower().startswith('not a child of')):
            self._type = 'svn'
            self._svn_info = svn_info
        else:
            self._type = 'hg'

            for candidate in self._remote_path_candidates:
                rc_key = 'paths.%s' % candidate

                if rc_key in self.hgrc:
                    self._remote_path = (candidate, self.hgrc[rc_key])
                    logging.debug('Using candidate path %r: %r' %
                                  self._remote_path)
                    break

        self._initted = True

    def get_repository_info(self):
        if not check_install(['hg', '--help']):
            logging.debug('Unable to execute "hg --help": skipping Mercurial')
            return None

        self._init()

        if not self.hg_root:
            # hg aborted => no mercurial repository here.
            return None

        if self._type == 'svn':
            return self._calculate_hgsubversion_repository_info(self._svn_info)
        else:
            path = self.hg_root
            base_path = '/'

            if self._remote_path:
                path = self._remote_path[1]
                base_path = ''

            return RepositoryInfo(path=path, base_path=base_path,
                                  supports_parent_diffs=True)

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
            'parent_base': (optional) The revision to use as the base of a
                           parent diff.
            'commit_id':   (optional) The ID of the single commit being posted,
                           if not using a range.

        These will be used to generate the diffs to upload to Review Board (or
        print). The diff for review will include the changes in (base, tip],
        and the parent diff (if necessary) will include (parent, base].

        If zero revisions are passed in, this will return the outgoing changes
        from the parent of the working directory.

        If a single revision is passed in, this will return the parent of that
        revision for 'base' and the passed-in revision for 'tip'. This will
        result in generating a diff for the changeset specified.

        If two revisions are passed in, they will be used for the 'base'
        and 'tip' revisions, respectively.

        In all cases, a parent base will be calculated automatically from
        changesets not present on the remote.
        """
        self._init()

        n_revisions = len(revisions)

        if n_revisions == 1:
            # If there's a single revision, try splitting it based on hg's
            # revision range syntax (either :: or ..). If this splits, then
            # it's handled as two revisions below.
            revisions = re.split(r'\.\.|::', revisions[0])
            n_revisions = len(revisions)

        result = {}
        if n_revisions == 0:
            # No revisions: Find the outgoing changes. Only consider the
            # working copy revision and ancestors because that makes sense.
            # If a user wishes to include other changesets, they can run
            # `hg up` or specify explicit revisions as command arguments.
            if self._type == 'svn':
                result['base'] = self._get_parent_for_hgsubversion()
                result['tip'] = '.'
            else:
                # Ideally, generating a diff for outgoing changes would be as
                # simple as just running `hg outgoing --patch <remote>`, but
                # there are a couple problems with this. For one, the
                # server-side diff parser isn't equipped to filter out diff
                # headers such as "comparing with..." and
                # "changeset: <rev>:<hash>". Another problem is that the output
                # of `hg outgoing` potentially includes changesets across
                # multiple branches.
                #
                # In order to provide the most accurate comparison between
                # one's local clone and a given remote (something akin to git's
                # diff command syntax `git diff <treeish>..<treeish>`), we have
                # to do the following:
                #
                # - Get the name of the current branch
                # - Get a list of outgoing changesets, specifying a custom
                #   format
                # - Filter outgoing changesets by the current branch name
                # - Get the "top" and "bottom" outgoing changesets
                #
                # These changesets are then used as arguments to
                # `hg diff -r <rev> -r <rev>`.
                #
                # Future modifications may need to be made to account for odd
                # cases like having multiple diverged branches which share
                # partial history--or we can just punish developers for doing
                # such nonsense :)
                outgoing = \
                    self._get_bottom_and_top_outgoing_revs_for_remote(rev='.')
                if outgoing[0] is None or outgoing[1] is None:
                    raise InvalidRevisionSpecError(
                        'There are no outgoing changes')
                result['base'] = self._identify_revision(outgoing[0])
                result['tip'] = self._identify_revision(outgoing[1])
                result['commit_id'] = result['tip']

            if self.options.parent_branch:
                result['parent_base'] = result['base']
                result['base'] = self._identify_revision(
                    self.options.parent_branch)
        elif n_revisions == 1:
            # One revision: Use the given revision for tip, and find its parent
            # for base.
            result['tip'] = self._identify_revision(revisions[0])
            result['commit_id'] = result['tip']
            result['base'] = self._execute(
                ['hg', 'parents', '--hidden', '-r', result['tip'],
                 '--template', '{node|short}']).split()[0]
        elif n_revisions == 2:
            # Two revisions: Just use the given revisions
            result['base'] = self._identify_revision(revisions[0])
            result['tip'] = self._identify_revision(revisions[1])
        else:
            raise TooManyRevisionsError

        if 'base' not in result or 'tip' not in result:
            raise InvalidRevisionSpecError(
                '"%s" does not appear to be a valid revision spec' % revisions)

        if self._type == 'hg' and 'parent_base' not in result:
            # If there are missing changesets between base and the remote, we
            # need to generate a parent diff.
            outgoing = self._get_outgoing_changesets(self._get_remote_branch(),
                                                 rev=result['base'])

            logging.debug('%d outgoing changesets between remote and base.',
                          len(outgoing))

            if not outgoing:
                return result

            result['parent_base'] = self._execute(
                ['hg', 'parents', '--hidden', '-r', outgoing[0][1],
                 '--template', '{node|short}']).split()[0]
            logging.debug('Identified %s as parent base', result['parent_base'])

        return result

    def _identify_revision(self, revision):
        identify = self._execute(
            ['hg', 'identify', '-i', '--hidden', '-r', str(revision)],
            ignore_errors=True, none_on_ignored_error=True)

        if identify is None:
            raise InvalidRevisionSpecError(
                '"%s" does not appear to be a valid revision' % revision)
        else:
            return identify.split()[0]

    def _calculate_hgsubversion_repository_info(self, svn_info):
        def _info(r):
            m = re.search(r, svn_info, re.M)

            if m:
                return urlsplit(m.group(1))
            else:
                return None

        self._type = 'svn'

        root = _info(r'^Repository Root: (.+)$')
        url = _info(r'^URL: (.+)$')

        if not (root and url):
            return None

        scheme, netloc, path, _, _ = root
        root = urlunparse([scheme, root.netloc.split("@")[-1], path,
                           "", "", ""])
        base_path = url.path[len(path):]

        return RepositoryInfo(path=root, base_path=base_path,
                              supports_parent_diffs=True)


    def _load_hgrc(self):
        for line in execute(['hg', 'showconfig'], split_lines=True):
            line = line.split('=', 1)
            if len(line) == 2:
                key, value = line
            else:
                key = line[0]
                value = ''

            self.hgrc[key] = value.strip()

    def get_raw_commit_message(self, revisions):
        """
        Extracts all descriptions in the given revision range and concatenates
        them, most recent ones going first.
        """
        rev1 = revisions['base']
        rev2 = revisions['tip']

        delim = str(uuid.uuid1())
        descs = self._execute([
            'hg', 'log', '--hidden', '-r', '%s::%s' % (rev1, rev2),
            '--template', '{desc}%s' % delim], env=self._hg_env)
        # This initial element in the base changeset, which we don't
        # care about. The last element is always empty due to the string
        # ending with <delim>.
        descs = descs.split(delim)[1:-1]

        return '\n\n'.join([desc.strip() for desc in descs])

    def diff(self, revisions, files=[], extra_args=[]):
        """
        Performs a diff across all modified files in a Mercurial repository.
        """
        self._init()

        diff_cmd = ['hg', 'diff', '--hidden']

        if self._type == 'svn':
            diff_cmd.append('--svn')

        diff_cmd += files

        diff = self._execute(
            diff_cmd + ['-r', revisions['base'], '-r', revisions['tip']],
            env=self._hg_env)

        if self._supports_empty_files():
            diff = self._handle_empty_files(diff, revisions['base'],
                                            revisions['tip'])

        if 'parent_base' in revisions:
            base_commit_id = revisions['parent_base']
            parent_diff = self._execute(
                diff_cmd + ['-r', base_commit_id, '-r', revisions['base']],
                env=self._hg_env)

            if self._supports_empty_files():
                parent_diff = self._handle_empty_files(parent_diff,
                                                       base_commit_id,
                                                       revisions['base'])
        else:
            base_commit_id = revisions['base']
            parent_diff = None

        return {
            'diff': diff,
            'parent_diff': parent_diff,
            'commit_id': revisions.get('commit_id'),
            'base_commit_id': base_commit_id,
        }

    def _handle_empty_files(self, diff, base, tip):
        """Adds added and deleted 0-length files to the diff output.

        Since the diff output from hg diff does not give any information on
        0-length files, we manually add this extra information to the patch.
        """
        # If the files in the base and tip changesets are the same, no files
        # (empty or otherwise) were added or deleted.
        base_files = self._get_files_in_changeset(base)
        tip_files = self._get_files_in_changeset(tip)

        if base_files == tip_files:
            return diff

        tip_empty_files = self._get_files_in_changeset(tip, get_empty=True)
        added_empty_files = tip_empty_files - base_files

        base_empty_files = self._get_files_in_changeset(base, get_empty=True)
        deleted_empty_files = base_empty_files - tip_files

        if not (added_empty_files or deleted_empty_files):
            return diff

        base_date, tip_date = execute(['hg', 'log', '-r', base, '-r', tip,
                                       '--template', '{date|date}\\t'],
                                      env=self._hg_env).strip().split('\t')

        for filename in added_empty_files:
            diff += ('diff -r %s -r %s %s\n'
                     '--- %s\t%s\n'
                     '+++ b/%s\t%s\n'
                     % (base, tip, filename,
                        self.PRE_CREATION, self.PRE_CREATION_DATE,
                        filename, tip_date))

        for filename in deleted_empty_files:
            diff += ('diff -r %s -r %s %s\n'
                     '--- a/%s\t%s\n'
                     '+++ %s\t%s\n'
                     % (base, tip, filename,
                        filename, base_date,
                        self.PRE_CREATION, self.PRE_CREATION_DATE))

        return diff

    def _get_files_in_changeset(self, rev, get_empty=False):
        """Returns a set of all files in the specified changeset.

        If get_empty is True, we return only 0-length files in the changeset.
        """
        cmd = ['hg', 'locate', '-r', rev]

        if get_empty:
            cmd.append('set:size(0)')

        files = execute(cmd, env=self._hg_env, ignore_errors=True,
                        none_on_ignored_error=True)

        return (files and set(files.splitlines())) or set()

    def _get_parent_for_hgsubversion(self):
        """Returns the parent Subversion branch.

        Returns the parent branch defined in the command options if it exists,
        otherwise returns the parent Subversion branch of the current
        repository.
        """
        return (getattr(self.options, 'tracking', None) or
                execute(['hg', 'parent', '--svn', '--template',
                        '{node}\n']).strip())

    def _get_remote_branch(self):
        """Returns the remote branch assoicated with this repository.

        If the remote branch is not defined, the parent branch of the
        repository is returned.
        """
        try:
            remote = self._remote_path[0]
        except IndexError:
            remote = None

        tracking = getattr(self.options, 'tracking', None)

        if not remote and tracking:
            remote = tracking

        if not remote:
            die('Could not determine remote branch to use for diff creation. '
                'Specify --tracking-branch to continue.')

        return remote

    def _get_current_branch(self):
        """Returns the current branch of this repository."""
        return execute(['hg', 'branch'], env=self._hg_env).strip()

    def _get_bottom_and_top_outgoing_revs_for_remote(self, rev=None):
        """Returns the bottom and top outgoing revisions.

        Returns the bottom and top outgoing revisions for the changesets
        between the current branch and the remote branch.
        """
        remote = self._get_remote_branch()
        current_branch = self._get_current_branch()

        outgoing = [o for o in self._get_outgoing_changesets(remote, rev=rev)
                    if current_branch == o[2]]

        if outgoing:
            top_rev, bottom_rev = \
                self._get_top_and_bottom_outgoing_revs(outgoing)
        else:
            top_rev = None
            bottom_rev = None

        return bottom_rev, top_rev

    def _get_outgoing_changesets(self, remote, rev=None):
        """
        Return the outgoing changesets between us and a remote.

        This will return a list of tuples of (rev, node, branch) for
        each outgoing changeset. The list will be sorted in revision order.

        If rev is specified, we will limit the changesets to ancestors of
        the specified revision. Otherwise, all changesets not in the remote
        will be returned.
        """

        outgoing_changesets = []
        args = ['hg', '-q', 'outgoing', '--template',
                "{rev}\\t{node|short}\\t{branch}\\n",
                remote]
        if rev:
            args.extend(['-r', rev])

        # We must handle the special case where there are no outgoing commits
        # as mercurial has a non-zero return value in this case.
        raw_outgoing = execute(args,
                               env=self._hg_env,
                               extra_ignore_errors=(1,))

        for line in raw_outgoing.splitlines():
            if not line:
                continue

            # Ignore warning messages that hg might put in, such as
            # "warning: certificate for foo can't be verified (Python too old)"
            if line.startswith('warning: '):
                continue

            rev, node, branch = [f.strip() for f in line.split('\t')]
            branch = branch or 'default'

            if not rev.isdigit():
                raise Exception('Unexpected output from hg: %s' % line)

            logging.debug('Found outgoing changeset %s:%s' % (rev, node))

            outgoing_changesets.append((int(rev), node, branch))

        return outgoing_changesets

    def _get_top_and_bottom_outgoing_revs(self, outgoing_changesets):
        revs = set(t[0] for t in outgoing_changesets)

        top_rev = max(revs)
        bottom_rev = min(revs)

        for rev, node, branch in reversed(outgoing_changesets):
            parents = execute(
                ["hg", "log", "-r", str(rev), "--template", "{parents}"],
                env=self._hg_env)
            parents = re.split(':[^\s]+\s*', parents)
            parents = [int(p) for p in parents if p != '']

            parents = [p for p in parents if p not in outgoing_changesets]

            if len(parents) > 0:
                bottom_rev = parents[0]
                break
            else:
                bottom_rev = rev - 1

        bottom_rev = max(0, bottom_rev)

        return top_rev, bottom_rev

    def scan_for_server(self, repository_info):
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = \
            super(MercurialClient, self).scan_for_server(repository_info)

        if not server_url and self.hgrc.get('reviewboard.url'):
            server_url = self.hgrc.get('reviewboard.url').strip()

        if not server_url and self._type == "svn":
            # Try using the reviewboard:url property on the SVN repo, if it
            # exists.
            prop = SVNClient().scan_for_server_property(repository_info)

            if prop:
                return prop

        return server_url

    def _execute(self, cmd, *args, **kwargs):
        if not self.hidden_changesets_supported and '--hidden' in cmd:
            cmd = [p for p in cmd if p != '--hidden']

        # Add our extension which normalizes settings. This is the easiest
        # way to normalize settings since it doesn't require us to chase
        # a tail of diff-related config options.
        cmd.extend([
            '--config',
            'extensions.rbtoolsnormalize=%s' % self._hgext_path
        ])

        return execute(cmd, *args, **kwargs)

    def _supports_empty_files(self):
        """Checks if the RB server supports added/deleted empty files."""
        return (self.capabilities and
                self.capabilities.has_capability('scmtools', 'mercurial',
                                                 'empty_files'))
