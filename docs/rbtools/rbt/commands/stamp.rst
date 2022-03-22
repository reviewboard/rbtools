.. rbt-command:: rbtools.commands.stamp.Stamp

=====
stamp
=====

:command:`rbt stamp` looks up a review request matching the latest commit on
the active branch and, if found, alters the commit message to contain a
``Reviewed at <url>`` line.


.. rbt-command-usage::

The ``revisions`` argument behaves like it does in rbt post, where it is
required for some SCMs (e.g. Perforce) and unnecessary/ignored for others
(e.g. Git). For repositories that use it, the specified revision/changelist
will be stamped, rather than the latest one.

Normally, this command will guess the review request (based on the revision
number if provided, and the commit summary and description otherwise).
However, if a review request ID is specified with :option:`-r`, it stamps the
URL of that review request instead of guessing.

Pointing to a matching review request in a commit message helps later on when
trying to piece together the reason or discussions behind a change.

If the repository is configured with appropriate post-commit hooks, this line
can inform the hook of the matching review request, allowing that hook to
perform actions such as closing the review request.

A commit message can also be stamped from :command:`rbt post` by adding the
`-s` flag:

.. code-block:: console

    $ rbt post -s


.. rbt-command-options::
