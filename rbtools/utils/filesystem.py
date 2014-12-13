from __future__ import unicode_literals

import logging
import os
import shutil
import tempfile

from rbtools.utils.process import die


CONFIG_FILE = '.reviewboardrc'

tempfiles = []
tempdirs = []
builtin = {}


def cleanup_tempfiles():
    for tmpfile in tempfiles:
        try:
            os.unlink(tmpfile)
        except:
            pass

    for tmpdir in tempdirs:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _load_python_file(filename, config):
    with open(filename) as f:
        exec(compile(f.read(), filename, 'exec'), config)
        return config


def load_config_files(homepath):
    """Loads data from .reviewboardrc files."""
    def _load_config(path):
        config = {
            'TREES': {},
            'ALIASES': {},
        }

        filename = os.path.join(path, CONFIG_FILE)

        if os.path.exists(filename):
            try:
                config = _load_python_file(filename, config)
            except SyntaxError as e:
                die('Syntax error in config file: %s\n'
                    'Line %i offset %i\n' % (filename, e.lineno, e.offset))

            return dict((k, config[k])
                        for k in set(config.keys()) - set(builtin.keys()))

        return None

    configs = []

    for path in walk_parents(os.getcwd()):
        config = _load_config(path)

        if config:
            configs.append(config)

    user_config = _load_config(homepath)
    if user_config:
        configs.append(user_config)

    return user_config, configs


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
    if 'APPDATA' in os.environ:
        return os.environ['APPDATA']
    elif 'HOME' in os.environ:
        return os.environ['HOME']
    else:
        return ''


def get_config_paths():
    """Return the paths to each .reviewboardrc influencing the cwd.

    A list of paths to .reviewboardrc files will be returned, where
    each subsequent list entry should take precedence over the previous.
    i.e. configuration found in files further down the list will take
    precedence.
    """
    config_paths = []
    for path in walk_parents(os.getcwd()):
        filename = os.path.join(path, CONFIG_FILE)
        if os.path.exists(filename):
            config_paths.insert(0, filename)

    filename = os.path.join(get_home_path(), CONFIG_FILE)
    if os.path.exists(filename):
        config_paths.append(filename)

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
        die('Syntax error in config file: %s\n'
            'Line %i offset %i\n' % (filename, e.lineno, e.offset))

    return dict((k, config[k])
                for k in set(config.keys()) - set(builtin.keys()))


def load_config():
    """Load configuration from .reviewboardrc files.

    This will read all of the .reviewboardrc files influencing the
    cwd and return a dictionary containing the configuration.
    """
    config = {}
    trees = {}
    aliases = {}

    for filename in get_config_paths():
        parsed_config = parse_config_file(filename)

        trees.update(parsed_config.pop('TREES'))
        aliases.update(parsed_config.pop('ALIASES'))
        config.update(parsed_config)

    config['TREES'] = trees
    config['ALIASES'] = aliases

    return config


# This extracts a dictionary of the built-in globals in order to have a clean
# dictionary of settings, consisting of only what has been specified in the
# config file.
exec('True', builtin)
