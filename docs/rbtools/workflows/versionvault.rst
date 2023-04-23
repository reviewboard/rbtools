.. _rbtools-workflow-versionvault:

=====================================================
Using RBTools with HCL VersionVault and IBM ClearCase
=====================================================

This guide covers the various ways to use RBTools with `HCL VersionVault`_ or
`IBM ClearCase`_. You can post changes using both Base ClearCase or UCM
workflows.

A typical workflow looks like this:

1. :ref:`Create your change for the review request
   <rbtools-workflow-versionvault-step1>`

2. :ref:`Post your change for review <rbtools-workflow-versionvault-step2>`

3. :ref:`Make changes based on feedback and re-port for review
   <rbtools-workflow-versionvault-step3>`

4. :ref:`Finish your code by checking in or delivering your activity
   <rbtools-workflow-versionvault-step4>`

5. :ref:`Close your review request <rbtools-workflow-versionvault-step5>`


.. _HCL VersionVault: https://www.hcltechsw.com/versionvault
.. _IBM ClearCase: https://www.ibm.com/products/rational-clearcase


.. _rbtools-workflow-versionvault-step1:

Step 1: Create your change
==========================

You'll be able to post a branch, label, activity, baseline, or stream
representing the change you want to review.


.. _rbtools-workflow-versionvault-step2:

Step 2: Posting changes for review
==================================

Posting checked-out files
-------------------------

The most simple case is posting a diff of all currently checked out files in
your view. This will work no matter what workflow you are using:

.. code-block:: console

    $ rbt post


Posting changes with Base ClearCase workflows
---------------------------------------------

When using Base ClearCase, there are several ways you can post code for review.

To post a change between a branch and its predecessor, use:

.. code-block:: console

    $ rbt post brtype:branchname

To post a change between a label and its predecessor, use:

.. code-block:: console

    $ rbt post lbtype:labelname

A diff between two labels can also be posted. This requires posting from within
a dynamic view:

.. code-block:: console

    $ rbt post lbtype:label1 lbtype:label2


Posting changes with UCM workflows
----------------------------------

If you're using UCM, you can also post activities, baselines, and streams.

To post an activity, use:

.. code-block:: console

    $ rbt post activity:my-activity


To post the diff between a baseline and its predecessor, use:

.. code-block:: console

    $ rbt post baseline:project-dev

To post the diff between two baselines:

.. code-block:: console

    $ rbt post baseline:project-integration baseline:project-dev

To post a stream:

.. code-block:: console

    $ rbt post stream:dev-stream


Posting files manually
----------------------

Finally, you can also assemble a diff using file@revision pairs. This requires
posting from within a dynamic view. Each argument will be a
``file@@revision1:file@@revision2`` pair:

.. code-block:: console

    $ rbt post /vobs/proj/file.c@@/main/0:/vobs/proj/file.c@@/main/1

Multiple files can be posted by adding additional file/revision pairs:

.. code-block:: console

    $ rbt post /vobs/proj/file.c@@/main/0:/vobs/proj/file.c@@/main/1 \
               /vobs/proj/file.h@@/main/0:/vobs/proj/file.h@@/main/1


Once you've posted...
---------------------

Your changes are now posted to Review Board, but are in a draft state. Nobody
can see it until you're ready to publish.

You'll now need to go to the URL and fill out the :guilabel:`Summary`,
:guilabel:`Description`, or any other fields.

If you have :ref:`default reviewers <default-reviewers>` set up, they'll be
assigned automatically, but you can also specify the people or groups you want
to review your change.

Once you're done filling out fields on the review request, click
:guilabel:`Publish` to send it out for review.


.. _rbtools-workflow-versionvault-step3:

Step 3: Update from reviewer feedback and re-post
=================================================

Got some reviewer feedback to incorporate into your change? Easy.

1. Depending on your workflow, make any changes as necessary. For example,
   continue to edit your existing checked-out files, or add additional changes
   to your activity.

2. Update the review request with the latest code, using :option:`rbt post -r
   \<review_request_id\> <rbt post -r>`. This option can be used with any of
   the diff selection methods listed above.

   For example:

   .. code-block:: console

       $ rbt post -r 123 activity:my-activity
       Review request #123 posted.

       https://reviewboard.example.com/r/123/
       https://reviewboard.example.com/r/123/diff/

3. Update any information on the review request, if you want to.

   We recommend describing the changes you've made, so reviewers know what
   to look for. The field for this is on the green draft banner.

4. Publish the new changes for review.

5. Rinse and repeat until the review process is complete and the change is
   accepted.


.. _rbtools-workflow-versionvault-step4:

Step 4: Finish your code
========================

Depending on what workflow you're doing, you can now proceed to finish the code
change. This could involve checking in any checked-out files, or delivering
your current UCM activity.


.. _rbtools-workflow-versionvault-step5:

Step 5: Close your review request
=================================

Now that your change is in, it's time to close your review request. You can do
this in one of two ways:

1. Navigate to the review request and close it.

   In Review Board 6 and newer, click :guilabel:`Close -> Completed`.

   In Review Board 5 and older, click :guilabel:`Close -> Submitted`.

2. Run :command:`rbt close <review request ID>` (see the
   :ref:`documentation <rbt-close>`).


.. _rbtools-workflow-versionvault-example:

Putting it all together
=======================

Let's walk through an example using a UCM activity.

Posting your change
-------------------

First we'll create our activity and edit some files.

.. code-block:: console

    $ cleartool mkactivity -nc my-activity
    $ cleartool checkout -nc foo.py
    $ vim foo.py
    $ cleartool checkin -c "Make initial change" foo.py
    $ cleartool checkout -nc bar.py
    $ vim bar.py
    $ cleartool checkin -c "Make initial change" bar.py

Now let's post these changes for review.

.. code-block:: console

    $ rbt post activity:my-activity
    Review request #1001 posted.

    https://reviewboard.example.com/r/1001/
    https://reviewboard.example.com/r/1001/diff/

At this point, we'll publish the review request, and then wait for feedback.


Update from review feedback
---------------------------

Hey, we got some review feedback. Let's make changes to our code, and then
update our review request:

.. code-block:: console

    $ cleartool checkout -nc foo.py
    $ vim foo.py
    $ cleartool checkin -c "Update for review feedback" foo.py
    $ rbt post -r 1001 activity:my-activity
    Review request #1001 posted.

    https://reviewboard.example.com/r/1001/
    https://reviewboard.example.com/r/1001/diff/

Go to the review request, describe the changes you made, and publish the new
changes.


Finish up
---------

Once you've gotten approval (reviews with a "Ship It!" that match your
department/company's policies), you can complete your change and close the
review request.

.. code-block:: console

    $ cleartool deliver -activities my-activity
    $ rbt close 1001

(You can also close it in the review request page.)
