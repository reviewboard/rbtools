.. rbt-command:: rbtools.commands.close.Close

=====
close
=====

:command:`rbt close` will close the review request matching
``review-request-id`` as submitted. Optionally a review request may be
discarded by providing the value ``discarded`` to the :option:`--close-type`
option.


.. rbt-command-usage::


.. _rbt-close-json:

JSON Output
===========

.. versionadded:: 3.0

When running with :option:`--json`, the result of the close operation will be
outputted as JSON. This can be used by programs that wrap RBTools in order to
automate closing review requests.


Successful Payloads
-------------------

When closing is successful, the results are in the form of:

.. code-block:: javascript

   {
       "status": "success",

       // The resulting close type ("submitted" or "discarded").
       "close_type": "<string>",

       // The provided close description.
       "description": "<string>",

       // The ID of the review request.
       "review_request_id": <int>,

       // The URL of the review request.
       "review_request_url": "<string>"
   }

For example:

.. code-block:: console

   $ rbt close --json --description "Committed to release-6.x" 123
   {
       "close_type": "submitted",
       "description": "Committed to release-6.x",
       "review_request_id": 123,
       "review_request_url": "https://example.com/r/123/"
   }


Error Payloads
--------------

When there's an error closing a review request (for instance, if it's already
closed), the results will be in the form of:

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

   $ rbt close --json 123

   {
       "errors": [
           "Review request #123 is already submitted."
       ],
       "status": "failed"
   }


.. rbt-command-options::
