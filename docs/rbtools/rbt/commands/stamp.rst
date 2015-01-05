.. rbt-command:: rbtools.commands.stamp.Stamp

=====
stamp
=====

:command:`rbt stamp` looks up a review request matching the latest commit on
the active branch and, if found, alters the commit message to contain a
``Reviewed at <url>`` line.

Pointing to a matching review request in a commit message helps later on when
trying to piece together the reason or discussions behind a change.

If the repository is configured with appropriate post-commit hooks, this line
can inform the hook of the matching review request, allowing that hook to
perform actions such as closing the review request.


.. rbt-command-usage::
.. rbt-command-options::
