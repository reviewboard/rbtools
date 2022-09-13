"""Unit tests for TFSClient."""

import argparse
import os
import re

import kgb

from rbtools.clients.errors import (InvalidRevisionSpecError,
                                    SCMClientDependencyError,
                                    TooManyRevisionsError)
from rbtools.clients.tests import SCMClientTestCase
from rbtools.clients.tfs import (BaseTFWrapper,
                                 TEEWrapper,
                                 TFExeWrapper,
                                 TFHelperWrapper,
                                 TFSClient)
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_install
from rbtools.utils.process import run_process_exec


class TFExeWrapperTests(SCMClientTestCase):
    """Unit tests for TFExeWrapper."""

    def test_check_dependencies_with_found(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe found"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Version Control Tool, Version 15\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()
        wrapper.check_dependencies()

        self.assertSpyCallCount(run_process_exec, 1)

    def test_check_dependencies_with_found_wrong_version(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe found but
        wrong version
        """
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Version Control Tool, Version 14\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(run_process_exec, 1)
        self.assertEqual(ctx.exception.missing_exes, ['tf'])

    def test_check_dependencies_with_not_found(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe not found"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'op': kgb.SpyOpRaise(FileNotFoundError),
            },
        ]))

        wrapper = TFExeWrapper()

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(run_process_exec, 1)
        self.assertEqual(ctx.exception.missing_exes, ['tf'])

    def test_parse_revision_spec_with_0_revisions(self):
        """Testing TFExeWrapper.parse_revision_spec with 0 revisions"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:W',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 123\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        self.assertEqual(
            wrapper.parse_revision_spec([]),
            {
                'base': '123',
                'tip': '--rbtools-working-copy',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_1_revision(self):
        """Testing TFExeWrapper.parse_revision_spec with 1 revision"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:Lrev',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 123\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev']),
            {
                'base': '122',
                'tip': '123',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_2_revisions(self):
        """Testing TFExeWrapper.parse_revision_spec with 2 revisions"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:Lrev1',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 123\n',
                    b'',
                )),
            },
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:124',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 124\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1', '124']),
            {
                'base': '123',
                'tip': '124',
            })

        self.assertSpyCallCount(run_process_exec, 2)

    def test_parse_revision_spec_with_3_revisions(self):
        """Testing TFExeWrapper.parse_revision_spec with 3 revisions"""
        wrapper = TFExeWrapper()

        with self.assertRaises(TooManyRevisionsError):
            wrapper.parse_revision_spec(['Lrev1', '124', '125'])

    def test_parse_revision_spec_with_r1_tilde_t2(self):
        """Testing TFExeWrapper.parse_revision_spec with r1~r2"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:Lrev1',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 123\n',
                    b'',
                )),
            },
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:Lrev2',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'Changeset: 456\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1~Lrev2']),
            {
                'base': '123',
                'tip': '456',
            })

        self.assertSpyCallCount(run_process_exec, 2)

    def test_parse_revision_spec_with_no_changeset_found(self):
        """Testing TFExeWrapper.parse_revision_spec with no changeset found"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', 'vc', 'history', '/stopafter:1',
                    '/recursive', '/format:detailed', '/version:W',
                    cwd, '/noprompt',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'',
                    b'',
                )),
            },
        ]))

        wrapper = TFExeWrapper()

        message = '"W" does not appear to be a valid versionspec'

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            wrapper.parse_revision_spec([])


