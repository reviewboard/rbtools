from __future__ import unicode_literals

import json
import logging
import os
import shutil
import sys
import tempfile


CONFIG_FILE = '.reviewboardrc'

tempfiles = []
tempdirs = []
builtin = {}


def is_exe_in_path(name):
    """Checks whether an executable is in the user's search path.

    This expects a name without any system-specific executable extension.
    It will append the proper extension as necessary. For example,
    use "myapp" and not "myapp.exe".

    This will return True if the app is in the path, or False otherwise.

    Taken from djblets.util.filesystem to avoid an extra dependency
    """
    if sys.platform == 'win32' and not name.endswith('.exe'):
        name += '.exe'

    for dir in os.environ['PATH'].split(os.pathsep):
        if os.path.exists(os.path.join(dir, name)):
            return True

    return False


def cleanup_tempfiles():
    for tmpfile in tempfiles:
        try:
            os.unlink(tmpfile)
        except OSError:
            pass

    for tmpdir in tempdirs:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _load_python_file(filename, config):
    with open(filename) as f:
        exec(compile(f.read(), filename, 'exec'), config)
        return config


def make_tempfile(content=None):
    """Creates a temporary file and returns the path.

    The path is stored in an array for later cleanup.
    """
    fd, tmpfile = tempfile.mkstemp()

    if content:
        os.write(fd, content)

    os.close(fd)
    tempfiles.append(tmpfile)
    return tmpfile


def make_tempdir(parent=None):
    """Creates a temporary directory and returns the path.

    The path is stored in an array for later cleanup.
    """
    tmpdir = tempfile.mkdtemp(dir=parent)
    tempdirs.append(tmpdir)

    return tmpdir


def make_empty_files(files):
    """Creates each file in the given list and any intermediate directories."""
    for f in files:
        path = os.path.dirname(f)

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                logging.error('Unable to create directory %s: %s', path, e)
                continue

        try:
            with open(f, 'w'):
                # Set the file access and modified times to the current time.
                os.utime(f, None)
        except IOError as e:
            logging.error('Unable to create empty file %s: %s', f, e)


def walk_parents(path):
    """Walks up the tree to the root directory."""
    while os.path.splitdrive(path)[1] != os.sep:
        yield path
        path = os.path.dirname(path)


def get_home_path():
    """Retrieve the homepath."""
    if 'HOME' in os.environ:
        return os.environ['HOME']
    elif 'APPDATA' in os.environ:
        return os.environ['APPDATA']
    else:
        return ''


def get_config_paths():
    """Return the paths to each :file:`.reviewboardrc` influencing the cwd.

    A list of paths to :file:`.reviewboardrc` files will be returned, where
    each subsequent list entry should have lower precedence than the previous.
    i.e. configuration found in files further up the list will take precedence.

    Configuration in the paths set in :envvar:`$RBTOOLS_CONFIG_PATH` will take
    precedence over files found in the current working directory or its
    parents.
    """
    config_paths = []

    # Apply config files from $RBTOOLS_CONFIG_PATH first, ...
    for path in os.environ.get('RBTOOLS_CONFIG_PATH', '').split(os.pathsep):
        # Filter out empty paths, this also takes care of if
        # $RBTOOLS_CONFIG_PATH is unset or empty.
        if not path:
            continue

        filename = os.path.realpath(os.path.join(path, CONFIG_FILE))

        if os.path.exists(filename) and filename not in config_paths:
            config_paths.append(filename)

    # ... then config files from the current or parent directories.
    for path in walk_parents(os.getcwd()):
        filename = os.path.realpath(os.path.join(path, CONFIG_FILE))

        if os.path.exists(filename) and filename not in config_paths:
            config_paths.append(filename)

    # Finally, the user's own config file.
    home_config_path = os.path.realpath(os.path.join(get_home_path(),
                                                     CONFIG_FILE))

    if (os.path.exists(home_config_path) and
        home_config_path not in config_paths):
        config_paths.append(home_config_path)

    return config_paths


def parse_config_file(filename):
    """Parse a .reviewboardrc file.

    Returns a dictionary containing the configuration from the file.

    The ``filename`` argument should contain a full path to a
    .reviewboardrc file.
    """
    config = {
        'TREES': {},
        'ALIASES': {},
    }

    try:
        config = _load_python_file(filename, config)
    except SyntaxError as e:
        raise Exception('Syntax error in config file: %s\n'
                        'Line %i offset %i\n'
                        % (filename, e.lineno, e.offset))

    return dict((k, config[k])
                for k in set(config.keys()) - set(builtin.keys()))


def load_config():
    """Load configuration from .reviewboardrc files.

    This will read all of the .reviewboardrc files influencing the
    cwd and return a dictionary containing the configuration.
    """
    nested_config = {
        'ALIASES': {},
        'COLOR': {
            'INFO': None,
            'DEBUG': None,
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red'
        },
        'TREES': {},
    }
    config = {}

    for filename in reversed(get_config_paths()):
        parsed_config = parse_config_file(filename)

        for key in nested_config:
            nested_config[key].update(parsed_config.pop(key, {}))

        config.update(parsed_config)

    config.update(nested_config)

    return config


# This extracts a dictionary of the built-in globals in order to have a clean
# dictionary of settings, consisting of only what has been specified in the
# config file.
exec('True', builtin)
