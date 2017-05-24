.. _rbt-diff:
.. program:: rbt diff

====
diff
====

:command:`rbt diff` is similar to :command:`rbt post`, but will only
print the diff to standard out instead of creating a review request
for it.

Usage::

   $ rbt diff [options] [revisions]


Default Options
===============

A number of options to :command:`rbt diff` can be set by default
in :file:`.reviewboardrc`. These can go either in the repository's
or the user's :file:`.reviewboardrc`.

The options include:

* ``DEBUG`` (:option:`-d`)
* ``REVIEWBOARD_URL`` (:option:`--server`)
* ``USERNAME`` (:option:`--username`)
* ``PASSWORD`` (:option:`--password`)
* ``REPOSITORY_TYPE`` (:option:`--repository-type`)


Options
=======

.. cmdoption:: -d, --debug

   Display debug output.

   The default can be set in ``DEBUG`` in :file:`.reviewboardrc`.

.. cmdoption:: --server

   Specify a different Review Board server to use.

   The default can be set in ``REVIEWBOARD_URL`` in :file:`.reviewboardrc`.

.. cmdoption:: --parent

   The parent branch this diff should be against (only available if your
   repository supports parent diffs).

.. cmdoption:: -I <file>, --include <file>

   Include only the specified file in the diff. This argument can be passed in
   multiple times to include multiple files. This is only available with some
   SCM backends (Bazaar, CVS, Git, Mercurial, Perforce, and SVN).

.. cmdoption:: --tracking-branch

   Tracking branch from which your branch is derived (Git only, defaults to
   origin/master)

.. cmdoption:: --svn-changelist

   Generate the diff for review based on a local SVN changelist.

.. cmdoption:: --repository

   The name of the repository to look up when posting the change. This is
   the same name shown on the New Review Request page or in the repository
   configuration page.

   The default can be set in ``REPOSITORY`` in :file:`.reviewboardrc`.

.. cmdoption:: --repository-url

   The url for a repository for creating a diff outside of a working copy
   (currently only supported by Subversion with specific revisions or
   :option:`--diff-filename` and ClearCase with relative paths outside the
   view). For Git, this specifies the origin url of the current repository,
   overriding the origin url supplied by the Git client.

   The default can be set in ``REPOSITORY_URL`` in :file:`.reviewboardrc`.

   Note that versions of RBTools prior to 0.6 used the ``REPOSITORY``
   setting in :file:`.reviewboardrc`, and allowed a repository name to be
   passed to :option:`--repository-url`. This is no longer supported in
   0.6 and higher. You may need to update your configuration and scripts
   appropriately.

.. cmdoption:: --username

   Username to be supplied to the Review Board server.

   The default can be set in ``USERNAME`` in :file:`.reviewboardrc`.

.. cmdoption:: --password

   Password to be supplied to the Review Board server.

   The default can be set in ``PASSWORD`` in :file:`.reviewboardrc`.

.. cmdoption:: --repository-type

   Specifies the type of repository in the current directory. In most cases
   this should be detected automatically, but some directory structures
   containing multiple repositories require this option to select the proper
   type. The :command:`rbt list-repo-types` command can be used to list the
   supported values.

   The default can be set in ``REPOSITORY_TYPE`` in :file:`.reviewboardrc`.

.. cmdoption:: --p4-client

   The Perforce client name that the review is in.

   The default can be set in ``P4_CLIENT`` in :file:`.reviewboardrc`.

.. cmdoption:: --p4-port

   The Perforce servers IP address that the review is on.

   The default can be set in ``P4_PORT`` in :file:`.reviewboardrc`.

.. cmdoption:: --p4-passwd

   The Perforce password or ticket of the user in the P4USER environment
   variable.

   The default can be set in ``P4_PASSWD`` in :file:`.reviewboardrc`.
