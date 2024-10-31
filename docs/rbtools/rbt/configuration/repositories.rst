.. _rbtools-repo-config:

=========================
Repository Configuration
=========================

There are many ways to configure :command:`rbt` in order to associate
a Review Board server with a repository. The ideal setup is to configure
a repository to point to a Review Board server, so that users can use
:command:`rbt` out of the box, but there are other methods available.

All repository types support a :file:`.reviewboardrc` file, which is the
recommended way to configure your repository. Through here, you can specify
the URL to your Review Board server, the repository name, and provide some
helpful defaults.

Alternatively, some types of repositories can have special metadata associated
that point to your server, but those don't support some of the more advanced
features of :file:`.reviewboardrc`.


.. _rbtools-reviewboardrc:

.reviewboardrc
--------------

The :file:`.reviewboardrc` file is a generic place for configuring a
repository. This must be in a directory in the user's checkout path to work.
It must parse as a valid Python file, or you'll see an error when using
:command:`rbt`.

This is the recommended way of configuring your repository to talk to
Review Board.

You can generate this file automatically, starting with RBTools 0.5.3,
by typing:

.. code-block:: console

    $ rbt setup-repo

Just follow the instructions, and it will create your :file:`.reviewboardrc`.
You should then commit this to your repository.

The rest of this section covers some of the more common settings you may want
for your :file:`.reviewboardrc`. You can find more in the documentation for
many of the commands. For example, see
:ref:`rbt post's options <rbt-post-options>`.

The main configuration settings you'll want to set are:

* :rbtconfig:`BRANCH`
* :rbtconfig:`REPOSITORY`
* :rbtconfig:`REPOSITORY_TYPE`
* :rbtconfig:`REVIEWBOARD_URL`
* :rbtconfig:`TRACKING_BRANCH` (if using Git)


.. rbtconfig:: BASEDIR

BASEDIR
~~~~~~~

**Type:** String

**Default:** Auto-detected

This is used only for Subversion repositories, and specifies a path within
the repository that should be prepended to all files in a diff.

Example:

.. code-block:: python

    BASEDIR = "trunk/myproject/"

.. note::

   This is normally not needed, as this information is auto-detected. It
   should only be set if there's a specialized requirement.

This can also be provided by passing :option:`--basedir` to most commands.


.. rbtconfig:: BRANCH

BRANCH
~~~~~~

**Type:** String

**Default:** Unset

A review request's Branch field is a helpful way of seeing where a change is
expected to be merged into. You can specify the default for all review
requests on a branch by setting the ``BRANCH`` field.

Note that the intent is to show the destination branch, and not the feature
branch that the code is being developed on.

This also does not affect code generation. It's used solely to display to the
reviewers where the code will land.

Example:

.. code-block:: python

    BRANCH = "release-2.0.x"

This can also be provided by passing :option:`--branch` to most commands.


.. rbtconfig:: CA_CERTS

CA_CERTS
~~~~~~~~

**Type:** String

**Default:** Unset

A path to a custom SSL CA certifications file.

Example:

.. code-block:: python

    CA_CERTS = "/mnt/corp-shared/ssl/ca-certs.pem"

This can also be provided by passing :option:`--ca-certs` to any command.


.. rbtconfig:: CLIENT_CERT

CLIENT_CERT
~~~~~~~~~~~

**Type:** String

**Default:** Unset

A path to a SSL certification file.

Example:

.. code-block:: python

    CLIENT_CERT = "/mnt/corp-shared/ssl/repo.pem"

This can also be provided by passing :option:`--client-cert` to any command.


.. rbtconfig:: CLIENT_KEY

CLIENT_KEY
~~~~~~~~~~

**Type:** String

**Default:** Unset

A path to a SSL client authentication key.

Example:

.. code-block:: python

    CLIENT_KEY = "/mnt/corp-shared/ssl/repo.key"

This can also be provided by passing :option:`--client-key` to any command.


.. rbtconfig:: DEPENDS_ON

