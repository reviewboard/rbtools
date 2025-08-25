.. _python-api-overview:

=================================
Overview of the Python API Client
=================================

Introduction
============

The RBTools Python API allows you to interact with Review Board's Web API
purely through Python code, without having to worry about the details of REST.

All API usage is accessed by first creating a
:py:class:`~rbtools.api.client.RBClient`, and then using that to get the
:py:class:`~rbtools.api.resource.root.RootResource`:

.. code-block:: python

   from rbtools.api.client import RBClient

   client = RBClient('http://localhost:8080/',
                     api_token='rbp_******')
   root = client.get_root()


The :py:class:`~rbtools.api.client.RBClient` constructor takes the URL of the
Review Board server, and also accepts any parameters
that can be passed to the :py:meth:`underlying transport
<rbtools.api.transport.sync.SyncTransport.__init__>`. At a minimum, you'll
probably want to specify either an API token, or a username and password.

The :py:class:`~rbtools.api.resource.root.RootResource` will
then be the object you use to start all other requests to the API.


Authentication
==============

The :py:class:`~rbtools.api.client.RBClient` constructor takes the URL of the
Review Board server, as well as a number of parameters that are given to the
underlying transport, including authentication-related parameters such as
``api_token``, or ``username`` and ``password``.

For details on these parameters, see
:py:meth:`SyncTransport.__init__() <rbtools.api.transport.sync.SyncTransport.__init__>`.

The exact method of authentication will depend on the way you intend to use the
API. If you're writing a script that is used for automation, you probably want
to use an API token:

.. code-block:: python

   client = RBClient('http://localhost:8080/',
                     api_token='rbp_******')


For one-off scripts or interactive usage, a username and password is often
easiest:

.. code-block:: python

   client = RBClient('http://localhost:8080/',
                     username='myuser',
                     password='******')

If you're writing an interactive command, you have a few other options.
:py:func:`~rbtools.utils.users.get_authenticated_session` is a helper which can
be used to ask the user to log in if necessary (assuming they don't already
have an authenticated session). If you are implementing a new ``rbt`` command,
set ``needs_api = True`` in your
:py:class:`~rbtools.commands.base.command.BaseCommand` subclass and
authentication will be handled for you.


Resources
=========

All API endpoints in Review Board are reflected in the Python API as
:py:class:`~rbtools.api.resource.base.Resource` objects. Most of these will be
either an :py:class:`~rbtools.api.resource.base.ItemResource` or a
:py:class:`~rbtools.api.resource.base.ListResource`.

Item resources are for interacting with a single item such as a review request,
user, or comment. The exact methods supported by each depends on the specific
resource, but in general most of these will support
:py:meth:`~rbtools.api.resource.base.ItemResource.update` and
:py:meth:`~rbtools.api.resource.base.ItemResource.delete`.

List resources are for interacting with lists of items. These represent both
loaded results from a query (potentially paginated), but are also used to
create new items. The exact methods supported by each depends on the specific
resource, but in general most of these will support
:py:meth:`~rbtools.api.resource.base.ListResource.create`,
:py:meth:`~rbtools.api.resource.base.ListResource.get_item`,
:py:meth:`~rbtools.api.resource.base.ListResource.get_next`, and
:py:meth:`~rbtools.api.resource.base.ListResource.get_prev`.


Accessing Resource Data
=======================

Item resources define a
:py:meth:`~rbtools.api.resource.base.ItemResource.__getattr__` method, allowing
you to access the fields contained in the API payload like regular Python
attributes.

The following payload from the :ref:`webapi2.0-server-info-resource`
will be used as an example.

.. code-block:: javascript

   {
     "info": {
       "capabilities": {
         "diffs": {
           "moved_files": true
         }
       },
       "product": {
         "is_release": true,
         "name": "Review Board",
         "package_version": "7.0.2",
         "version": "7.0.2"
       },
       "site": {
         "administrators": [
           {
             "email": "admin@example.com",
             "name": "Example Admin"
           }
         ],
         "time_zone": "UTC",
         "url": "http://example.com/"
       }
     },
     "stat": "ok"
   }

To demonstrate how the data from this payload would be accessed, the following
is a short example:

.. code-block:: python

   # Retrieve the info resource using the root resources
   # info link.
   info = root.get_info()

   # Print the product version ("7.0.2").
   print(info.product.version)

   # Print the only administrator's name ("Example Admin")
   print(info.site.administrators[0].name)

.. note::

   While using attributes is the preferred way of accessing fields on a
   resource (both for code readability and for type hinting), you can also
   access the resource with dictionary-like syntax using the field names as the
   keys. The following would have also worked in the previous example:

   .. code-block:: python

      info['product']['version']


Iterating Over Lists
====================

When fetching a list resource, the results will be paginated. By default, each
page will include no more than 25 items. Iterating over the
:py:class:`~rbtools.api.resource.base.ListResource` will iterate only over the
items in the currently-fetched page. Additional pages can be fetched using
:py:meth:`~rbtools.api.resource.base.ListResource.get_next`.

.. code-block:: python

    page = api_root.get_review_requests()

    while 1:
        for review_request in page:
            ...

        try:
            page = page.get_next()
        except StopIteration:
            break


List resources also have a helper
:py:attr:`~rbtools.api.resource.base.ListResource.all_items` property to make
this easier when you want to iterate over all items across all pages.

.. code-block:: python

    review_requests = api_root.get_review_requests()

    for review_request in review_requests.all_items:
        ...

.. note::

   Iterating over all items in a list resource may involve many HTTP requests,
   especially when working with large servers with a lot of data. You may want
   to use the :py:class:`max_results
   <rbtools.api.resource.base.BaseGetListParams>` parameter when fetching the
   list in order to fetch more than 25 items at a time, as well as :ref:`limit
   what data is fetched <python-api-limiting-data>`.


