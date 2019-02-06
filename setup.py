#!/usr/bin/env python
#
# setup.py -- Installation for rbtools.
#
# Copyright (C) 2009 Christian Hammond
# Copyright (C) 2009 David Trowbridge
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import unicode_literals

import sys

from setuptools import setup, find_packages

from rbtools import get_package_version, is_release, VERSION


# Make sure this is a version of Python we are compatible with. This should
# prevent people on older versions from unintentionally trying to install
# the source tarball, and failing.
if sys.hexversion < 0x02050000:
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please install RBTools 0.5.x or upgrade Python to at least '
        '2.7.x.\n' % get_package_version())
    sys.exit(1)
elif sys.hexversion < 0x02060000:
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please install RBTools 0.6.x or upgrade Python to at least '
        '2.7.x.\n' % get_package_version())
    sys.exit(1)
elif sys.hexversion < 0x02070000:
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please install RBTools 0.7.x or upgrade Python to at least '
        '2.7.x.\n' % get_package_version())
    sys.exit(1)
elif 0x03000000 <= sys.hexversion < 0x03050000:
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please use either Python 2.7 or 3.5+.\n'
        % get_package_version())
    sys.exit(1)


rb_commands = [
    'api-get = rbtools.commands.api_get:APIGet',
    'alias = rbtools.commands.alias:Alias',
    'attach = rbtools.commands.attach:Attach',
    'clear-cache = rbtools.commands.clearcache:ClearCache',
    'close = rbtools.commands.close:Close',
    'diff = rbtools.commands.diff:Diff',
    'land = rbtools.commands.land:Land',
    'list-repo-types = rbtools.commands.list_repo_types:ListRepoTypes',
    'login = rbtools.commands.login:Login',
    'logout = rbtools.commands.logout:Logout',
    'patch = rbtools.commands.patch:Patch',
    'post = rbtools.commands.post:Post',
    'publish = rbtools.commands.publish:Publish',
    'setup-completion = rbtools.commands.setup_completion:SetupCompletion',
    'setup-repo = rbtools.commands.setup_repo:SetupRepo',
    'stamp = rbtools.commands.stamp:Stamp',
    'status = rbtools.commands.status:Status',
    'status-update = rbtools.commands.status_update:StatusUpdate',
]

scm_clients = [
    'bazaar = rbtools.clients.bazaar:BazaarClient',
    'clearcase = rbtools.clients.clearcase:ClearCaseClient',
    'cvs = rbtools.clients.cvs:CVSClient',
    'git = rbtools.clients.git:GitClient',
    'mercurial = rbtools.clients.mercurial:MercurialClient',
    'perforce = rbtools.clients.perforce:PerforceClient',
    'plastic = rbtools.clients.plastic:PlasticClient',
    'svn = rbtools.clients.svn:SVNClient',
    'tfs = rbtools.clients.tfs:TFSClient',
]


PACKAGE_NAME = 'RBTools'

with open('README.md') as fp:
    long_description = fp.read()


setup(
    name=PACKAGE_NAME,
    version=get_package_version(),
    license='MIT',
    description=(
        'Command line tools and API for working with code and document '
        'reviews on Review Board'
    ),
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Beanbag, Inc.',
    author_email='reviewboard@googlegroups.com',
    entry_points={
        'console_scripts': [
            'rbt = rbtools.commands.main:main',
        ],
        'rbtools_commands': rb_commands,
        'rbtools_scm_clients': scm_clients,
    },
    install_requires=[
        'backports.shutil_get_terminal_size; python_version<"3.0"',
        'colorama',
        'six>=1.8.0',
        'texttable',
        'tqdm',
    ],
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    url='https://www.reviewboard.org/downloads/rbtools/',
    download_url=('https://downloads.reviewboard.org/releases/%s/%s.%s/'
                  % (PACKAGE_NAME, VERSION[0], VERSION[1])),
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Framework :: Review Board',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development',
        'Topic :: Software Development :: Quality Assurance',
    ],
)
