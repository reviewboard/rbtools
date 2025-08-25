.. _python-api-tutorial:

================
Common Use Cases
================

This tutorial will walk you through using the API to accomplish a
number of common Review Board tasks. We will start by creating a new
review request, including uploading a diff and a file attachment.
After publishing the request, we will create a review, and publish it
as well.

To begin, we instantiate the API client::

   from rbtools.api.client import RBClient


   client = RBClient('http://localhost:8080/',
                     username='username',
                     password='password')
   root = client.get_root()


Creating a Review Request
=========================

You may only upload a diff to a review request that had a repository
specified when it was created. For our repository we will select the
first in the list of repositories, and retrieve its ``id``::

   try:
       repository = root.get_repositories(name='Main repo')[0]
   except KeyError:
       raise Exception('Could not find main repository')

Now, we can create a review request::

   review_request = root.get_review_requests().create(
        repository=repository.id)

Now that we have created a review request, we may upload a diff.


Adding a Diff
=============

Uploading a diff is accomplished by performing a POST request on the
review request's :ref:`webapi2.0-diff-list-resource`. Theoretically this could
be accomplished using the resource's
:py:meth:`~rbtools.api.resource.base.ListResource.create` method, but the
:py:class:`~rbtools.api.resource.diff.DiffListResource` has a helper to make
this task easier. The
:py:meth:`~rbtools.api.resource.diff.DiffListResource.upload_diff` method can
be used to handle the complexities of formatting the request.

We will upload a simple diff which we read from a file using the
following code::

   with open('path/to/diff.txt', mode='rb') as f:
       diff_contents = f.read()

   review_request.get_diffs().upload_diff(diff_contents)


Adding a File Attachment
========================

Uploading file attachments is similar to the process of uploading a diff. First
the review request's :ref:`webapi2.0-file-attachment-list-resource` must be
retrieved, and the resource's
:py:meth:`~rbtools.api.resource.file_attachment.FileAttachmentListResource.upload_attachment`
method is called.

When uploading the attachment, the ``content`` argument should contain the body
of the file to be uploaded, in string format. We will upload an attachment read
from a file to demonstrate the functionality::

   with open('path/to/attachment.png', mode='rb') as f:
       attachment_contents = f.read()

   review_request.get_file_attachments().upload_attachment(
       filename='attachment',
       content=attachment_contents,
       caption="An attachment.")


Modifying the Draft
===================

In order to update and publish this review request, we must use the
associated :ref:`webapi2.0-review-request-draft-resource`. We can
retrieve the draft using the link from our request::

   draft = review_request.get_draft()
   draft = draft.update(
       summary='API tutorial request',
       description='This request was created using the RBTools Python API.')

After retrieving the draft, a summary and description were added by
calling :py:meth:`update`. The call to update returns the resulting updated
draft, which we use to overwrite our previous draft.

In order to publish a review request, at least one review group or
reviewer must be added to the request. To meet this requirement, we
can add a couple reviewers using their usernames::

   draft = draft.update(target_people='user1,user2')

To publish this review request, we update the draft and set
``public`` to ``True``::

   draft.update(public=True)


Creating a Review
=================

Now that we've created and published a review request, we can create a
review. We will start by retrieving the :ref:`webapi2.0-review-list-resource`
and creating a new review::

   review = review_request.get_reviews().create()

Creating a comment is accomplished by calling :py:meth:`create` on the
:ref:`webapi2.0-review-diff-comment-list-resource`. We will create
a comment on the first line of a file in the review requests diff::

   filediff_id = review.get_diffs()[0].get_files()[0].id
   review.get_diff_comments().create(
       filediff_id=filediff_id,
       first_line=1,
       num_lines=1,
       text='This is a diff comment!')

Now that we've created a review with a single diff comment, let's provide
text at the top of the review, and publish it::

   review.update(body_top='Awesome patch!', public=True)

By this point you should have a feel for how to use the API client and
make several different requests to the Review Board server. For more
general information see the :ref:`python-api-overview`.
