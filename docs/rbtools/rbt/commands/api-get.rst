.. rbt-command:: rbtools.commands.api_get.APIGet

=======
api-get
=======

:command:`rbt api-get` will request the API resource found at the provided
``<path>`` and display it as JSON.

Paths will be appended to the root of the API to generate a URL. For example,
the ``/review-requests/123/`` path would result in a request to
``http://example.com/api/review-requests/123/``.

The path may also be replaced by a full URL. If :command:`rbt api-get`
detects the path begins with ``http://`` or ``https://``, it will treat the
path itself as the request URL.

Query arguments may also be specified for the request. Each query argument
takes the form of ``--<query-arg>=<value>``. For example::

   $ # Make a request to http://example.com/api/review-requests/?counts-only=1
   $ rbt api-get /review-requests/ --counts-only=1


.. rbt-command-usage::
.. rbt-command-options::
