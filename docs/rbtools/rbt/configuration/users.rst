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

For instance, if you look at the :rbtcommand:`rbt post` documentation, you'll
see that you can automatically open your browser when posting a review request
by setting:

.. code-block:: python

    OPEN_BROWSER = True

Or, you can disable usage of your HTTP proxy on any command by setting:

.. code-block:: python

    ENABLE_PROXY = False

The following options might be useful to set in your own
:file:`.reviewboardrc` file. This can also contain anything normally found in
a :ref:`repository's .reviewboardrc <rbtools-reviewboardrc>`.


.. rbtconfig:: API_TOKEN

API_TOKEN
---------

**Type:** String

**Default:** Unset

Your Review Board API token, for logging into Review Board.

This can also be provided by passing :option:`--api-token` to any command.

.. warning::

   We recommend that you provide your credentials only on demand, rather
   than setting this in a file. However, this can be useful for specialized
   automation in a locked-down environment.


.. rbtconfig:: CACHE_LOCATION

CACHE_LOCATION
--------------

**Type:** String

**Default:** See :ref:`rbtools-user-cache`

A custom path used to store any cached HTTP responses.

Example:

.. code-block:: python

    CACHE_LOCATION = "/tmp/rbtools-cache"

This can also be provided by passing :option:`--cache-location` to any
command.


COOKIES_STRICT_DOMAIN_MATCH
---------------------------

.. rbtconfig:: COOKIES_STRICT_DOMAIN_MATCH

.. versionadded:: 5.1

**Type:** Boolean

**Default:** ``False``

RBTools uses cookies to manage Review Board login sessions. By defaut,
if RBTools has stored cookies for both a domain and a parent domain
(e.g., ``staging.rb.example.com`` and ``rb.example.com``), both cookies
may be passed, and this may interfere with authentication.

Setting ``COOKIES_STRICT_DOMAIN_MATCH = True`` will only match cookies that
exactly match the domain name you're connecting to.

Example::

    COOKIES_STRICT_DOMAIN_MATCH = True


.. rbtconfig:: DEBUG

DEBUG
-----

**Type:** Boolean

**Default:** ``False``

If enabled, RBTools commands will output extra debug information.

Example:

.. code-block:: python

    DEBUG = True

This can also be provided by passing :option:`--debug` to any command.


.. rbtconfig:: DISABLE_CACHE

DISABLE_CACHE
-------------

**Type:** Boolean

**Default:** ``False``

If enabled, HTTP responses will be cached (either in memory or saved to a
local cache -- see :rbtconfig:`IN_MEMORY_CACHE`), speeding up subsequent
requests.

If disabled, RBTools always perform full HTTP requests.

Example:

.. code-block:: python

    DISABLE_CACHE = True

This can also be disabled by passing :option:`--disable-cache` to any command.


.. rbtconfig:: DISABLE_SSL_VERIFICATION

DISABLE_SSL_VERIFICATION
------------------------

**Type:** Boolean

**Default:** ``False``

If enabled, SSL certificates won't be verified.

Example:

.. code-block:: python

    DISABLE_SSL_VERIFICATION = True

.. warning::

   Disabling SSL verification presents a security risk. We instead recommend
   using :rbtconfig:`CA_CERTS`.

This can also be disabled by passing :option:`--disable-ssl-verification` to
any command.


.. rbtconfig:: EXT_AUTH_COOKIES

EXT_AUTH_COOKIES
----------------

**Type:** String

**Default:** Unset

This can be set to a local file path to use an existing pre-fetched cookie
store, which can be useful for automation. This file must be compatible with
Python's urllib2 cookie

Example:

.. code-block:: python

    EXT_AUTH_COOKIES = "/opt/scripts/rbtools/cookies.txt"

This can also be provided by passing :option:`--ext-auth-cookies` to any
command.


.. rbtconfig:: GUESS_FIELDS

GUESS_FIELDS
------------

**Commands:** :rbtcommand:`rbt post`

**Type:** String

**Default:** ``"auto"``

The default behavior for guessing the value for the review request's intended
summary and description based on the posted commit's message (on repositories
that support posting from an existing commit). This can be set to ``"yes"``,
``"no"``, or ``"auto"``.

