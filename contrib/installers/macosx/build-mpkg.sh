#!/bin/sh
#
# Builds RBTools installers for macOS.
#
# This will build an installer that users can download and use on
# El Capitan or higher.
#
# This package ships modules for all versions of Python supported in modern
# versions of macOS, in order to be compatible with any custom or third-party
# scripts that want to use the API.
#
# By default, this will attempt to sign the installer with the official
# certificate. This requires that the private key for the certificate exists
# on the machine building the installer. To disable signing a package, set
# RBTOOLS_SIGN_PACKAGE=no in the environment variable, or to change the
# certificate used, set RBTOOLS_SIGNATURE to the Common Name of the
# desired certificate.

set -e

PWD=`pwd`

if test ! -e "$PWD/setup.py"; then
    echo "This must be run from the root of the RBTools tree." >&2
    exit 1
fi


# As of macOS High Sierra (10.13), only Python 2.7 is available natively.
# Python 3.x is not available.
PYTHON_VERSIONS=(
    2.7
)

for pyver in "${PYTHON_VERSIONS[@]}"; do
    which python${pyver} >/dev/null || {
        echo "python${pyver} could not be found." >&2
        exit 1
    }

    which pip${pyver} >/dev/null || {
        echo "pip${pyver} could not be found." >&2
        exit 1
    }
done


PACKAGE_NAME=RBTools
IDENTIFIER=org.reviewboard.rbtools

# Figure out the version of the package.
VERSION=`PYTHONPATH=. python -c 'import rbtools; print rbtools.get_package_version()'`

DATA_SRC=contrib/installers/macosx
RESOURCES_SRC=$DATA_SRC/resources
PKG_BASE=$PWD/build/osx-pkg
PKG_PYBUILD=$PKG_BASE/pybuild
PKG_BUILD=$PKG_BASE/build
PKG_SRC=$PKG_BASE/src
PKG_RESOURCES=$PKG_BASE/resources
PKG_DEST=$PWD/dist

# Note that we want explicit paths so that we don't use the version in a
# virtualenv. For consistency and safety, we'll just do the same for all
# executables.
TIFFUTIL=/usr/bin/tiffutil
PKGBUILD=/usr/bin/pkgbuild
PRODUCTBUILD=/usr/bin/productbuild
RM=/bin/rm
MKDIR=/bin/mkdir
CP=/bin/cp

PIP_INSTALL_ARGS="
    --disable-pip-version-check \
    --no-cache-dir \
    --ignore-installed \
    --force-reinstall \
    --root $PKG_SRC
"

# Clean up from any previous builds.
rm -rf $PKG_BASE
$MKDIR -p $PKG_SRC $PKG_PYBUILD $PKG_BUILD $PKG_RESOURCES $PKG_DEST

# Install RBTools and dependencies.
#
# We start off by building a wheel distribution, which we can build in
# "release" package mode. It's a universal wheel, so we'll build just one.
# Then we install that using pip for each version of Python, ensuring we
# have modern packages with all dependencies installed.
echo
echo
echo == Building Wheel package ==
echo
/usr/bin/python2.7 ./setup.py release bdist_wheel \
    -b ${PKG_PYBUILD}/build \
    -d ${PKG_PYBUILD}/dist

RBTOOLS_PACKAGE_FILENAME=${PKG_PYBUILD}/dist/RBTools-*-py2.py3-none-any.whl

for pyver in "${PYTHON_VERSIONS[@]}"; do
    # Set the PYTHONPATH to the location used for the upstream Python installer
    # builds, so that if upstream Python is installed, we'll make use of the
    # newer modules there (like pip) instead of the system Python.
    #
    # We're also going to invoke pip as a module, to avoid having to figure out
    # the right file path.
    PYTHONPATH=/Library/Frameworks/Python.framework/Versions/${pyver}/lib/python${pyver}/site-packages \
    /usr/bin/python${pyver} -m pip.__main__ install \
        $PIP_INSTALL_ARGS \
        $RBTOOLS_PACKAGE_FILENAME

    rm $RBTOOLS_PACKAGE_FILENAME
done

# Fix up the /usr/local/bin/rbt script to try to use the version of Python in
# the path, instead of a hard-coded version. For modern versions of macOS,
# this will use Python 2.7, and for older versions, 2.6.
#
# If the user has a custom Python installed (from the official Python
# installers or from Homebrew), this will favor those.
#
# If they have Python 3 as the default for "python" (which must be an explicit
# choice on their end), then they're going to have a bad time.
echo "#!/usr/bin/env python

# -*- coding: utf-8 -*-
import re
import sys

sys.path.insert(
    0, '/Library/Python/%s.%s/site-packages' % sys.version_info[:2])

from rbtools.commands.main import main


if __name__ == '__main__':
    sys.exit(main())
" > ${PKG_SRC}/usr/local/bin/rbt


# Copy any needed resource files, so that productbuild can later get to them.
$CP $RESOURCES_SRC/* $PKG_RESOURCES

# Generate a background suitable for both Retina and non-Retina use.
$TIFFUTIL \
    -cat $RESOURCES_SRC/background.tiff $RESOURCES_SRC/background@2x.tiff \
    -out $PKG_RESOURCES/background.tiff

# Build the source .pkg. This is an intermediary package that will later be
# assembled into a shippable package.
$PKGBUILD \
    --root $PKG_SRC \
    --identifier $IDENTIFIER \
    --version $VERSION \
    --ownership recommended \
    $PKG_BUILD/$PACKAGE_NAME.pkg

$CP $DATA_SRC/distribution.xml $PKG_BUILD

# Now build the actual package that we can ship.
if [ "$RBTOOLS_SIGN_PACKAGE" != "no" ]; then
    if [ -z "$RBTOOLS_SIGNATURE" ]; then
        RBTOOLS_SIGNATURE="Developer ID Installer: Beanbag, Inc. (8P6MEUDM64)"
    fi

    PRODUCTBUILD_SIGN_PARAMS="--sign \"${RBTOOLS_SIGNATURE}\" --timestamp"
fi

eval $PRODUCTBUILD \
    --distribution contrib/installers/macosx/distribution.xml \
    --resources $PKG_RESOURCES \
    --package-path $PKG_BUILD \
    --version $VERSION \
    $PRODUCTBUILD_SIGN_PARAMS \
    $PKG_DEST/$PACKAGE_NAME-$VERSION.pkg
