.. rbt-command:: rbtools.commands.attach.Attach

======
attach
======

:command:`rbt attach` is used to upload file attachments to a review request.
The provided ``file`` will be attached to the review request matching
``review-request-id``.


.. rbt-command-usage::


.. _rbt-attach-json:

JSON Output
===========

.. versionadded:: 3.0

When running with :option:`--json`, the results of the attachment will be
outputted as JSON. This can be used by programs that wrap RBTools in order to
automate attaching changes to review requests.


Successful Payloads
-------------------

When attachment is successful, the results are in the form of:

.. code-block:: javascript

   {
       "status": "success",

       // Absolute path to the local attached file.
       "attached_file": "<string>",

       // The ID of the attachment history record.
       "attachment_history_id": <int>,

       // The provided or generated caption.
       "caption": "<string>",

       // The filename recorded for the attachment.
       "filename": "<string>",

       // The ID of the file attachment.
       "id": <int>,

       // The stored mimetype of the attachment.
       "mimetype": "<string>",

       // The ID of the review request.
       "review_request_id": <int>,

       // The URL of the review request.
       "review_request_url": "<string>",

       // The URL of the review UI for the attachment.
       "review_url": "<string>",

       // The ID of the attachment revision.
       "revision": <int>
   }

For example:

.. code-block:: console

   $ rbt attach --json --caption "My Screenshot" 123 ./screenshot.png
   {
       "attached_file": "/home/user/src/project/screenshot.png",
       "attachment_history_id": 132,
       "caption": "My Screenshot",
       "download_url": "https://example.com/media/uploaded/files/2022/03/17/94c05e13-de20-43e4-a0f8-bbb9b403af6f__screenshot.png",
       "filename": "screenshot.png",
       "id": 289,
       "mimetype": "image/png",
       "review_request_id": 123,
       "review_request_url": "https://example.com/r/123/",
       "review_url": "https://example.com/r/123/file/289/",
       "revision": 1,
       "status": "success"
   }


Error Payloads
--------------

When there's an error attaching a file, the results will be in the form of:

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

   $ rbt attach --json 123 ./screenshorts.png
   {
       "errors": [
           "/home/user/src/project/screenshorts.png is not a valid file."
       ],
       "status": "failed"
   }


.. rbt-command-options::
