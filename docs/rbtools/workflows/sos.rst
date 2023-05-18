.. _rbtools-workflow-sos:

===============================
Using RBTools With Cliosoft SOS
===============================

This guide covers how you can use RBTools to post changes to `Cliosoft SOS`_
7.20 or higher. We'll cover posting both selections and changelists (new in SOS
7.20) for review.

A typical workflow looks like this:

1. :ref:`Create a SOS changelist for your changes (optional)
   <rbtools-workflow-sos-step1>`

2. :ref:`Post your changes for review (via changelist or selection)
   <rbtools-workflow-sos-step2>`

3. :ref:`Make changes based on feedback and re-post for review
   <rbtools-workflow-sos-step3>`

4. :ref:`Commit your change to SOS <rbtools-workflow-sos-step4>`

5. :ref:`Close your review request <rbtools-workflow-sos-step5>`

We'll go over these concepts and then
:ref:`show you an example session <rbtools-workflow-sos-example>`.


.. important::

   You'll need to wait to commit your changes until *after* you're finished
   with the review process and your change has been approved (with a Ship
   It!).

   Changes that are already committed cannot currently be posted for review.


.. _Cliosoft SOS: https://www.cliosoft.com/products/sos/


.. _rbtools-workflow-sos-step1:

Step 1. Create a SOS changelist for your changes
================================================

SOS changelists are new in SOS 7.20, and are recommended to help you keep track
of all the files that you want to post for review and, later, commit to your
project.


.. Check on the below to make sure that's still true.

.. note::

   Changelists require a writable workarea (:command:`soscmd newworkarea
   -LWRITABLE ...`).

Changelists are created through :command:`socmd add`, like so:

.. code-block:: console

   $ soscmd add -c <changelist_name> <file1> <file2> ...

For example:

.. code-block:: console

   $ soscmd add -c memory-leak-fix src/driver-main.c src/memutils.c

You can name the changelist anything you want, and can pass any files you've
created, modified, or deleted.

If you choose not to use changelists, then you'll instead post selections for
review, which we'll show below.


.. _rbtools-workflow-sos-step2:

Step 2: Post your change for review
===================================

There are three ways you can post changes for review:

1. If you have a changelist to post, you can pass the name to
   :rbtcommand:`post`.

   .. code-block:: console

      $ rbt post <changelist_name>
      Review request #123 posted.

      https://reviewboard.example.com/r/123/
      https://reviewboard.example.com/r/123/diff/

   For example:

   .. code-block:: console

      $ rbt post memory-leak-fix

2. You can simply post all the files that you've modified or added to/deleted
   from checked-out directories by running:

   .. code-block:: console

      $ rbt post
      Review request #123 posted.

      https://reviewboard.example.com/r/123/
      https://reviewboard.example.com/r/123/diff/

   That's roughly equivalent to posting a selection represented by the
   ``-scm`` selection flag.

3. You can post an explicit selection:

   .. code-block:: console

      $ rbt post "select:<flags>"

   For example:

   .. code-block:: console

      $ rbt post "select:-scm -sor -sunm"
      Review request #123 posted.

      https://reviewboard.example.com/r/123/
      https://reviewboard.example.com/r/123/diff/


Including/Excluding Files
-------------------------

You can also provide the explicit files you want to post for review with
:option:`rbt post -I`:

.. code-block:: console

   $ rbt post -I <file1> -I <file2>


Or exclude certain file patterns from a changelist or selection with
:option:`rbt post -X`:

.. code-block:: console

   $ rbt post -X '*.txt'

These can be paired with a selection or a changelist name.


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


.. _rbtools-workflow-sos-step3:

Step 3: Update from reviewer feedback and re-post
=================================================

Got some reviewer feedback to incorporate into your change? Easy.

1. Make the changes to your tree (make sure not to commit yet!)

