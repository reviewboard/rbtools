.. _python-api-overview:

=================================
Overview of the Python API Client
=================================

Introduction
============

The API client provides convenient access to Review Board Web API
resources, and makes performing REST operations simple. The API is
accessed by instantiating the :py:class:`rbtools.api.client.RBClient`
class. Here is an example of how to instantiate the client, and retrieve
the :ref:`webapi2.0-root-resource` resource::

   from rbtools.api.client import RBClient

   client = RBClient('http://localhost:8080/')
   root = client.get_root()


Links Between Resources
=======================

Resources are linked together using `hyperlinks`_ in the payload.
Accessing the hyperlinks, and retrieving the linked resources is
accomplished using method calls on a resource. A method of the form
``get_<link>`` will be created for each link. The special operation
links ``create``, ``delete``, and ``update`` are exceptions and are
not prefixed with ``get_``.

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


Accessing Resource Data
=======================

Accessing the fields contained in a resource payload is accomplished
using attributes of the resource object. Each field in the payload
under the resource's main key will be accessed through an attribute of
the same name. This also applies to fields contained within another
field.

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
         "package_version": "1.7beta1",
         "version": "1.7 beta 1"
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
is a short example::

   # Retrieve the info resource using the root resources
   # info link.
   info = root.get_info()

   # Print the product version ("1.7 beta 1").
   print(info.product.version)

   # Print the only administrator's name ("Example Admin")
   print(info.site.administrators[0].name)

.. note::
   While using attributes is the preferred way of accessing fields
   on a resource, using the `[]` operator is also supported.
   The following would have also worked in the previous example::

      info['product']['version']


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


Resource Specific Details
=========================

The API provides additional functionality for a number of resources.
Specific information can be found in
:ref:`python-api-resource-specific-functionality`.
