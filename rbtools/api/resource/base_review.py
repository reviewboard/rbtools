"""Base class for review resources.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import ItemResource, TextType, api_stub

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import BaseGetListParams
    from rbtools.api.resource.base_user import UserGetParams
    from rbtools.api.resource.diff_comment import (
        DiffCommentGetListParams,
        DiffCommentListResource,
    )
    from rbtools.api.resource.file_attachment_comment import \
        FileAttachmentCommentListResource
    from rbtools.api.resource.general_comment import GeneralCommentListResource
    from rbtools.api.resource.screenshot_comment import \
        ScreenshotCommentListResource
    from rbtools.api.resource.user import UserItemResource


class BaseReviewItemResource(ItemResource):
    """Base class for review item resources.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The review content shown below the comments.
    body_bottom: str

    #: The text type used for the ``body_bottom`` field.
    body_bottom_text_type: TextType

    #: The review content shown above the comments.
    body_top: str

    #: The text type used for the ``body_top`` field.
    body_top_text_type: TextType

    #: The text type, if any, to force for returned text fields.
    #:
    #: The contents will be converted to the requested type in the payload, but
    #: will not be saved as that type.
    force_text_type: TextType

    #: Whether or not the review is public.
    #:
    #: Saving with this set to ``True`` will publish the review.
    public: bool

    #: Whether to archive the review request after the review is published.
    publish_and_archive: bool

    #: Whether to send e-mail only to the owner of the review request.
    publish_to_owner_only: bool

    #: Whether or not to mark the review as "Ship It!"
    ship_it: bool

    #: The mode for text fields.
    #:
    #: This is deprecated in favor of the ``body_bottom_text_type`` and
    #: ``body_top_text_type`` fields.
    text_type: TextType

    @api_stub
    def get_diff_comments(
        self,
        **kwargs: Unpack[DiffCommentGetListParams],
    ) -> DiffCommentListResource:
        """Get the diff comments list.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffCommentListResource:
            The diff comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_file_attachment_comments(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> FileAttachmentCommentListResource:
        """Get the file attachment comments list.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileAttachmentCommentListResource:
            The file attachment comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_general_comments(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> GeneralCommentListResource:
        """Get the general comments list.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.GeneralCommentListResource:
            The general comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_screenshot_comments(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> ScreenshotCommentListResource:
        """Get the screenshot comments list.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ScreenshotCommentListResource:
            The screenshot comment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_user(
        self,
        **kwargs: Unpack[UserGetParams],
    ) -> UserItemResource:
        """Get the user who owns the review.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.UserItemResource:
            The user item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError
