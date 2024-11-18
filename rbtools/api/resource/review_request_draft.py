"""Resource definitions for review request drafts.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    TextType,
    api_stub,
    resource_mimetype,
)
from rbtools.api.resource.base_review_request import \
    BaseReviewRequestItemResource

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.base import (
        BaseGetListParams,
        BaseGetParams,
    )
    from rbtools.api.resource.diff import DiffListResource
    from rbtools.api.resource.draft_file_attachment import \
        DraftFileAttachmentListResource
    from rbtools.api.resource.draft_screenshot import \
        DraftScreenshotListResource
    from rbtools.api.resource.review_request import ReviewRequestItemResource


@resource_mimetype('application/vnd.reviewboard.org.review-request-draft')
class ReviewRequestDraftResource(BaseReviewRequestItemResource):
    """Resource for review request drafts.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: A description of what changes are being made in this update.
    changedescription: str

    #: The current or forced text type for the ``changedescription`` field.
    changedescription_text_type: TextType

    #: The numeric ID of the draft.
    id: int

    #: Whether or not the draft is public.
    #:
    #: This will always be false up until the draft is published. At that
    #: point, the draft is deleted.
    public: bool

    @api_stub
    def get_draft_diffs(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> DiffListResource:
        """Get the draft diffs list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DiffListResource:
            The draft diff list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_draft_file_attachments(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> DraftFileAttachmentListResource:
        """Get the draft file attachments list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DraftFileAttachmentListResource:
            The draft file attachment list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_draft_screenshots(
        self,
        **kwargs: Unpack[BaseGetListParams],
    ) -> DraftScreenshotListResource:
        """Get the draft screenshots list resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.DraftScreenshotListResource:
            The draft screenshot list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_review_request(
        self,
        **kwargs: Unpack[BaseGetParams],
    ) -> ReviewRequestItemResource:
        """Get the review request for this draft.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ReviewRequestItemResource:
            The review request item resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError
