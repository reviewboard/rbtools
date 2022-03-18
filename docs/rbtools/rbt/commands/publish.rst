.. rbt-command:: rbtools.commands.publish.Publish

=======
publish
=======

:command:`rbt publish` will publish the draft associated with the review
request matching ``review-request-id``.


.. rbt-command-usage::


.. _rbt-publish-json:

JSON Output
===========

.. versionadded:: 3.0

When running with :option:`--json`, the results of publishing a review request
will be outputted as JSON. This can be used by programs that wrap RBTools in
order to automate publishing changes.


Successful Payloads
-------------------

When publishing is successful, the results are in the form of:

.. code-block:: javascript

   {
       "status": "success",

       // The ID of the review request.
       "review_request_id": <int>,

       // The URL of the review request.
       "review_request_url": "<string>"
   }

For example:

.. code-block:: console

   $ rbt publish --json 123
   {
       "review_request_id": 123,
       "review_request_url": "https://example.com/r/123/",
       "status": "success"
   }


Error Payloads
--------------

When there's an error publishing a change, the results will be in the form of:

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

   $ rbt publish --json 123
   {
       "errors"; [
           "Error publishing review request (it may already be published)"
       ],
       "status": "success"
   }


.. rbt-command-options::