DEPENDS_ON
~~~~~~~~~~

**Commands:** :rbtcommand:`rbt post`

**Type:** List of String

**Default:** Unset

A comma-separated list of review request IDs that any posted change will
automatically depend on.

This is rarely needed, but can be useful if all the work being done on a
branch depends on some main review request.

Example:

.. code-block:: python

    DEPENDS_ON = '42,43'

This can also be provided by using :option:`rbt post --depends-on`.


.. rbtconfig:: ENABLE_PROXY

ENABLE_PROXY
~~~~~~~~~~~~

**Type:** Boolean

**Default:** ``True``

By default, any configured HTTP/HTTPS proxy will be used for requests. If
your server is within your own network, you may want to turn this off.

Example:

.. code-block:: python

    ENABLE_PROXY = False

This can also be disabled by passing :option:`--disable-proxy` to any command.


.. rbtconfig:: EXCLUDE_PATTERNS

EXCLUDE_PATTERNS
~~~~~~~~~~~~~~~~

**Type:** List of String

**Default:** Unset

Excludes one or more files or file patterns from being posted for review.
This uses standard UNIX glob patterns, like most shell commands.

Example:

.. code-block:: python

    EXCLUDE_PATTERNS = ['_build', '*.min.js', '.*.swp']

Patterns that begin with a path separator (``/`` on Mac OS and Linux, ``\\``
on Windows) will be treated as being relative to the root of the repository.
All other patterns are treated as being relative to the current working
directory.

When working with Mercurial, the patterns are provided directly to
:command:`hg` and are not limited to globs. For more information on advanced
pattern syntax in Mercurial, run :command:`hg help patterns`.

When working with CVS, all diffs are generated relative to the current working
directory so patterns beginning with a path separator are treated as relative
to the current working directory.

When working with Perforce, an exclude pattern beginning with ``//`` will be
matched against depot paths. All other patterns will be matched against local
paths.

This can also be provided by passing :option:`--exclude` to most commands.


.. rbtconfig:: INCLUDE_PATTERNS

INCLUDE_PATTERNS
~~~~~~~~~~~~~~~~

**Type:** List of String

**Default:** Unset

Includes one or more files or file patterns when posting a review. Only these
files will be posted by default. This uses standard UNIX glob patterns, like
most shell commands.

Example:

.. code-block:: python

    INCLUDE_PATTERNS = ['src/*.c', 'doc/*.txt']

This can also be provided by passing :option:`--include` to most commands.


.. rbtconfig:: LAND_DELETE_BRANCH

LAND_DELETE_BRANCH
~~~~~~~~~~~~~~~~~~

**Commands:** :rbtcommand:`rbt land`

**Type:** Boolean

**Default:** ``True``

If enabled, and :rbtcommand:`rbt land` is landing a local branch, then that
branch will be deleted once landed. This is the default behavior, as it
indicates that work on that branch is complete.

Example:

.. code-block:: python

    LAND_DELETE_BRANCH = False

This can also be enabled by using :option:`rbt land --delete-branch`, or
disabled by using :option:`rbt land --no-delete-branch`.


.. rbtconfig:: LAND_DEST_BRANCH

LAND_DEST_BRANCH
~~~~~~~~~~~~~~~~

**Commands:** :rbtcommand:`rbt land`

**Type:** String

**Default:** Current branch

The branch where :rbtcommand:`rbt land` should land changes.

This is often set in common upstream branches where feature branches are
derived from.

Example:

.. code-block:: python

    LAND_DEST_BRANCH = "release-4.x"

This can also be provided by using :option:`rbt land --dest`.


.. rbtconfig:: LAND_SQUASH

LAND_SQUASH
~~~~~~~~~~~

**Commands:** :rbtcommand:`rbt land`

**Type:** Boolean

**Default:** ``False``

If enabled, :rbtcommand:`rbt land` will squash all commits on a review request
into a single commit before landing it, which can lead to cleaner, more linear
commit histories.

Example:

