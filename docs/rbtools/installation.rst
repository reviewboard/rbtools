.. _rbtools-installation:

==================
Installing RBTools
==================

RBTools is most often installed as a Python package. Installation steps depend
on your system and whether you're developing against RBTools:

* :ref:`Use an official installer <rbtools-installer>`
  (recommended for Windows)

* :ref:`Use pipx <rbtools-install-pipx>`
  (recommended for Linux and macOS)

* :ref:`Use Python pip <rbtools-install-pip>`
  (recommended if you manage your Python environment)


Installation Options
====================

.. _rbtools-installer:

Using an official installer
---------------------------

We provide an official installer for Windows, helping you quickly get started
with RBTools without needing to worry about Python.

To install RBTools using the official installer:

.. tabs::

   .. tab:: Windows

      1. Download and run the `RBTools for Windows installer`_.

      2. Open a new command prompt and verify RBTools is installed and in
         your path:

         .. code-block:: doscon

            C:\> rbt

         You should see the RBTools help displayed. If it doesn't work, make
         :file:`C:\\Program Files\\RBTools\\bin` is in your path.


.. _rbtools-install-pipx:

Using pipx
----------

pipx_ is a command line tool that safely installs Python packages (such as
RBTools) in a self-contained environment. This is recommended for most users.

To install RBTools using :command:`pipx`:

1. Install pipx_:

   .. tabs::

      .. code-tab:: console Ubuntu/Debian

         $ sudo apt install pipx

      .. code-tab:: console RHEL/Fedora/CentOS

         $ sudo yum install pipx

      .. tab:: macOS

         If you use Homebrew_:

         .. code-block:: console

            $ brew install pipx

   If you can't install the package using the instructions above, you can
   install it using :command:`pip3` instead:

   .. code-block:: console

      $ sudo pip3 install -U pip

2. Set up your executable search path:

   .. code-block:: console

      $ pipx ensurepath

   Follow the displayed instructions.

3. Install RBTools:

   .. code-block:: console

      $ pipx install RBTools

4. Verify RBTools is installed and in your path:

   .. code-block:: console

      $ rbt

   You should see the RBTools help displayed. If it doesn't work, make sure
   that you followed the instructions from :command:`pipx ensurepath`.

5. To upgrade RBTools, run:

   .. code-block:: console

      $ pipx upgrade RBTools


.. _rbtools-install-pip:

Using Python pip
----------------

:command:`pip` is the standard Python package installation tool. It's
available on most (but not all) systems.

You may want to use :command:`pip` instead of :command:`pipx` in you are:

* Installing in a `Python virtual environment`_
* Developing against the :ref:`RBTools API <rbtools-api>`
* Using pyenv_ to manage your Python install

1. To install using :command:`pip`:

   .. code-block:: console

      $ pip3 install RBTools

   (To install globally, you may need to run this using :command:`sudo`.)

2. Verify RBTools is installed and in your path:

   .. code-block:: console

      $ rbt

   You should see the RBTools help displayed. If it doesn't work, make sure
   that you followed the instructions from :command:`pipx ensurepath`.

3. To upgrade RBTools, run:

   .. code-block:: console

      $ pip3 install -U RBTools


.. note::

   :command:`pip install` used to be preferred, but many systems no longer
   allow this command, including:

   * Debian 12+
   * Fedora 38+
   * Kali Linux 2023.1+
   * Ubuntu 23.04+

   For systems without :command:`pip install`, you will need to create a
   `Python virtual environment`_ or :ref:`install using pipx
   <rbtools-install-pipx>`.


.. _Homebrew: https://brew.sh/
.. _pipx: https://pypa.github.io/pipx/
.. _pyenv: https://github.com/pyenv/pyenv
.. _Python virtual environment:
   https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/
.. _RBTools for Windows installer:
   https://www.reviewboard.org/downloads/rbtools/#windows


After Installation
==================

Once RBTools is installed, you'll need to authenticate with Review Board
and configure RBTools.

See our :ref:`step-by-step instructions to get you started
<rbtools-getting-started>`.
