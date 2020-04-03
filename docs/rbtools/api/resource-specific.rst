.. _python-api-resource-specific-functionality:

===============================
Resource-Specific Functionality
===============================

The API provides extra functionality specific to a number of a resources.


.. _root-list-resource-specific-functionality:

Root List Resource Functionality
================================

The :ref:`webapi2.0-root-resource` provides a set of ``uri-templates`` which
can be used to retrieve a specific resource without traversing the resource
tree. Each uri-template consists of a ``key`` and a ``uri-template``. For
examples, please see the :ref:`webapi2.0-root-resource` page.

The API client allows the templates to be used through method calls on the
root resource. For each ``uri-template``, a method named ``get_<name>`` will
be created. This method will take keyword arguments which will be used
to replace the fields in the ``uri-template``. We will use the following
``uri-template`` as an example.

.. code-block:: javascript

   "files": "http://reviews.example.com/api/review-requests/{review_request_id}/diffs/{diff_revision}/files/"

To use this ``uri-template``, the :py:meth:`get_files` method would be
called. For example, you could retrieve a specific
:ref:`webapi2.0-file-diff-list-resource` using the following code::

   files = root.get_files(review_request_id=1, diff_revision=1)


.. _diff-list-resource-specific-functionality:

Diff List Resource Functionality
================================

The resource object for a :ref:`webapi2.0-diff-list-resource` provides
the following additional methods.

.. py:method:: DiffListResource.upload_diff(diff, parent_diff=None, base_dir=None)

   Upload a diff contained in ``diff`` with the optional ``parent_diff`` and
   optional ``base_dir``.


.. _diff-resource-specific-functionality:

Diff Resource Functionality
===========================

The resource object for a :ref:`webapi2.0-diff-resource` provides
the following additional methods.

.. py:method:: DiffResource.get_patch()

   Retrieve the actual contents of the uploaded diff.


.. _file-diff-list-resource-specific-functionality:

File Diff Resource Functionality
================================

The resource object for a :ref:`webapi2.0-file-diff-resource` provides
the following additional methods.

.. py:method:: FileDiffResource.get_patch()

   Retrieve the actual contents of the uploaded diff for this file.

.. py:method:: FileDiffResource.get_diff_data()

   Retrieves the actual raw diff data for the file. For more information
   about what this contains, see the :ref:`webapi2.0-file-diff-resource`
   documentation.


.. _file-attachment-list-resource-specific-functionality:

File Attachment List Resource Functionality
===========================================

The resource object for a :ref:`webapi2.0-file-attachment-list-resource`
provides the following additional methods.

.. py:method:: FileAttachmentListResource.upload_attachment(filename, content, caption=None, attachment_history=None)

   Uploads a new attachment containing ``content``, named ``filename``, with
   the optional ``caption`` and optional ``attachment_history``.


.. _draft-file-attachment-list-resource-specific-functionality:

Draft File Attachment List Resource Functionality
=================================================

The resource object for a :ref:`webapi2.0-draft-file-attachment-list-resource`
provides the following additional methods.

.. py:method:: DraftFileAttachmentListResource.upload_attachment(filename, content, caption=None, attachment_history=None)

   Uploads a new attachment containing ``content``, named ``filename``, with
   the optional ``caption`` and optional ``attachment_history``.


.. _screenshot-list-resource-specific-functionality:

Screenshot List Resource Functionality
======================================

The resource object for a :ref:`webapi2.0-screenshot-list-resource`
provides the following additional methods.

.. py:method:: ScreenshotListResource.upload_attachment(filename, content, caption=None)

   Uploads a new screenshot contained in ``content``, named ``filename``, with
   the optional ``caption``.


.. _draft-screenshot-list-resource-specific-functionality:

Draft Screenshot List Resource Functionality
============================================

The resource object for a :ref:`webapi2.0-draft-screenshot-list-resource`
provides the following additional methods.

.. py:method:: DraftScreenshotListResource.upload_attachment(filename, content, caption=None)

   Uploads a new screenshot contained in ``content``, named ``filename``, with
   the optional ``caption``.


.. _review-request-resource-specific-functionality:

Review Request Resource Functionality
=====================================

The resource object for a :ref:`webapi2.0-review-request-resource`
provides the following additional methods.

.. py:method:: ReviewRequestResource.get_or_create_draft(**kwargs)

   Retrieve the review request's draft resource. If the draft does not exist
   it will be created and retrieved.
