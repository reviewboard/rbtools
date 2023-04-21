.. highlight:: text
.. _rbtools-workflow-git:

======================
Using RBTools with Git
======================

There are many ways you can use RBTools with Git. This guide covers the way
that we use RBTools ourselves.

A typical workflow looks like this:

1. :ref:`Create a branch for each review request <rbtools-workflow-git-step1>`
   (containing one or more commits)

2. :ref:`Post your change for review <rbtools-workflow-git-step2>`

3. :ref:`Commit/amend based on feedback and re-post for review
   <rbtools-workflow-git-step3>`

4. :ref:`Land your change <rbtools-workflow-git-step4>`

5. :ref:`Close your review request <rbtools-workflow-git-step5>`

We'll go over these concepts and then
:ref:`show you an example session <rbtools-workflow-git-example>`.


.. _rbtools-workflow-git-step1:

Step 1: Create a branch for your review request
===============================================

We recommend using one branch for every review request you're working with.
These may all be based on upstream branches, or they might be stacked on top
of each other as a series of dependent branches.

Create your branch, and create as many commits on it as you want. These
commits will later be posted as a single review request.


.. _rbtools-workflow-git-step2:

Step 2: Post your change for review
===================================

Once you have a branch full of commits, and you're ready to post it for
review, you'll need to check out the branch and run :rbtcommand:`post`.


.. admonition:: You don't need to push!

   Review requests are not pull requests. They're more flexible. You don't
   have to push anything anywhere, if you don't want to.

   You means you have more control over what's posted. You can selectively
   post only certain files with :option:`rbt post --include` or exclude files
   (like auto-generated files) with :option:`rbt post --exclude`.


There's a few useful tips to keep in mind when posting commits for review:

1. **RBTools commands accept standard Git revision ranges.**

   For example: ``rbt post HEAD`` or ``rbt post my-parent..HEAD``.

   If an explicit revision is not specified, *all* commits since the nearest
   matching upstream remote branch will be posted for review.

   If you're working in a branch based on another branch, you'll probably
   use one of the above examples, depending on whether you have one or more
   commits in your branch.

2. **You might want to specify an explicit tracking branch.**

   RBTools will *try* to find the "correct" upstream remote branch, but if
   you're not using tracking branches and you're using something other than
   ``origin``, it might find the wrong thing.

   This is important, because getting it wrong might mean *very* large or
   incorrect diffs (Git might try to show a reverted version of many commits
   worth of changes), and may time out or just fail to validate diffs.

   You can specify one using :option:`rbt post --tracking-branch` or, better,
   configuring :rbtconfig:`TRACKING_BRANCH` in
   :ref:`rbtools-reviewboardrc`.

   .. tip::

      We recommend you commit a :ref:`rbtools-reviewboardrc` file to your
      repository, and set the :rbtconfig:`TRACKING_BRANCH`,
      :rbtconfig:`BRANCH` and :rbtconfig:`LAND_DEST_BRANCH` settings in each
      main upstream branch. That way, this will always be set correctly for
      all users.

3. **Make sure the branch you're posting (or its parents) are on top of the
   latest upstream changes.**

   RBTools needs to figure out a suitable upstream commit to base your diff
   (or an intermediary parent diff) off of, so Review Board can find it. It
   will do its best, but Git is tricky, and it might get it wrong.

   It's safest to make sure your branch looks something like::

       o [my-branch]
       |
       o [origin/master]
       |
       .

   Rather than::

       o [my-branch]
       |
       |  o [origin/master]
       | /
       o
       |
       .


For example:

.. code-block:: console

   $ rbt post some-parent..HEAD
   Review request #123 posted.

   https://reviewboard.example.com/r/123/
   https://reviewboard.example.com/r/123/diff/

The posted review request will be populated with your commit's summary and
description. If you have :ref:`default reviewers <default-reviewers>` set up,
they'll be assigned.

Once you're done filling out fields on the review request, click
:guilabel:`Publish` to send it out for review.


.. _rbtools-workflow-git-step3:

Step 3: Update from reviewer feedback and re-post
=================================================

Got some reviewer feedback to incorporate into your change? Easy.

1. Create a new commit or amend an existing one. You can even change the
   entire ordering of commits in your branch, if you want to.

2. Run :option:`rbt post -u` to update your review request.

   This will try to locate the review request you posted to before, comparing
   the summary and description. It will ask you if it's not sure which one is
   correct.

3. Update any information on the review request, if you want to.

   We recommend describing the changes you've made, so reviewers know what
   to look for. The field for this is on the green draft banner.

4. Publish the new changes for review.


.. _rbtools-workflow-git-step4:

Step 4: Land your change
========================

.. program:: rbt land

