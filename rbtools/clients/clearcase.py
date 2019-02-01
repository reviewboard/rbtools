"""A client for ClearCase."""

from __future__ import unicode_literals

import datetime
import itertools
import logging
import os
import sys
import threading
from collections import deque

import six
from pkg_resources import parse_version

from rbtools.api.errors import APIError
from rbtools.clients import SCMClient, RepositoryInfo
from rbtools.clients.errors import InvalidRevisionSpecError, SCMError
from rbtools.utils.checks import check_gnu_diff, check_install
from rbtools.utils.filesystem import make_tempfile
from rbtools.utils.process import execute

# This specific import is necessary to handle the paths when running on cygwin.
if sys.platform.startswith(('cygwin', 'win')):
    import ntpath as cpath
else:
    import os.path as cpath


class _get_elements_from_label_thread(threading.Thread):
    def __init__(self, threadID, dir_name, label, elements):
        self.threadID = threadID
        self.dir_name = dir_name
        self.elements = elements

        # Remove any trailing vobstag not supported by cleartool find.
        try:
            label, vobstag = label.rsplit('@', 1)
        except Exception:
            pass
        self.label = label

        if sys.platform.startswith('win'):
            self.cc_xpn = '%CLEARCASE_XPN%'
        else:
            self.cc_xpn = '$CLEARCASE_XPN'

        threading.Thread.__init__(self)

    def run(self):
        """Run the thread.

        This will store a dictionary of ClearCase elements (oid + version)
        belonging to a label and identified by path.
        """
        output = execute(
            ['cleartool', 'find', self.dir_name, '-version',
             'lbtype(%s)' % self.label, '-exec',
             r'cleartool describe -fmt "%On\t%En\t%Vn\n" ' + self.cc_xpn],
            extra_ignore_errors=(1,), with_errors=False)

        for line in output.split('\n'):
            # Does not process empty lines.
            if not line:
                continue

            oid, path, version = line.split('\t', 2)
            self.elements[path] = {
                'oid': oid,
                'version': version,
            }


