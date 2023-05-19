#!/usr/bin/env python3

import os
import subprocess
import sys

from setuptools import setup, find_packages
from setuptools.command.develop import develop

from rbtools import get_package_version, VERSION


# Make sure this is a version of Python we are compatible with. This should
# prevent people on older versions from unintentionally trying to install
# the source tarball, and failing.
if sys.hexversion < 0x02050000:
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please install RBTools 0.5.x or upgrade Python to at least '
        '2.7.x.\n' % get_package_version())
    sys.exit(1)
elif sys.hexversion < 0x02060000:
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please install RBTools 0.6.x or upgrade Python to at least '
        '2.7.x.\n' % get_package_version())
    sys.exit(1)
elif sys.hexversion < 0x02070000:
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please install RBTools 0.7.x or upgrade Python to at least '
        '2.7.x.\n' % get_package_version())
    sys.exit(1)
elif (3, 0) <= sys.version_info < (3, 6):
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please use Python 3.7+.\n'
        % get_package_version())
    sys.exit(1)
elif sys.version_info < (3, 7):
    sys.stderr.write(
        'RBTools %s is incompatible with your version of Python.\n'
        'Please install RBTools 3.x or upgrade Python to at least '
        '3.7.x.\n'
        % get_package_version())
    sys.exit(1)


rb_commands = [
    'api-get = rbtools.commands.api_get:APIGet',
    'alias = rbtools.commands.alias:Alias',
    'attach = rbtools.commands.attach:Attach',
    'clear-cache = rbtools.commands.clearcache:ClearCache',
    'close = rbtools.commands.close:Close',
    'diff = rbtools.commands.diff:Diff',
    'info = rbtools.commands.info:Info',
    'land = rbtools.commands.land:Land',
    'list-repo-types = rbtools.commands.list_repo_types:ListRepoTypes',
    'login = rbtools.commands.login:Login',
    'logout = rbtools.commands.logout:Logout',
    'patch = rbtools.commands.patch:Patch',
    'post = rbtools.commands.post:Post',
    'publish = rbtools.commands.publish:Publish',
    'review = rbtools.commands.review:Review',
    'setup-completion = rbtools.commands.setup_completion:SetupCompletion',
    'setup-repo = rbtools.commands.setup_repo:SetupRepo',
    'stamp = rbtools.commands.stamp:Stamp',
    'status = rbtools.commands.status:Status',
    'status-update = rbtools.commands.status_update:StatusUpdate',
]


PACKAGE_NAME = 'RBTools'

with open('README.md') as fp:
    long_description = fp.read()


class DevelopCommand(develop):
    """Installs RBTools in developer mode.

    This will install all standard and development dependencies (using Python
    wheels) and add the source tree to the Python module search path. That
    includes updating the versions of pip and setuptools on the system.
    """

    user_options = develop.user_options + [
        (str('with-doc-deps'), None,
         'Install documentation-related dependencies'),
    ]

    boolean_options = develop.boolean_options + [
        str('with-doc-deps'),
    ]

    def initialize_options(self):
        """Initialize options for the command."""
        develop.initialize_options(self)

        self.with_doc_deps = None

    def install_for_development(self):
        """Install the package for development.

        This takes care of the work of installing all dependencies.
        """
        if self.no_deps:
            # In this case, we don't want to install any of the dependencies
            # below. However, it's really unlikely that a user is going to
            # want to pass --no-deps.
            #
            # Instead, what this really does is give us a way to know we've
            # been called by `pip install -e .`. That will call us with
            # --no-deps, as it's going to actually handle all dependency
            # installation, rather than having easy_install do it.
            develop.install_for_development(self)
            return

        self._run_pip(['install', '-e', '.'])
        self._run_pip(['install', '-r', 'dev-requirements.txt'])

        if self.with_doc_deps:
            self._run_pip(['install', '-r', 'doc-requirements.txt'])

    def _run_pip(self, args):
        """Run pip.

        Args:
            args (list):
                Arguments to pass to :command:`pip`.

        Raises:
            RuntimeError:
                The :command:`pip` command returned a non-zero exit code.
        """
        cmd = subprocess.list2cmdline([sys.executable, '-m', 'pip'] + args)
        ret = os.system(cmd)

        if ret != 0:
            raise RuntimeError('Failed to run `%s`' % cmd)


setup(
    name=PACKAGE_NAME,
    version=get_package_version(),
    license='MIT',
    description=(
        'Command line tools and API for working with code and document '
        'reviews on Review Board'
    ),
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Beanbag, Inc.',
    author_email='reviewboard@googlegroups.com',
    entry_points={
        'console_scripts': [
            'rbt = rbtools.commands.main:main',
        ],
        'rbtools_commands': rb_commands,
    },
    install_requires=[
        'importlib-metadata~=4.12; python_version < "3.10"',
        'certifi>=2023.5.7',
        'colorama',
        'pydiffx~=1.1.0',
        'setuptools',
        'texttable',
        'typing_extensions>=4.3.0',
        'tqdm',
    ],
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    url='https://www.reviewboard.org/downloads/rbtools/',
    download_url=('https://downloads.reviewboard.org/releases/%s/%s.%s/'
                  % (PACKAGE_NAME, VERSION[0], VERSION[1])),
    cmdclass={
        'develop': DevelopCommand,
    },
    python_requires='>=3.7',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Framework :: Review Board',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Software Development',
        'Topic :: Software Development :: Quality Assurance',
    ],
)
