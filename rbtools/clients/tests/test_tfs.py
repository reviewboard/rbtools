"""Unit tests for TFSClient."""

import argparse
import re

import kgb

from rbtools.clients.errors import SCMClientDependencyError
from rbtools.clients.tests import SCMClientTestCase
from rbtools.clients.tfs import (BaseTFWrapper,
                                 TEEWrapper,
                                 TFExeWrapper,
                                 TFHelperWrapper,
                                 TFSClient)
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.checks import check_install
from rbtools.utils.process import execute


class TFExeWrapperTests(SCMClientTestCase):
    """Unit tests for TFExeWrapper."""

    def test_check_dependencies_with_found(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe found"""
        self.spy_on(execute, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'kwargs': {
                    'results_unicode': True,
                    'split_lines': False,
                    'return_error_code': False,
                    'return_errors': False,
                },
                'op': kgb.SpyOpReturn('Version Control Tool, Version 15\n'),
            },
        ]))

        wrapper = TFExeWrapper()
        wrapper.check_dependencies()

        self.assertSpyCallCount(execute, 1)

    def test_check_dependencies_with_found_wrong_version(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe found but
        wrong version
        """
        self.spy_on(execute, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'kwargs': {
                    'results_unicode': True,
                    'split_lines': False,
                    'return_error_code': False,
                    'return_errors': False,
                },
                'op': kgb.SpyOpReturn('Version Control Tool, Version 14\n'),
            },
        ]))

        wrapper = TFExeWrapper()

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(execute, 1)
        self.assertEqual(ctx.exception.missing_exes, ['tf'])

    def test_check_dependencies_with_not_found(self):
        """Testing TFExeWrapper.check_dependencies with tf.exe not found"""
        self.spy_on(execute, op=kgb.SpyOpMatchAny([
            {
                'args': (['tf', 'vc', 'help'],),
                'kwargs': {
                    'results_unicode': True,
                    'split_lines': False,
                    'return_error_code': False,
                    'return_errors': False,
                },
                'op': kgb.SpyOpReturn(None),
            },
        ]))

        wrapper = TFExeWrapper()

        with self.assertRaises(SCMClientDependencyError) as ctx:
            wrapper.check_dependencies()

        self.assertSpyCallCount(execute, 1)
        self.assertEqual(ctx.exception.missing_exes, ['tf'])


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
