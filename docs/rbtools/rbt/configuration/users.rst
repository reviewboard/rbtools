.. _rbtools-user-config:

======================
Per-User Configuration
======================

There's a lot of flexibility when it comes to the RBTools setup. You can
provide your own defaults for nearly all RBTools command options, and can
define custom aliases to improve your workflows.

Like with :ref:`repository configuration <rbtools-repo-config>`, these
settings are stored in a :file:`.reviewboardrc` file. These can go in the
repository's own version of the file, if these options should apply to all
users by default. Otherwise, they can go in the :file:`.reviewboardrc` in your
home directory.

On Linux and MacOS X, this file can be found in your home directory.

On Windows, it's in :file:`$USERPROFILE\\Local Settings\\Application Data`.

If you need to override repository-wide settings for yourself, you can set
:envvar:`$RBTOOLS_CONFIG_PATH` to a list of paths, separated by colons (Linux,
Mac OS X) or semicolons (Windows).  These paths are searched first for
:file:`.reviewboardrc` files.


Custom Option Defaults
======================

Most options to RBTools commands allow for custom defaults. Each command has
documentation on what to set to change the default.

For instance, if you look at the :ref:`rbt-post` documentation, you'll see
that you can automatically open your browser when posting a review request by
setting::

    OPEN_BROWSER = True

Or, you can disable usage of your HTTP proxy on any command by setting::

    ENABLE_PROXY = False

Check out the documentation for the different commands to see what you can do.


.. _rbtools-env:

Environment Variables
=====================

You can set the following environment variables to customize the RBTools
experience:

.. envvar:: RBTOOLS_CONFIG_PATH

   A list of paths to check for :file:`.reviewboardrc` files. These paths
   will be checked before any other location.

   Each path should be separated using the native environment path separator
   on your platform (``:`` on Linux/UNIX/macOS, ``;`` on Windows).


.. envvar:: RBTOOLS_EDITOR
.. envvar:: VISUAL
.. envvar:: EDITOR

   These specify a text editor to use to edit commits or other content. The
   given editor is invoked when running commands like
   :option:`rbt land --edit` or :option:`rbt patch --commit`.

   We recommending using :envvar:`RBTOOLS_EDITOR`, but any of the above
   environment variables are supported for compatibility purposes. They order
   of precedence is the order shown above.

   .. versionadded:: 1.0.3

      Added support for :envvar:`RBTOOLS_EDITOR`.


.. _rbtools-aliases:

Aliases
=======

:command:`rbt` can be configured to add command aliases. The ``ALIASES`` value
in :file:`.reviewboardrc` can be added to allow for command aliasing. It is a
dictionary where the keys are the alias names and the value is the command
that will be executed.

Aliases will only be executed when an :command:`rbt` command is executed that
:command:`rbt` does not recognize and when ``rbt-<commandname>`` does not exist
in the path. Aliases are case-sensitive.

For example, consider the following aliases:

.. code-block:: python

    ALIASES = {
        'post-this': 'post HEAD',
        'push': '!git push && rbt close $1'
    }


The following commands are equivalent::

    $ rbt post-this
    $ rbt post HEAD

As are the following::

    $ rbt push 3351
    $ git push && rbt close 3351


Types of Aliases
----------------

There are two types of aliases: aliases for other :command:`rbt` commands and
system aliases.


Aliases For Other :command:`rbt` Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These aliases allow short forms for frequently used :command:`rbt` commands
with parameter substitution. An alias of the form ``cmd`` is equivalent to
calling ``rbt cmd``. This will launch another instance of :command:`rbt` and
therefore can be used to reference other aliases or commands of the form
``rbt-<commandname>``.


System Command Aliases
~~~~~~~~~~~~~~~~~~~~~~

System aliases are aliases that begin with ``!``. These aliases are more
flexible because they are executed by the shell. However, since they are more
powerful it is possible to write an alias that will *destroy data*. Everything
after the ``!`` will be passed to the shell for execution after going through
parameter substitution.


Positional Parameter Substitution
---------------------------------

Aliases in :command:`rbt` supports inserting bash-like variables representing
positional arguments into aliases. Positional variables take the form ``$1``
(which corresponds to the first argument), ``$2`` (which corresponds to the
second argument), etc., and ``$*`` (which corresponds to *all* arguments).

If a positional variable is specified and not enough arguments were specified,
it will be replaced with an empty argument.

If no parameter substitution is performed, all supplied arguments will be
appended to the command when it is executed. Non-numeric variables are not
replaced in the parameter and, if the alias is a system command alias, will be
handled by the shell.


Special Files
=============

Cookies
-------

The :command:`rbt` command stores its login session in a cookies file called
:file:`~/.rbtools-cookies`. To force RBTools to log in again, simply delete
this file.

If the file is missing, RBTools will check for a legacy
:file:`~/.post-review-cookies.txt` file. This is for compatibility with the
old :command:`post-review` command.


Cache Database
--------------

The :command:`rbt` command stores cached API request responses in a SQLite
database in a cache directory. This is to reduce the time it takes to perform
certain API requests.

On MacOS X, this is in :file:`~/Library/Caches/rbtools/apicache.db`.

On Linux, this is in :file:`~/.cache/.rbtools/apicache.db`.

On Windows, this is in :file:`%APPDATA%\\rbtools\\rbtools\\apicache.db`.

To delete the cache, either remove this file, or call
:ref:`rbt clear-cache <rbt-clear-cache>`.