class TFHelperWrapperTests(SCMClientTestCase):
    """Unit tests for TFHelperWrapper."""

    def test_check_dependencies_with_found(self):
        """Testing TFHelperWrapper.check_dependencies with java and helper
        found
        """
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['java'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = __file__
        wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)

    def test_check_dependencies_with_helper_path_not_found(self):
        """Testing TFHelperWrapper.check_dependencies with helper path not
        found
        """
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['java'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = __file__ + 'xxx'

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(ctx.exception.missing_exes, [wrapper.helper_path])

    def test_check_dependencies_with_java_not_found(self):
        """Testing TFHelperWrapper.check_dependencies with java not found"""
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['java'],),
                'op': kgb.SpyOpReturn(False),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = __file__

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(ctx.exception.missing_exes, ['java'])

    def test_check_dependencies_with_not_found(self):
        """Testing TFHelperWrapper.check_dependencies with no dependencies
        found
        """
        self.spy_on(check_install, op=kgb.SpyOpMatchAny([
            {
                'args': (['java'],),
                'op': kgb.SpyOpReturn(False),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = __file__ + 'xxx'

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(ctx.exception.missing_exes,
                         [wrapper.helper_path, 'java'])

    def test_parse_revision_spec_with_0_revisions(self):
        """Testing TFHelperWrapper.parse_revision_spec with 0 revisions"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'123\n--rb-tfs-working-copy\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        self.assertEqual(
            wrapper.parse_revision_spec([]),
            {
                'base': '123',
                'tip': '--rb-tfs-working-copy',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_1_revision(self):
        """Testing TFHelperWrapper.parse_revision_spec with 1 revision"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision', 'Lrev',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'122\n123\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev']),
            {
                'base': '122',
                'tip': '123',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_2_revisions(self):
        """Testing TFHelperWrapper.parse_revision_spec with 2 revisions"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision', 'Lrev1', '124',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'123\n124\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1', '124']),
            {
                'base': '123',
                'tip': '124',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_3_revisions(self):
        """Testing TFHelperWrapper.parse_revision_spec with 3 revisions"""
        wrapper = TFHelperWrapper()

        with self.assertRaises(TooManyRevisionsError):
            wrapper.parse_revision_spec(['Lrev1', '124', '125'])

    def test_parse_revision_spec_with_r1_tilde_t2(self):
        """Testing TFHelperWrapper.parse_revision_spec with r1~r2"""
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision', 'Lrev1~Lrev2',
                ],),
                'op': kgb.SpyOpReturn((
                    0,
                    b'123\n456\n',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1~Lrev2']),
            {
                'base': '123',
                'tip': '456',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_no_changeset_found(self):
        """Testing TFHelperWrapper.parse_revision_spec with no changeset
        found
        """
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision',
                ],),
                'op': kgb.SpyOpReturn((
                    1,
                    b'',
                    b'"W" does not appear to be a valid versionspec\n',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        message = '"W" does not appear to be a valid versionspec'

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            wrapper.parse_revision_spec([])

    def test_parse_revision_spec_with_no_changeset_found_no_error(self):
        """Testing TFHelperWrapper.parse_revision_spec with no changeset
        found and no error result
        """
        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'java', '-Xmx2048M', '-jar', '/path/to/rb-tfs.jar',
                    'parse-revision', 'blah',
                ],),
                'op': kgb.SpyOpReturn((
                    1,
                    b'',
                    b'',
                )),
            },
        ]))

        wrapper = TFHelperWrapper()
        wrapper.helper_path = '/path/to/rb-tfs.jar'

        message = "Unexpected error while parsing revision spec ['blah']"

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            wrapper.parse_revision_spec(['blah'])


class TEEWrapperTests(SCMClientTestCase):
    """Unit tests for TEEWrapper."""

    def test_check_dependencies_with_found_on_windows(self):
        """Testing TEEWrapper.check_dependencies with found on Windows"""
        self.spy_on(
            TEEWrapper.get_default_tf_locations,
            op=kgb.SpyOpReturn(TEEWrapper.get_default_tf_locations('windows')))

        self.spy_on(check_install, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['tf.cmd', 'help'],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': ([
                    '%programfiles(x86)%\\Microsoft Visual Studio 12.0\\'
                    'Common7\\IDE\\tf.cmd',
                    'help',
                ],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': ([
                    '%programfiles%\\Microsoft Team Foundation Server 12.0\\'
                    'Tools\\tf.cmd',
                    'help',
                ],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 3)
        self.assertEqual(
            wrapper.tf,
            '%programfiles%\\Microsoft Team Foundation Server 12.0\\'
            'Tools\\tf.cmd')

    def test_check_dependencies_with_found_on_linux(self):
        """Testing TEEWrapper.check_dependencies with found on Linux"""
        self.spy_on(
            TEEWrapper.get_default_tf_locations,
            op=kgb.SpyOpReturn(TEEWrapper.get_default_tf_locations('linux')))

        self.spy_on(check_install, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['tf', 'help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(wrapper.tf, 'tf')

    def test_check_dependencies_with_found_with_custom(self):
        """Testing TEEWrapper.check_dependencies with found using custom
        path
        """
        self.spy_on(
            TEEWrapper.get_default_tf_locations,
            op=kgb.SpyOpReturn(TEEWrapper.get_default_tf_locations('linux')))

        self.spy_on(check_install, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['/path/to/my-tf', 'help'],),
                'op': kgb.SpyOpReturn(True),
            },
        ]))

        options = argparse.Namespace()
        options.tf_cmd = '/path/to/my-tf'

        wrapper = TEEWrapper(options=options)
        wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 1)
        self.assertEqual(wrapper.tf, '/path/to/my-tf')

    def test_check_dependencies_with_not_found(self):
        """Testing TEEWrapper.check_dependencies with not found"""
        self.spy_on(
            TEEWrapper.get_default_tf_locations,
            op=kgb.SpyOpReturn(TEEWrapper.get_default_tf_locations('windows')))

        self.spy_on(check_install, op=kgb.SpyOpMatchInOrder([
            {
                'args': (['/path/to/my-tf', 'help'],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': (['tf.cmd', 'help'],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': ([
                    '%programfiles(x86)%\\Microsoft Visual Studio 12.0\\'
                    'Common7\\IDE\\tf.cmd',
                    'help',
                ],),
                'op': kgb.SpyOpReturn(False),
            },
            {
                'args': ([
                    '%programfiles%\\Microsoft Team Foundation Server 12.0\\'
                    'Tools\\tf.cmd',
                    'help',
                ],),
                'op': kgb.SpyOpReturn(False),
            },
        ]))

        options = argparse.Namespace()
        options.tf_cmd = '/path/to/my-tf'

        wrapper = TEEWrapper(options=options)

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(check_install, 4)
        self.assertEqual(
            ctx.exception.missing_exes,
            [(
                '/path/to/my-tf',
                'tf.cmd',
                ('%programfiles(x86)%\\Microsoft Visual Studio 12.0\\'
                 'Common7\\IDE\\tf.cmd'),
                ('%programfiles%\\Microsoft Team Foundation Server 12.0\\'
                 'Tools\\tf.cmd'),
            )])

    def test_parse_revision_spec_with_0_revisions(self):
        """Testing TEEWrapper.parse_revision_spec with 0 revisions"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="123"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        self.assertEqual(
            wrapper.parse_revision_spec([]),
            {
                'base': '123',
                'tip': '--rbtools-working-copy',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_1_revision(self):
        """Testing TEEWrapper.parse_revision_spec with 1 revision"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:Lrev', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="123"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev']),
            {
                'base': '122',
                'tip': '123',
            })

        self.assertSpyCallCount(run_process_exec, 1)

    def test_parse_revision_spec_with_2_revisions(self):
        """Testing TEEWrapper.parse_revision_spec with 2 revisions"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:Lrev1', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="123"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:124', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="124"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1', '124']),
            {
                'base': '123',
                'tip': '124',
            })

        self.assertSpyCallCount(run_process_exec, 2)

    def test_parse_revision_spec_with_3_revisions(self):
        """Testing TEEWrapper.parse_revision_spec with 3 revisions"""
        wrapper = TEEWrapper()

        with self.assertRaises(TooManyRevisionsError):
            wrapper.parse_revision_spec(['Lrev1', '124', '125'])

    def test_parse_revision_spec_with_r1_tilde_t2(self):
        """Testing TEEWrapper.parse_revision_spec with r1~r2"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:Lrev1', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="123"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', '-version:Lrev2', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets>\n'
                    b' <changeset id="456"/>\n'
                    b'</changesets>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        self.assertEqual(
            wrapper.parse_revision_spec(['Lrev1~Lrev2']),
            {
                'base': '123',
                'tip': '456',
            })

        self.assertSpyCallCount(run_process_exec, 2)

    def test_parse_revision_spec_with_no_changeset_found(self):
        """Testing TEEWrapper.parse_revision_spec with no changeset found"""
        cwd = os.getcwd()

        self.spy_on(run_process_exec, op=kgb.SpyOpMatchInOrder([
            {
                'args': ([
                    'tf', '-noprompt', 'history', '-stopafter:1',
                    '-recursive', '-format:xml', cwd,
                ],),
                'op': kgb.SpyOpReturn((
                    0,

                    # NOTE: We are not sensitive to the root element name,
                    #       and at the time of this writing, there is no
                    #       public documentation (or local setup) capable
                    #       of showing this. <changesets> is used as a
                    #       possibility.
                    b'<?xml version="1.0" encoding="utf-8"?>\n'
                    b'\n'
                    b'<changesets/>\n',

                    b'',
                )),
            },
        ]))

        wrapper = TEEWrapper()
        wrapper.tf = 'tf'

        message = '"W" does not appear to be a valid versionspec'

        with self.assertRaisesMessage(InvalidRevisionSpecError, message):
            wrapper.parse_revision_spec([])


class TFSClientTests(SCMClientTestCase):
    """Unit tests for TFSClient."""

    scmclient_cls = TFSClient

    def test_check_dependencies_with_tf_exe_found(self):
        """Testing TFSClient.check_dependencies with tf.exe found"""
        self.spy_on(TFExeWrapper.check_dependencies,
                    owner=TFExeWrapper,
                    op=kgb.SpyOpReturn(None))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertIsInstance(client.tf_wrapper, TFExeWrapper)

    def test_check_dependencies_with_tf_helper_found(self):
        """Testing TFSClient.check_dependencies with TF helper found"""
        self.spy_on(TFExeWrapper.check_dependencies,
                    owner=TFExeWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TFHelperWrapper.check_dependencies,
                    owner=TFHelperWrapper,
                    op=kgb.SpyOpReturn(None))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertIsInstance(client.tf_wrapper, TFHelperWrapper)

    def test_check_dependencies_with_tee_found(self):
        """Testing TFSClient.check_dependencies with TEE found"""
        self.spy_on(TFExeWrapper.check_dependencies,
                    owner=TFExeWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TFHelperWrapper.check_dependencies,
                    owner=TFHelperWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TEEWrapper.check_dependencies,
                    owner=TEEWrapper,
                    op=kgb.SpyOpReturn(None))

        client = self.build_client(setup=False)
        client.check_dependencies()

        self.assertIsInstance(client.tf_wrapper, TEEWrapper)

    def test_check_dependencies_with_not_found(self):
        """Testing TFSClient.check_dependencies with not found"""
        self.spy_on(TFExeWrapper.check_dependencies,
                    owner=TFExeWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TFHelperWrapper.check_dependencies,
                    owner=TFHelperWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(TEEWrapper.check_dependencies,
                    owner=TEEWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))

        client = self.build_client(setup=False)

        with self.assertRaises(SCMClientDependencyError) as ctx:
            client.check_dependencies()

        self.assertEqual(
            ctx.exception.missing_exes,
            [(
                'VS2017+ tf',
                'Team Explorer Everywhere tf.cmd',
                'Our wrapper (rbt install tfs)',
            )])

        # This should be the fallback.
        self.assertIsInstance(client.tf_wrapper, TEEWrapper)

    def test_tf_wrapper_with_deps_missing(self):
        """Testing TFSClient.get_local_path with dependencies missing"""
        self.spy_on(BaseTFWrapper.check_dependencies,
                    owner=BaseTFWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))
        self.spy_on(RemovedInRBTools50Warning.warn)

        client = self.build_client(setup=False)

        # Make sure dependencies are checked for this test before we run
        # get_local_path(). This will be the expected setup flow.
        self.assertFalse(client.has_dependencies())

        self.assertIsInstance(client.tf_wrapper, TEEWrapper)
        self.assertSpyNotCalled(RemovedInRBTools50Warning.warn)

    def test_tf_wrapper_with_deps_not_checked(self):
        """Testing TFSClient.get_local_path with dependencies not checked"""
        self.spy_on(BaseTFWrapper.check_dependencies,
                    owner=BaseTFWrapper,
                    op=kgb.SpyOpRaise(SCMClientDependencyError()))

        client = self.build_client(setup=False)

        message = re.escape(
            'Either TFSClient.setup() or TFSClient.has_dependencies() must '
            'be called before other functions are used. This will be '
            'required starting in RBTools 5.0.'
        )

        with self.assertWarnsRegex(RemovedInRBTools50Warning, message):
            client.tf_wrapper
