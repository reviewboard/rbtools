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


.reviewboardrc
--------------

The :file:`.reviewboardrc` file is a generic place for configuring a
repository. This must be in a directory in the user's checkout path to work.
It must parse as a valid Python file, or you'll see an error when using
:command:`rbt`.

This is the recommended way of configuring your repository to talk to
Review Board.

You can generate this file automatically, starting with RBTools 0.5.3,
by typing::

    $ rbt setup-repo

Just follow the instructions, and it will create your :file:`.reviewboardrc`.
You should then commit this to your repository.

The rest of this section covers some of the more common settings you may want
for your :file:`.reviewboardrc`. You can find more in the documentation for
many of the commands. For example, see
:ref:`rbt post's options <rbt-post-options>`.


REPOSITORY
~~~~~~~~~~

By default, RBTools will try to determine the repository path and pass that to
Review Board. This won't always work in all setups, particularly when
different people are checking out the repository with different URLs.

You can use the ``REPOSITORY`` setting to specify the name of the
repository to use. This is the same as on Review Board's New Review Request
page. For example::

    REPOSITORY = 'RBTools'


REVIEWBOARD_URL
~~~~~~~~~~~~~~~

To specify the Review Board server to use, you can use the
``REVIEWBOARD_URL`` setting. This takes the URL to the Review Board server
as a value. For example::

    REVIEWBOARD_URL = "https://reviewboard.example.com"


TRACKING_BRANCH
~~~~~~~~~~~~~~~

When using Git or other DVCS repositories, RBTools makes an assumption about
the upstream branch, which it needs to know in order to generate a diff.
You can set the ``TRACKING_BRANCH`` setting to the branch name in order to
force the usage of a specific branch. This is equivalent to providing the
:option:`--tracking-branch` option.

We recommend you set this for any :file:`.reviewboardrc` files on any
long-running release or feature branches.

For example::

    TRACKING_BRANCH = "origin/release-2.0.x"


BRANCH
~~~~~~

A review request's Branch field is a helpful way of seeing where a change is
expected to be merged into. You can specify the default for all review
requests on a branch by setting the ``BRANCH`` field. For example::

    BRANCH = "release-2.0.x"

Note that the intent is to show the destination branch, and not the feature
branch that the code is being developed on.

This also does not affect code generation. It's used solely to display to the
reviewers where the code will land.


ENABLE_PROXY
~~~~~~~~~~~~

By default, any configured HTTP/HTTPS proxy will be used for requests. If
your server is within your own network, you may want to turn this off. You can
do so by setting ``ENABLE_PROXY`` to ``False``::

    ENABLE_PROXY = False


Git Properties
--------------

Repository information can be set in a ``reviewboard.url`` property on
the Git tree. Users may need to do this themselves on their own Git
tree, so in some cases, it may be ideal to use dotfiles instead.

To set the property on a Git tree, type::

    $ git config reviewboard.url http://reviewboard.example.com


Perforce Counters
-----------------

Repository information can be set on Perforce servers by using
``reviewboard.url`` Perforce counters. How this works varies between versions
of Perforce.

Perforce version 2008.1 and up support strings in counters, so you can simply
do::

    $ p4 counter reviewboard.url http://reviewboard.example.com

Older versions of Perforce support only numeric counters, so you must encode
the server as part of the counter name. As ``/`` characters aren't supported
in counter names, they must be replaced by ``|`` characters. ``|`` is a
special character in shells, so you'll need need to escape these using ``\|``.
For example::

    $ p4 counter reviewboard.url.http:\|\|reviewboard.example.com 1


Subversion Properties
---------------------

Repository information can be set in a ``reviewboard:url`` property on
a directory. This is usually done on whatever directory or directories
are common as base checkout paths. This usually means something like
:file:`/trunk` or :file:`/trunk/myproject`. If the directory is in the
user's checkout, it will be faster to find the property.

To set the property on a directory, type::

    $ svn propset reviewboard:url http://reviewboard.example.com .