If set to ``"yes"``, then the review request's fields will always be set,
overriding any manual changes you've made the next time you run
:rbtcommand:`rbt post`.

If set to ``"no"``, then the review request's fields will never be updated.

If set to ``"auto"`` (the default), then only newly-posted review requests
will have their fields updated. Updates to an existing review request won't
override any fields.

See :ref:`guessing-behavior` for more information.

For example:

.. code-block:: python

    GUESS_FIELDS = "yes"

This can also be provided by using :option:`rbt post --guess-fields`.


.. rbtconfig:: GUESS_DESCRIPTION

GUESS_DESCRIPTION
-----------------

**Commands:** :rbtcommand:`rbt post`

**Type:** String

**Default:** Value of :rbtconfig:`GUESS_FIELDS`

The default behavior for guessing a review request's intended description
based on the posted commit's message.

Most of the time, you'll just want to use :rbtconfig:`GUESS_FIELDS`. See
:ref:`guessing-behavior` for additional information.

Example:

.. code-block:: python

    GUESS_DESCRIPTION = "no"

This can also be provided by using :option:`rbt post --guess-description`.


.. rbtconfig:: GUESS_SUMMARY

GUESS_SUMMARY
-------------

**Commands:** :rbtcommand:`rbt post`

**Type:** String

**Default:** Value of :rbtconfig:`GUESS_FIELDS`

The default behavior for guessing a review request's intended summary based on
the posted commit's message.

Most of the time, you'll just want to use :rbtconfig:`GUESS_FIELDS`. See
:ref:`guessing-behavior` for additional information.

Example:

.. code-block:: python

    GUESS_DESCRIPTION = "yes"

This can also be provided by using :option:`rbt post --guess-summary`.


.. rbtconfig:: IN_MEMORY_CACHE

IN_MEMORY_CACHE
---------------

**Type:** Boolean

**Default:** ``False``

If enabled, any cached HTTP responses will be stored only in local memory, and
not saved to disk.

If disabled, and :rbtconfig:`DISABLE_CACHE` isn't used, HTTP responses will be
saved locally.

See :rbtconfig:`CACHE_LOCATION` for configuring the cache location.

Example:

.. code-block:: python

    IN_MEMORY_CACHE = True

This can also be enabled by passing :option:`--disable-cache` to any command.


.. rbtconfig:: OPEN_BROWSER

OPEN_BROWSER
------------

**Commands:** :rbtcommand:`rbt post`

**Type:** Boolean

**Default:** ``False``

If set, a web browser will be opened to the review request after running
:rbtcommand:`rbt post`.

Example:

.. code-block:: python

    OPEN_BROWSER = True

This can also be provided by using :option:`rbt post --open`.


.. rbtconfig:: P4_CLIENT

P4_CLIENT
---------

**Type:** String

**Default:** Unset

The Perforce client name to use, overriding the default for your local
setup.

Example:

.. code-block:: python

    P4_CLIENT = "my-client"

This can also be provided by passing :option:`--p4-client` to most commands.


.. rbtconfig:: P4_PASSWD

P4_PASSWD
---------

**Type:** String

**Default:** Unset

The password or ticket for your Perforce user, corresponding to the user
set in the :envvar:`P4USER` environment variable.

Example:

.. code-block:: python

    P4_PASSWD = "ticket123"

This can also be provided by passing :option:`--p4-user` to most commands.

.. warning::

   We recommend that you provide your credentials through a
   :command:`p4 login`, rather than setting this in a file. However, this can
   be useful for specialized automation in a locked-down environment.


.. rbtconfig:: PASSWORD

PASSWORD
--------

**Type:** String

**Default:** Unset

Your password, for logging into Review Board.

Example:

.. code-block:: python

    PASSWORD = "s3cr3t"

This can also be provided by passing :option:`--password` to any command.

.. warning::

   We recommend that you provide your credentials only on demand, rather
   than setting this in a file. However, this can be useful for specialized
   automation in a locked-down environment.


.. rbtconfig:: PUBLISH

PUBLISH
-------

**Commands:** :rbtcommand:`rbt post`

**Type:** Boolean