2. If you're using changelists, run :option:`rbt post -u \<changelist_name\>
   <rbt post -u>` to update your review request.

   This will try to locate the review request you posted to before, comparing
   workarea ID and changelist name. It will ask you if it's not sure which one
   is correct.

   For example:

   .. code-block:: console

      $ rbt post -u memory-leak-fix
      Review request #123 posted.

      https://reviewboard.example.com/r/123/
      https://reviewboard.example.com/r/123/diff/

   If you're using selections, you'll need to instead run
   :option:`rbt post -r \<review_request_id\> <rbt post -r>` with your
   preferred selection or :option:`-I <rbt post -I>`/:option:`-X <rbt post
   -X>` to update the desired review request.

   For example:

   .. code-block:: console

      $ rbt post -r 123
      Review request #123 posted.

      https://reviewboard.example.com/r/123/
      https://reviewboard.example.com/r/123/diff/

   Or:

   .. code-block:: console

      $ rbt post -r 123 "select:-scm -sor -sunm"
      Review request #123 posted.

      https://reviewboard.example.com/r/123/
      https://reviewboard.example.com/r/123/diff/

3. Update any information on the review request, if you want to.

   We recommend describing the changes you've made, so reviewers know what
   to look for. The field for this is on the green draft banner.

4. Publish the new changes for review.

5. Rinse and repeat until you have the necessary approval to commit your
   change.


.. _rbtools-workflow-sos-step4:

Step 4: Commit your change
==========================

Once you've gotten approval to commit the change, you can commit it using
:command:`soscmd` as normal.

To commit your changelist, use :command:`soscmd commit`. For example:

.. code-block:: console

   $ soscmd commit -c memory-leak-fix

To commit your selections, use :command:`soscmd ci` as normal.


.. _rbtools-workflow-sos-step5:

Step 5: Close your review request
=================================

Now that your change is in, it's time to close your review request.

1. Navigate to the review request and close it.

   In Review Board 6 and newer, click :guilabel:`Close -> Completed`.

   In Review Board 5 and older, click :guilabel:`Close -> Submitted`.

2. Run :command:`rbt close <review request ID>` (see the
   :ref:`documentation <rbt-close>`).


.. _rbtools-workflow-sos-example:

Putting it all together
=======================

Let's walk through an example using changelists in a writeable workarea.


Posting your change
-------------------

First, assume we've created a file (``newfile``), deleted a file
(``oldfile``), and modified a file (``changedfile``).

Let's create a changelist and add these files to it (note that we can call
:command:`soscmd add` multiple times if we want to):

.. code-block:: console

   $ soscmd add -c my-changelist newfile oldfile changedfile

We now have a changelist called ``my-changelist``. Let's post it for review.

.. code-block:: console

   $ rbt post my-changelist
   Review request #1001 posted.

   https://reviewboard.example.com/r/1001/
   https://reviewboard.example.com/r/1001/diff/

The review request will be posted, and will start off blank. You can go to the
URL now to fill out those fields, and then click :guilabel:`Publish`.

Wait and grab some coffee...


Update From review feedback
---------------------------

Hey, we got some review feedback. Let's make some changes to those files in
our changelist and then update our review request:

.. code-block:: console

   $ rbt post -u my-changelist
   Review request #1001 posted.

   https://reviewboard.example.com/r/1001/
   https://reviewboard.example.com/r/1001/diff/

Go to the review request, describe what you've fixed to help our your fellow
reviewers, and publish the new draft.

.. tip::

   You can update (:option:`-u <rbt post -u>`), describe the changes
   (:option:`-m <rbt post -m>`), and publish (:option:`-p <rbt post -p>`),
   all in the same step:

   .. code-block:: console

      $ rbt post -u -m "Fixed a broken link." -p my-changelist


Commit the change
-----------------

Once you've gotten an approval (reviews with a "Ship It!" that match your
department/company's policies), you can commit your change and close the
review request.

.. code-block:: console

   $ soscmd commit -c my-changelist
   $ rbt close 1001

(You can also close it in the review request page).

You'll get the hang of this process in no time. Soon you'll be well on your
way to better code quality.
