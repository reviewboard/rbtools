#!/usr/bin/env python

from __future__ import unicode_literals

import os
import sys

import nose


def run_tests():
    """Run the test suite."""
    nose_argv = [
        'runtests.py',
        '-v',
        '--match=^test',
        '--with-id',
    ]

    if '--with-coverage' in sys.argv:
        sys.argv.remove('--with-coverage')
        nose_argv += [
            '--with-coverage',
            '--cover-inclusive',
            '--cover-package=rbtools',
        ]

    if len(sys.argv) > 1:
        nose_argv += sys.argv[1:]

    nose.run(argv=nose_argv)


if __name__ == '__main__':
    os.chdir(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, os.getcwd())
    run_tests()
