.. _rbt-api-get:
.. program:: rbt api-get

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
appears after ``--`` on the command line and takes the form of
``--<query-arg>=<value>``. For example::

   $ # Make a request to http://example.com/api/review-requests/?counts-only=1
   $ rbt api-get /review-requests/ -- --counts-only=1

Usage::

   $ rbt api-get [options] <path> [-- [--<query-arg>=<value> ...]]


Default Options
===============

A number of options to :command:`rbt api-get` can be set by default
in :file:`.reviewboardrc`. These can go either in the repository's
or the user's :file:`.reviewboardrc`.

The options include:

* ``DEBUG`` (:option:`-d`)
* ``API_GET_PRETTY_PRINT`` (:option:`--pretty`)

Options
=======

.. cmdoption:: -d, --debug

   Display debug output.

   The default can be set in ``DEBUG`` in :file:`.reviewboardrc`.

.. cmdoption:: --pretty

   Pretty print output.

   The default can be set in ``API_GET_PRETTY_PRINT`` in :file:`.reviewboardrc`.