Links Between Resources
=======================

Resources are linked together using `hyperlinks`_ in the payload.

The RBTools API uses methods of the form ``get_<link>()`` in order to follow
these links.

For example, the following links payload will result in a resource
with ``get_self``, ``create``, and ``get_some_sub_resource`` methods.

.. code-block:: javascript

    {
      "links": {
        "self": {
          "href": "/path/to/whatever",
          "method": "GET"
        },
        "create": {
          "href": "/path/to/whatever",
          "method": "POST"
        },
        "some_sub_resource": {
          "href": "/path/to/whatever/some-sub-resource",
          "method": "GET"
        },
        "user": {
          "href": "/path/to/joe",
          "method": GET,
          "title": "joe"
        }
      }
    }

Calling any of the link methods will cause a request to the Review
Board server and a resource constructed from the response to be
returned. For example, assuming ``resource`` is a resource constructed
with the previously shown links payload, retrieving ``some_sub_resource``
could be accomplished with the following code::

   some_sub_resource = resource.get_some_sub_resource()

To specify fields for links causing ``'POST'`` or ``'PUT'`` requests,
the values of the field should be passed using a keyword argument matching
the field's name. The following example uses the ``update`` link
of a :ref:`webapi2.0-review-request-draft-resource` to publish the
draft::

   # Retrieve the review draft for review request 1
   # using the root resources uri template.
   draft = root.get_draft(review_request_id=1)

   # Publish the draft.
   draft = draft.update(public=True)

The links are also directly accessible via a ``links`` property on the
resource. This allows pulling out the URLs or other data about the links::

   username = resource.links.user.title


.. _hyperlinks: http://www.reviewboard.org/docs/manual/dev/webapi/2.0/overview/#hyperlinks


Request Parameters
==================

Some resources in the Web API allow query arguments to be passed with
the request to alter what should be returned as the response. The
supported request parameters are unique to each resource, and are
listed on each resource's documentation page.

Query arguments are added to a request by specifying keyword arguments
when calling the method. A number of the request parameters use the
'-' character, which should be replaced by an underscore when
specified as a keyword argument (e.g. ``max-results`` would become
``max_results``).

The following is an example which uses the ``counts-only`` and
``status`` request parameters on the
:ref:`webapi2.0-review-request-list-resource`, to get a count of pending
review requests::

   # Make a request for the list of pending review requests.
   # Specify counts-only so only the number of results is returned.
   requests = root.get_review_requests(counts_only=True, status="pending")

   # Print the number of pending review requests
   print(requests.count)


.. _python-api-expanding-resources:

Expanding Resources
===================

Requests to the API support an ``expand`` parameter which can be used to follow
links within the returned payload.

.. code-block:: python

    # This performs two HTTP requests.
    review_request = root.get_review_request(review_request_id=123)
    latest_diff = review_request.get_latest_diff()

    print(latest_diff.revision)

    # This requires only one request to the server.
    review_request = root.get_review_request(
        review_request_id=123,
        expand='latest_diff')

    print(review_request.latest_diff.revision)

.. note::

    The data included in an expanded payload will allow you to access the
    requested fields, but does not create resource-specific subclasses. For
    example, calling :py:meth:`ReviewRequestItemResource.get_latest_diff
    <rbtools.api.resource.review_request.ReviewRequestItemResource.get_latest_diff>`
    will normally return a
    :py:class:`~rbtools.api.resource.diff.DiffItemResource`, but if
    ``latest_diff`` is expanded when fetching the review request, the resulting
    ``latest_diff`` attribute will be a generic
    :py:class:`rbtools.api.resource.base.ItemResource` instance.


.. _python-api-limiting-data:

Limiting Data
=============

When requesting a resource (via a ``get_<name>()`` method), you can choose to
limit what data is returned. This can be particularly effective when fetching
list resources.

The :py:class:`parameters <rbtools.api.resource.base.BaseGetParams>` accepted
by get methods include ``only_links`` and ``only_fields``. These can both be
set to a comma-separated list of which items to include in the resulting
payload.

.. code-block:: python

    review_requests = root.get_review_requests(
        only_fields='summary,description',
        only_links='diffs')

To know which fields and links are present for any given resource, see the
associated documentation in the Review Board :ref:`rb:webapiguide`.


.. _python-api-error-handling:

Error Handling
==============

The RBTools Python API uses three main exception types for error handling:

:py:class:`~rbtools.api.errors.APIError`:
    Base exception for API communication errors containing error codes and messages.

:py:class:`~rbtools.api.errors.AuthorizationError`:
    Raised when authentication fails (HTTP 401).

:py:class:`~rbtools.api.errors.BadRequestError`:
    Raised when the request was invalid (HTTP 400).

:py:class:`~rbtools.api.errors.ServerInterfaceError`:
    Raised for network or server communication issues.

Here's an example of API code which handles all potential error cases:

.. code-block:: python

    from rbtools.api.errors import APIError, AuthorizationError, ServerInterfaceError

    try:
        client = RBClient('http://localhost:8080/', api_token='rbp_******')
        root = client.get_root()
        review_request = root.get_review_request(review_request_id=123)
    except ServerInterfaceError as e:
        print(f'Could not connect to server: {e}')
    except AuthorizationError:
        print('Authentication failed. Check your credentials.')
    except BadRequestError as e:
        print(f'Bad request: {e}')
    except APIError as e:
        if e.error_code == 100:  # Does Not Exist
            print('Review request not found')
        else:
            print(f'API error: {e}')