class ClearCaseClient(SCMClient):
    """A client for ClearCase.

    This is a wrapper around the clearcase tool that fetches repository
    information and generates compatible diffs. This client assumes that cygwin
    is installed on Windows.
    """

    name = 'ClearCase'
    viewtype = None
    supports_patch_revert = True

    REVISION_ACTIVITY_BASE = '--rbtools-activity-base'
    REVISION_ACTIVITY_PREFIX = 'activity:'
    REVISION_BRANCH_BASE = '--rbtools-branch-base'
    REVISION_BRANCH_PREFIX = 'brtype:'
    REVISION_CHECKEDOUT_BASE = '--rbtools-checkedout-base'
    REVISION_CHECKEDOUT_CHANGESET = '--rbtools-checkedout-changeset'
    REVISION_FILES = '--rbtools-files'
    REVISION_LABEL_BASE = '--rbtools-label-base'
    REVISION_LABEL_PREFIX = 'lbtype:'

    def get_repository_info(self):
        """Return information on the ClearCase repository.

        This will first check if the cleartool command is installed and in the
        path, and that the current working directory is inside of the view.

        Returns:
            ClearCaseRepositoryInfo:
            The repository info structure.
        """
        if not check_install(['cleartool', 'help']):
            logging.debug('Unable to execute "cleartool help": skipping '
                          'ClearCase')
            return None

        viewname = execute(['cleartool', 'pwv', '-short']).strip()
        if viewname.startswith('** NONE'):
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
                #
                # Specifically check if webview was listed in properties
                # because webview types also list the 'snapshot'
                # entry in properties.
                if 'webview' in properties:
                    raise SCMError('Webviews are not supported. You can use '
                                   'rbt commands only in dynamic or snapshot '
                                   'views.')
                if 'dynamic' in properties:
                    self.viewtype = 'dynamic'
                else:
                    self.viewtype = 'snapshot'

                break

        # Find current VOB's tag
        vobstag = execute(['cleartool', 'describe', '-short', 'vob:.'],
                          ignore_errors=True).strip()
        if 'Error: ' in vobstag:
            raise SCMError('Failed to generate diff run rbt inside vob.')

        root_path = execute(['cleartool', 'pwv', '-root'],
                            ignore_errors=True).strip()
        if 'Error: ' in root_path:
            raise SCMError('Failed to generate diff run rbt inside view.')

        # From current working directory cut path to VOB. On Windows
        # and under cygwin, the VOB tag contains the VOB's path including
        # name, e.g. `\new_proj` for a VOB `new_proj` mounted at the root
        # of a drive. On Unix, the VOB tag is similar, but with a different
        # path separator, e.g. `/vobs/new_proj` for our new_proj VOB mounted
        # at `/vobs`.
        cwd = os.getcwd()
        base_path = cwd[:len(root_path) + len(vobstag)]

        return ClearCaseRepositoryInfo(path=base_path,
                                       base_path=base_path,
                                       vobstag=vobstag)

    def _determine_branch_path(self, version_path):
        """Determine the branch path of a version path.

        Args:
            version_path (unicode):
                A version path consisting of a branch path and a version
                number.

        Returns:
            unicode:
            The branch path.
        """
        branch_path, number = cpath.split(version_path)
        return branch_path

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

    def _is_a_label(self, label, vobstag=None):
        """Return whether a given label is a valid ClearCase lbtype.

        Args:
            label (unicode):
                The label to check.

            vobstag (unicode, optional):
                An optional vobstag to limit the label to.

        Raises:
            Exception:
                The vobstag did not match.

        Returns:
            bool:
            Whether the label was valid.
        """
        label_vobstag = None
        # Try to find any vobstag.
        try:
            label, label_vobstag = label.rsplit('@', 1)
        except Exception:
            pass

        # Be sure label is prefix by lbtype, required by cleartool describe.
        if not label.startswith(self.REVISION_LABEL_PREFIX):
            label = '%s%s' % (self.REVISION_LABEL_PREFIX, label)

        # If vobstag defined, check if it matches with the one extracted from
        # label, otherwise raise an exception.
        if vobstag and label_vobstag and label_vobstag != vobstag:
            raise Exception('label vobstag %s does not match expected vobstag '
                            '%s' % (label_vobstag, vobstag))

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
            raise Exception(
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

        if number == 'CHECKEDOUT':
            return sys.maxint

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
        if not version or version.endswith('CHECKEDOUT'):
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
            if revisions[0].startswith(self.REVISION_ACTIVITY_PREFIX):
                return {
                    'base': self.REVISION_ACTIVITY_BASE,
                    'tip': revisions[0][len(self.REVISION_ACTIVITY_PREFIX):],
                }
            if revisions[0].startswith(self.REVISION_BRANCH_PREFIX):
                return {
                    'base': self.REVISION_BRANCH_BASE,
                    'tip': revisions[0][len(self.REVISION_BRANCH_PREFIX):],
                }
            if revisions[0].startswith(self.REVISION_LABEL_PREFIX):
                return {
                    'base': self.REVISION_LABEL_BASE,
                    'tip': [revisions[0][len(self.REVISION_BRANCH_PREFIX):]],
                }
            # TODO:
            # stream:streamname[@pvob] => review changes in this UCM stream
            #                             (UCM "branch")
            # baseline:baseline[@pvob] => review changes between this baseline
            #                             and the working directory
        elif n_revs == 2:
            if self.viewtype != 'dynamic':
                raise SCMError('To generate a diff using multiple revisions, '
                               'you must use a dynamic view.')

            if (revisions[0].startswith(self.REVISION_LABEL_PREFIX) and
                revisions[1].startswith(self.REVISION_LABEL_PREFIX)):
                return {
                    'base': self.REVISION_LABEL_BASE,
                    'tip': [x[len(self.REVISION_BRANCH_PREFIX):]
                            for x in revisions],
                }
            # TODO:
            # baseline:baseline1[@pvob] baseline:baseline2[@pvob]
            #                             => review changes between these two
            #                                baselines
            pass

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

    def _sanitize_activity_changeset(self, changeset):
        """Return changeset containing non-binary, branched file versions.

        A UCM activity changeset contains all file revisions created/touched
        during this activity. File revisions are ordered earlier versions first
        in the format:
        changelist = [
        <path>@@<branch_path>/<version_number>, ...,
        <path>@@<branch_path>/<version_number>
        ]

        <path> is relative path to file
        <branch_path> is clearcase specific branch path to file revision
        <version number> is the version number of the file in <branch_path>.

        A UCM activity changeset can contain changes from different vobs,
        however reviewboard supports only changes from a single repo at the
        same time, so changes made outside of the current vobstag will be
        ignored.

        Args:
            changeset (unicode):
                The changeset to fetch.

        Returns:
            list:
            The list of file versions.
        """
        changelist = {}
        # Maybe we should be able to access repository_info without calling
        # cleartool again.
        repository_info = self.get_repository_info()

        for change in changeset:
            path, current = change.split('@@')

            # If a file isn't in the correct vob, then ignore it.
            if path.find('%s/' % (repository_info.vobstag,)) == -1:
                logging.debug('Vobstag does not match, ignoring changes on %s',
                              path)
                continue

            version_number = self._determine_version(current)
            if path not in changelist:
                changelist[path] = {
                    'highest': version_number,
                    'lowest': version_number,
                    'current': current,
                }

            if version_number == 0:
                raise SCMError('Unexepected version_number=0 in activity '
                               'changeset')
            elif version_number > changelist[path]['highest']:
                changelist[path]['highest'] = version_number
                changelist[path]['current'] = current
            elif version_number < changelist[path]['lowest']:
                changelist[path]['lowest'] = version_number

        # Convert to list
        changeranges = []
        for path, version in six.iteritems(changelist):
            # Previous version is predecessor of lowest ie its version number
            # decreased by 1.
            branch_path = self._determine_branch_path(version['current'])
            prev_version_number = str(int(version['lowest']) - 1)
            version['previous'] = self._construct_revision(branch_path,
                                                           prev_version_number)
            changeranges.append(
                (self._construct_extended_path(path, version['previous']),
                 self._construct_extended_path(path, version['current']))
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
            Thee sanitized revision.
        """
        # There is no predecessor for @@/main/0, so keep current revision.
        if file_revision.endswith('@@/main/0'):
            return file_revision

        if file_revision.endswith('/0'):
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

    def _directory_content(self, path):
        """Return directory content ready for saving to tempfile.

        Args:
            path (unicode):
                The path to list.

        Returns:
            unicode:
            The listed files in the directory.
        """
        # Get the absolute path of each element located in path, but only
        # clearcase elements => -vob_only
        output = execute(['cleartool', 'ls', '-short', '-nxname', '-vob_only',
                          path])
        lines = output.splitlines(True)

        content = []
        # The previous command returns absolute file paths but only file names
        # are required.
        for absolute_path in lines:
            short_path = os.path.basename(absolute_path.strip())
            content.append(short_path)

        return ''.join([
            '%s\n' % s
            for s in sorted(content)])

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

    def _get_checkedout_changeset(self):
        """Return information about the checked out changeset.

        This function returns: kind of element, path to file, previews and
        current file version.

        Returns:
            list:
            A list of the changed files.
        """
        changeset = []
        # We ignore return code 1 in order to omit files that ClearCase can't
        # read.
        output = execute(['cleartool',
                          'lscheckout',
                          '-all',
                          '-cview',
                          '-me',
                          '-fmt',
                          r'%En\t%PVn\t%Vn\n'],
                         extra_ignore_errors=(1,),
                         with_errors=False)

        if output:
            changeset = self._construct_changeset(output)

        return self._sanitize_checkedout_changeset(changeset)

    def _get_activity_changeset(self, activity):
        """Return information about the versions changed on a branch.

        This takes into account the changes attached to this activity
        (including rebase changes) in all vobs of the current view.

        Args:
            activity (unicode):
                The activity name.

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
                          '%[versions]p',
                          activity],
                         extra_ignore_errors=(1,),
                         with_errors=False)

        if output:
            # UCM activity changeset is split by spaces not but EOL, so we
            # cannot reuse self._construct_changeset here.
            changeset = output.split()

        return self._sanitize_activity_changeset(changeset)

    def _get_branch_changeset(self, branch):
        """Return information about the versions changed on a branch.

        This takes into account the changes on the branch owned by the
        current user in all vobs of the current view.

        Args:
            branch (unicode):
                The branch name.

        Returns:
            list:
            A list of the changed files.
        """
        changeset = []

        # We ignore return code 1 in order to omit files that ClearCase can't
        # read.
        if sys.platform.startswith('win'):
            CLEARCASE_XPN = '%CLEARCASE_XPN%'
        else:
            CLEARCASE_XPN = '$CLEARCASE_XPN'

        output = execute(
            [
                'cleartool',
                'find',
                '-all',
                '-version',
                'brtype(%s)' % branch,
                '-exec',
                'cleartool descr -fmt "%%En\t%%PVn\t%%Vn\n" %s' % CLEARCASE_XPN
            ],
            extra_ignore_errors=(1,),
            with_errors=False)

        if output:
            changeset = self._construct_changeset(output)

        return self._sanitize_branch_changeset(changeset)

    def _get_label_changeset(self, labels):
        """Return information about the versions changed between labels.

        This takes into account the changes done between labels and restrict
        analysis to current working directory. A ClearCase label belongs to a
        unique vob.

        Args:
            labels (list):
                A list of labels to compare.

        Returns:
            list:
            A list of the changed files.
        """
        changeset = []
        tmp_labels = []

        # Initialize comparison_path to current working directory.
        # TODO: support another argument to manage a different comparison path.
        comparison_path = os.getcwd()

        error_message = None

        try:
            # Unless user has provided 2 labels, set a temporary label on
            # current version seen of comparison_path directory. It will be
            # used to process changeset.
            # Indeed ClearCase can identify easily each file and associated
            # version belonging to a label.
            if len(labels) == 1:
                tmp_lb = self._get_tmp_label()
                tmp_labels.append(tmp_lb)
                self._set_label(tmp_lb, comparison_path)
                labels.append(tmp_lb)

            label_count = len(labels)

            if label_count != 2:
                raise Exception(
                    'ClearCase label comparison does not support %d labels'
                    % label_count)

            # Now we get 2 labels for comparison, check if they are both valid.
            repository_info = self.get_repository_info()
            for label in labels:
                if not self._is_a_label(label, repository_info.vobstag):
                    raise Exception(
                        'ClearCase label %s is not a valid label' % label)

            previous_label, current_label = labels
            logging.debug('Comparison between labels %s and %s on %s',
                          previous_label, current_label, comparison_path)

            # List ClearCase element path and version belonging to previous and
            # current labels, element path is the key of each dict.
            previous_elements = {}
            current_elements = {}
            previous_label_elements_thread = _get_elements_from_label_thread(
                1, comparison_path, previous_label, previous_elements)
            previous_label_elements_thread.start()

            current_label_elements_thread = _get_elements_from_label_thread(
                2, comparison_path, current_label, current_elements)
            current_label_elements_thread.start()

            previous_label_elements_thread.join()
            current_label_elements_thread.join()

            seen = []
            changelist = {}
            # Iterate on each ClearCase path in order to find respective
            # previous and current version.
            for path in itertools.chain(previous_elements.keys(),
                                        current_elements.keys()):
                if path in seen:
                    continue

                seen.append(path)

                # Initialize previous and current version to '/main/0'
                changelist[path] = {
                    'previous': '/main/0',
                    'current': '/main/0',
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

        finally:
            # Delete all temporary labels.
            for lb in tmp_labels:
                if self._is_a_label(lb):
                    self._remove_label(lb)

            if error_message:
                raise SCMError('Label comparison failed:\n%s' % error_message)

        return changeset

    def diff(self, revisions, include_files=[], exclude_patterns=[],
             no_renames=False, extra_args=[]):
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

            extra_args (list, unused):
                Additional arguments to be passed to the diff generation.
                Unused for ClearCase.

        Returns:
            dict:
            A dictionary containing the following keys:

            ``diff`` (:py:class:`bytes`):
                The contents of the diff to upload.
        """
        if include_files:
            raise Exception(
                'The ClearCase backend does not currently support the '
                '-I/--include parameter. To diff for specific files, pass in '
                'file@revision1:file@revision2 pairs as arguments')

        if revisions['tip'] == self.REVISION_CHECKEDOUT_CHANGESET:
            changeset = self._get_checkedout_changeset()
            return self._do_diff(changeset)
        elif revisions['base'] == self.REVISION_ACTIVITY_BASE:
            changeset = self._get_activity_changeset(revisions['tip'])
            return self._do_diff(changeset)
        elif revisions['base'] == self.REVISION_BRANCH_BASE:
            changeset = self._get_branch_changeset(revisions['tip'])
            return self._do_diff(changeset)
        elif revisions['base'] == self.REVISION_LABEL_BASE:
            changeset = self._get_label_changeset(revisions['tip'])
            return self._do_diff(changeset)
        elif revisions['base'] == self.REVISION_FILES:
            include_files = revisions['tip']
            return self._do_diff(include_files)
        else:
            assert False

    def _diff_files(self, old_file, new_file):
        """Return a unified diff for file.

        Args:
            old_file (unicode):
                The name and version of the old file.

            new_file (unicode):
                The name and version of the new file.

        Returns:
            bytes:
            The diff between the two files.
        """
        # In snapshot view, diff can't access history clearcase file version
        # so copy cc files to tempdir by 'cleartool get -to dest-pname pname',
        # and compare diff with the new temp ones.
        if self.viewtype == 'snapshot':
            # Create temporary file first.
            tmp_old_file = make_tempfile()
            tmp_new_file = make_tempfile()

            # Delete so cleartool can write to them.
            try:
                os.remove(tmp_old_file)
            except OSError:
                pass

            try:
                os.remove(tmp_new_file)
            except OSError:
                pass

            execute(['cleartool', 'get', '-to', tmp_old_file, old_file])
            execute(['cleartool', 'get', '-to', tmp_new_file, new_file])
            diff_cmd = ['diff', '-uN', tmp_old_file, tmp_new_file]
        else:
            diff_cmd = ['diff', '-uN', old_file, new_file]

        dl = execute(diff_cmd,
                     extra_ignore_errors=(1, 2),
                     results_unicode=False)

        # Replace temporary file name in diff with the one in snapshot view.
        if self.viewtype == 'snapshot':
            dl = dl.replace(tmp_old_file.encode('utf-8'),
                            old_file.encode('utf-8'))
            dl = dl.replace(tmp_new_file.encode('utf-8'),
                            new_file.encode('utf-8'))

        # If the input file has ^M characters at end of line, lets ignore them.
        dl = dl.replace(b'\r\r\n', b'\r\n')
        dl = dl.splitlines(True)

        # Special handling for the output of the diff tool on binary files:
        #     diff outputs "Files a and b differ"
        # and the code below expects the output to start with
        #     "Binary files "
        if (len(dl) == 1 and
            dl[0].startswith(b'Files %s and %s differ'
                             % (old_file.encode('utf-8'),
                                new_file.encode('utf-8')))):
            dl = [b'Binary files %s and %s differ\n'
                  % (old_file.encode('utf-8'),
                     new_file.encode('utf-8'))]

        # We need oids of files to translate them to paths on reviewboard
        # repository.
        old_oid = execute(['cleartool', 'describe', '-fmt', '%On', old_file],
                          results_unicode=False)
        new_oid = execute(['cleartool', 'describe', '-fmt', '%On', new_file],
                          results_unicode=False)

        if dl == [] or dl[0].startswith(b'Binary files '):
            if dl == []:
                dl = [b'File %s in your changeset is unmodified\n' %
                      new_file.encode('utf-8')]

            dl.insert(0, b'==== %s %s ====\n' % (old_oid, new_oid))
            dl.append(b'\n')
        else:
            dl.insert(2, b'==== %s %s ====\n' % (old_oid, new_oid))

        return dl

    def _diff_directories(self, old_dir, new_dir):
        """Return a unified diff between two directories' content.

        This function saves two version's content of directory to temp
        files and treats them as casual diff between two files.

        Args:
            old_dir (unicode):
                The path to a directory within a vob.

            new_dir (unicode):
                The path to a directory within a vob.

        Returns:
            list:
            The diff between the two directory trees, split into lines.
        """
        old_content = self._directory_content(old_dir)
        new_content = self._directory_content(new_dir)

        old_tmp = make_tempfile(content=old_content)
        new_tmp = make_tempfile(content=new_content)

        diff_cmd = ['diff', '-uN', old_tmp, new_tmp]
        dl = execute(diff_cmd,
                     extra_ignore_errors=(1, 2),
                     results_unicode=False,
                     split_lines=True)

        # Replace temporary filenames with real directory names and add ids
        if dl:
            dl[0] = dl[0].replace(old_tmp.encode('utf-8'),
                                  old_dir.encode('utf-8'))
            dl[1] = dl[1].replace(new_tmp.encode('utf-8'),
                                  new_dir.encode('utf-8'))
            old_oid = execute(['cleartool', 'describe', '-fmt', '%On',
                               old_dir],
                              results_unicode=False)
            new_oid = execute(['cleartool', 'describe', '-fmt', '%On',
                               new_dir],
                              results_unicode=False)
            dl.insert(2, b'==== %s %s ====\n' % (old_oid, new_oid))

        return dl

    def _do_diff(self, changeset):
        """Generate a unified diff for all files in the given changeset.

        Args:
            changeset (list):
                A list of changes.

        Returns:
            dict:
            A dictionary containing a ``diff`` key.
        """
        # Sanitize all changesets of version 0 before processing
        changeset = self._sanitize_version_0_changeset(changeset)

        diff = []
        for old_file, new_file in changeset:
            dl = []

            # cpath.isdir does not work for snapshot views but this
            # information can be found using `cleartool describe`.
            if self.viewtype == 'snapshot':
                # ClearCase object path is file path + @@
                object_path = new_file.split('@@')[0] + '@@'
                output = execute(['cleartool', 'describe', '-fmt', '%m',
                                  object_path])
                object_kind = output.strip()
                isdir = object_kind == 'directory element'
            else:
                isdir = cpath.isdir(new_file)

            if isdir:
                dl = self._diff_directories(old_file, new_file)
            elif cpath.exists(new_file) or self.viewtype == 'snapshot':
                dl = self._diff_files(old_file, new_file)
            else:
                logging.error('File %s does not exist or access is denied.',
                              new_file)
                continue

            if dl:
                diff.append(b''.join(dl))

        return {
            'diff': b''.join(diff),
        }


class ClearCaseRepositoryInfo(RepositoryInfo):
    """A representation of a ClearCase source code repository.

    This version knows how to find a matching repository on the server even if
    the URLs differ.
    """

    def __init__(self, path, base_path, vobstag):
        """Initialize the repsitory info.

        Args:
            path (unicode):
                The path of the repository.

            base_path (unicode):
                The relative path between the repository root and the working
                directory.

            vobstag (unicode):
                The vobstag for the repository.
        """
        RepositoryInfo.__init__(self, path, base_path,
                                supports_parent_diffs=False)
        self.vobstag = vobstag

    def find_server_repository_info(self, server):
        """Find a matching repository on the server.

        The point of this function is to find a repository on the server that
        matches self, even if the paths aren't the same. (For example, if self
        uses an 'http' path, but the server uses a 'file' path for the same
        repository.) It does this by comparing the VOB's name and uuid. If the
        repositories use the same path, you'll get back self, otherwise you'll
        get a different ClearCaseRepositoryInfo object (with a different path).

        Args:
            server (rbtools.api.resource.RootResource):
                The root resource for the Review Board server.

        Returns:
            ClearCaseRepositoryInfo:
            The server-side information for this repository.
        """
        # Find VOB's family uuid based on VOB's tag
        uuid = self._get_vobs_uuid(self.vobstag)
        logging.debug('Repository vobstag %s uuid is %r', self.vobstag, uuid)

        # To reduce HTTP requests (_get_repository_info calls), we build an
        # ordered list of ClearCase repositories starting with the ones that
        # have a similar vobstag.
        repository_scan_order = deque()

        # Because the VOB tag is platform-specific, we split and search
        # for the remote name in any sub-part so this HTTP request
        # optimization can work for users on both Windows and Unix-like
        # platforms.
        vob_tag_parts = self.vobstag.split(cpath.sep)

        # Reduce list of repositories to only ClearCase ones and sort them by
        # repo name matching vobstag (or some part of the vobstag) first.
        for repository in server.get_repositories(tool='ClearCase').all_items:
            # Ignore non-ClearCase repositories.
            if repository['tool'] != 'ClearCase':
                continue

            repo_name = repository['name']

            # Repositories with a similar VOB tag get put at the beginning and
            # the others at the end.
            if repo_name == self.vobstag or repo_name in vob_tag_parts:
                repository_scan_order.appendleft(repository)
            else:
                repository_scan_order.append(repository)

        # Now try to find a matching uuid
        for repository in repository_scan_order:
            repo_name = repository['name']
            try:
                info = repository.get_info()
            except APIError as e:
                # If the current repository is not publicly accessible and the
                # current user has no explicit access to it, the server will
                # return error_code 101 and http_status 403.
                if not (e.error_code == 101 and e.http_status == 403):
                    # We can safely ignore this repository unless the VOB tag
                    # matches.
                    if repo_name == self.vobstag:
                        raise SCMError('You do not have permission to access '
                                       'this repository.')

                    continue
                else:
                    # Bubble up any other errors
                    raise e

            if not info or uuid != info['uuid']:
                continue

            path = info['repopath']
            logging.debug('Matching repository uuid:%s with path:%s',
                          uuid, path)
            return ClearCaseRepositoryInfo(path=path, base_path=path,
                                           vobstag=self.vobstag)

        # We didn't found uuid but if version is >= 1.5.3
        # we can try to use VOB's name hoping it is better
        # than current VOB's path.
        if parse_version(server.rb_version) >= parse_version('1.5.3'):
            self.path = cpath.split(self.vobstag)[1]

        # We didn't find a matching repository on the server.
        # We'll just return self and hope for the best.
        return self

    def _get_vobs_uuid(self, vobstag):
        property_lines = execute(['cleartool', 'lsvob', '-long', vobstag],
                                 split_lines=True)
        for line in property_lines:
            if line.startswith('Vob family uuid:'):
                return line.split(' ')[-1].rstrip()

    def _get_repository_info(self, server, repository):
        try:
            return server.get_repository_info(repository['id'])
        except APIError as e:
            # If the server couldn't fetch the repository info, it will return
            # code 210. Ignore those.
            # Other more serious errors should still be raised, though.
            if e.error_code == 210:
                return None

            raise e