**Default:** ``False``

If set, any new review request drafts will be automatically published. This
does require all fields on the review request to be provided.

Example:

.. code-block:: python

    PUBLISH = True

This can also be provided by using :option:`rbt post --publish`.


.. rbtconfig:: SAVE_COOKIES

SAVE_COOKIES
------------

**Type:** Boolean

**Default:** ``True``

If enabled, cookies will be saved after logging in (see
:ref:`rbtools-user-cookies` for cookie store location).

If disabled, no cookies will be stored, and the next RBTools command will
require logging in again.

Example:

.. code-block:: python

    SAVE_COOKIES = False

This can also be disabled by passing :option:`--disable-cookie-storage` to any
command.


.. rbtconfig:: STAMP_WHEN_POSTING

STAMP_WHEN_POSTING
------------------

**Commands:** :rbtcommand:`rbt post`

**Type:** Boolean

**Default:** ``False``

If enabled, the latest commit for a review request will be stamped with the
review request URL when posting the commit for review.

Example:

.. code-block:: python

    STAMP_WHEN_POSTING = True

This can also be enabled by using :option:`rbt post --stamp-when-posting`.


.. rbtconfig:: SUBMIT_AS

SUBMIT_AS
---------

**Commands:** :rbtcommand:`rbt post`

**Type:** String

**Default:** Unset

The username to use instead of the logged-in user when posting a change for
review. This is useful for automation, enabling a script to post changes on
behalf of users.

This requires that the logged-in user is either an administrator or has the
``reviews.can_submit_as`` permission set.

Most of the time, it won't make much sense to put this in
:file:`.reviewboardrc`. Using :option:`rbt post --submit-as` might be a better
option.

Example:

.. code-block:: python

    SUBMIT_AS = "other-user"


.. rbtconfig:: TREES

TREES
-----

**Type:** Dictionary

**Default:** Unset

This setting allows a central :file:`.reviewboardrc` file to override settings
for individual repositories or directories. This is defined as a dictionary
where the keys can be either the remote or local repository paths. The values
should be a dictionary of configuration settings to apply for that directory or
repository.

This was available in RBTools 4 and earlier, but was previously limited to just
the :rbtconfig:`REVIEWBOARD_URL` setting. As of RBTools 5.1, this allows
including any configuration settings.

.. code-block:: python

    TREES = {
        'https://svn.example.com/': {
            'REVIEWBOARD_URL': 'https://reviews.example.com',
        },
        '/home/user/dev': {
            'MARKDOWN': False,
            'TRACKING_BRANCH': 'origin/rewrite',
        }
    }


.. rbtconfig:: USERNAME

USERNAME
--------

**Type:** String

**Default:** Unset

Your username, for logging into Review Board.

Example:

.. code-block:: python

    USERNAME = "myuser"

This can also be provided by passing :option:`--username` to any command.

.. warning::

   We recommend that you provide your credentials only on demand, rather
   than setting this in a file. However, this can be useful for specialized
   automation in a locked-down environment.


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


The following commands are equivalent:

.. code-block:: console

    $ rbt post-this
    $ rbt post HEAD

As are the following:

.. code-block:: console

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

.. _rbtools-user-cookies:

Cookies
-------

The :command:`rbt` command stores its login session in a cookies file called
:file:`~/.rbtools-cookies`. To force RBTools to log in again, simply delete
this file.

If the file is missing, RBTools will check for a legacy
:file:`~/.post-review-cookies.txt` file. This is for compatibility with the
old :command:`post-review` command.


.. _rbtools-user-cache:

Cache Database
--------------

The :command:`rbt` command stores cached API request responses in a SQLite
database in a cache directory. This is to reduce the time it takes to perform
certain API requests.

On macOS, this is in :file:`~/Library/Caches/rbtools/apicache.db`.

On Linux, this is in :file:`~/.cache/.rbtools/apicache.db`.

On Windows, this is in :file:`%APPDATA%\\rbtools\\rbtools\\apicache.db`.

This location can be controlled by setting :rbtconfig:`CACHE_LOCATION`.

To delete the cache, either remove this file, or call
:rbtcommand:`rbt clear-cache`.
