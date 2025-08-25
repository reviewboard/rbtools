"""Resource definitions for diff commits.

Version Added:
    6.0:
    This was moved from :py:mod:`rbtools.api.resource`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import (
    ListResource,
    api_stub,
    resource_mimetype,
)
from rbtools.api.resource.base_diff_commit import BaseDiffCommitItemResource
from rbtools.api.resource.mixins import GetPatchMixin

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from rbtools.api.resource.file_diff import (
        FileDiffGetListParams,
        FileDiffListResource,
    )


@resource_mimetype('application/vnd.reviewboard.org.commit')
class DiffCommitItemResource(BaseDiffCommitItemResource):
    """Item resource for diff commits.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-diff-commit-resource`.
    """

    @api_stub
    def get_files(
        self,
        **kwargs: Unpack[FileDiffGetListParams],
    ) -> FileDiffListResource:
        """Get the files for the commit.

        Args:
            **kwargs (dict):
                Query arguments to include with the request.

        Returns:
            rbtools.api.resource.FileDiffListResource:
            The file diff list resource.

        Raises:
            rbtools.api.errors.APIError:
                The Review Board API returned an error.

            rbtools.api.errors.ServerInterfaceError:
                An error occurred while communicating with the server.
        """
        ...


@resource_mimetype('application/vnd.reviewboard.org.commits')
class DiffCommitListResource(GetPatchMixin,
                             ListResource[DiffCommitItemResource]):
    """List resource for diff commits.

    This corresponds to Review Board's
    :ref:`rb:webapi2.0-diff-commit-list-resource`.

    Version Added:
        6.0
    """
