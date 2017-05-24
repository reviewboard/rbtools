.. _rbt-patch:
.. program:: rbt patch

=====
patch
=====

:command:`rbt patch` will download the latest diff from the review request
matching ``review-request-id`` and apply it to the local working directory. The
:option:`--diff-revision` option may be used to specify a specific revision
of the diff to use.

Usage::

   $ rbt patch [options] <review-request-id>


Default Options
===============

A number of options to :command:`rbt patch` can be set by default
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

.. cmdoption:: --diff-revision

   Revision id of diff to be used as patch.

.. cmdoption:: --px

   Numerical pX argument for patch.

.. cmdoption:: -c, --commit

   Commit using information fetched from the review request (Git only).

.. cmdoption:: --server

   Specify a different Review Board server to use.

   The default can be set in ``REVIEWBOARD_URL`` in :file:`.reviewboardrc`.

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

.. cmdoption:: --print

   Prints the patch to standard output instead of applying it to the tree.
