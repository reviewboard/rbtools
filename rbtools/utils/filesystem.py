"""Utilities for working with files."""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from typing import Generator, Iterable, Optional, Sequence, TYPE_CHECKING

from housekeeping import func_moved

from rbtools.deprecation import RemovedInRBTools60Warning

if TYPE_CHECKING:
    from rbtools.config import RBToolsConfig


_iter_exes_in_path_cache: dict[str, bool] = {}
tempfiles: list[str] = []
tempdirs = []


def is_exe_in_path(
    name: str,
) -> bool:
    """Return whether an executable is in the user's search path.

    This expects a name without any system-specific executable extension.
    It will append the proper extension as necessary. For example,
    use "myapp" and not "myapp.exe".

    The result will be cached. Future lookups for the same executable will
    return the same value.

    Version Changed:
        3.0:
        The result is now cached.

    Args:
        name (str):
            The name of the executable.

    Returns:
        bool:
        ``True`` if the executable is in the path. ``False`` if it is not.
    """
    return any(iter_exes_in_path(name))


def iter_exes_in_path(
    name: str,
) -> Iterable[str]:
    """Iterate through all executables with a name in the user's search path.

    This expects a name without any system-specific executable extension. It
    will append the proper extension as necessary. For example, use "myapp"
    and not "myapp.exe" or "myapp.cmd". This will look for both variations.

    Version Changed:
        4.0.1:
        On Windows, if not searching for a deliberate ``.exe`` or ``.cmd``
        extension, this will now look for variations with both extensions.

    Version Added:
        4.0

    Args:
        name (str):
            The name of the executable.

    Yields:
        str:
        The location of an executable in the path.
    """
    names: list[str] = []

    if (sys.platform == 'win32' and not name.endswith(('.exe', '.cmd'))):
        names += [
            '%s.exe' % name,
            '%s.cmd' % name,
        ]
    else:
        names.append(name)

    cache = _iter_exes_in_path_cache

    for dirname in os.environ['PATH'].split(os.pathsep):
        for name in names:
            path = os.path.join(dirname, name)

            try:
                found = cache[path]
            except KeyError:
                found = os.path.exists(path)
                cache[path] = found

            if found:
                yield path


def cleanup_tempfiles() -> None:
    """Clean up temporary files which have been created."""
    for tmpfile in tempfiles:
        try:
            os.unlink(tmpfile)
        except OSError:
            pass

    for tmpdir in tempdirs:
        shutil.rmtree(tmpdir, ignore_errors=True)


def make_tempfile(
    *,
    content: Optional[bytes] = None,
    prefix: str = 'rbtools.',
    suffix: Optional[str] = None,
    filename: Optional[str] = None,
) -> str:
    """Create a temporary file and return the path.

    If not manually removed, then the resulting temp file will be removed when
    RBTools exits (or if :py:func:`cleanup_tempfiles` is called).

    This can be given an explicit name for a temporary file, in which case
    the file will be created inside of a temporary directory (created with
    :py:func:`make_tempdir`. In this case, the parent directory will only
    be deleted when :py:func:`cleanup_tempfiles` is called.

    Args:
        content (bytes, optional):
            The content for the text file.

        prefix (str, optional):
            The prefix for the temp filename. This defaults to ``rbtools.``.

        suffix (str, optional):
            The suffix for the temp filename.

        filename (str, optional):
            An explicit name of the file. If provided, this will override
            ``suffix`` and ``prefix``.

    Returns:
        str:
        The temp file path.
    """
    if filename is not None:
        tmpdir = make_tempdir()
        tmpfile = os.path.join(tmpdir, filename)

        with open(tmpfile, 'wb') as fp:
            if content:
                fp.write(content)
    else:
        with tempfile.NamedTemporaryFile(prefix=prefix,
                                         suffix=suffix or '',
                                         delete=False) as fp:
            tmpfile = fp.name

            if content:
                fp.write(content)

    tempfiles.append(tmpfile)

    return tmpfile


