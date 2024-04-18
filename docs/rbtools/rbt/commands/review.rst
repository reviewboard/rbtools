.. rbt-command:: rbtools.commands.review.Review

======
review
======

:command:`rbt review` provides several features for creating and editing
reviews.


.. rbt-command-usage::

For help on individual subcommands, run::

    $ rbt review <subcommand> --help


Creating and editing reviews
============================

To create a new draft, or update an existing one, use :command:`rbt review
edit`. This command allows specifying the review header and footer text, as
well as setting the "Ship It!" state. For example::

    $ rbt review edit -r 23 --header "Looks good" --markdown --ship-it

A draft review will also be created if necessary when creating comments.


Adding comments
===============

There are three commands used to add comments to a draft review, corresponding
to the three types of comments that Review Board has.

For a general comment, not attached to any kind of content::

    $ rbt review add-general-comment -r 23 -t "Comment text" --open-issue

For a comment on a file attachment::

    $ rbt review add-file-attachment-comment -r 23 --file-attachment-id 96 -t "Comment text"

Finally, for a comment on a diff::

    $ rbt review add-diff-comment -r 23 --diff-revision 2 -f test.py --line 485 --num-lines 4 -t "Comment text"

See the help options for each of these commands for full usage details.


Publishing reviews
==================

When a draft review is ready, publishing it is simple::

    $ rbt review publish -r 23


Discarding reviews
==================

On the other hand, to discard a draft review, run::

    $ rbt review discard -r 23


.. _rbt-review-json:

JSON Output
===========

.. versionadded:: 5.0

When running with :option:`--json`, the results of posting the review request
will be outputted as JSON. This can be used by programs that wrap RBTools in
order to automate posting changes for review.


.. rbt-command-options::
