.. _rbtools-workflow-jujutsu:

==========================
Using RBTools with Jujutsu
==========================

Jujutsu_ is a version control system which works seamlessly with Git servers
while providing new and innovative concepts and commands. Because of its
interoperability, it's a powerful tool that can be integrated into individual
developer workflows without requiring major organizational changes.

.. note::

    The Jujutsu support in Review Board and RBTools is client-side only, and
    expects that your remote is a Git server. Jujutsu does have a "native"
    backend, but as of now it is not usable. If and when the native backend
    becomes useful, we will consider adding support for it.

.. note::

   Jujutsu is a young project, and is undergoing rapid changes. It's possible
   that changes to the :command:`jj` command-line interface may break RBTools
   integration.


.. _Jujutsu: https://jj-vcs.github.io/jj/latest/


.. _rbtools-workflow-jujutsu-configuration:

Configuration
=============

Tracking bookmark
-----------------

RBTools will attempt to find your nearest tracking bookmark and use that as the
base for posted changes. Depending on how your repository is laid out (for
example, if you have multiple remotes), this may not find the correct upstream
branch. You can override this in :file:`.reviewboardrc`:

.. code-block:: python

    TRACKING_BRANCH = 'main@origin'


Commit IDs
----------

By default, the Jujutsu integration in RBTools will use Jujutsu change IDs for
commits. Depending on your environment, this may not be desirable--for example,
your Git server may reject any pushes for commits that have not been marked as
"Ship it!" in Review Board. This can be changed to send the Git hash instead.

.. code-block:: python

   JJ_COMMITS_USE_GIT_SHA = True


Overriding the repository config
--------------------------------

It's common for repositories to have a :file:`.reviewboardrc` committed to the
source tree, with standard settings defined. If you're using Jujutsu on a
project where everyone else is using Git, this file might have settings which
need to be overridden.

The :rbtconfig:`TREES` setting allows you to define overrides for configuration
keys. For example, consider a repository with a :file:`.reviewboardrc` that
contains:

.. code-block:: python

    REVIEWBOARD_URL = 'https://reviews.example.com/'
    REPOSITORY_TYPE = 'git'
    BRANCH = 'main'
    TRACKING_BRANCH = 'origin/main'
    LAND_DEST_BRANCH = 'main'

This will obviously not work correctly if you're using Jujutsu on the client.
You can create a :ref:`personal configuration <rbtools-reviewboardrc>` file
(e.g. in :file:`$HOME/.reviewboardrc`) with the following to override the
problematic settings:

.. code-block:: python

    TREES = {
        '/home/user/src/my-jj-repo': {
            'REPOSITORY_TYPE': 'jujutsu',
            'TRACKING_BRANCH': 'main@origin',
        },
    }


.. _rbtools-workflow-jujutsu-posting:

Step 1: Posting Changes
=======================

When using the Jujutsu integration, you can use the `Revset Language`_ to
specify which changes to include in your post.


.. _Revset Language: https://jj-vcs.github.io/jj/latest/revsets/


Posting all changes since the tracking bookmark
-----------------------------------------------

With no arguments, :command:`rbt post` will attempt to find your closest
tracking bookmark and post all changes between that and your working copy.


Posting a single change
-----------------------

If you want to post the diff for only a single change (or commit), you can pass
in that commit as a single revision argument. This can be used with a specific
change ID, or you can pass ``@`` to post the content of your working copy.

.. code-block:: console

    $ rbt post @

    $ rbt post <change-id>

    $ rbt post <bookmark-name>


Posting a range of changes
--------------------------

You can post a range of commits by passing a revset that represents a range of
commits, or passing two arguments representing the base and tip of the range
you want to post.

.. code-block:: console

    $ rbt post release-branch..@


Step 2: Update from reviewer feedback
=====================================

Got some reviewer feedback to incorporate into your change? Easy.

1. Create a new change, or edit your existing change.

2. Run :option:`rbt post -u` to update your review request.

   This will try to locate the review request you posted to before, comparing
   the summary and description with your change description. It will ask you if
   it's not sure which one is correct.

3. Update any information on the review request, if you want to.

   We recommend describing the changes you've made, so reviewers know what
   to look for. The field for this is on the green draft banner.

4. Publish the new changes for review.


Step 3: Land your change
========================

.. program:: rbt land

