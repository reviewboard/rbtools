.. rbt-command:: rbtools.commands.status_update.StatusUpdate

=============
status-update
=============

:command:`rbt status-update` is used to create, edit, or delete status updates
on a review request.

Status updates can be used by code checking tools, such as internal scripts,
CI systems, or `Review Bot`_, to communicate that code is being analyzed or
to communicate the result of that analysis, usually in the form of a review.

This command makes it easy to integrate your own code checking or review
request validation scripts with Review Board.

.. _Review Bot: https://www.reviewboard.org/downloads/reviewbot/


.. rbt-command-usage::


.. admonition:: Upgrading from RBTools 1.x or 2.x

   RBTools 2 required that the ``get``, ``set``, or ``delete`` action be
   last. In RBTools 3 and up, it must be before any options.

   The old form is supported in RBTools 3, but will be removed in RBTools 4.


.. rbt-subcommand:: get

rbt status-update get
=====================

This is is used to list all the status updates on a review request, or to
display information on a particular status update.

It requires the :option:`-r`/:option:`--review-request-id` option, and can
take a :option:`-s`/:option:`--status-update-id` to specify a particular
status update.

.. rbt-subcommand-usage::


Listing Status Updates
----------------------

To list status updates, run :command:`rbt status-update get -r
<review_request_id>` without :option:`--status-update-id`. For example:

.. code-block:: console

   $ rbt status-update get -r 123
   180	reviewbot.17: <done-failure> cpplint: failed.
   181	reviewbot.18: <done-success> GoTool: passed.
   182	reviewbot.19: <done-success> ShellCheck: passed.

This information can also be returned in JSON form by using :option:`--json`:

.. code-block:: console

   $ rbt status-update get -r 123 --json
   {
       "status": "success",
       "status_updates": [
           {
               "description": "failed.",
               "extra_data": {
                   "can_retry": true
               },
               "id": 180,
               "service_id": "reviewbot.17",
               "state": "done-failure",
               "summary": "cpplint",
               "timeout": 60
           },
           {
               "description": "passed.",
               "id": 181,
               "service_id": "reviewbot.18",
               "state": "done-success",
               "summary": "GoTool",
               "timeout": 60
           },
           {
               "description": "passed.",
               "id": 182,
               "service_id": "reviewbot.19",
               "state": "done-success",
               "summary": "ShellCheck",
               "timeout": 60
           }
       ]
   }

If anything goes wrong, you'll receive an error:

.. code-block:: console

   $ rbt status-update get -r 123 --json
   {
       "errors": [
           "Something terrible happened and hopefully this explains why."
       ],
       "status": "failed"
   }


Displaying a Status Update
--------------------------

:command:`rbt status-update get -r <review_request_id> -s <status_update_id>`
can be used to display information on a particular status update. For example:

.. code-block:: console

   $ rbt status-update get -r 123 -s 180
   180	reviewbot.17: <done-failure> cpplint: failed.

This information can also be returned in JSON form by using :option:`--json`:

.. code-block:: console

   $ rbt status-update get -r 123 -s 180 --json
   {
       "status": "success",
       "status_updates": [
           {
               "description": "failed.",
               "extra_data": {
                   "can_retry": true
               },
               "id": 180,
               "service_id": "reviewbot.17",
               "state": "done-failure",
               "summary": "cpplint",
               "timeout": 60
           }
       ]
   }

If anything goes wrong, you'll receive an error:

.. code-block:: console

   $ rbt status-update get -r 123 -s 180 --json
   {
       "errors": [
           "Something terrible happened and hopefully this explains why."
       ],
       "status": "failed"
   }


.. rbt-subcommand-options::


.. rbt-subcommand:: set

rbt status-update set
=====================

This is used to create or modify a status update on a review request. It's
useful for custom CI, build, or code analysis integrations that need to
report results on a review request.

.. rbt-subcommand-usage::


Creating a Status Update
------------------------

When creating a status update, you need to specify the following:

* A service ID (:option:`--service-id`) that uniquely identifies this category
  of status update (e.g., ``internal-code-checker.styles``).

* An initial summary (:option:`--summary`) naming this status update (e.g.,
  ``Code Compliance Checker``).

Optionally, you may also want to specify:

* A timeout in seconds (:option:`--timeout`) before the status update is
  listed as having failed due to timeout.

* A URL (:option:`--url`) and accompanying link text (:option:`--url-text`)
  for monitoring results.

* A description (:option:`--description`) shown beside the summary name
  conveying the current status (e.g., ``starting...``).

* A change ID ("Review Request Changed" box) to attach the status update to
  (:option:`--change-id`).

For example:

.. code-block:: console

   $ rbt status-update set \
         -r 123 \
         --service-id internal-code-checker.styles \
         --summary "Code Compliance Checker" \
         --description "starting..." \
         --timeout 120 \
         --url https://ci.eng.example.com/codechecker/builds/12345/ \
         --url-text "Build Log"
   234	internal-code-checker.styles: <pending> starting...

You can use :option:`--json` to return a payload containing the information:

.. code-block:: console

   $ rbt status-update set \
         -r 123 \
         --service-id internal-code-checker.styles \
         --summary "Code Compliance Checker" \
         --description "starting..." \
         --timeout 120 \
         --url https://ci.eng.example.com/codechecker/builds/12345/ \
         --url-text "Build Log" \
         --json
   {
       "status": "success",
       "status_updates": [
           {
               "description": "starting...",
               "id": 234,
               "service_id": "internal-code-checker.styles",
               "state": "pending",
               "summary": "Code Compliance Checker",
               "timeout": 120
           }
       ]
   }

If anything goes wrong, you'll receive an error:

