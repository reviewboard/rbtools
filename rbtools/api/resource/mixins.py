"""Mixins for API resources.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import request_method

if TYPE_CHECKING:
    from rbtools.api.request import HttpRequest, QueryArgs
    from rbtools.api.resource.base import Resource

    MixinParent = Resource
else:
    MixinParent = object


class AttachmentUploadMixin(MixinParent):
    """A mixin for resources that implement an upload_attachment method.

    Version Added:
        6.0
    """

    @request_method
    def upload_attachment(
        self,
        filename: str,
        content: bytes,
        caption: (str | None) = None,
        attachment_history: (str | None) = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Upload a new attachment.

        Args:
            filename (str):
                The name of the file.

            content (bytes):
                The content of the file to upload.

            caption (str, optional):
                The caption to set on the file attachment.

            attachment_history (str, optional):
                The ID of the FileAttachmentHistory to add this attachment to.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            FileAttachmentItemResource:
            The newly-created file attachment.
        """
        request = self._make_httprequest(url=self._url, method='POST',
                                         query_args=kwargs)
        request.add_file('path', filename, content)

        if caption:
            request.add_field('caption', caption)

        if attachment_history:
            request.add_field('attachment_history', attachment_history)

        return request


class DiffUploaderMixin(MixinParent):
    """A mixin for uploading diffs to a resource."""

    def prepare_upload_diff_request(
        self,
        diff: bytes,
        parent_diff: (bytes | None) = None,
        base_dir: (str | None) = None,
        base_commit_id: (str | None) = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Create a request that can be used to upload a diff.

        The diff and parent_diff arguments should be strings containing the
        diff output.

        Args:
            diff (bytes):
                The diff content.

            parent_diff (bytes, optional):
                The parent diff content, if present.

            base_dir (str, optional):
                The base directory for the diff, if present.

            base_commit_id (str, optional):
                The ID of the commit that the diff is against, if present.

            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.request.HttpRequest:
            The API request.
        """
        request = self._make_httprequest(url=self._url, method='POST',
                                         query_args=kwargs)
        request.add_file('path', 'diff', diff)

        if parent_diff:
            request.add_file('parent_diff_path', 'parent_diff', parent_diff)

        if base_dir:
            request.add_field('basedir', base_dir)

        if base_commit_id:
            request.add_field('base_commit_id', base_commit_id)

        return request


class GetPatchMixin(MixinParent):
    """Mixin for resources that implement a get_patch method.

    Version Added:
        4.2
    """

    @request_method
    def get_patch(
        self,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Retrieve the diff file contents.

        Args:
            **kwargs (dict of rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ItemResource:
            A resource containing the patch. The patch data will be in the
            ``data`` attribute.
        """
        return self._make_httprequest(url=self._url,
                                      query_args=kwargs,
                                      headers={'Accept': 'text/x-patch'})


class ScreenshotUploadMixin(MixinParent):
    """Mixin for resources that implement an upload_screenshot method.

    Version Added:
        6.0
    """

    @request_method
    def upload_screenshot(
        self,
        filename: str,
        content: bytes,
        caption: (str | None) = None,
        **kwargs: QueryArgs,
    ) -> HttpRequest:
        """Upload a new screenshot.

        The content argument should contain the body of the screenshot
        to be uploaded, in string format.

        Args:
            filename (str):
                The filename of the screenshot.

            content (bytes):
                The image file content.

            caption (str, optional):
                The caption to add to the screenshot.

            **kwargs (rbtools.api.request.QueryArgs):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotItemResource or
            rbtools.api.resource.DraftScreenshotItemResource:
            The newly-created screenshot.
        """
        request = self._make_httprequest(url=self._url, method='POST',
                                         query_args=kwargs)
        request.add_file('path', filename, content)

        if caption:
            request.add_field('caption', caption)

        return request
