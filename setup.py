#!/usr/bin/env python
#
# setup.py -- Installation for rbtools.
#
# Copyright (C) 2009 Christian Hammond
# Copyright (C) 2009 David Trowbridge
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
import re

from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages
from setuptools.command.test import test

from rbtools import get_package_version, is_release, VERSION
from rbtools.commands.__init__ import scripts

PACKAGE_NAME = 'RBTools'

if is_release():
    download_url = "http://downloads.reviewboard.org/releases/%s/%s.%s/" % \
                   (PACKAGE_NAME, VERSION[0], VERSION[1])
else:
    download_url = "http://downloads.reviewboard.org/nightlies/"


install_requires = []


try:
    import json
except ImportError:
    install_requires.append('simplejson')


script_list = []
script_list.append('post-review = rbtools.postreview:main')
script_list.append('rb = rbtools.commands.rb:main')


for n in scripts:
    name = re.split('rb', n)[1]
    script_list.append('rb-%s = rbtools.commands.rb%s:main' % (name, name))


entry_scripts = {'console_scripts': script_list}


setup(name=PACKAGE_NAME,
      version=get_package_version(),
      license="MIT",
      description="Command line tools for use with Review Board",
      entry_points = entry_scripts,
      install_requires=install_requires,
      dependency_links = [
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
      ]
)
