"""A client for ClearCase."""

from __future__ import unicode_literals

import datetime
import itertools
import logging
import os
import re
import sys
import threading
from collections import defaultdict, deque

import six
from pydiffx.dom import DiffX

from rbtools.api.errors import APIError
from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import InvalidRevisionSpecError, SCMError
from rbtools.deprecation import RemovedInRBTools40Warning
from rbtools.utils.checks import check_gnu_diff, check_install
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import execute
from rbtools.utils.repository import get_repository_resource

# This specific import is necessary to handle the paths when running on cygwin.
if sys.platform.startswith(('cygwin', 'win')):
    import ntpath as cpath
else:
    import os.path as cpath


# This is used to split and assemble paths.
_MAIN = '%smain%s' % (os.sep, os.sep)


class _GetElementsFromLabelThread(threading.Thread):
    """A thread to collect results from ``cleartool find``.

    Collecting elements with ``cleartool find`` can take a long time. This
    thread allows us to do multiple finds concurrently.
    """

    def __init__(self, dir_name, label, elements, vob_tags):
        """Initialize the thread.

        Args:
            dir_name (unicode):
                The directory name to search.

            label (unicode):
                The label name.

            elements (dict):
                A dictionary mapping element path to an info dictionary. Each
                element contains ``oid`` and ``version`` keys.

            vob_tags (list of unicode):
                A list of the VOBs to search.
        """
        self.dir_name = dir_name
        self.elements = elements
        self.vob_tags = vob_tags

        # Remove any trailing VOB tag not supported by cleartool find.
        try:
            label, vobtag = label.rsplit('@', 1)
        except Exception:
            pass
        self.label = label

        threading.Thread.__init__(self)

    def run(self):
        """Run the thread.

        This will store a dictionary of ClearCase elements (oid + version)
        belonging to a label and identified by path.
        """
        env = os.environ.copy()

        if sys.platform.startswith('win'):
            CLEARCASE_XPN = '%CLEARCASE_XPN%'
            CLEARCASE_PN = '%CLEARCASE_PN%'
            env['CLEARCASE_AVOBS'] = ';'.join(self.vob_tags)
        else:
            CLEARCASE_XPN = '$CLEARCASE_XPN'
            CLEARCASE_PN = '$CLEARCASE_PN'
            env['CLEARCASE_AVOBS'] = ':'.join(self.vob_tags)

        command = [
            'cleartool',
            'find',
            '-avobs',
        ]

        if self.label is None:
            command += [
                '-version',
                'lbtype(%s)' % self.label,
                '-exec',
                ('cleartool describe -fmt "%%On\t%%En\t%%Vn\n" "%s"'
                 % CLEARCASE_XPN)
            ]
        else:
            command = [
                '-exec',
                ('cleartool describe -fmt "%%On\t%%En\t%%Vn\n" "%s"'
                 % CLEARCASE_PN),
            ]

        output = execute(command,
                         extra_ignore_errors=(1,),
                         with_errors=False,
                         split_lines=True,
                         env=env)

        for line in output:
            # Skip any empty lines.
            if not line:
                continue

            oid, path, version = line.split('\t', 2)
            self.elements[path] = {
                'oid': oid,
                'version': version,
            }


class ChangesetEntry(object):
    """An entry in a changeset.

    This is a helper class which wraps a changed element, and
    centralizes/caches various information about that element's old and new
    revisions.

    Version Added:
        3.0
    """

    def __init__(self, root_path, old_path=None, new_path=None,
                 old_oid=None, new_oid=None, op='modify'):
        """Initialize the changeset entry.

        Args:
            root_path (unicode):
                The root path of the view.

            old_path (unicode, optional):
                The extended path of the "old" version of the element.

            new_path (unicode, optional):
                The extended path of the "new" version of the element.

            old_oid (unicode, optional):
                The OID of the "old" version of the element.

            new_oid (unicode, optional):
                The OID of the "new" version of the element.

            op (unicode, optional):
                The change operation.
        """
        self.root_path = root_path

        self.old_path = old_path
        self._old_name = None
        self._old_oid = old_oid
        self._old_version = None

        self.new_path = new_path
        self._new_name = None
        self._new_oid = new_oid
        self._new_version = None

        self.op = op

    @property
    def old_oid(self):
        """The OID of the old version of the element.

        Type:
            unicode
        """
        if self._old_oid is None:
            if self.old_path:
                self._old_oid = execute(['cleartool', 'describe', '-fmt',
                                         '%On', self.old_path])
            else:
                self._old_oid = '0'

        return self._old_oid

    @property
    def old_name(self):
        """The name of the old version of the element.

        Type:
            unicode:
        """
        if self._old_name is None and self.old_path:
            self._old_name = os.path.relpath(
                execute(['cleartool', 'describe', '-fmt', '%En',
                         self.old_path]),
                self.root_path)

        return self._old_name

    @property
    def old_version(self):
        """The version of the old version of the element.

        Type:
            unicode
        """
        if self._old_version is None and self.old_path:
            self._old_version = execute(['cleartool', 'describe', '-fmt',
                                         '%Vn', 'oid:%s' % self.old_oid])

        return self._old_version

    @property
    def new_oid(self):
        """The OID of the new version of the element.

        Type:
            unicode
        """
        if self._new_oid is None:
            if self.new_path:
                self._new_oid = execute(['cleartool', 'describe', '-fmt',
                                         '%On', self.new_path])
            else:
                self._new_oid = '0'

        return self._new_oid

    @property
    def new_name(self):
        """The name of the new version of the element.

        Type:
            unicode:
        """
        if self._new_name is None and self.new_path:
            self._new_name = os.path.relpath(
                execute(['cleartool', 'describe', '-fmt', '%En',
                         self.new_path]),
                self.root_path)

        return self._new_name

    @property
    def new_version(self):
        if self._new_version is None and self.new_path:
            self._new_version = execute(['cleartool', 'describe', '-fmt',
                                         '%Vn', 'oid:%s' % self.new_oid],
                                        ignore_errors=True,
                                        with_errors=True)

            if 'Not a vob object' in self._new_version:
                self._new_version = 'CHECKEDOUT'

        return self._new_version

    def __repr__(self):
        """Return a representation of the object.

        Returns:
            unicode:
            The internal representation of the object.
        """
        return ('<ChangesetEntry op=%s old_path=%s new_path=%s>'
                % (self.op, self.old_path, self.new_path))


