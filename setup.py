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


PACKAGE_NAME = 'RBTools'

if is_release():
    download_url = "http://downloads.reviewboard.org/releases/%s/%s.%s/" % \
                   (PACKAGE_NAME, VERSION[0], VERSION[1])
else:
    download_url = "http://downloads.reviewboard.org/nightlies/"


install_requires = [
    'backports.shutil_get_terminal_size',
    'colorama',
    'six>=1.8.0',
    'texttable',
    'tqdm',
]


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
    install_requires.append('argparse')
elif 0x03000000 <= sys.hexversion < 0x03050000:
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please use either Python 2.7 or 3.5+.\n'
        % get_package_version())


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

setup(name=PACKAGE_NAME,
      version=get_package_version(),
      license="MIT",
      description="Command line tools for use with Review Board",
      entry_points={
          'console_scripts': [
              'rbt = rbtools.commands.main:main',
          ],
          'rbtools_commands': rb_commands,
          'rbtools_scm_clients': scm_clients,
      },
      install_requires=install_requires,
      dependency_links=[
          download_url,
      ],
      packages=find_packages(),
      include_package_data=True,
      maintainer="Christian Hammond",
      maintainer_email="chipx86@chipx86.com",
      url="http://www.reviewboard.org/",
      download_url=download_url,
      classifiers=[
          "Development Status :: 4 - Beta",
          "Environment :: Console",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: MIT License",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Topic :: Software Development",
      ])
