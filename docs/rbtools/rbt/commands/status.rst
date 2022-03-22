.. rbt-command:: rbtools.commands.status.Status

======
status
======

:command:`rbt status` will output a list of your pending review requests
associated with the working directories repository. Review requests which
currently have a draft will be identified by an asterisk (``*``).

Optionally pending review requests from all repositories can be displayed
by providing the :option:`--all` option.


.. rbt-command-usage::


.. _rbt-status-json:

JSON Output
===========

.. versionadded:: 3.0

When running with :option:`--json`, the status information will be outputted
as JSON. This can be used by programs that wrap RBTools in order to automate
fetching the status of your changes and providing their own representations.


Successful Payloads
-------------------

When fetching and displaying status is successful, the results are in the form
of:

.. code-block:: javascript

   {
       "status": "success",

       // A list of review requests that are open.
       "review_requests": [
           {
               // The reason a change is not yet approved.
               "approval_failure": "<string>",

               // Whether a change is approved.
               "approved": <bool>,

               // The local branch where the change resides, if known.
               "branch": "<string>",

               // The review request description.
               "description": "<string>",

               // Whether the review request currently has a draft.
               "has_draft": <bool>,

               // The number of open issues on the review request.
               "open_issue_count": <int>,

               // The ID of the review request.
               "review_request_id": <int>,

               // The URL of the review request.
               "review_request_url": "<string>",

               // The number of Ship Its on the review request.
               "shipit_count": <int>,

               // A human-readable string showing the current status.
               "status": "<string>",

               // The summary of the review request.
               "summary": "<string>",
           },
           ...
       ]
   }

The ``approved`` and ``approval_failure`` will reflect the Review Board
server's approval logic, which can be customized using
:ref:`review-request-approval-hook`.

Here's an example of the payload:

.. code-block:: console

   $ rbt status --json
   {
       "review_requests": [
           {
               "approval_failure": "The review request has not been marked \"Ship It!\"",
               "approved": false,
               "branch": "my-feature1",
               "description": "Description of the change...",
               "has_draft": true,
               "open_issue_count": 0,
               "review_request_id": 123,
               "review_request_url": "https://example.com/r/123/",
               "shipit_count": 0,
               "status": "Pending",
               "summary": "Summary of the change...",
           },
           {
               "approval_failure": null,
               "approved": true,
               "branch": "my-feature2",
               "description": "Description of the change...",
               "has_draft": false,
               "open_issue_count": 0,
               "review_request_id": 124,
               "review_request_url": "https://example.com/r/124/",
               "shipit_count": 1,
               "status": "Ship It! (1)",
               "summary": "Summary of the change...
           }
       ]
   }


Error Payloads
--------------

When there's an unexpected error fetching status, the results will be in the
form of:

.. code-block:: javascript

   {
       "status": "failed",

       // A list of errors from the operation.
       "errors": [
           "<string>",
           ...
       ]
   }

For example:

.. code-block:: console

   $ rbt status --json
   {
       "errors": [
           "An unknown error occurred."
       ],
       "status": "failed"
   }


.. rbt-command-options::
