.. _rbtools-configuration:

=============
Configuration
=============

.. _rbtools-reviewboardrc:

.reviewboardrc
--------------

The :file:`.reviewboardrc` file is a generic place for storing RBTools
configuration data.

.. important::

    The :file:`.reviewboardrc` file must parse as a valid Python file, or
    you'll see an error when using :command:`rbt`.

Multiple :file:`.reviewboardrc` files can be present, and configuration therein
will be merged according to priority. These files are found according to the
following rules:

1. The :envvar:`RBTOOLS_CONFIG_PATH` environment variable can point to a file.
   Keys in this file override all others.

2. The current directory, and all parent directories, will be searched for
   files named :file:`.reviewboardrc`. Closer files are higher priority.

3. Last, your user's home directory is searched.

   On Linux and MacOS X, this file can be found in :file:`$HOME`.

   On Windows, it's in :file:`$USERPROFILE\\Local Settings\\Application Data`.


.. toctree::
   :hidden:

   aliases
   repositories
   users
   tfs
