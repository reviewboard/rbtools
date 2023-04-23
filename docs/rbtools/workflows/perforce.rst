.. _rbtools-workflow-perforce:

===========================
Using RBTools With Perforce
===========================

This guide covers how you can use RBTools to post changes to Perforce_.

A typical workflow looks like this:

1. :ref:`Create a changeset for each review request
   <rbtools-workflow-perforce-step1>`

2. :ref:`Post your change for review <rbtools-workflow-perforce-step2>`

3. :ref:`Make changes based on feedback and re-post for review
   <rbtools-workflow-perforce-step3>`

4. :ref:`Submit your change to the depot <rbtools-workflow-perforce-step4>`

5. :ref:`Close your review request <rbtools-workflow-perforce-step5>`

We'll go over these concepts and then
:ref:`show you an example session <rbtools-workflow-perforce-example>`.


.. _Perforce: https://www.perforce.com/


Before you begin
================

This guide assumes the following are already set up:

* An administrator has :ref:`configured a Perforce repository
  <rb:repository-scm-perforce>` in Review Board.

* A :ref:`rbtools-reviewboardrc` file has been created and placed in your
  checkout location.

* RBTools is installed and the p4_ command line tool is in your
  system path.


.. _p4: https://www.perforce.com/products/helix-core-apps/command-line-client


.. _rbtools-workflow-perforce-step1:

Step 1: Create your change
==========================

Create your change using :command:`p4 change` and open/add/delete any files
you want included in the review request:

.. code-block:: console

   $ p4 change
   $ p4 open -c <changenum> <filename>
   $ vim <filename>
   $ p4 add -c <changenum> <filename>
   $ ...

Changes can optionally be associated with a stream.

You'll want to populate the changeset with a summary and description. These
will be used to populate the review request's own summary and description.


.. _rbtools-workflow-perforce-step2:

Step 2: Post your change for review
===================================

Once you have a change with modifications to the depot, and you're ready to
post it for review, you can run :rbtcommand:`post` and include the change
number:

.. code-block:: console

   $ rbt post <changenum>

For example:

.. code-block:: console

   $ rbt post 10291
   Review request #123 posted.

   https://reviewboard.example.com/r/123/
   https://reviewboard.example.com/r/123/diff/

You can use the :option:`-o <rbt post -o>` option to automatically open
this review request in your web browser for editing.

The posted review request will be populated with your changeset's summary and
description. If you have :ref:`default reviewers <rb:default-reviewers>` set
up, they'll be assigned.

Once you're done filling out fields on the review request, click
:guilabel:`Publish` to send it out for review.


.. _rbtools-workflow-perforce-step3:

Step 3: Update from reviewer feedback and re-post
=================================================

Got some reviewer feedback to incorporate into your change? Easy.

1. Update the files in your change, and/or the information in your changeset.

2. Re-run :option:`rbt post <changenum>` to update your review request.

   This will update the same review request already associated with your
   change number, and will also update the review request details (such as
   the summary and description) from the changeset description.

3. Update any information on the review request, if you want to.

   We recommend describing the changes you've made, so reviewers know what
   to look for. The field for this is on the green draft banner.

4. Publish the new changes for review.


.. _rbtools-workflow-perforce-step4:

Step 4: Submit your change to Perforce
======================================

Once you've received approval to land the change, it's time to submit your
change. You'll do this using the standard :command:`p4 submit`:

.. code-block:: console

   $ p4 submit -c <changenum>


.. _rbtools-workflow-perforce-step5:

Step 5: Close your review request
=================================

Now that your change is in, it's time to close your review request.

This *might* happen automatically, if your server and repositories are set up
to auto-close review requests when changes are pushed.

This can be configured in Perforce using a custom `Perforce change-submit
trigger script`_.

If you're not set up this way, no problem. You have two options:

1. Navigate to the review request and close it.

   In Review Board 6 and newer, click :guilabel:`Close -> Completed`.

   In Review Board 5 and older, click :guilabel:`Close -> Submitted`.

2. Run :command:`rbt close <review request ID>` (see the
   :ref:`documentation <rbt-close>`).


.. _Perforce change-submit trigger script:
   https://github.com/reviewboard/rbtools/blob/master/contrib/tools/p4-trigger-script


.. _rbtools-workflow-perforce-example:

Putting it all together
=======================

Let's walk through an example.

1. We'll create a new change and make some modifications:

   .. code-block:: console

      $ p4 change
      <edit the changeset:>
      ...

      Description:
          Add a change to do something great.

          Let me spend a lot of time explaining what this change is doing
          so that reviewers can fully understand it.

      <save the changeset...>

      Change 105 created.

      $ p4 add -c 105 art/spritesheet.png
      $ p4 open -c 105 src/engine/collision.cs
      $ vim src/engine/collision.cs
      $ p4 delete -c 105 docs/proposed-spec.txt
      $ p4 move -c 105 src/utils.cs src/common/utils.cs

2. We'll now post change #105 for review:

   .. code-block:: console

      $ rbt post 105
      Review request #1001 posted.

      https://reviewboard.example.com/r/1001/
      https://reviewboard.example.com/r/1001/diff/

   That review request will be populated with your changeset's summary and
   description.

3. Let's create a second review request, covering a couple more changes.

   We'll take the opportunity to mark these as dependent on our new review
   request #1001:

   .. code-block:: console

      $ p4 change
      ...
      Change 106 created.

      $ p4 add -c 106 art/character-model.png
      $ rbt post --depends-on 1001 106
      Review request #1002 posted.

      https://reviewboard.example.com/r/1002/
      https://reviewboard.example.com/r/1002/diff/

4. Meanwhile, we got some feedback on change #105/review request #1001, so
   let's update our changes.

   .. code-block:: console

      $ vim src/engine/collision.cs
      $ rbt post 105
      Review request #1001 posted.

      https://reviewboard.example.com/r/1001/
      https://reviewboard.example.com/r/1001/diff/

   Go to the review request, describe the changes you made, and publish the
   new changes.

   .. tip::

      You can update, describe the changes (:option:`-m <rbt post -m>`), and
      publish (:option:`-p <rbt post -p>`), all in the same step:

      .. code-block:: console

          $ rbt post -p -m "Fixed a broken link." 105

5. Hey, we got a Ship It! for both review requests! Great, let's submit these
   and close out the review requests.

   .. code-block:: console

      $ p4 submit -c 105
      $ p4 submit -c 106
      $ rbt close 1001
      $ rbt close 1002

   :command:`rbt close` isn't necessary if using a `Perforce change-submit
   trigger script`_ for the repository!

   If a script is installed, the changes will be checked for approval before
   they can be submitted, and the review requests will be closed
   automatically:

   .. code-block:: console

      $ p4 submit -c 105
      $ p4 submit -c 106

You'll get the hang of this process in no time. Soon you'll be well on your
way to better code quality.