class ClearCaseClient(SCMClient):
    """A client for ClearCase.

    This is a wrapper around the clearcase tool that fetches repository
    information and generates compatible diffs. This client assumes that cygwin
    is installed on Windows.
    """

    name = 'ClearCase'
    server_tool_names = 'ClearCase,VersionVault / ClearCase'
    supports_patch_revert = True

    REVISION_ACTIVITY_BASE = '--rbtools-activity-base'
    REVISION_ACTIVITY_PREFIX = 'activity:'
    REVISION_BASELINE_BASE = '--rbtools-baseline-base'
    REVISION_BASELINE_PREFIX = 'baseline:'
    REVISION_BRANCH_BASE = '--rbtools-branch-base'
    REVISION_BRANCH_PREFIX = 'brtype:'
    REVISION_CHECKEDOUT_BASE = '--rbtools-checkedout-base'
    REVISION_CHECKEDOUT_CHANGESET = '--rbtools-checkedout-changeset'
    REVISION_FILES = '--rbtools-files'
    REVISION_LABEL_BASE = '--rbtools-label-base'
    REVISION_LABEL_PREFIX = 'lbtype:'
    REVISION_STREAM_BASE = '--rbtools-stream-base'
    REVISION_STREAM_PREFIX = 'stream:'

    CHECKEDOUT_RE = re.compile(r'CHECKEDOUT(\.\d+)?$')

    def __init__(self, **kwargs):
        """Initialize the client.

        Args:
            **kwargs (dict):
                Keyword arguments to pass through to the superclass.
        """
        super(ClearCaseClient, self).__init__(**kwargs)
        self.viewtype = None
        self.viewname = None
        self.is_ucm = False
        self.vobtag = None
        self.host_properties = self._get_host_info()

    def get_local_path(self):
        """Return the local path to the working tree.

        Returns:
            unicode:
            The filesystem path of the repository on the client system.
        """
        if not check_install(['cleartool', 'help']):
            logging.debug('Unable to execute "cleartool help": skipping '
                          'ClearCase')
            return None

        # Bail out early if we're not in a view.
        self.viewname = execute(['cleartool', 'pwv', '-short']).strip()

        if self.viewname.startswith('** NONE'):
            return None


        # Get the root path of the view.
        self.root_path = execute(['cleartool', 'pwv', '-root'],
                                 ignore_errors=True).strip()

        if 'Error: ' in self.root_path:
            raise SCMError('Failed to generate diff run rbt inside view.')

        vobtag = self._get_vobtag()

        return os.path.join(self.root_path, vobtag)

    def get_repository_info(self):
        """Return repository information for the current working tree.

        Returns:
            ClearCaseRepositoryInfo:
            The repository info structure.
        """
        local_path = self.get_local_path()

        if not local_path:
            return None

        # Now that we know it's ClearCase, make sure we have GNU diff
        # installed, and error out if we don't.
        check_gnu_diff()

        property_lines = execute(
            ['cleartool', 'lsview', '-full', '-properties', '-cview'],
            split_lines=True)

        for line in property_lines:
            properties = line.split(' ')

            if properties[0] == 'Properties:':
                # Determine the view type and check if it's supported.
                if 'automatic' in properties or 'webview' in properties:
                    # These are checked first because automatic views and
                    # webviews with both also list "snapshot", but won't be
                    # usable as a snapshot view.
                    raise SCMError('Webviews and automatic views are not '
                                   'currently supported. RBTools commands can '
                                   'only be used in dynamic or snapshot '
                                   'views.')
                elif 'snapshot' in properties:
                    self.viewtype = 'snapshot'
                elif 'dynamic' in properties:
                    self.viewtype = 'dynamic'
                else:
                    raise SCMError('Unable to determine the view type. '
                                   'RBTools commands can only be used in '
                                   'dynamic or snapshot views.')

                self.is_ucm = 'ucmview' in properties

                break

        return ClearCaseRepositoryInfo(path=local_path,
                                       vobtag=self._get_vobtag(),
                                       tool=self)

    def find_matching_server_repository(self, repositories):
        """Find a match for the repository on the server.

        Args:
            repositories (rbtools.api.resource.ListResource):
                The fetched repositories.

        Returns:
            tuple:
            A 2-tuple of :py:class:`~rbtools.api.resource.ItemResource`. The
            first item is the matching repository, and the second is the
            repository info resource.
        """
        vobtag = self._get_vobtag()
        uuid = self._get_vob_uuid(vobtag)

        # To reduce calls to fetch the repository info resource (which can be
        # expensive to compute on the server and isn't cacheable), we build an
        # ordered list of ClearCase repositories starting with the ones that
        # have a similar vobtag.
        repository_scan_order = deque()

        # Because the VOB tag is platform-specific, we split and search for the
        # remote name in any sub-part so the request optimiziation can work for
        # users on both Windows and Unix-like platforms.
        vobtag_parts = vobtag.split(cpath.sep)

        for repository in repositories.all_items:
            repo_name = repository['name']

            # Repositories with a name similar to the VOB tag get put at the
            # beginning, and others at the end.
            if repo_name == vobtag or repo_name in vobtag_parts:
                repository_scan_order.appendleft(repository)
            else:
                repository_scan_order.append(repository)

        # Now scan through and look for a repository with a matching UUID.
        for repository in repository_scan_order:
            try:
                info = repository.get_info()
            except APIError:
                continue

            if not info:
                continue

            # There are two possibilities here. The ClearCase SCMTool shipped
            # with Review Board is now considered a legacy implementation, and
            # supports a single VOB (the "uuid" case). The new VersionVault
            # tool (which supports IBM ClearCase as well) ships with Power
            # Pack, and supports multiple VOBs (the "uuids" case).
            if (('uuid' in info and uuid == info['uuid']) or
                ('uuids' in info and uuid in info['uuids'])):
                return repository, info

        return None, None

    def parse_revision_spec(self, revisions):
        """Parse the given revision spec.

        Args:
            revisions (list of unicode, optional):
                A list of revisions as specified by the user. Items in the list
                do not necessarily represent a single revision, since the user
                can use SCM-native syntaxes such as ``r1..r2`` or ``r1:r2``.
                SCMTool-specific overrides of this method are expected to deal
                with such syntaxes.

        Raises:
            rbtools.clients.errors.InvalidRevisionSpecError:
                The given revisions could not be parsed.

            rbtools.clients.errors.TooManyRevisionsError:
                The specified revisions list contained too many revisions.

        Returns:
            dict:
            A dictionary with the following keys:

            ``base`` (:py:class:`unicode`):
                A revision to use as the base of the resulting diff.

            ``tip`` (:py:class:`unicode`):
                A revision to use as the tip of the resulting diff.

            These will be used to generate the diffs to upload to Review Board
            (or print).

            There are many different ways to generate diffs for clearcase,
            because there are so many different workflows. This method serves
            more as a way to validate the passed-in arguments than actually
            parsing them in the way that other clients do.
        """
        n_revs = len(revisions)

        if n_revs == 0:
            return {
                'base': self.REVISION_CHECKEDOUT_BASE,
                'tip': self.REVISION_CHECKEDOUT_CHANGESET,
            }
        elif n_revs == 1:
            revision = revisions[0]

            if revision.startswith(self.REVISION_ACTIVITY_PREFIX):
                return {
                    'base': self.REVISION_ACTIVITY_BASE,
                    'tip': revision[len(self.REVISION_ACTIVITY_PREFIX):],
                }
            elif revision.startswith(self.REVISION_BASELINE_PREFIX):
                tip = revision[len(self.REVISION_BASELINE_PREFIX):]

                if len(tip.rsplit('@', 1)) != 2:
                    raise InvalidRevisionSpecError(
                        'Baseline name %s must include a PVOB tag' % tip)

                return {
                    'base': self.REVISION_BASELINE_BASE,
                    'tip': [tip],
                }
            elif revision.startswith(self.REVISION_BRANCH_PREFIX):
                return {
                    'base': self.REVISION_BRANCH_BASE,
                    'tip': revision[len(self.REVISION_BRANCH_PREFIX):],
                }
            elif revision.startswith(self.REVISION_LABEL_PREFIX):
                return {
                    'base': self.REVISION_LABEL_BASE,
                    'tip': [revision[len(self.REVISION_BRANCH_PREFIX):]],
                }
            elif revision.startswith(self.REVISION_STREAM_PREFIX):
                tip = revision[len(self.REVISION_STREAM_PREFIX):]

                if len(tip.rsplit('@', 1)) != 2:
                    raise InvalidRevisionSpecError(
                        'UCM stream name %s must include a PVOB tag' % tip)

                return {
                    'base': self.REVISION_STREAM_BASE,
                    'tip': tip,
                }
        elif n_revs == 2:
            if self.viewtype != 'dynamic':
                raise SCMError('To generate a diff using multiple revisions, '
                               'you must use a dynamic view.')

            if (revisions[0].startswith(self.REVISION_BASELINE_PREFIX) and
                revisions[1].startswith(self.REVISION_BASELINE_PREFIX)):
                tips = [
                    revision[len(self.REVISION_BASELINE_PREFIX):]
                    for revision in revisions
                ]

                pvobs = []

                for tip in tips:
                    try:
                        pvobs.append(tip.rsplit('@', 1)[1])
                    except KeyError:
                        raise InvalidRevisionSpecError(
                            'Baseline name %s must include a PVOB tag' % tip)

                if pvobs[0] != pvobs[1]:
                    raise InvalidRevisionSpecError(
                        'Baselines %s and %s do not have the same PVOB tag'
                        % (pvobs[0], pvobs[1]))

                return {
                    'base': self.REVISION_BASELINE_BASE,
                    'tip': tips,
                }
            elif (revisions[0].startswith(self.REVISION_LABEL_PREFIX) and
                  revisions[1].startswith(self.REVISION_LABEL_PREFIX)):
                return {
                    'base': self.REVISION_LABEL_BASE,
                    'tip': [
                        revision[len(self.REVISION_BRANCH_PREFIX):]
                        for revision in revisions
                    ],
                }

        # None of the "special" types have been found. Assume that the list of
        # items are one or more pairs of files to compare.
        pairs = []
        for r in revisions:
            p = r.split(':')

            if len(p) != 2:
                raise InvalidRevisionSpecError(
                    '"%s" is not a valid file@revision pair' % r)

            pairs.append(p)

        return {
            'base': self.REVISION_FILES,
            'tip': pairs,
        }

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             repository_info=None, extra_args=[], **kwargs):
        """Perform a diff using the given revisions.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

            include_files (list of unicode, optional):
                A list of files to whitelist during the diff generation.

            exclude_patterns (list of unicode, optional):
                A list of shell-style glob patterns to blacklist during diff
                generation.

            repository_info (ClearCaseRepositoryInfo, optional):
                The repository info structure.

            extra_args (list, unused):
                Additional arguments to be passed to the diff generation.
                Unused for ClearCase.

            **kwargs (dict, optional):
                Unused keyword arguments.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.
        """
        if include_files:
            raise SCMError(
                'The ClearCase backend does not currently support the '
                '-I/--include parameter. To diff for specific files, pass in '
                'file@revision1:file@revision2 pairs as arguments')

        base = revisions['base']
        tip = revisions['tip']

        if tip == self.REVISION_CHECKEDOUT_CHANGESET:
            changeset = self._get_checkedout_changeset(repository_info)
        elif base == self.REVISION_ACTIVITY_BASE:
            changeset = self._get_activity_changeset(tip, repository_info)
        elif base == self.REVISION_BASELINE_BASE:
            changeset = self._get_baseline_changeset(tip)
        elif base == self.REVISION_BRANCH_BASE:
            changeset = self._get_branch_changeset(tip, repository_info)
        elif base == self.REVISION_LABEL_BASE:
            changeset = self._get_label_changeset(tip, repository_info)
        elif base == self.REVISION_STREAM_BASE:
            changeset = self._get_stream_changeset(tip, repository_info)
        elif base == self.REVISION_FILES:
            changeset = tip
        else:
            assert False

        metadata = self._get_diff_metadata(revisions)

        return self._do_diff(changeset, repository_info, metadata)

    def _get_vobtag(self):
        """Return the current repository's VOB tag.

        Returns:
            unicode:
            The VOB tag for the current working directory.

        Raises:
            rbtools.clients.errors.SCMError:
                The VOB tag was unable to be determined.
        """
        if not self.vobtag:
            self.vobtag = execute(['cleartool', 'describe', '-short', 'vob:.'],
                                  ignore_errors=True).strip()

            if 'Error: ' in self.vobtag:
                raise SCMError('Unable to determine the current VOB. Make '
                               'sure to run RBTools from within your '
                               'ClearCase view.')

        return self.vobtag

    def _get_vob_uuid(self, vobtag):
        """Return the current VOB's UUID.

        Args:
            vobtag (unicode):
                The VOB tag to query.

        Returns:
            unicode:
            The VOB UUID.

        Raises:
            rbtools.clients.errors.SCMError:
                The current VOB tag was unable to be determined.
        """
        property_lines = execute(
            ['cleartool', 'lsvob', '-long', vobtag],
            split_lines=True)

        for line in property_lines:
            if line.startswith('Vob family uuid:'):
                return line.split(' ')[-1].rstrip()

        return None

    def _list_checkedout(self, path):
        """List all checked out elements in current view below path.

        Run the :command:`cleartool` command twice because ``recurse`` finds
        checked out elements under path except path, and the directory is
        detected only if the path directory is checked out.

        Args:
            path (unicode):
                The path of the directory to find checked-out files in.

        Returns:
            list of unicode:
            A list of the checked out files.
        """
        checkedout_elements = []

        for option in ['-recurse', '-directory']:
            # We ignore return code 1 in order to omit files that ClearCase
            # cannot read.
            output = execute(['cleartool', 'lscheckout', option, '-cview',
                              '-fmt', r'%En@@%Vn\n', path],
                             split_lines=True,
                             extra_ignore_errors=(1,),
                             with_errors=False)

            if output:
                checkedout_elements.extend(output)
                logging.debug(output)

        return checkedout_elements

    def _is_a_label(self, label, vobtag=None):
        """Return whether a given label is a valid ClearCase lbtype.

        Args:
            label (unicode):
                The label to check.

            vobtag (unicode, optional):
                An optional VOB tag to limit the label to.

        Raises:
            rbtools.clients.errors.SCMError:
                The VOB tag did not match.

        Returns:
            bool:
            Whether the label was valid.
        """
        label_vobtag = None

        # Try to find any vobtag.
        try:
            label, label_vobtag = label.rsplit('@', 1)
        except Exception:
            pass

        # Be sure label is prefix by lbtype, required by cleartool describe.
        if not label.startswith(self.REVISION_LABEL_PREFIX):
            label = '%s%s' % (self.REVISION_LABEL_PREFIX, label)

        # If vobtag defined, check if it matches with the one extracted from
        # label, otherwise raise an exception.
        if vobtag and label_vobtag and label_vobtag != vobtag:
            raise SCMError('label vobtag %s does not match expected vobtag '
                           '%s' % (label_vobtag, vobtag))

        # Finally check if label exists in database, otherwise quit. Ignore
        # return code 1, it means label does not exist.
        output = execute(['cleartool', 'describe', '-short', label],
                         extra_ignore_errors=(1,),
                         with_errors=False)
        return bool(output)

    def _get_tmp_label(self):
        """Return a string that will be used to set a ClearCase label.

        Returns:
            unicode:
            A string suitable for using as a temporary label.
        """
        now = datetime.datetime.now()
        temporary_label = 'Current_%d_%d_%d_%d_%d_%d_%d' % (
            now.year, now.month, now.day, now.hour, now.minute, now.second,
            now.microsecond)
        return temporary_label

    def _set_label(self, label, path):
        """Set a ClearCase label on elements seen under path.

        Args:
            label (unicode):
                The label to set.

            path (unicode):
                The filesystem path to set the label on.
        """
        checkedout_elements = self._list_checkedout(path)
        if checkedout_elements:
            raise SCMError(
                'ClearCase backend cannot set label when some elements are '
                'checked out:\n%s' % ''.join(checkedout_elements))

        # First create label in vob database.
        execute(['cleartool', 'mklbtype', '-c', 'label created for rbtools',
                 label],
                with_errors=True)

        # We ignore return code 1 in order to omit files that ClearCase cannot
        # read.
        recursive_option = ''
        if cpath.isdir(path):
            recursive_option = '-recurse'

        # Apply label to path.
        execute(['cleartool', 'mklabel', '-nc', recursive_option, label, path],
                extra_ignore_errors=(1,),
                with_errors=False)

    def _remove_label(self, label):
        """Remove a ClearCase label from vob database.

        It will remove all references of this label on elements.

        Args:
            label (unicode):
                The ClearCase label to remove.
        """
        # Be sure label is prefix by lbtype.
        if not label.startswith(self.REVISION_LABEL_PREFIX):
            label = '%s%s' % (self.REVISION_LABEL_PREFIX, label)

        # Label exists so remove it.
        execute(['cleartool', 'rmtype', '-rmall', '-force', label],
                with_errors=True)

    def _determine_version(self, version_path):
        """Determine the numeric version of a version path.

        This will split a version path, pulling out the branch and version. A
        special version value of ``CHECKEDOUT`` represents the latest version
        of a file, similar to ``HEAD`` in many other types of repositories.

        Args:
            version_path (unicode):
                A version path consisting of a branch path and a version
                number.

        Returns:
            int:
            The numeric portion of the version path.
        """
        branch, number = cpath.split(version_path)

        if self.CHECKEDOUT_RE.search(number):
            return sys.maxsize

        return int(number)

    def _construct_extended_path(self, path, version):
        """Construct an extended path from a file path and version identifier.

        This will construct a path in the form of ``path@version``. If the
        version is the special value ``CHECKEDOUT``, only the path will be
        returned.

        Args:
            path (unicode):
                A file path.

            version (unicode):
                The version of the file.

        Returns:
            unicode:
            The combined extended path.
        """
        if not version or self.CHECKEDOUT_RE.search(version):
            return path

        return '%s@@%s' % (path, version)

    def _construct_revision(self, branch_path, version_number):
        """Construct a revisioned path from a branch path and version ID.

        Args:
            branch_path (unicode):
                The path of a branch.

            version_number (unicode):
                The version number of the revision.

        Returns:
            unicode:
            The combined revision.
        """
        return cpath.join(branch_path, version_number)

    def _get_previous_version(self, path, branch_path, version_number):
        """Return the previous version for a ClearCase versioned element.

        The previous version of an element can usually be found by simply
        decrementing the version number at the end of an extended path, but it
        is possible to use `cleartool rmver` to remove individual versions.
        This method will query ClearCase for the predecessor version.

        Args:
            path (unicode):
                The path to an element.

            branch_path (unicode):
                The path of the branch of the element (typically something like
                /main/).

            version_number (int):
                The version number of the element.

        Returns:
            tuple:
            A 2-tuple consisting of the predecessor branch path and version
            number.
        """
        full_version = cpath.join(branch_path, '%d' % version_number)
        extended_path = '%s@@%s' % (path, full_version)

        previous_version = execute(
            ['cleartool', 'desc', '-fmt', '%[version_predecessor]p',
             extended_path],
            ignore_errors=True).strip()

        if 'Error' in previous_version:
            raise SCMError('Unable to find the predecessor version for %s'
                           % extended_path)

        return cpath.split(previous_version)

    def _sanitize_activity_changeset(self, changeset, repository_info):
        """Return changeset containing non-binary, branched file versions.

        A UCM activity changeset contains all file revisions created/touched
        during this activity. File revisions are ordered earlier versions first
        in the format::

            changelist = [
                '<path>@@<branch_path>/<version_number>',
                '<path>@@<branch_path>/<version_number>',
                ...
            ]

        ``<path>`` is relative path to file
        ``<branch_path>`` is clearcase specific branch path to file revision
        ``<version number>`` is the version number of the file in branch_path

        Args:
            changeset (unicode):
                The changeset to fetch.

            repository_info (rbtools.clients.RepositoryInfo):
                The repository info structure.

        Returns:
            list:
            The list of file versions.
        """
        changelist = {}
        ignored_changes = []
        changeset = list(changeset)

        for change in changeset:
            # Split from the right on /main/, just in case some directory
            # elements are reported with a different version.
            path, current = change.rsplit(_MAIN, 1)

            if path.endswith('@@'):
                path = path[:-2]

            current = _MAIN + current

            # If a file isn't in the correct vob, then ignore it.
            for tag in repository_info.vob_tags:
                if ('%s/' % tag) in path:
                    break
            else:
                logging.debug('VOB tag does not match, ignoring changes on %s',
                              path)
                ignored_changes.append(change)
                continue

            version_number = self._determine_version(current)

            if version_number == 0:
                logging.warning('Unexpected version 0 for %s in activity '
                                'changeset. Did you rmver the first version, '
                                'or forget to check it in? This file will '
                                'be ignored.'
                                % path)
                ignored_changes.append(change)
                continue

            if path not in changelist:
                changelist[path] = {
                    'highest': version_number,
                    'lowest': version_number,
                    'current': current,
                }

            if version_number > changelist[path]['highest']:
                changelist[path]['highest'] = version_number
                changelist[path]['current'] = current
            elif version_number < changelist[path]['lowest']:
                changelist[path]['lowest'] = version_number

        if ignored_changes:
            print('The following elements from this change set are not part '
                  'of the currently configured repository, and will be '
                  'ignored:')

            for change in ignored_changes:
                print(change)

            print()

        # Convert to list
        changeranges = []

        for path, version in six.iteritems(changelist):
            current_version = version['current']
            branch_path, current_version_number = cpath.split(current_version)

            lowest_version = version['lowest']

            if lowest_version == sys.maxsize:
                # This is a new file.
                prev_version_number = '0'
            else:
                # Query for the previous version, just in case an old revision
                # was removed.
                branch_path, prev_version_number = self._get_previous_version(
                    path, branch_path, lowest_version)

            previous_version = self._construct_revision(branch_path,
                                                        prev_version_number)

            changeranges.append(
                (self._construct_extended_path(path, previous_version),
                 self._construct_extended_path(path, current_version))
            )

        return changeranges

    def _sanitize_branch_changeset(self, changeset):
        """Return changeset containing non-binary, branched file versions.

        Changeset contain only first and last version of file made on branch.

        Args:
            changeset (unicode):
                The changeset to fetch.

        Returns:
            list:
            The list of file versions.
        """
        changelist = {}

        for path, previous, current in changeset:
            version_number = self._determine_version(current)

            if path not in changelist:
                changelist[path] = {
                    'highest': version_number,
                    'current': current,
                    'previous': previous
                }

            if version_number == 0:
                # Previous version of 0 version on branch is base
                changelist[path]['previous'] = previous
            elif version_number > changelist[path]['highest']:
                changelist[path]['highest'] = version_number
                changelist[path]['current'] = current

        # Convert to list
        changeranges = []
        for path, version in six.iteritems(changelist):
            changeranges.append(
                (self._construct_extended_path(path, version['previous']),
                 self._construct_extended_path(path, version['current']))
            )

        return changeranges

    def _sanitize_checkedout_changeset(self, changeset):
        """Return extended paths for all modifications in a changeset.

        Args:
            changeset (unicode):
                The changeset to fetch.

        Returns:
            list:
            The list of file versions.
        """
        changeranges = []

        for path, previous, current in changeset:
            changeranges.append(
                (self._construct_extended_path(path, previous),
                 self._construct_extended_path(path, current))
            )

        return changeranges

    def _sanitize_version_0_file(self, file_revision):
        """Sanitize a version 0 file.

        This fixes up a revision identifier to use the correct predecessor
        revision when the version is 0. ``/main/0`` is a special case which is
        left as-is.

        Args:
            file_revision (unicode):
                The file revision to sanitize.

        Returns:
            unicode:
            The sanitized revision.
        """
        # There is no predecessor for @@/main/0, so keep current revision.
        if file_revision.endswith('%s0' % _MAIN):
            return file_revision

        if file_revision.endswith('%s0' % os.sep):
            logging.debug('Found file %s with version 0', file_revision)
            file_revision = execute(['cleartool',
                                     'describe',
                                     '-fmt', '%En@@%PSn',
                                     file_revision])
            logging.debug('Sanitized with predecessor, new file: %s',
                          file_revision)

        return file_revision

    def _sanitize_version_0_changeset(self, changeset):
        """Return changeset sanitized of its <branch>/0 version.

        Indeed this predecessor (equal to <branch>/0) should already be
        available from previous vob synchro in multi-site context.

        Args:
            changeset (list):
                A list of changes in the changeset.

        Returns:
            list:
            The sanitized changeset.
        """
        sanitized_changeset = []

        for old_file, new_file in changeset:
            # This should not happen for new file but it is safer to sanitize
            # both file revisions.
            sanitized_changeset.append(
                (self._sanitize_version_0_file(old_file),
                 self._sanitize_version_0_file(new_file)))

        return sanitized_changeset

    def _construct_changeset(self, output):
        """Construct a changeset from cleartool output.

        Args:
            output (unicode):
                The result from a :command:`cleartool lsX` operation.

        Returns:
            list:
            A list of changes.
        """
        return [
            info.split('\t')
            for info in output.strip().split('\n')
        ]

    def _get_checkedout_changeset(self, repository_info):
        """Return information about the checked out changeset.

        This function returns: kind of element, path to file, previous and
        current file version.

        Args:
            repository_info (rbtools.clients.RepositoryInfo):
                The repository info structure.

        Returns:
            list:
            A list of the changed files.
        """
        env = os.environ.copy()

        if sys.platform.startswith('win'):
            env['CLEARCASE_AVOBS'] = ';'.join(repository_info.vob_tags)
        else:
            env['CLEARCASE_AVOBS'] = ':'.join(repository_info.vob_tags)

        # We ignore return code 1 in order to omit files that ClearCase can't
        # read.
        output = execute(
            [
                'cleartool',
                'lscheckout',
                '-avobs',
                '-cview',
                '-me',
                '-fmt',
                r'%En\t%PVn\t%Vn\n',
            ],
            extra_ignore_errors=(1,),
            with_errors=False,
            env=env)

        if output:
            changeset = self._construct_changeset(output)
        else:
            changeset = []

        return self._sanitize_checkedout_changeset(changeset)

    def _get_activity_changeset(self, activity, repository_info):
        """Return information about the versions changed on a branch.

        This takes into account the changes attached to this activity
        (including rebase changes) in all vobs of the current view.

        Args:
            activity (unicode):
                The activity name.

            repository_info (rbtools.clients.RepositoryInfo):
                The repository info structure.

        Returns:
            list:
            A list of the changed files.
        """
        changeset = []

        # Get list of revisions and get the diff of each one. Return code 1 is
        # ignored in order to omit files that ClearCase can't read.
        output = execute(['cleartool',
                          'lsactivity',
                          '-fmt',
                          '%[versions]Qp',
                          activity],
                         extra_ignore_errors=(1,),
                         with_errors=False)

        if output:
            # UCM activity changeset with %[versions]Qp is split by spaces but
            # not EOL, so we cannot reuse self._construct_changeset here.
            # However, since each version is enclosed in double quotes, we can
            # split and consolidate the list.
            changeset = filter(None, [x.strip() for x in output.split('"')])

        return self._sanitize_activity_changeset(changeset, repository_info)

    def _get_baseline_changeset(self, baselines):
        """Return information about versions changed between two baselines.

        Args:
            baselines (list of unicode):
                A list of one or two baselines including PVOB tags. If one
                baseline is included, this will do a diff between that and the
                predecessor baseline.

        Returns:
            list:
            A list of the changed files.
        """
        command = [
            'cleartool',
            'diffbl',
            '-version',
        ]

        if len(baselines) == 1:
            command += [
                '-predecessor',
                'baseline:%s' % baselines[0],
            ]
        else:
            command += [
                'baseline:%s' % baselines[0],
                'baseline:%s' % baselines[1],
            ]

        diff = execute(command,
                       extra_ignore_errors=(1, 2),
                       splitlines=True)

        WS_RE = re.compile(r'\s+')
        versions = [
            WS_RE.split(line.strip(), 1)[1]
            for line in diff
            if line.startswith(('>>', '<<'))
        ]

        version_info = filter(None, [
            execute(
                [
                    'cleartool',
                    'describe',
                    '-fmt',
                    '%En\t%PVn\t%Vn\n',
                    version,
                ],
                extra_ignore_errors=(1,),
                results_unicode=True)
            for version in versions
        ])

        changeset = self._construct_changeset(''.join(version_info))

        return self._sanitize_branch_changeset(changeset)

    def _get_branch_changeset(self, branch, repository_info):
        """Return information about the versions changed on a branch.

        This takes into account the changes on the branch owned by the
        current user in all vobs of the current view.

        Args:
            branch (unicode):
                The branch name.

            repository_info (rbtools.clients.RepositoryInfo):
                The repository info structure.

        Returns:
            list:
            A list of the changed files.
        """
        env = os.environ.copy()

        if sys.platform.startswith('win'):
            CLEARCASE_XPN = '%CLEARCASE_XPN%'
            env['CLEARCASE_AVOBS'] = ';'.join(repository_info.vob_tags)
        else:
            CLEARCASE_XPN = '$CLEARCASE_XPN'
            env['CLEARCASE_AVOBS'] = ':'.join(repository_info.vob_tags)

        # We ignore return code 1 in order to omit files that ClearCase can't
        # read.
        output = execute(
            [
                'cleartool',
                'find',
                '-avobs',
                '-version',
                'brtype(%s)' % branch,
                '-exec',
                ('cleartool descr -fmt "%%En\t%%PVn\t%%Vn\n" "%s"'
                 % CLEARCASE_XPN),
            ],
            extra_ignore_errors=(1,),
            with_errors=False,
            env=env)

        if output:
            changeset = self._construct_changeset(output)
        else:
            changeset = []

        return self._sanitize_branch_changeset(changeset)

    def _get_label_changeset(self, labels, repository_info):
        """Return information about the versions changed between labels.

        This takes into account the changes done between labels and restrict
        analysis to current working directory. A ClearCase label belongs to a
        unique vob.

        Args:
            labels (list):
                A list of labels to compare.

            repository_info (rbtools.clients.RepositoryInfo):
                The repository info structure.

        Returns:
            list:
            A list of the changed files.
        """
        changeset = []

        # Initialize comparison_path to current working directory.
        # TODO: support another argument to manage a different comparison path.
        comparison_path = os.getcwd()

        error_message = None

        try:
            if len(labels) == 1:
                labels.append('LATEST')

            assert len(labels) == 2

            matched_vobs = set()

            for tag in repository_info.vob_tags:
                labels_present = True

                for label in labels:
                    if label != 'LATEST' and not self._is_a_label(label, tag):
                        labels_present = False

                if labels_present:
                    matched_vobs.add(tag)

            if not matched_vobs:
                raise SCMError(
                    'Label %s was not found in any of the configured VOBs'
                    % label)

            previous_label, current_label = labels
            logging.debug('Comparison between labels %s and %s on %s',
                          previous_label, current_label, comparison_path)

            # List ClearCase element path and version belonging to previous and
            # current labels, element path is the key of each dict.
            previous_elements = {}
            current_elements = {}
            previous_label_elements_thread = _GetElementsFromLabelThread(
                comparison_path,
                previous_label,
                previous_elements,
                matched_vobs)
            previous_label_elements_thread.start()

            current_label_elements_thread = _GetElementsFromLabelThread(
                comparison_path,
                current_label,
                current_elements,
                matched_vobs)
            current_label_elements_thread.start()

            previous_label_elements_thread.join()
            current_label_elements_thread.join()

            seen = set()
            changelist = {}

            # Iterate on each ClearCase path in order to find respective
            # previous and current version.
            for path in itertools.chain(previous_elements.keys(),
                                        current_elements.keys()):
                if path in seen:
                    continue

                seen.add(path)

                # Initialize previous and current version to '/main/0'
                main0 = '%s0' % _MAIN
                changelist[path] = {
                    'current': main0,
                    'previous': main0,
                }

                if path in current_elements:
                    changelist[path]['current'] = \
                        current_elements[path]['version']

                if path in previous_elements:
                    changelist[path]['previous'] = \
                        previous_elements[path]['version']

                logging.debug('path: %s\nprevious: %s\ncurrent:  %s\n',
                              path,
                              changelist[path]['previous'],
                              changelist[path]['current'])

                # Prevent adding identical version to comparison.
                if changelist[path]['current'] == changelist[path]['previous']:
                    continue

                changeset.append(
                    (self._construct_extended_path(
                        path,
                        changelist[path]['previous']),
                     self._construct_extended_path(
                        path,
                        changelist[path]['current'])))

        except Exception as e:
            error_message = str(e)

            if error_message:
                raise SCMError('Label comparison failed:\n%s' % error_message)

        return changeset

    def _get_stream_changeset(self, stream, repository_info):
        """Return information about the versions changed in a stream.

        Args:
            stream (unicode):
                The UCM stream name. This must include the PVOB tag as well, so
                that ``cleartool describe`` can fetch the branch name.

            repository_info (rbtools.clients.RepositoryInfo):
                The repository info structure.

        Returns:
            list:
            A list of the changed files.
        """
        stream_info = execute(
            [
                'cleartool',
                'describe',
                '-long',
                'stream:%s' % stream,
            ],
            split_lines=True)

        branch = None

        for line in stream_info:
            if line.startswith('  Guarding: brtype'):
                line_parts = line.strip().split(':', 2)
                branch = line_parts[2]
                break

        if not branch:
            logging.error('Unable to determine branch name for UCM stream %s',
                          stream)
            return ''

        # TODO: It's possible that some project VOBs may exist in the stream
        # but not be included in the Review Board repository configuration. In
        # this case, _get_branch_changeset will only include changes in the
        # configured VOBs. There's also a possibility that some non-UCM or
        # other non-related UCM VOBs may have the same stream name or branch
        # name as the one being searched, and so it could include unexpected
        # versions. The chances of this in reality are probably pretty small.
        return self._get_branch_changeset(branch, repository_info)

    def _diff_files(self,
                    entry,
                    repository_info,
                    diffx_change):
        """Return a unified diff for file.

        Args:
            entry (ChangesetEntry):
                The changeset entry.

            repository_info (ClearCaseRepositoryInfo):
                The repository info structure.

            diffx (pydiffx.dom.DiffXChangeSection):
                The DiffX DOM object for writing VersionVault diffs.

        Returns:
            list of bytes:
            The diff between the two files, for writing legacy ClearCase diffs.
        """
        if entry.old_path:
            old_file_rel = os.path.relpath(entry.old_path, self.root_path)
        else:
            old_file_rel = '/dev/null'

        if entry.new_path:
            new_file_rel = os.path.relpath(entry.new_path, self.root_path)
        else:
            new_file_rel = '/dev/null'

        if self.viewtype == 'snapshot':
            # For snapshot views, we have to explicitly query to get the file
            # content and store in temporary files.
            try:
                diff_old_file = self._get_content_snapshot(entry.old_path)
                diff_new_file = self._get_content_snapshot(entry.new_path)
            except Exception as e:
                logging.exception(e)
                return b''
        else:
            # Dynamic views can access any version in history, but we may have
            # to create empty temporary files to compare against in the case of
            # created or deleted files.
            diff_old_file = entry.old_path or make_tempfile()
            diff_new_file = entry.new_path or make_tempfile()

        dl = execute(['diff', '-uN', diff_old_file, diff_new_file],
                     extra_ignore_errors=(1, 2),
                     results_unicode=False)

        # Replace temporary filenames in the diff with view-local relative
        # paths.
        dl = dl.replace(diff_old_file.encode('utf-8'),
                        old_file_rel.encode('utf-8'))
        dl = dl.replace(diff_new_file.encode('utf-8'),
                        new_file_rel.encode('utf-8'))

        # If the input file has ^M characters at end of line, lets ignore them.
        dl = dl.replace(b'\r\r\n', b'\r\n')
        dl = dl.splitlines(True)

        # Special handling for the output of the diff tool on binary files:
        #     diff outputs "Files a and b differ"
        # and the code below expects the output to start with
        #     "Binary files "
        if (len(dl) == 1 and
            dl[0].startswith(b'Files ') and dl[0].endswith(b' differ')):
            dl = [b'Binary f%s' % dl[0][1:]]

        # We need oids of files to translate them to paths on reviewboard
        # repository.
        vob_oid = execute(['cleartool', 'describe', '-fmt', '%On',
                           'vob:%s' % (entry.new_path or entry.old_path)])

        if dl and dl[0].startswith(b'Binary files '):
            if repository_info.is_legacy:
                dl.insert(
                    0,
                    b'==== %s %s ====\n' % (entry.old_oid.encode('utf-8'),
                                            entry.new_oid.encode('utf-8')))
        elif dl:
            if repository_info.is_legacy:
                dl.insert(
                    2,
                    b'==== %s %s ====\n' % (entry.old_oid.encode('utf-8'),
                                            entry.new_oid.encode('utf-8')))

        if not repository_info.is_legacy:
            vv_metadata = {
                'vob': vob_oid,
            }

            if dl and dl[0].startswith(b'Binary files'):
                diff_type = 'binary'
            else:
                diff_type = 'text'

            if entry.op == 'create':
                revision = entry.new_version

                path = new_file_rel
                revision = {
                    'new': revision,
                }
                vv_metadata['new'] = {
                    'name': entry.new_name,
                    'path': path,
                    'oid': entry.new_oid,
                }
            elif entry.op == 'delete':
                revision = entry.old_version

                path = old_file_rel
                revision = {
                    'old': revision,
                }
                vv_metadata['old'] = {
                    'name': entry.old_name,
                    'path': path,
                    'oid': entry.old_oid,
                }
            elif entry.op in ('modify', 'move'):
                path = {
                    'old': old_file_rel,
                    'new': new_file_rel,
                }
                revision = {
                    'old': entry.old_version,
                    'new': entry.new_version,
                }
                vv_metadata['old'] = {
                    'name': entry.old_name,
                    'path': old_file_rel,
                    'oid': entry.old_oid,
                }
                vv_metadata['new'] = {
                    'name': entry.new_name,
                    'path': new_file_rel,
                    'oid': entry.new_oid,
                }

                if entry.op == 'move' and dl != []:
                    entry.op = 'move-modify'
            else:
                logging.warning('Unexpected operation "%s" for file %s %s',
                                entry.op, entry.old_path, entry.new_path)

            diffx_change.add_file(
                meta={
                    'versionvault': vv_metadata,
                    'path': path,
                    'op': entry.op,
                    'revision': revision,
                },
                diff_type=diff_type,
                diff=b''.join(dl))

            return dl

    def _get_content_snapshot(self, filename):
        """Return the content of a file in a snapshot view.

        Snapshot views don't support accessing file content directly like
        dynamic views do, so we have to fetch the content to a temporary file.

        Args:
            filename (unicode):
                The extended path of the file element to fetch.

        Returns:
            unicode:
            The filename of the temporary file with the content.
        """
        temp_file = make_tempfile()

        if filename:
            # Delete the temporary file so cleartool can write to it.
            try:
                os.remove(temp_file)
            except OSError:
                pass

            execute(['cleartool', 'get', '-to', temp_file, filename])

        return temp_file

    def _do_diff(self, changeset, repository_info, metadata):
        """Generate a unified diff for all files in the given changeset.

        Args:
            changeset (list):
                A list of changes.

            repository_info (ClearCaseRepositoryInfo):
                The repository info structure.

            metadata (dict):
                Extra data to inject into the diff headers.

        Returns:
            dict:
            A dictionary containing a ``diff`` key.
        """
        # Sanitize all changesets of version 0 before processing
        changeset = self._sanitize_version_0_changeset(changeset)
        changeset = self._process_directory_changes(changeset)

        diffx = DiffX()
        diffx_change = diffx.add_change(meta={
            'versionvault': metadata,
        })
        legacy_diff = []

        for entry in changeset:
            legacy_dl = []

            if self.viewtype == 'snapshot' or cpath.exists(entry.new_path):
                legacy_dl = self._diff_files(entry, repository_info,
                                             diffx_change)
            else:
                logging.error('File %s does not exist or access is denied.',
                              entry.new_path)
                continue

            if repository_info.is_legacy and legacy_dl:
                legacy_diff.append(b''.join(legacy_dl))

        if repository_info.is_legacy:
            diff = b''.join(legacy_diff)
        else:
            diffx.generate_stats()
            diff = diffx.to_bytes()

        return {
            'diff': diff,
        }

    def _process_directory_changes(self, changeset):
        """Scan through the changeset and handle directory elements.

        Depending on how the changeset is created, it may include changes to
        directory elements. These cover things such as file renames or
        deletions which may or may not be already included in the changeset.

        This method will perform diffs for any directory-type elements,
        processing those and folding them back into the changeset for use
        later.

        Args:
            changeset (list):
                The list of changed elements (2-tuples of element versions to
                compare)

        Returns:
            list of ChangesetEntry:
            The new changeset including adds, deletes, and moves.
        """
        files = []
        directories = []

        for old_file, new_file in changeset:
            if self.viewtype == 'snapshot':
                object_kind = execute(['cleartool', 'describe', '-fmt', '%m',
                                       new_file])

                is_dir = object_kind.startswith('directory')
            else:
                is_dir = cpath.isdir(new_file)

            if is_dir:
                directories.append((old_file, new_file))
            else:
                files.append(ChangesetEntry(self.root_path, old_path=old_file,
                                            new_path=new_file))

        for old_dir, new_dir in directories:
            changes = self._diff_directory(old_dir, new_dir)

            for filename, oid in changes['added']:
                for file in files:
                    if file.new_oid == oid:
                        file.op = 'create'
                        break
                else:
                    files.append(ChangesetEntry(self.root_path,
                                                new_path=filename,
                                                new_oid=oid,
                                                op='create'))

            for filename, oid in changes['deleted']:
                for file in files:
                    if file.old_oid == oid:
                        file.op = 'delete'
                        break
                else:
                    # The extended path we get here doesn't include the
                    # revision of the element. While many operations can
                    # succeed in this case, fetching the content of the file
                    # from snapshot views does not. We therefore look at the
                    # history of the file and get the last revision from it.
                    filename = execute(['cleartool', 'lshistory', '-last',
                                        '1', '-fmt', '%Xn', 'oid:%s' % oid])
                    files.append(ChangesetEntry(self.root_path,
                                                old_path=filename,
                                                old_oid=oid,
                                                op='delete'))

            for old_file, old_oid, new_file, new_oid in changes['renamed']:
                # Just using the old filename that we get from the
                # directory diff will break in odd ways depending on
                # the view type. Explicitly appending the element
                # version seems to work.
                old_version = execute(
                    ['cleartool', 'describe', '-fmt', '%Vn', file.old_path])
                old_path = '%s@@%s' % (old_file, old_version)

                for file in files:
                    if (file.old_oid == old_oid or
                        file.new_oid == new_oid):
                        file.old_path = old_path
                        file.op = 'move'
                        break
                else:
                    files.append(ChangesetEntry(self.root_path,
                                                old_path=old_path,
                                                new_path=new_file,
                                                old_oid=old_oid,
                                                new_oid=new_oid,
                                                op='move'))

        return files

    def _diff_directory(self, old_dir, new_dir):
        """Get directory differences.

        This will query and parse the diff of a directory element, in order to
        properly detect added, renamed, and deleted files.

        Args:
            old_dir (unicode):
                The extended path of the directory at its old revision.

            new_dir (unicode):
                The extended path of the directory at its new revision.

        Returns:
            dict:
            A dictionary with three keys: ``renamed``, ``added``, and
            ``deleted``.
        """
        diff_lines = execute(
            [
                'cleartool',
                'diff',
                '-ser',
                old_dir,
                new_dir,
            ],
            split_lines=True,
            extra_ignore_errors=(1,))

        current_mode = None
        mode_re = re.compile(r'^-----\[ (?P<mode>[\w ]+) \]-----$')

        def _extract_filename(fileline):
            return fileline.rsplit(None, 2)[0][2:]

        i = 0
        results = {
            'added': set(),
            'deleted': set(),
            'renamed': set(),
        }

        while i < len(diff_lines):
            line = diff_lines[i]
            i += 1

            m = mode_re.match(line)

            if m:
                current_mode = m.group('mode')
                continue

            get_oid_cmd = ['cleartool', 'desc', '-fmt', '%On']

            if current_mode == 'renamed to':
                old_file = cpath.join(old_dir, _extract_filename(line))
                old_oid = execute(get_oid_cmd + [old_file])
                new_file = cpath.join(new_dir,
                                      _extract_filename(diff_lines[i + 1]))
                new_oid = execute(get_oid_cmd + [new_file])

                results['renamed'].add((old_file, old_oid, new_file, new_oid))
                i += 2
            elif current_mode == 'added':
                new_file = cpath.join(new_dir, _extract_filename(line))
                oid = execute(get_oid_cmd + [new_file])

                results['added'].add((new_file, oid))
            elif current_mode == 'deleted':
                old_file = cpath.join(old_dir, _extract_filename(line))
                oid = execute(get_oid_cmd + [old_file])

                results['deleted'].add((old_file, oid))

        return results

    def _get_diff_metadata(self, revisions):
        """Return a starting set of metadata to inject into the diff.

        Args:
            revisions (dict):
                A dictionary of revisions, as returned by
                :py:meth:`parse_revision_spec`.

        Returns:
            dict:
            A starting set of data to inject into the diff, which will become
            part of the FileDiff's extra_data field. Additional keys may be set
            on this before it gets serialized into the diff.
        """
        metadata = {
            'os': {
                'short': os.name,
                'long': self.host_properties.get('Operating system'),
            },
            'region': self.host_properties.get('Registry region'),
            'scm': {
                'name': self.host_properties.get('Product name'),
                'version': self.host_properties.get('Product version'),
            },
            'view': {
                'tag': self.viewname,
                'type': self.viewtype,
                'ucm': self.is_ucm,
            },
        }

        base = revisions['base']
        tip = revisions['tip']

        if tip == self.REVISION_CHECKEDOUT_CHANGESET:
            metadata['scope'] = {
                'name': 'checkout',
                'type': 'checkout',
            }
        elif base == self.REVISION_ACTIVITY_BASE:
            metadata['scope'] = {
                'name': tip,
                'type': 'activity',
            }
        elif base == self.REVISION_BASELINE_BASE:
            if len(tip) == 1:
                metadata['scope'] = {
                    'name': tip[0],
                    'type': 'baseline/predecessor',
                }
            else:
                metadata['scope'] = {
                    'name': '%s/%s' % (tip[0], tip[1]),
                    'type': 'baseline/baseline',
                }
        elif base == self.REVISION_BRANCH_BASE:
            metadata['scope'] = {
                'name': tip,
                'type': 'branch',
            }
        elif base == self.REVISION_LABEL_BASE:
            if len(tip) == 1:
                metadata['scope'] = {
                    'name': tip[0],
                    'type': 'label/current',
                }
            else:
                metadata['scope'] = {
                    'name': '%s/%s' % (tip[0], tip[1]),
                    'type': 'label/label',
                }
        elif base == self.REVISION_STREAM_BASE:
            metadata['scope'] = {
                'name': tip,
                'type': 'stream',
            }
        elif base == self.REVISION_FILES:
            # TODO: We'd like to keep a record of the individual files listed
            # in "tip"
            metadata['scope'] = {
                'name': 'changeset',
                'type': 'changeset',
            }
        else:
            assert False

        return metadata

    def _get_host_info(self):
        """Return the current ClearCase/VersionVault host info.

        Returns:
            dict:
            A dictionary with the host properties.

        Raises:
            rbtools.clients.errors.SCMError:
                Could not determine the host info.
        """
        if not check_install(['cleartool', 'help']):
            logging.debug('Unable to execute "cleartool help": skipping '
                          'ClearCase')
            return None

        property_lines = execute(['cleartool', 'hostinfo', '-l'],
                                 split_lines=True)

        if 'Error' in property_lines:
            raise SCMError('Unable to determine the current region')

        properties = {}

        for line in property_lines:
            key, value = line.split(':', 1)
            properties[key.strip()] = value.strip()

        # Add derived properties
        try:
            product = properties['Product'].split(' ', 1)
            properties['Product name'] = product[0]
            properties['Product version'] = product[1]
        except Exception:
            pass

        return properties


