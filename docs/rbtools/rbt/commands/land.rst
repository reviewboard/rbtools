.. rbt-command:: rbtools.commands.land.Land

====
land
====

:command:`rbt land` is used to land a change on a branch, once it has been
approved through the review process. It takes care of validating that the
change is approved, creates a commit for it on a destination branch, and
optionally pushes that branch upstream.

The destination branch must either be specified on the command line (using
:option:`--dest`) or by setting ``LAND_DEST_BRANCH`` in
:file:`.reviewboardrc`.

There are two types of changes that can be landed: Locally-accessible
branches of commits, and patches stored on Review Board.


.. rbt-command-usage::


.. _landing-local-branches:

Landing local branches
======================

To land a local branch, you must either specify the branch to land, or you
must first switch to the branch. The following examples are therefore
equivalent::

    # Landing a specific branch.
    $ rbt land my-branch

    # Landing the current branch.
    $ git checkout my-branch
    $ rbt land

:command:`rbt land` will look for a matching review request, prompting if it
cannot find one. In some cases, you may need to specify :option:`-r` with a
review request ID, along with :option:`--local`, if it's unable to find a
match.

By default, the branch and all of its history will be merged into the
destination branch. To instead squash the branch's history into a single
commit, pass :option:`--squash`.

Squashing can be made the default by specifying ``LAND_SQUASH = True`` in
:file:`.reviewboardrc`. It can then be selectively disabled by passing
:option:`--no-squash`.


Landing remote patches
======================

To land a remote patch, pass :option:`-r` with a review request ID, and
don't specify a branch name on the command line. :command:`rbt land` will
attempt to apply the latest patch on that review request to the destination
branch.

If the patch can't apply, an error will be provided. You can then attempt to
apply the patch manually to a branch and then :ref:`land the branch
<landing-local-branches>`.


Working with commit messages
============================

The resulting commit's message (whether a standard commit or a merge commit)
will mirror the summary, description, and testing in the review request. The
commit will follow this template::

    <summary>

    <description>

    Testing Done:
    <testing_done>

    Bugs closed: <bugs>
    Reviewed at <review_request_url>

If the Testing Done field was blank, that section will be omitted. The same
is true of the bugs closed.

The commit message be edited in your default editor by passing
:option:`--edit`.


Automatically pushing changes
=============================

By default, landed changes won't be pushed upstream. This gives the committer
time to test the patch or alter it as needed before pushing.

To instead push the commit immediately after landing, pass :option:`--push`.

The default behavior can be changed by specifying ``LAND_PUSH = True`` in
:file:`.reviewboardrc`. It can then be selectively disabled by passing
:option:`--no-push`.


Deleting landed branches
========================

Typically, when a branch has landed, it's no longer necessary to keep it
around. :command:`rbt land` will default to deleting this branch after landing
it.

If the branch needs to stay around after landing, you can pass
:option:`--no-delete-branch`.

The default behavior can be changed by specifying
``LAND_DELETE_BRANCH = False`` in :file:`.reviewboardrc`. It can then be
selectively enabled by passing :option:`--delete-branch`.


.. rbt-command-options::
