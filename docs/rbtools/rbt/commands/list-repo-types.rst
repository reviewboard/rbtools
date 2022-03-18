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


.. _rbt-list-repo-types-json:

JSON Output
===========

.. versionadded:: 3.0

When running with :option:`--json`, the list of repository types will be
outputted as JSON. This can be used by programs that wrap RBTools in order to
perform repository detection or to fetch lists of compatible types of
repositories.

The results are in the form of:

.. code-block:: javascript

   {
       "status": "success",

       // The list of repository types.
       "repository_types": [
           {
               // Whether this matches the local directory or a parent.
               "detected": <bool>,

               // The configured name of the repository.
               "name": "<string>",

               // The name of the tool backing this repository.
               "tool": "<string>"
           },
           ...
       ]
   }

For example:

.. code-block:: console

   $ rbt list-repo-types --json
   {
       "repository_types": [
           {
               "detected": false,
               "name": "bazaar",
               "tool": "Bazaar"
           },
           {
               "detected": false,
               "name": "clearcase",
               "tool": "ClearCase"
           },
           {
               "detected": false,
               "name": "cvs",
               "tool": "CVS"
           },
           {
               "detected": true,
               "name": "git",
               "tool": "Git"
           },
           {
               "detected": false,
               "name": "mercurial",
               "tool": "Mercurial"
           },
           {
               "detected": false,
               "name": "perforce",
               "tool": "Perforce"
           },
           {
               "detected": false,
               "name": "plastic",
               "tool": "Plastic"
           },
           {
               "detected": false,
               "name": "svn",
               "tool": "Subversion"
           },
           {
               "detected": false,
               "name": "tfs",
               "tool": "Team Foundation Server"
           }
       ],
       "status": "success"
    }


.. rbt-command-options::
