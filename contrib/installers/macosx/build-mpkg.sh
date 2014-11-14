#!/bin/sh
#
# Builds RBTools installers for MacOS X.
#
# This will build an installer that users can download and use on
# Snow Leopard and higher.
#
# This package ships both Python 2.6 and 2.7 modules, in order to be
# compatible with any custom or third-party scripts that want to use the
# API.

PWD=`pwd`

if test ! -e "$PWD/setup.py"; then
    echo "This must be run from the root of the RBTools tree." >&2
    exit 1
fi

PACKAGE_NAME=RBTools
IDENTIFIER=org.reviewboard.rbtools

# Figure out the version of the package.
VERSION=`python -c 'import rbtools; print rbtools.get_package_version()'`

DATA_SRC=contrib/installers/macosx
RESOURCES_SRC=$DATA_SRC/resources
PKG_BASE=$PWD/build/osx-pkg
PKG_DEPS=$PKG_BASE/deps
PKG_BUILD=$PKG_BASE/build
PKG_SRC=$PKG_BASE/src
PKG_RESOURCES=$PKG_BASE/resources
PKG_DEST=$PWD/dist

# Note that we want explicit paths so that we don't use the version in a
# virtualenv. For consistency and safety, we'll just do the same for all
# executables.
PYTHON_26=/usr/bin/python2.6
PYTHON_27=/usr/bin/python2.7
EASY_INSTALL_26=/usr/bin/easy_install-2.6
TIFFUTIL=/usr/bin/tiffutil
PKGBUILD=/usr/bin/pkgbuild
PRODUCTBUILD=/usr/bin/productbuild
RM=/bin/rm
MKDIR=/bin/mkdir
CP=/bin/cp

PY_INSTALL_ARGS="--root $PKG_SRC"

# Clean up from any previous builds.
rm -rf $PKG_BASE
$MKDIR -p $PKG_SRC $PKG_DEPS $PKG_BUILD $PKG_RESOURCES $PKG_DEST

# Python 2.6 requires the argparse module, so install that first. We don't
# need this for Python 2.7.
$EASY_INSTALL_26 -q --editable --always-copy --build-directory $PKG_DEPS argparse
pushd $PKG_DEPS/argparse
$PYTHON_26 ./setup.py install $PY_INSTALL_ARGS
popd

# Install the six module.
$EASY_INSTALL_26 -q --editable --always-copy --build-directory $PKG_DEPS six
pushd $PKG_DEPS/six
$PYTHON_26 ./setup.py install $PY_INSTALL_ARGS
$PYTHON_27 ./setup.py install $PY_INSTALL_ARGS
popd

# Note the ordering. We're going to install the Python 2.6 version last,
# so that `rbt` will point to it. This ensures compatibility with
# Snow Leopard and higher.
$PYTHON_27 ./setup.py install $PY_INSTALL_ARGS
$PYTHON_26 ./setup.py install $PY_INSTALL_ARGS

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
$PRODUCTBUILD \
    --distribution contrib/installers/macosx/distribution.xml \
    --resources $PKG_RESOURCES \
    --package-path $PKG_BUILD \
    --version $VERSION \
    $PKG_DEST/$PACKAGE_NAME-$VERSION.pkg
