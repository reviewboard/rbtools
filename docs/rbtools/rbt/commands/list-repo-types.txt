.. _rbt-list-repo-types:
.. program:: rbt list-repo-types

===============
list-repo-types
===============

:command:`rbt list-repo-types` will print the list of supported repository
types. Each printed type can be used as a value to the
:option:`--repository-type` option of many rbt commands.

If a repository of a specific type is detected in the current directory,
that repository type will be marked by an asterisk (``*``).

Usage::

   $ rbt list-repo-types [options]


Default Options
===============

A number of options to :command:`rbt list-repo-types` can be set by default
in :file:`.reviewboardrc`. These can go either in the repository's
or the user's :file:`.reviewboardrc`.

The options include:

* ``DEBUG`` (:option:`-d`)

Options
=======

.. cmdoption:: -d, --debug

   Display debug output.

   The default can be set in ``DEBUG`` in :file:`.reviewboardrc`.
