"""Implementation of rbt install."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import zipfile
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from appdirs import user_data_dir

from rbtools.commands.base import BaseCommand, CommandError
from rbtools.utils.checks import check_install
from rbtools.utils.process import run_process

if TYPE_CHECKING:
    from collections.abc import Iterator


class Install(BaseCommand):
    """Install a dependency.

    This allows RBTools to install external dependencies that may be needed for
    some features.
    """

    name = 'install'
    author = 'The Review Board Project'
    description = 'Install an optional dependency.'
    args = '<package>'
    option_list = []

    package_urls = {
        'tfs': 'http://downloads.beanbaginc.com/rb-tfs/rb-tfs.zip'
    }

    def main(
        self,
        package: str,
    ) -> None:
        """Run the command.

        Args:
            package (str):
                The name of the package to install.

        Raises:
            rbtools.commands.CommandError:
                An error occurred during installation.
        """
        try:
            url = self.package_urls[package]
        except KeyError:
            err = f'Package "{package}" not found. Available packages are:\n'
            err += '\n'.join(
                f'    {package_name}'
                for package_name in self.package_urls
            )

            raise CommandError(err)

        zip_filename = self.download_file(url, label=f'Downloading {package}')

        try:
            self.check_download(url, zip_filename)
            self.unzip(
                zip_filename,
                os.path.join(user_data_dir('rbtools'), 'packages', package))
            self.console.print_success(f'Installed package {package}')
        finally:
            os.unlink(zip_filename)

    def check_download(
        self,
        url: str,
        zip_filename: str,
    ) -> None:
        """Check to see if the file was successfully downloaded.

        If the user has :command:`gpg` installed on their system, use that to
        check that the package was signed. Otherwise, check the sha256sum.

        Args:
            url (str):
                The URL that the file came from.

            zip_filename (str):
                The filename of the downloaded copy.

        Raises:
            rbtools.commands.CommandError:
                The authenticity of the file could not be verified.
        """
        logger = self.log
        validate = True

        if not check_install(['gpg']):
            self.console.print_warning(
                'gpg not installed. Skipping signature validation.')
            validate = False
        else:
            result = run_process(
                [
                    'gpg', '--recv-keys',
                    '09D506DABB62A09E891DA9F3285291B34ED1F993',
                ],
                ignore_errors=True)

            if result.exit_code != 0:
                self.console.print_warning(
                    'Unable to download verification key. Skipping signature '
                    'validation.')
                validate = False

        if validate:
            sig_filename = self.download_file(f'{url}.asc',
                                              show_progress=False)

            try:
                result = run_process(
                    ['gpg', '--verify', sig_filename, zip_filename],
                    ignore_errors=True)

                if result.exit_code == 0:
                    self.console.print_success('Verified file signature')
                else:
                    raise CommandError(
                        f'Unable to verify authenticity of file '
                        f'downloaded from {url}:\n{result.stderr.read()}'
                    )
            finally:
                os.unlink(sig_filename)
        else:
            try:
                sha_url = f'{url}.sha256sum'
                logger.debug('Downloading %s', sha_url)
                response = urlopen(sha_url)
                real_sha = response.read().decode('ascii').split(' ')[0]
            except (HTTPError, URLError) as e:
                raise CommandError(f'Error when downloading file: {e}')

            with open(zip_filename, 'rb') as f:
                our_sha = hashlib.sha256(f.read()).hexdigest()

            if real_sha == our_sha:
                self.console.print_success('Verified SHA256 hash')
            else:
                logger.debug('SHA256 hash does not match!')
                logger.debug('  Downloaded file hash was: %s', our_sha)
                logger.debug('  Expected hash was: %s', real_sha)

                raise CommandError(
                    f'Unable to verify the checksum of the downloaded copy of '
                    f'{url}.\n'
                    f'This could be due to an invasive proxy or an attempted '
                    f'man-in-the-middle attack.'
                )

    def unzip(
        self,
        zip_filename: str,
        package_dir: str,
    ) -> None:
        """Unzip a .zip file.

        This method will unpack the contents of a .zip file into a target
        directory. If that directory already exists, it will first be removed.

        Args:
            zip_filename (str):
                The absolute path to the .zip file to unpack.

            package_dir (str):
                The directory to unzip the files into.

        Raises:
            rbtools.commands.CommandError:
                The file could not be unzipped.
        """
        self.log.debug('Extracting %s to %s', zip_filename, package_dir)

        try:
            if os.path.exists(package_dir):
                if os.path.isdir(package_dir):
                    shutil.rmtree(package_dir)
                else:
                    os.remove(package_dir)

            os.makedirs(package_dir)
        except OSError as e:
            raise CommandError(
                f'Failed to set up package directory {package_dir}: {e}')

        zip_file = zipfile.ZipFile(zip_filename, 'r')

        try:
            zip_file.extractall(package_dir)
        except Exception as e:
            raise CommandError(f'Failed to extract file: {e}')
        finally:
            zip_file.close()

    def download_file(
        self,
        url: str,
        *,
        label: (str | None) = None,
        show_progress: bool = True,
    ) -> str:
        """Download the given file.

        This is intended to be used as a context manager, and the bound value
        will be the filename of the downloaded file.

        Args:
            url (str):
                The URL of the file to download.

            label (str, optional):
                The label to use for the progress bar. If ``show_progress`` is
                ``True``, this must be specified.

            show_progress (bool, optional):
                Whether to hide the progress bar.

        Returns:
            str:
            The filename of the downloaded file.

        Raises:
            ValueError:
                The function was called with an invalid combination of
                ``label`` and ``hide_progress``.

            rbtools.commands.CommandError:
                An error occurred while downloading the file.
        """
        if show_progress and label is None:
            raise ValueError(
                'label must be provided when show_progress is True')

        self.log.debug('Downloading %s', url)

        try:
            response = urlopen(url)

            total_bytes = int(response.headers['Content-Length'].strip())

            tmpfile_kwargs = {'delete': False}

            if sys.version_info >= (3, 12):
                tmpfile_kwargs['delete_on_close'] = False

            with tempfile.NamedTemporaryFile(**tmpfile_kwargs) as f:
                def download_chunks() -> Iterator[int]:
                    read_bytes = 0

                    while read_bytes != total_bytes:
                        chunk = response.read(8192)
                        chunk_length = len(chunk)
                        read_bytes += chunk_length

                        f.write(chunk)

                        yield chunk_length

                if show_progress:
                    assert label is not None

                    with self.console.progress_bar(label,
                                                   total=total_bytes) as bar:
                        for chunk_len in download_chunks():
                            bar.advance(chunk_len)
                else:
                    for _chunk_len in download_chunks():
                        pass

                return f.name
        except (HTTPError, URLError) as e:
            raise CommandError(f'Error when downloading file: {e}')
