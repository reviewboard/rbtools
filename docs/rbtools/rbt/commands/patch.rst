.. rbt-command:: rbtools.commands.patch.PatchCommand

=====
patch
=====

:command:`rbt patch` will download the latest diff from the review request
matching ``review-request-id`` and apply it to the local working directory. The
:option:`--diff-revision` option may be used to specify a specific revision
of the diff to use.


.. rbt-command-usage::


.. _rbt-patch-json:

JSON Output
===========

.. versionadded:: 3.0

When running with :option:`--json`, the results of patching a change will be
outputted as JSON. This can be used by programs that wrap RBTools in order to
automate patching source trees from review requests.


Successful Payloads
-------------------

When patching is successful, the results are in the form of:

.. code-block:: javascript

   {
       "status": "success",

       // The revision of the diff that was applied.
       "diff_revision": <int>,

       // The total number of patches that were applied.
       "total_patches": <int>,

       // The ID of the review request.
       "review_request_id": <int>,

       // The URL of the review request.
       "review_request_url": "<string>",

       // Any warnings found during patching that could affect the tree.
       "warnings": [
           "<string>",
           ...
       ]
   }

For example:

.. code-block:: console

   $ rbt patch --json 123
   {
       "diff_revision": 2,
       "review_request_id": 123,
       "review_request_url": "https://example.com/r/123/",
       "status": "success",
       "total_patches": 1,
   }

.. code-block:: console
   :caption: If the working directory is not clean:

   $ rbt patch --json 123
   {
       "diff_revision": 2,
       "review_request_id": 123,
       "review_request_url": "https://example.com/r/123/",
       "status": "success",
       "total_patches": 1,
       "warnings": [
           "Working directory is not clean."
       ]
   }


Error Payloads
--------------

When there's an error applying a patch, the results will be in the form of:

.. code-block:: javascript

   {
       "status": "failed",

       /*
        * A list of filenames that conflicted when applying the patch.
        *
        * This key is only present if conflicts were found.
        */
       "conflicting_files": [
           "<string>",
           ...
       ],

       // The revision of the diff that RBTools was trying to apply.
       "diff_revision": <int>,

       // A list of errors from the operation.
       "errors": [
           "<string>",
           ...
       ],

       // The number of the patch in the series that failed to patch.
       "failed_patch_num": <int>,

       // The total number of patches that RBTools were trying to apply.
       "total_patches": <int>,

       // The ID of the review request.
       "review_request_id": <int>,

       // The URL of the review request.
       "review_request_url": "<string>",

       // Any warnings found that could have affected the tree.
       "warnings": [
           "<string>",
           ...
       ]
   }

Most errors will have identifying information, but not all. Consumers should
not assume the presence of any fields except for ``errors`` and ``status``.

Examples:

.. code-block:: console
   :caption: If there's an invalid patch:

   $ rbt patch --json 123
   {
       "diff_revision": 2,
       "errors": [
           "Unable to apply the patch. The patch may be invalid, or there may be conflicts that could not be resolved.",
       ],
       "failed_patch_num": 1,
       "review_request_id": 123,
       "review_request_url": "https://example.com/r/123/",
       "status": "failed",
       "total_patches": 1
   }

.. code-block:: console
   :caption: If there are conflicts:

   $ rbt patch --json 123
   {
       "conflicting_files": [
           "README.txt",
           "src/main.c"
       ],
       "diff_revision": 2,
       "errors": [
           "The patch was partially applied, but there were conflicts.",
           "Could not revert patch 1 of 1",
       ],
       "failed_patch_num": 1,
       "review_request_id": 123,
       "review_request_url": "https://example.com/r/123/",
       "status": "failed",
       "total_patches": 1
   }


.. rbt-command-options::