.. code-block:: python

    LAND_SQUASH = True

This can also be enabled by using :option:`rbt land --squash`, or disabled
if using :option:`rbt land --no-squash`.


.. rbtconfig:: LAND_PUSH

LAND_PUSH
~~~~~~~~~

**Commands:** :rbtcommand:`rbt land`

**Type:** Boolean

**Default:** ``False``

If enabled, :rbtcommand:`rbt land` will push the branch upstream once
successfully landing a change.

Example:

.. code-block:: python

    LAND_PUSH = True

This can also be enabled by using :option:`rbt land --push`, or disabled
if using :option:`rbt land --no-push`.


.. rbtconfig:: MARKDOWN

MARKDOWN
~~~~~~~~

**Commands:** :rbtcommand:`rbt post`

**Type:** Boolean

**Default:** ``False``

If enabled, any commit message used to auto-populate a review request's
description will be interpreted as valid Markdown.

This can be a useful setting if standardizing on Markdown-formatted commit
descriptions, as it will also allow for nicely-formatted review requests by
default.

Example:

.. code-block:: python

    MARKDOWN = True

This can also be enabled by using :option:`rbt post --markdown`.


.. rbtconfig:: P4_PORT

P4_PORT
~~~~~~~

**Type:** String

**Default:** Unset

The IP address or hostname of the Perforce server, overriding
the :envvar:`P4PORT` environment variable.

Example:

.. code-block:: python

    P4_PORT = "perforce.example.com:1666"

This can also be provided by passing :option:`--p4-port` to most commands.


.. rbtconfig:: PARENT_BRANCH

PARENT_BRANCH
~~~~~~~~~~~~~

**Type:** String

**Default:** Unset

A specific parent branch that the change should be generated from.

.. note::

   This is rarely needed. Normally, you'll just want to pass a revision range
   to :rbtcommand:`rbt land` or other commands.


.. rbtconfig:: REPOSITORY

REPOSITORY
~~~~~~~~~~

**Type:** String

**Default:** Unset

By default, RBTools will try to determine the repository path and pass that to
Review Board. This won't always work in all setups, particularly when
different people are checking out the repository with different URLs.

You can use the ``REPOSITORY`` setting to specify the name of the
repository to use. This is the same as on Review Board's New Review Request
page.

Example:

.. code-block:: python

    REPOSITORY = "RBTools"

This can also be provided by passing :option:`--repository` to any command.


.. rbtconfig:: REPOSITORY_TYPE

REPOSITORY_TYPE
~~~~~~~~~~~~~~~

**Type:** String

**Default:** Unset

The type of the repository. If set, RBTools won't have to scan to find the
type of repository, which is a slow process.

Valid repository types include:

* ``bazaar``
* ``clearcase``
* ``cvs``
* ``git``
* ``mercurial``
* ``perforce``
* ``plastic``
* ``sos``
* ``svn``
* ``tfs``

Example:

.. code-block:: python

    REPOSITORY_TYPE = "git"

This can also be provided by passing :option:`--repository-type` to any
command.


.. _rbtools-reviewboardrc-repository-url:
.. rbtconfig:: REPOSITORY_URL

REPOSITORY_URL
~~~~~~~~~~~~~~

**Type:** String

**Default:** Unset

The URL pointing to the upstream repository.

When generating diffs, this can be used for creating a diff outside of a
working copy (currently only supported by Subversion with specific revisions
or :option:`--diff-filename`, and by ClearCase with relative paths outside the
view).

For Git, this specifies the origin URL of the current repository, overriding
the origin URL supplied by the client.

Example:

.. code-block:: python

    REPOSITORY_URL = "https://git.example.com/myrepo.git"

This can also be provided by passing :option:`--repository-url` to most
commands.


.. _rbtools-reviewboard-url:
.. rbtconfig:: REVIEWBOARD_URL

REVIEWBOARD_URL
~~~~~~~~~~~~~~~

**Type:** String

**Default:** Unset

