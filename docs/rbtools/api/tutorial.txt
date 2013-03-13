.. _python-api-tutorial:

========
Tutorial
========

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

   repos = root.get_repositories()
   if repos.num_items < 1:
       raise Exception('No valid repositories.')

   repository = repos[0].id

Having a valid repository ID, we may now create a review request::

   review_request = root.get_review_requests().create(repository=repository)

Now that we have created a review request, we may upload a diff.


Uploading the Diff
==================

Uploading a diff is accomplished by performing a POST request on the
review request's :ref:`webapi2.0-diff-list-resource`. This can be
accomplished using the resource's :py:meth:`create` method, but the
:ref:`webapi2.0-diff-list-resource` has
:ref:`python-api-resource-specific-functionality`
to make this task easier. The :py:meth:`upload_diff`
method can be used to automatically format the request properly given the
body of the diff. For more information see the
:ref:`diff-list-resource-specific-functionality`.

We will upload a simple diff which we read from a file using the
following code::

   f = open("path/to/diff.txt", mode="r")
   diff_contents = f.read()
   f.close()

   review_request.get_diffs().upload_diff(diff_contents)


Adding a File Attachment
========================

Uploading file attachments is similar to the process of uploading a
diff. First the review request's :ref:`webapi2.0-file-attachment-list-resource`
must be retrieved, and the resource's :py:meth:`upload_attachment` method is
called. For more information about :py:meth:`upload_attachment`, please see
:ref:`file-attachment-list-resource-specific-functionality`.

When uploading the attachment, the second argument should contain the
body of the file to be uploaded, in string format. We will upload
an attachment read from a file to demonstrate the functionality::

   f = open("path/to/attachment", mode="r")
   attachment_contents = f.read()
   f.close()

   review_request.get_file_attachments().upload_attachment(
       "attachment",
       attachment_contents,
       caption="An attachment.")


Modifying the Draft
===================

In order to update and publish this review request, we must use the
associated :ref:`webapi2.0-review-request-draft-resource`. We can
retrieve the draft using the link from our request::

   draft = review_request.get_draft()
   draft = draft.update(
       summary='API tutorial request',
       description='This request was created in the API tutorial.')

After retrieving the draft, a summary and description were added by
calling :py:meth:`update`. The call to update returns the resulting updated
draft, which we use to overwrite our previous draft.

In order to publish a review request, at least one review group or
reviewer must be added to the request. To meet this requirement, we
will add ourselves as the reviewer. To accomplish this we will use the
:ref:`webapi2.0-session-resource` to retrieve the user we are logged
in as::

   user = root.get_session().get_user()
   draft = draft.update(target_people=user.username)


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
       filediff_id=1,
       first_line=1,
       num_lines=1,
       text='This is a diff comment!')

Now that we've created a review with a single diff comment, let's provide
text at the top of the review, and publish it::

   review.update(body_top='Awesome patch!', public=True)

By this point you should have a feel for how to use the API client and
make several different requests to the Review Board server. For more
general information see the :ref:`python-api-overview`.