def make_tempdir(
    parent: Optional[str] = None,
    track: bool = True,
) -> str:
    """Create a temporary directory and return the path.

    By default, the path will be stored in a list for cleanup when calling
    :py:func:`cleanup_tempfiles`.

    Version Changed:
        3.0:
        Added ``track``.

    Args:
        parent (str, optional):
            An optional parent directory to create the path in.

        track (bool, optional):
            Whether to track the directory for later cleanup.

            .. versionadded:: 3.0

    Returns:
        str:
        The name of the new temporary directory.
    """
    tmpdir = tempfile.mkdtemp(prefix='rbtools.',
                              dir=parent)

    if track:
        tempdirs.append(tmpdir)

    return tmpdir


def make_empty_files(
    files: Sequence[str],
) -> None:
    """Create each file in the given list and any intermediate directories.

    Args:
        files (list of str):
            The list of filenames to create.
    """
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
        except OSError as e:
            logging.error('Unable to create empty file %s: %s', f, e)


def walk_parents(
    path: str,
) -> Iterable[str]:
    """Walk up the tree to the root directory.

    Yields:
        str:
        Each directory name while walking up to the root.
    """
    while os.path.splitdrive(path)[1] != os.sep:
        yield path

        path = os.path.dirname(path)


def get_home_path() -> str:
    """Return the path to the home directory.

    Returns:
        str:
        The user's home directory (or general place to store application data).
    """
    if 'HOME' in os.environ:
        return os.environ['HOME']
    elif 'APPDATA' in os.environ:
        return os.environ['APPDATA']
    else:
        return ''


@func_moved(RemovedInRBTools60Warning,
            'rbtools.config.loader.get_config_paths')
def get_config_paths() -> Sequence[str]:
    """Return the paths to each :file:`.reviewboardrc` influencing the cwd.

    A list of paths to :file:`.reviewboardrc` files will be returned, where
    each subsequent list entry should have lower precedence than the previous.
    i.e. configuration found in files further up the list will take precedence.

    Configuration in the paths set in :envvar:`$RBTOOLS_CONFIG_PATH` will take
    precedence over files found in the current working directory or its
    parents.

    Deprecated:
        5.0:
        This has been replaced with
        :py:func:`rbtools.config.loader.get_config_paths`, and will be removed
        in RBTools 6.
    """
    from rbtools.config.loader import get_config_paths as _get_config_paths

    return _get_config_paths()


@func_moved(RemovedInRBTools60Warning,
            'rbtools.config.loader.parse_config_file')
def parse_config_file(
    filename: str,
) -> RBToolsConfig:
    """Parse a .reviewboardrc file.

    Returns a dictionary containing the configuration from the file.

    Deprecated:
        5.0:
        This has been replaced with
        :py:func:`rbtools.config.loader.parse_config_file`, and will be removed
        in RBTools 6.

    Args:
        filename (str):
            The full path to a :file:`.reviewboardrc` file.

    Returns:
        dict:
        The loaded configuration data.

    Raises:
        SyntaxError:
            There was a syntax error in the configuration file.
    """
    from rbtools.config.loader import parse_config_file as _parse_config_file

    return _parse_config_file(filename)


@func_moved(RemovedInRBTools60Warning,
            'rbtools.config.loader.load_config')
def load_config() -> RBToolsConfig:
    """Load configuration from .reviewboardrc files.

    This will read all of the :file:`.reviewboardrc` files influencing the
    cwd and return a dictionary containing the configuration.

    Deprecated:
        5.0:
        This has been replaced with
        :py:func:`rbtools.config.loader.load_config`, and will be removed in
        RBTools 6.

    Returns:
        dict:
        The loaded configuration data.
    """
    from rbtools.config.loader import load_config as _load_config

    return _load_config()


@contextmanager
def chdir(
    path: str,
) -> Generator[None, None, None]:
    """Change to the specified directory for the duration of the  context.

    Version Added:
        4.0

    Args:
        path (str):
            The path to change to.

    Context:
        Operations will run within the specified directory.

    Raises:
        FileNotFoundError:
            The provided path does not exist.
    """
    old_cwd = os.getcwd()
    os.chdir(path)

    try:
        yield
    finally:
        os.chdir(old_cwd)