To specify the Review Board server to use, you can use the
``REVIEWBOARD_URL`` setting. This takes the URL to the Review Board server
as a value.

Example:

.. code-block:: python

    REVIEWBOARD_URL = "https://reviewboard.example.com"

This can also be provided by passing :option:`--server` to any command.


.. rbtconfig:: SQUASH_HISTORY

SQUASH_HISTORY
~~~~~~~~~~~~~~

.. versionadded:: 2.0

**Commands:** :rbtcommand:`rbt post`

**Type:** Boolean

**Default:** ``False``

If enabled, :rbtcommand:`rbt post` will squash all commits comprising a review
request into a single diff when uploading to Review Board. The default is to
retain each commit so the reviewer has the option of reviewing each
individually.

Example:

.. code-block:: python

    SQUASH_HISTORY = True

This can also be provided by using :option:`rbt post --squash`.


.. rbtconfig:: TF_CMD

TF_CMD
~~~~~~

**Type:** String

**Default:** Auto-detected

The full path to the :command:`tf` command, overriding any detected path. This
can be useful if there's a central copy of this command on a shared drive.

Example:

.. code-block:: python

    TF_CMD = "/opt/tfs/bin/tf"

This can also be provided by passing :option:`--tf-cmd` to most commands.


.. rbtconfig:: TRACKING_BRANCH

TRACKING_BRANCH
~~~~~~~~~~~~~~~

**Type:** String

**Default:** Unset

When using Git or other DVCS repositories, RBTools makes an assumption about
the upstream branch, which it needs to know in order to generate a diff.
You can set the ``TRACKING_BRANCH`` setting to the branch name in order to
force the usage of a specific branch. This is equivalent to providing the
:option:`--tracking-branch` option.

We recommend you set this for any :file:`.reviewboardrc` files on any
long-running release or feature branches.

Example:

.. code-block:: python

    TRACKING_BRANCH = "origin/release-2.0.x"

This can also be provided by passing :option:`--tracking-branch` to most
commands.


.. rbtconfig:: WEB_LOGIN

WEB_LOGIN
~~~~~~~~~

.. versionadded:: 5.0

**Type:** Boolean

**Default:** ``False``

If enabled, web-based login will be used to authenticate users by default.
This means users will be directed to the Review Board web site to log in
when using any commands that require authentication. When disabled, users
will be prompted to enter a username and password directly into the
terminal instead.

Example:

.. code-block:: python

    WEB_LOGIN = True

When using :command:`rbt login`, this can be enabled by passing
:option:`--web`.


Git Properties
--------------

Repository information can be set in a ``reviewboard.url`` property on
the Git tree. Users may need to do this themselves on their own Git
tree, so in some cases, it may be ideal to use dotfiles instead.

To set the property on a Git tree, type:

.. code-block:: console

    $ git config reviewboard.url http://reviewboard.example.com


Perforce Counters
-----------------

Repository information can be set on Perforce servers by using
``reviewboard.url`` Perforce counters. How this works varies between versions
of Perforce.

Perforce version 2008.1 and up support strings in counters, so you can simply
do:

.. code-block:: console

    $ p4 counter reviewboard.url http://reviewboard.example.com

Older versions of Perforce support only numeric counters, so you must encode
the server as part of the counter name. As ``/`` characters aren't supported
in counter names, they must be replaced by ``|`` characters. ``|`` is a
special character in shells, so you'll need need to escape these using ``\|``.
For example:

.. code-block:: console

    $ p4 counter reviewboard.url.http:\|\|reviewboard.example.com 1


Subversion Properties
---------------------

Repository information can be set in a ``reviewboard:url`` property on
a directory. This is usually done on whatever directory or directories
are common as base checkout paths. This usually means something like
:file:`/trunk` or :file:`/trunk/myproject`. If the directory is in the
user's checkout, it will be faster to find the property.

To set the property on a directory, type:

.. code-block:: console

    $ svn propset reviewboard:url http://reviewboard.example.com .