Once you've gotten approval to land the change, it's time to use
:ref:`rbt land <rbt-land>`. This will take a local branch (or a review request
ID using :option:`-r`, if landing another person's change) and:

1. Validate that the change has been approved.
2. Creates a commit in the target branch (merging/squashing in your changes).
   The resulting commit (or merge commit) will contain information from the
   review request, including the URL of the review request.
3. Optionally pushes the changes upstream
   (:option:`--push`).

You can choose a branch to land to by using :option:`--dest`. To
configure a standard destination branch in your :ref:`rbtools-reviewboardrc`,
set ``LAND_DEST_BRANCH = '<branchname>'``. Make sure this is a local branch,
not a remote branch!

:ref:`rbt land <rbt-land>` has a lot of :ref:`options <rbt-land-options>` you
can play with. For Git, you may want to use :option:`--squash`
(``LAND_SQUASH = True``), if you like clean, linear commit histories.

You can edit the commit message before creating the commit using
:option:`--edit`.


.. _rbtools-workflow-git-step5:

Step 5: Close your review request
=================================

Now that your change is in, it's time to close your review request.

This *might* happen automatically, if your server and repositories are set up
to auto-close review requests when changes are pushed. This can be configured
for certain Git hosting services, or done with a custom `post-commit hook
script`_ in a self-hosted repository.

If you're using one of these supported repository hosting services, follow the
guides to set up automatic closing of review requests:

* :ref:`Beanstalk <repository-hosting-beanstalk-config-webhooks>`
* :ref:`Bitbucket <repository-hosting-bitbucket-config-webhooks>`
* :ref:`GitHub <repository-hosting-github-config-webhooks>`
* :ref:`GitHub Enterprise <repository-hosting-github-enterprise-config-webhooks>`

If you're not set up this way, no problem. You have two options:

1. Navigate to the review request and close it.

   In Review Board 6 and newer, click :guilabel:`Close -> Completed`.

   In Review Board 5 and older, click :guilabel:`Close -> Submitted`.

2. Run :command:`rbt close <review request ID>` (see the
   :ref:`documentation <rbt-close>`).


.. _post-commit hook script:
   https://github.com/reviewboard/rbtools/blob/master/contrib/tools/git-hook-set-submitted


.. _rbtools-workflow-git-example:

Putting it all together
=======================

Let's walk through an example using 3 commits across two branches.

First, we'll create ``my-branch-1`` off of ``master`` with the first 2
commits:

.. code-block:: console

    $ git checkout -b my-branch-1 master
    $ vim foo.py
    $ git commit -a
    $ vim bar.py
    $ git commit -a

Now let's create ``my-branch-2`` off of that, with only a single commit:

.. code-block:: console

    $ git checkout -b my-branch-2
    $ vim foo.py
    $ git commit -a

Your tree now looks like this::

    o 167ba59 [my-branch-2]
    |
    o 81abb90 [my-branch-1]
    |
    o a987ee1
    |
    o 81a0a95 [master] [origin/master]
    |
    .

We'll post ``my-branch-1`` for review. Since we want everything since
``origin/master``, this will be very easy. We just post like so:

.. code-block:: console

    $ git checkout my-branch-1
    $ rbt post
    Review request #1001 posted.

    https://reviewboard.example.com/r/1001/
    https://reviewboard.example.com/r/1001/diff/


.. tip::

   We could have just ran ``rbt post origin/master..my-branch-1``, if we
   didn't want to switch to the branch first.

That review request will be populated with your commit's summary and
description.

Let's create a second review request, covering the changes on ``my-branch-2``.
We'll take the opportunity to mark these as dependent on our new review
request #1001:

.. code-block:: console

    $ git checkout my-branch-2
    $ rbt post --depends-on 1001 my-branch-1..HEAD
    Review request #1002 posted.

    https://reviewboard.example.com/r/1002/
    https://reviewboard.example.com/r/1002/diff/


.. tip::

   Since we were on ``my-branch-2``, and there was only one commit, we could
   have just ran ``rbt post HEAD``.

   Or we could have ran ``rbt post my-branch-1..my-branch-2``, if we didn't
   want to switch branches.

   We also could have set the Depends On field on the review request page, or
   left it out entirely. Just helps reviewers know what to review first.

Let's make some changes to the commit on `my-branch-1`, based on review
feedback, and post a new diff to the review request:

.. code-block:: console

    $ git checkout my-branch-1
    $ vim README
    $ git commit -a --amend
    $ rbt post -u
    Review request #1001 posted.

    https://reviewboard.example.com/r/1001/
    https://reviewboard.example.com/r/1001/diff/

Go to the review request, describe the changes you made, and publish the new
changes.

.. tip::

   You can update (:option:`-u <rbt post -u>`), describe the changes
   (:option:`-m <rbt post -m>`), and publish (:option:`-p <rbt post -p>`),
   all in the same step:

   .. code-block:: console

       rbt post -u -p -m "Fixed a broken link." HEAD

And now for ``my-branch-2``. Let's rebase onto ``my-branch-1``, edit a file,
and post:

.. code-block:: console

     $ git checkout my-branch-2
     $ git rebase my-branch-1
     $ vim AUTHORS
     $ git commit -a --amend
     $ rbt post -u my-branch-1..HEAD
     Review request #1002 posted.

     https://reviewboard.example.com/r/1002/
     https://reviewboard.example.com/r/1002/diff/

Hey, we got a Ship It! for both review requests. Great, let's land these:

.. code-block:: console

    $ git checkout master
    $ rbt land --dest=master my-branch-1
    $ rbt land --dest=master my-branch-2
    $ git push

Each branch's review request will be verified for approval before their
commits are merged onto ``master``. The old branches will be deleted after
they've landed.

Maybe we wanted to land them as linear, squashed commits, one per branch? If
so, we could have used ``--squash``.

Once you get the hang of this process, you'll find it *much* faster band more
flexible than methods like pull requests.
