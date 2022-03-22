.. rbt-command:: rbtools.commands.alias.Alias

=====
alias
=====

.. versionadded:: 1.0

:command:`rbt alias` is used to display any :ref:`aliases <rbtools-aliases>`
configured by the user or a repository. It can list them or perform a "dry
run" that shows what would be executed when running a given alias.

.. rbt-command-usage::


Listing Aliases
===============

To list all the aliases defined in :file:`.reviewboardrc`, use the
:option:`--list` option.

For example:

.. code-block:: console

    $ rbt alias --list
    [/home/user/.reviewboardrc]
        pt = post HEAD
        ptu = post -u HEAD
        push = !git push && rbt close $1


Simulating an Alias
===================

To display the commands that would be run by an alias, use the
:option:`--dry-run` option. This will expand the alias and print the results.

For example:

.. code-block:: console

    $ rbt alias --dry-run ptu
    rbt post HEAD

If the alias takes any command line arguments, they will be included in the
output if provided. For example:

.. code-block:: console

    $ rbt alias --dry-run push my-branch
    git push && rbt close my-branch


.. rbt-command-options::
