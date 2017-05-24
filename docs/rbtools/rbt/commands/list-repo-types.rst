.. rbt-command:: rbtools.commands.list_repo_types.ListRepoTypes

===============
list-repo-types
===============

:command:`rbt list-repo-types` will print the list of supported repository
types. Each printed type can be used as a value to the ``REPOSITORY_TYPE``
configuration option in :file:`.reviewboardrc`, or as the
``--repository-type`` option of many rbt commands.

If a repository of a specific type is detected in the current directory,
that repository type will be marked by an asterisk (``*``).


.. rbt-command-usage::
.. rbt-command-options::
