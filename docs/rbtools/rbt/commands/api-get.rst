.. rbt-command:: rbtools.commands.api_get.APIGet

=======
api-get
=======

:command:`rbt api-get` is a convenient way of fetching information from the
Review Board API using HTTP GET. It takes a full URL or a path relative to the
API, along with optional parameters for query arguments, and outputs the API
payload as JSON.

.. rbt-command-usage::


Querying the API
================

Paths will be appended to the root of the API to generate a URL. For example,
if the Review Board server is located at ``https://example.com/``, the path
``/review-requests/123/`` path would result in an HTTP GET request to
``https://example.com/api/review-requests/123/``.

For example:

.. code-block:: console

   $ rbt api-get /review-requests/
   {
       ...
   }

The full URL to an API endpoint can be provided instead. For example:

.. code-block:: console

   $ rbt api-get https://example.com/api/review-requests/
   {
       ...
   }

As a convenience, you query arguments can be provided as command line options.
A query string in the form of ``?<query-arg>=<value>`` can be provided as
``--<query-arg>=<value>``. For example:

.. code-block:: console

   $ rbt api-get /review-requests/ --counts-only=1
   {
       ...
   }


.. rbt-command-options::
