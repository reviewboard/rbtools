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

from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages

from setuptools.command.test import test


VERSION = "0.2beta2"
IS_RELEASE = False


if IS_RELEASE:
    download_url = "http://downloads.review-board.org/releases/"
else:
    download_url = "http://downloads.review-board.org/nightlies/"


setup(name="RBTools",
      version=VERSION,
      license="MIT",
      description="Command line tools for use with Review Board",
      entry_points = {
          'console_scripts': [
              'post-review = rbtools.postreview:main',
          ],
      },
      install_requires=['simplejson'],
      dependency_links = [
          download_url,
      ],
      packages=find_packages(),
      include_package_data=True,
      maintainer="Christian Hammond",
      maintainer_email="chipx86@chipx86.com",
      url="http://www.review-board.org/",
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
