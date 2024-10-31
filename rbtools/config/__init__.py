"""Configuration management for RBTools.

This provides convenience imports for the following:

.. autosummary::

   ~rbtools.config.config.RBToolsConfig
   ~rbtools.config.loader.get_config_paths
   ~rbtools.config.loader.load_config
   ~rbtools.config.loader.parse_config_file

Version Added:
    5.0
"""

from rbtools.config.config import ConfigData, RBToolsConfig
from rbtools.config.loader import (get_config_paths,
                                   load_config,
                                   parse_config_file)


__all__ = (
    'ConfigData',
    'RBToolsConfig',
    'get_config_paths',
    'load_config',
    'parse_config_file',
)