Once you've gotten approval to land the change, it's time to use
:ref:`rbt land <rbt-land>`. This will take your local change (or a review
request ID using :option:`-r`, if landing another person's change) and:

1. Validate that the change has been approved.
2. Merge or squash the change into the target branch.
3. Optionally push the change(es) upstream (:option:`--push`).

You can choose a branch to land to by using :option:`--dest`. To
configure a standard destination branch in your :ref:`rbtools-reviewboardrc`,
set ``LAND_DEST_BRANCH = '<branchname>'``. Make sure this is a local branch,
not a remote branch!

:ref:`rbt land <rbt-land>` has a lot of :ref:`options <rbt-land-options>` you
can play with. Because of the way Jujutsu handles merges (i.e. the lack of
built-in fast-forward merges), you may want to use :option:`--squash`
(``LAND_SQUASH = True``), if you like clean, linear commit histories.

You can edit the commit message before creating the commit using
:option:`--edit`.


Putting it all together
=======================

Let's walk through an example. We'll start with a ``jj`` repository which is
cloned from a Git upstream:

.. code-block:: console

    $ jj log
    @  mkykvuvp me@example.com 2025-01-09 10:10:53 c4c38566
    │  (empty) (no description set)
    ◆  uwxxsykv colleague@example.com 2025-01-03 09:54:00 main 1ddfc59e
    │  docs: Use "branch" consistently when talking about Git's branches
    ~

First let's make sure we have our configuration set correctly in
:file:`.reviewboardrc`::

    REPOSITORY_TYPE = 'jujutsu'
    TRACKING_BRANCH = 'main@origin'
    LAND_DEST_BRANCH = 'main'


We do some work, creating a couple changes:

.. code-block:: console

    $ vim foo.py
    $ jj commit -m "Change 1"
    $ vim bar.py
    $ jj commit -m "Change 2"


Our log now looks like this:

.. code-block:: console

    $ jj log
    @  wrsqkluy me@example.com 2025-02-07 09:27:17 81ba1f2c
    │  (empty) (no description set)
    ○  wwxtrsxp me@example.com 2025-02-07 09:13:23 e79f595f
    │  Change 2
    ○  pxolvpnn me@example.com 2025-02-07 08:29:46 8be9e5ff
    │  Change 1
    ◆  wulynnnz colleague@example.com 2025-01-24 09:16:35 main 918a5d23
    │  Fix unit tests for main module.
    ~


At this point, we need to make a decision about what and how we want to ask for
review. If all our changes were fundamentally part of the same thing, we might
collapse them in to a single review request. If they're separate, we'd want to
post them individually.

Let's say for this example that these changes are for two different things.
We're still iterating on our second change, but we think the first one is
ready:

.. code-block:: console

    $ rbt post p
    Review Request #1002 posted.

    https://reviewboard.example.com/r/1002/
    https://reviewboard.example.com/r/1002/diff/


Now we can do some more work and post our second change for review as well:

.. code-block:: console

    $ vim bar.py

    $ jj absorb bar.py
    Absorbed changes into these revisions:
      wwxtrsxp e79f595f Change 2
    Rebased 1 descendant commits.
    Working copy now at: wrsqkluy a2925006 (empty) (no description set)
    Parent commit      : wwtrsxpu 351657f9 Change 2

    $ rbt post ww
    Review Request #1007 posted.

    https://reviewboard.example.com/r/1007/
    https://reviewboard.example.com/r/1007/diff/


Say we've now received some feedback on our first change, and we want to make
some changes. We'll implement the requested changes, squash them into that
first change, and then update our review request.

.. code-block:: console

    $ vim foo.py

    $ jj squash -t p
    Rebased 2 descendant commits.
    Working copy now at: zzovrlyy 51513a22 (empty) (no description set)
    Parent commit      : wwtrsxpu e04b53f7 Change 2

    $ rbt post -u p
    Review Request #1002 posted.

    https://reviewboard.example.com/r/1002/
    https://reviewboard.example.com/r/1002/diff/

.. tip::

    You can update (:option:`-u <rbt post -u>`, describe the changes
    (:option:`-m <rbt post -m>`), and publish (:option:`-p <rbt post -p>`), all
    in the same step:

    .. code-block:: console

        $ rbt post -u -p -m "Fixed a broken link." p


Hey, we got a Ship It! for that first review request. Let's land it.

We have a choice between doing a merge or a squash. By default,
:rbtcommand:`rbt land` will do a merge. This involves creating a new merge
change, whether or not it is actually necessary. For example:

.. code-block:: console

    $ rbt land p
    Land Review Request #1002: "Change 1"?  [Yes/No]: y
    Merging branch "p" into "main".
    Review request 14305 has landed on "main".

    $ jj log
    @  wrsqkluy me@example.com 2025-02-07 09:27:17 81ba1f2c
    │  (empty) (no description set)
    ○  wwxtrsxp me@example.com 2025-02-07 09:13:23 e79f595f
    │  Change 2
    │ ○  ntyoqzrk me@example.com 2025-02-07 08:34:30 main* c4d581cd
    ╭─┤  (empty) Change 1
    ○ │  pxolvpnn me@example.com 2025-02-07 08:29:46 8be9e5ff
    ├─╯  Change 1
    ◆  wulynnnz colleague@example.com 2025-01-24 09:16:35 main@origin 918a5d23
    │  Fix unit tests for main module.
    ~

    $ jj git push -b main
    $ jj rebase -d main


In most cases, having these merge commits is ugly. When we're working
with branches that are just a single commit, it's not adding any value.
Instead, we can use a squash workflow to keep our history linear:

.. code-block:: console

    $ rbt land --squash m
    Land Review Request #1002: "Change 1"?  [Yes/No]: y
    Merging branch "p" into "main".
    Review request 14305 has landed on "main".

    $ jj log
    @  upxolvpnn me@example.com 2025-01-30 19:22:14 main 51187c77
    │  Change 1
    │ ○  tnqtqtwu me@example.com 2025-01-29 09:27:17 be927f5c
    ├─╯  Change 2
    ◆  uwxxsykv colleague@example.com 2025-01-03 09:54:00 1ddfc59e
    │  Edit some code
    ~

    @  wrsqkluy me@example.com 2025-02-07 09:27:17 81ba1f2c
    │  (empty) (no description set)
    ○  wwxtrsxp me@example.com 2025-02-07 08:37:53 72aa68eb
    │  Change 2
    │ ○  wktnlpxw me@example.com 2025-02-07 08:37:53 main* 51c29bc5
    ├─╯  Change 1
    ◆  wulynnnz colleague@example.com 2025-01-24 09:16:35 main@origin 918a5d23
    │  Fix unit tests for main module.
    ~

    $ jj git push -b main
    $ jj rebase -d main

.. tip::

    You can configure :rbtcommand:`rbt land` to always use squash by setting
    ``LAND_SQUASH = True`` in your :file:`.reviewboardrc`.
