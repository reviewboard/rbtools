.. rbt-command:: rbtools.commands.alias.Alias

=====
alias
=====

.. versionadded:: 1.0

:command:`rbt alias` is used to display any
:ref:`aliases <rbtools-aliases>` configured by the user
or repository. It can list them or perform a "dry run" that shows what would
be executed when running a given alias.

To display all aliases, run::

    $ rbt alias --list

To print the commands invoked by ``my_alias``, run::

    $ rbt alias --dry-run my_alias


.. rbt-command-usage::
.. rbt-command-options::