.. code-block:: console

   $ rbt status-update set \
         -r 123 \
         --service-id internal-code-checker.styles \
         --summary "Code Compliance Checker" \
         --description "starting..." \
         --timeout 120 \
         --url https://ci.eng.example.com/codechecker/builds/12345/ \
         --url-text "Build Log" \
         --json
   {
       "errors": [
           "Something terrible happened and hopefully this explains why."
       ],
       "status": "failed"
   }


Modifying a Status Update
-------------------------

Eventually you'll want to report a result for your status update, indicating
if the checks have succeeded, failed, or triggered some kind of error. You may
want to add a review, or link to some result.

To modify a status update, you'll use :command:`rbt status-update set` again,
but you'll specify :option:`-s`/:option:`--status-update-id` to indicate which
status update you're modifying.

You'll probably want to specify some of the following:

* The new state of the change (:option:`--state`). This can be one of:
  ``pending``, ``done-failure``, ``done-success``, ``error``

* The new description (:option:`--description`) shown beside the summary name,
  conveying the new status (e.g., ``passed.``)

* A new URL (:option:`--url`) and accompanying link text (:option:`--url-text`)
  for the results.

* A review with any failures (:option:`--review`).

  See :ref:`rbt-status-update-set-review` below.

For example, if successful:

.. code-block:: console

   $ rbt status-update set \
         -r 123 \
         -s 234 \
         --state done-success \
         --description "passed."
   234	internal-code-checker.styles: <done-success> passed.

Or if checks found some problems to report:

.. code-block:: console

   $ rbt status-update set \
         -r 123 \
         -s 234 \
         --state done-failure \
         --description "failed." \
         --review results.json
   234	internal-code-checker.styles: <done-failure> failed.

You can use :option:`--json` to return a payload containing the information:

.. code-block:: console

   $ rbt status-update set \
         -r 123 \
         -s 234 \
         --state done-success \
         --description "passed." \
         --json
   {
       "status": "success",
       "status_updates": [
           {
               "description": "failed.",
               "id": 234,
               "service_id": "internal-code-checker.styles",
               "state": "done-failure",
               "summary": "Code Compliance Checker",
               "timeout": 120
           }
       ]
   }

If anything goes wrong, you'll receive an error:

.. code-block:: console

   $ rbt status-update set \
         -r 123 \
         -s 234 \
         --state done-success \
         --description "passed." \
         --json
   {
       "errors": [
           "Something terrible happened and hopefully this explains why."
       ],
       "status": "failed"
   }


.. _rbt-status-update-set-review:

Reporting Failed Results
------------------------

When reporting a ``done-failure`` result, you'll want to include some
information to help the owner of the change know what went wrong.

This can be done by generating a JSON file containing information on a review,
and then passing that filename to :option:`--review`. Any comments or text
provided in this file will be filed on the review request, attached to the
results of your status update.

The format of the file looks like:

.. code-block:: javascript

    {
        // Optional: Header/footer for the review.
        "review": {
            // Optional: Header text to display above the list of comments.
            "body_top": "<string>",

            // Optional: Footer text to display below the list of comments.
            "body_bottom": "<string>"
        },

        // Optional list of comments on diffs.
        "diff_comments": [
            {
                // Required: The ID of the file being reviewed
                "filediff_id": <int>,

                // Required: The 1-based line number for the comment.
                "first_line": <int>,

                // Optional: Set to true to open an issue.
                "issue_opened": true|false,

                // Required: The number of lines the comment should span.
                "num_lines": <int>,

                // Required: Text shown in the comment.
                "text": "<string>",

                // Required: Type of text formatting ("plain" or "markdown").
                "text_type": "plain|markdown"
            },
            ...
        ],

        // Optional list of general comments, not bound to a file or diff.
        "general_comments": [
            {
                // Optional: Set to true to open an issue.
                "issue_opened": true|false,

                // Required: Text shown in the comment.
                "text": "<string>",

                // Required: Type of text formatting ("plain" or "markdown").
                "text_type": "plain|markdown"
            },
            ...
        ]
    }

Anything listed as optional can be omitted.

For example:

.. code-block:: javascript

    {
        "review": {
            "body_top": "Header comment"
        },
        "diff_comments": [
            {
                "filediff_id": 1,
                "first_line": 1,
                "issue_opened": true,
                "num_lines": 1,
                "text": "Adding a comment on a diff line",
                "text_type": "markdown"
            },
            {
                "filediff_id": 2,
                "first_line": 2,
                "issue_opened": true,
                "num_lines": 1,
                "text": "Adding a second diff comment",
                "text_type": "markdown"
            }
        ],
        "general_comments": [
            {
                "text": "Adding a general comment",
                "text_type": "markdown"
            }
        ]
    }


.. rbt-subcommand-options::


.. rbt-subcommand:: delete

rbt status-update delete
========================

This is used to delete a status update.

This may be useful if you're playing around with the command. In production,
once a status update is filed on a review request, it should only be resolved
by updating the state, not deleting it.

.. rbt-subcommand-usage::

When deleting a status update, :option:`-s`/:option:`--status-update-id` is
required.

For example:

.. code-block:: console

   $ rbt status-update delete -r 123 -s 234
   Status update 234 has been deleted.

This information can also be returned in JSON form by using :option:`--json`:

.. code-block:: console

   $ rbt status-update delete -r 123 -s 234 --json
   {
       "status": "success"
   }

If anything goes wrong, you'll receive an error:

.. code-block:: console

   $ rbt status-update delete -r 123 -s 234 --json
   {
       "errors": [
           "Something terrible happened and hopefully this explains why."
       ],
       "status": "failed"
   }


.. rbt-subcommand-options::
