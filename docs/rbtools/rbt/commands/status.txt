.. _rbt-status:
.. program:: rbt status

======
status
======

:command:`rbt status` will output a list of your pending review requests
associated with the working directories repository. Review requests which
currently have a draft will be identified by an asterisk (``*``).

Optionally pending review requests from all repositories can be displayed
by providing the :option:`--all` option.

Usage::

   $ rbt status [options]


Default Options
===============

A number of options to :command:`rbt status` can be set by default
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

.. cmdoption:: --username

   Username to be supplied to the Review Board server.

   The default can be set in ``USERNAME`` in :file:`.reviewboardrc`.

.. cmdoption:: --password

   Password to be supplied to the Review Board server.

   The default can be set in ``PASSWORD`` in :file:`.reviewboardrc`.

.. cmdoption:: --all

   Show review requests for all repositories instead of the detected
   repository.

.. cmdoption:: --repository-type

   Specifies the type of repository in the current directory. In most cases
   this should be detected automatically, but some directory structures
   containing multiple repositories require this option to select the proper
   type. The :command:`rbt list-repo-types` command can be used to list the
   supported values.

   The default can be set in ``REPOSITORY_TYPE`` in :file:`.reviewboardrc`.
