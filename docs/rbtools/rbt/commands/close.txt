.. _rbt-close:
.. program:: rbt close

=====
close
=====

:command:`rbt close` will close the review request matching
``review-request-id`` as submitted. Optionally a review request may be
discarded by providing the value ``discarded`` to the :option:`--close-type`
option.

Usage::

   $ rbt close [options] <review-request-id>


Default Options
===============

A number of options to :command:`rbt close` can be set by default
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

.. cmdoption:: --close-type

   Either ``submitted`` or ``discarded``. If not supplied, defaults
   to ``submitted``.

.. cmdoption:: --description

   Optional description accompanying the change.

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
