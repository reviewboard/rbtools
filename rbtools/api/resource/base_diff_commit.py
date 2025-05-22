"""Base class for diff commit resources.

Version Added:
    6.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rbtools.api.resource.base import ItemResource
from rbtools.api.resource.mixins import GetPatchMixin

if TYPE_CHECKING:
    from rbtools.api.resource.base import ResourceExtraDataField


class BaseDiffCommitItemResource(GetPatchMixin, ItemResource):
    """Base class for diff commit item resources.

    Version Added:
        6.0
    """

    ######################
    # Instance variables #
    ######################

    #: The date and time this commit was authored, in ISO-8601 format.
    author_date: str | None

    #: The e-mail address of the author of this commit.
    author_email: str | None

    #: The name of the author of this commit.
    author_name: str | None

    #: The ID of this commit.
    commit_id: str

    #: The commit message.
    commit_message: str

    #: The date and time this commit was committed, in ISO-8601 format.
    committer_date: str | None

    #: The e-mail address of the committer of this commit.
    committer_email: str | None

    #: The name of the committer of this commit.
    committer_name: str | None

    #: Extra data as part of the commit.
    extra_data: ResourceExtraDataField

    #: The name of the corresponding diff.
    filename: str

    #: The number ID of the commit resource.
    id: int

    #: The ID of the parent commit.
    parent_id: str
