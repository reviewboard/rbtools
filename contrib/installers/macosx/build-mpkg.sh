#!/bin/sh
#
# Builds RBTools installers for macOS.
#
# This will build an installer that users can download and use on
# Snow Leopard and higher.
#
# This package ships both Python 2.6 and 2.7 modules, in order to be
# compatible with any custom or third-party scripts that want to use the
# API.
#
# By default, this will attempt to sign the installer with the official
# certificate. This requires that the private key for the certificate exists
# on the machine building the installer. To disable signing a package, set
# RBTOOLS_SIGN_PACKAGE=no in the environment variable, or to change the
# certificate used, set RBTOOLS_SIGNATURE to the Common Name of the
# desired certificate.

PWD=`pwd`

if test ! -e "$PWD/setup.py"; then
    echo "This must be run from the root of the RBTools tree." >&2
    exit 1
fi

which python2.7 >/dev/null || {
    echo "python2.7 could not be found." >&2
    exit 1
}

which pip2.6 >/dev/null || {
    echo "pip2.6 could not be found." >&2
    exit 1
}

which pip2.7 >/dev/null || {
    echo "pip2.7 could not be found." >&2
    exit 1
}

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
    --root $PKG_SRC
"

# Clean up from any previous builds.
rm -rf $PKG_BASE
$MKDIR -p $PKG_SRC $PKG_PYBUILD $PKG_BUILD $PKG_RESOURCES $PKG_DEST

# Install RBTools and dependencies.
#
# We start off by building a wheel distribution, which we can build in
# "release" package mode, fixing egg filenames. Then we install that using
# pip on each supported version of Python, ensuring we have modern packages
# with all dependencies installed.
#
# Both the 2.6 and 2.7 binaries for "rbt" will end up being installed. Pip
# will install into /Library/Frameworks/Python.framework/Versions/2.7/bin for
# Python 2.7, and /usr/local/bin for 2.6. On modern macOS, the Python binary
# directories are searched first, allowing the 2.7 version to be favored over
# the 2.6 version.
python2.7 ./setup.py release bdist_wheel \
    -b $PKG_PYBUILD/build \
    -d $PKG_PYBUILD/dist

RBTOOLS_PY2_FILENAME=$PKG_PYBUILD/dist/RBTools-*-py2-none-any.whl
pip2.6 install $PIP_INSTALL_ARGS $RBTOOLS_PY2_FILENAME
pip2.7 install $PIP_INSTALL_ARGS $RBTOOLS_PY2_FILENAME

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
