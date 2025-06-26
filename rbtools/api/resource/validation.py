"""Resource definitions for the validation list.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    ItemResource,
    api_stub,
    resource_mimetype,
)

if TYPE_CHECKING:
    from rbtools.api.request import QueryArgs

    from .validate_diff import ValidateDiffResource
    from .validate_diff_commit import ValidateDiffCommitResource


@resource_mimetype('application/vnd.reviewboard.org.validation')
class ValidationResource(ItemResource):
    """The validation list resource.

    This corresponds to Review Board's :ref:`rb:webapi2.0-validation-resource`.

    Version Added:
        6.0
    """

    @api_stub
    def get_commit_validation(
        self,
        **kwargs: QueryArgs,
    ) -> ValidateDiffCommitResource:
        """Get the commit validation resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ValidateDiffCommitResource:
            The diff commit validation resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError

    @api_stub
    def get_diff_validation(
        self,
        **kwargs: QueryArgs,
    ) -> ValidateDiffResource:
        """Get the diff validation resource.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.ValidateDiffResource:
            The diff validation resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        raise NotImplementedError
