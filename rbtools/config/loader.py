"""Loaders for configuration files.

Version Added:
    5.0
"""

from __future__ import annotations

import os
from typing import Any, Final

from rbtools.config.config import ConfigDict, RBToolsConfig
from rbtools.config.errors import ConfigSyntaxError
from rbtools.utils.filesystem import get_home_path, walk_parents


#: Storage this module's builtins.
#:
#: This is used to exclude data from loaded Python-based
#: :file:`.reviewboardrc` configuration files.
_builtins: dict[str, Any] = {}


#: The name of the default configuration file.
CONFIG_FILENAME: Final[str] = '.reviewboardrc'


def _load_python_reviewboardrc(
    filename: str,
) -> ConfigDict:
    """Load a configuration file as Python code.

    Args:
        filename (str):
            The configuration filename.

    Returns:
        dict:
        The populated configuration dictionary.
    """
    config: ConfigDict = {}

    with open(filename) as fp:
        exec(compile(fp.read(), filename, 'exec'), config)

    return config


def get_config_paths() -> list[str]:
    """Return the paths to each :file:`.reviewboardrc` influencing the cwd.

    A list of paths to :file:`.reviewboardrc` files will be returned, where
    each subsequent list entry should have lower precedence than the previous.
    i.e. configuration found in files further up the list will take precedence.

    Configuration in the paths set in :envvar:`$RBTOOLS_CONFIG_PATH` will take
    precedence over files found in the current working directory or its
    parents.

    Returns:
        list of str:
        The list of configuration paths.
    """
    config_paths: list[str] = []

    # Apply config files from $RBTOOLS_CONFIG_PATH first, ...
    for path in os.environ.get('RBTOOLS_CONFIG_PATH', '').split(os.pathsep):
        # Filter out empty paths, this also takes care of if
        # $RBTOOLS_CONFIG_PATH is unset or empty.
        if not path:
            continue

        filename = os.path.realpath(os.path.join(path, CONFIG_FILENAME))

        if os.path.exists(filename) and filename not in config_paths:
            config_paths.append(filename)

    # ... then config files from the current or parent directories.
    for path in walk_parents(os.getcwd()):
        filename = os.path.realpath(os.path.join(path, CONFIG_FILENAME))

        if os.path.exists(filename) and filename not in config_paths:
            config_paths.append(filename)

    # Finally, the user's own config file.
    home_config_path = os.path.realpath(os.path.join(get_home_path(),
                                                     CONFIG_FILENAME))

    if (os.path.exists(home_config_path) and
        home_config_path not in config_paths):
        config_paths.append(home_config_path)

    return config_paths


def parse_config_file(
    filename: str,
) -> RBToolsConfig:
    """Parse a .reviewboardrc file.

    Returns a dictionary containing the configuration from the file.

    Args:
        filename (str):
            The full path to a :file:`.reviewboardrc` file.

    Returns:
        dict:
        The loaded configuration data.

    Raises:
        rbtools.config.errors.ConfigSyntaxError:
            There was a syntax error in the configuration file.
    """
    try:
        config = _load_python_reviewboardrc(filename)
    except SyntaxError as e:
        raise ConfigSyntaxError(filename=filename,
                                line=e.lineno,
                                column=e.offset,
                                details=str(e))

    return RBToolsConfig(
        filename=filename,
        config_dict={
            key: config[key]
            for key in set(config.keys()) - set(_builtins.keys())
        })


def load_config() -> RBToolsConfig:
    """Load configuration from .reviewboardrc files.

    This will read all of the :file:`.reviewboardrc` files influencing the
    cwd and return a dictionary containing the configuration.

    Returns:
        dict:
        The loaded configuration data.
    """
    config = RBToolsConfig()

    for filename in reversed(get_config_paths()):
        config.merge(parse_config_file(filename))

    return config


# This extracts a dictionary of the built-in globals in order to have a clean
# dictionary of settings, consisting of only what has been specified in the
# config file.
exec('True', _builtins)
