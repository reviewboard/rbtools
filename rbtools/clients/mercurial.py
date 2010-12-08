import os
import re

from repository import Client, Repository

class MercurialCLient(Client):
    """An implementation of Repository for Mercurial repositories"""

    url = None
    util = None

    def __init__(self, url=None, util=None):
        self.url = url
        self.util = util
        self.hgrc = {}
        self._type = 'hg'
        self._hg_root = ''
        self._remote_path = ()
        self._hg_env = {
            'HGRCPATH': os.devnull,
            'HGPLAIN': '1',
        }

        # `self._remote_path_candidates` is an ordered set of hgrc
        # paths that are checked if `parent_branch` option is not given
        # explicitly.  The first candidate found to exist will be used,
        # falling back to `default` (the last member.)
        self._remote_path_candidates = ['reviewboard', 'origin', 'parent',
                                        'default']

    def get_info(self):
        """Returns information about the repository
        
        This is an actual implementation that returns info about the hg repo
        """

        if not self.util.check_install('hg --help'):
            return None

        self._load_hgrc()

        if not self.hg_root:
            # hg aborted => no mercurial repository here.
            return None

        svn_info = self.util.execute(["hg", "svn", "info"], ignore_errors=True)

        if (not svn_info.startswith('abort:') and
            not svn_info.startswith("hg: unknown command") and
            not svn_info.lower().startswith('not a child of')):
            return self._calculate_hgsubversion_repository_info(svn_info)

        self._type = 'hg'

        path = self.hg_root
        base_path = '/'

        if self.hgrc:
            self._calculate_remote_path()

            if self._remote_path:
                path = self._remote_path[1]
                base_path = ''

        return Repository(path=path, base_path=base_path,
                              supports_parent_diffs=True)

    def _calculate_remote_path(self):
        """Calculate the remote path for the repository
    
        Calculates the correct remote path for the mercurial repository
        """

        for candidate in self._remote_path_candidates:

            rc_key = 'paths.%s' % candidate

            if (not self._remote_path and self.hgrc.get(rc_key)):
                self._remote_path = (candidate, self.hgrc.get(rc_key))
                self.util.execute('Using candidate path %r: %r' % \
                        self._remote_path)

                return

    def _calculate_hgsubversion_repository_info(self, svn_info):
        self._type = 'svn'
        m = re.search(r'^Repository Root: (.+)$', svn_info, re.M)

        if not m:
            return None

        path = m.group(1)
        m2 = re.match(r'^(svn\+ssh|http|https|svn)://([-a-zA-Z0-9.]*@)(.*)$',
                        path)
        if m2:
            path = '%s://%s' % (m2.group(1), m2.group(3))

        m = re.search(r'^URL: (.+)$', svn_info, re.M)

        if not m:
            return None

        base_path = m.group(1)[len(path):] or "/"
        return RepositoryInfo(path=path, base_path=base_path,
                              supports_parent_diffs=True)

    @property
    def hg_root(self):

        if not self._hg_root:
            root = self.util.execute(['hg', 'root'], env=self._hg_env,
                           ignore_errors=True)

            if not root.startswith('abort:'):
                self._hg_root = root.strip()
            else:
                self._hg_root = '.'

        return self._hg_root

    def _load_hgrc(self):
        for line in self.util.execute(['hg', 'showconfig'], split_lines=True):
            key, value = line.split('=', 1)
            self.hgrc[key] = value.strip()

    def extract_summary(self, revision):
        """
        Extracts the first line from the description of the given changeset.
        """
        return self.util.execute(['hg', 'log', '-r%s' % revision, '--template',
                        r'{desc|firstline}\n'], env=self._hg_env)

    def extract_description(self, rev1, rev2):
        """
        Extracts all descriptions in the given revision range and concatenates
        them, most recent ones going first.
        """
        numrevs = len(self.util.execute([
            'hg', 'log', '-r%s:%s' % (rev2, rev1),
            '--follow', '--template', r'{rev}\n'], env=self._hg_env
        ).strip().split('\n'))

        return self.util.execute(['hg', 'log', '-r%s:%s' % (rev2, rev1),
                        '--follow', '--template',
                        r'{desc}\n\n', '--limit',
                        str(numrevs - 1)], env=self._hg_env).strip()

    def diff(self, files):
        """
        Performs a diff across all modified files in a Mercurial repository.
        """
        files = files or []

        if self._type == 'svn':
            return self._get_hgsubversion_diff(files)
        else:
            return self._get_outgoing_diff(files)

    def _get_hgsubversion_diff(self, files):
        parent = self.util.execute(['hg', 'parent', '--svn', '--template',
                          '{node}\n']).strip()

        return (self.util.execute(["hg", "diff", "--svn", \
                                    '-r%s:.' % parent]), None)

    def _get_outgoing_diff(self, files):
        """
        When working with a clone of a Mercurial remote, we need to find
        out what the outgoing revisions are for a given branch.  It would
        be nice if we could just do `hg outgoing --patch <remote>`, but
        there are a couple of problems with this.

        For one, the server-side diff parser isn't yet equipped to filter out
        diff headers such as "comparing with..." and "changeset: <rev>:<hash>".
        Another problem is that the output of `outgoing` potentially includes
        changesets across multiple branches.

        In order to provide the most accurate comparison between one's local
        clone and a given remote -- something akin to git's diff command syntax
        `git diff <treeish>..<treeish>` -- we have to do the following:

            - get the name of the current branch
            - get a list of outgoing changesets, specifying a custom format
            - filter outgoing changesets by the current branch name
            - get the "top" and "bottom" outgoing changesets
            - use these changesets as arguments to `hg diff -r <rev> -r <rev>`


        Future modifications may need to be made to account for odd cases like
        having multiple diverged branches which share partial history -- or we
        can just punish developers for doing such nonsense :)
        """
        files = files or []

        remote = self._remote_path[0]

        current_branch = self.util.execute(['hg', 'branch'], \
                                            env=self._hg_env).strip()

        outgoing_changesets = \
            self._get_outgoing_changesets(current_branch, remote)

        top_rev, bottom_rev = \
            self._get_top_and_bottom_outgoing_revs(outgoing_changesets)

        full_command = ['hg', 'diff', '-r', str(bottom_rev), '-r',
                        str(top_rev)] + files

        return (self.util.execute(full_command, env=self._hg_env), None)

    def _get_outgoing_changesets(self, current_branch, remote):
        """
        Given the current branch name and a remote path, return a list
        of outgoing changeset numbers.
        """
        outgoing_changesets = []
        raw_outgoing = self.util.execute(['hg', '-q', 'outgoing', '--template',
                                'b:{branches}\nr:{rev}\n\n', remote],
                               env=self._hg_env)

        for pair in raw_outgoing.split('\n\n'):

            if not pair.strip():
                continue

            branch, rev = pair.strip().split('\n')

            branch_name = branch[len('b:'):].strip()
            branch_name = branch_name or 'default'
            revno = rev[len('r:'):]

            if branch_name == current_branch and revno.isdigit():
                #debug('Found outgoing changeset %s for branch %r'
                 #     % (revno, branch_name))
                outgoing_changesets.append(int(revno))

        return outgoing_changesets

    def _get_top_and_bottom_outgoing_revs(cls, outgoing_changesets):
        # This is a classmethod rather than a func mostly just to keep the
        # module namespace clean.  Pylint told me to do it.
        top_rev = max(outgoing_changesets)
        bottom_rev = min(outgoing_changesets)
        bottom_rev = max([0, bottom_rev - 1])

        return top_rev, bottom_rev

    # postfix decorators to stay pre-2.5 compatible
    _get_top_and_bottom_outgoing_revs = \
        classmethod(_get_top_and_bottom_outgoing_revs)

    def diff_between_revisions(self, revision_range, args, repository_info):
        """
        Performs a diff between 2 revisions of a Mercurial repository.
        """

        if self._type != 'hg':
            raise NotImplementedError

        r1, r2 = revision_range.split(':')

        return self.util.execute(["hg", "diff", "-r", r1, "-r", r2],
                       env=self._hg_env)

    def scan_for_server(self, repository_info):
        # Scan first for dot files, since it's faster and will cover the
        # user's $HOME/.reviewboardrc
        server_url = \
            super(MercurialRepository, self).scan_for_server(repository_info)

        if not server_url and self.hgrc.get('reviewboard.url'):
            server_url = self.hgrc.get('reviewboard.url').strip()

        if not server_url and self._type == "svn":
            # Try using the reviewboard:url property on the SVN repo, if it
            # exists.
            prop = SVNRepository().scan_for_server_property(repository_info)

            if prop:
                return prop

        return server_url