class ClearCaseRepositoryInfo(RepositoryInfo):
    """A representation of a ClearCase source code repository.

    This version knows how to find a matching repository on the server even if
    the URLs differ.
    """

    def __init__(self, path, vobtag, tool=None):
        """Initialize the repsitory info.

        Args:
            path (unicode):
                The path of the repository.

            vobtag (unicode):
                The VOB tag for the repository.

            tool (rbtools.clients.SCMClient):
                The SCM client.
        """
        super(ClearCaseRepositoryInfo, self).__init__(path)
        self.vobtag = vobtag
        self.tool = tool
        self.vob_tags = {vobtag}
        self.uuid_to_tags = {}
        self.is_legacy = True

    def update_from_remote(self, repository, info):
        """Update the info from a remote repository.

        Args:
            repository (rbtools.api.resource.ItemResource):
                The repository resource.

            info (rbtools.api.resource.ItemResource):
                The repository info resource.
        """
        path = info['repopath']
        self.path = path

        if 'uuid' in info:
            # Legacy ClearCase backend that supports a single VOB.
            self.vob_uuids = [info['uuid']]
        elif 'uuids' in info:
            # New VersionVault/ClearCase backend that supports multiple VOBs.
            self.vob_uuids = info['uuids']
            self.is_legacy = False
        else:
            raise SCMError('Unable to fetch VOB information from server '
                           'repository info.')

        tags = defaultdict(set)
        regions = execute(['cleartool', 'lsregion'],
                          ignore_errors=True,
                          split_lines=True)

        # Find local tag names for connected VOB UUIDs.
        for region, uuid in itertools.product(regions, self.vob_uuids):
            try:
                tag = execute(['cleartool', 'lsvob', '-s', '-family', uuid,
                               '-region', region.strip()])
                tags[uuid].add(tag.strip())
            except Exception:
                pass

        self.vob_tags = set()
        self.uuid_to_tags = {}

        for uuid, tags in six.iteritems(tags):
            self.vob_tags.update(tags)
            self.uuid_to_tags[uuid] = list(tags)

    def find_server_repository_info(self, api_root):
        """Find a matching repository on the server.

        The point of this function is to find a repository on the server that
        matches self, even if the paths aren't the same. (For example, if self
        uses an 'http' path, but the server uses a 'file' path for the same
        repository.) It does this by comparing the VOB's name and uuid. If the
        repositories use the same path, you'll get back self, otherwise you'll
        get a different ClearCaseRepositoryInfo object (with a different path).

        Deprecated:
            3.0:
            Commands which need to use the remote repository, or need data from
            the remote repository such as the base path, should set
            :py:attr:`needs_repository`.

        Args:
            api_root (rbtools.api.resource.RootResource):
                The root resource for the Review Board server.

        Returns:
            ClearCaseRepositoryInfo:
            The server-side information for this repository.
        """
        RemovedInRBTools40Warning.warn(
            'The find_server_repository_info method is deprecated, and will '
            'be removed in RBTools 4.0. If you need to access the remote '
            'repository, set the needs_repository attribute on your Command '
            'subclass.')

        repository, info = get_repository_resource(
            api_root,
            tool=self.tool)

        if repository:
            self.update_from_remote(repository, info)

        return self
