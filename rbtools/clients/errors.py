"""Error definitions for SCMClient implementations."""

from __future__ import annotations

from typing import List, Tuple, Union

from typing_extensions import TypeAlias


class SCMError(Exception):
    """A generic error from an SCM."""


class AuthenticationError(Exception):
    """An error for when authentication fails."""


class CreateCommitError(Exception):
    """The creation of a commit has failed or was aborted."""


class MergeError(Exception):
    """An error for when merging two branches fails."""


class PushError(Exception):
    """An error for when pushing a branch to upstream fails."""


class AmendError(Exception):
    """An error for when amending a commit fails."""


class OptionsCheckError(Exception):
    """An error for when command line options are used incorrectly."""


class InvalidRevisionSpecError(Exception):
    """An error for when the specified revisions are invalid."""


class MinimumVersionError(Exception):
    """An error for when software doesn't meet version requirements."""


class TooManyRevisionsError(InvalidRevisionSpecError):
    """An error for when too many revisions were specified."""

    def __init__(self):
        """Initialize the error."""
        super(TooManyRevisionsError, self).__init__(
            'Too many revisions specified')


class EmptyChangeError(Exception):
    """An error for when there are no changed files."""

    def __init__(self):
        """Initialize the error."""
        super(EmptyChangeError, self).__init__(
            "Couldn't find any affected files for this change.")


class SCMClientDependencyError(SCMError):
    """One or more required dependencies are missing.

    Version Added:
        4.0

    Attributes:
        missing_exes (list):
            A list of missing executable dependencies.

            Each item can be a string representing the name of the tool,
            or a tuple of possible interchangeable names.

        missing_modules (list):
            A list of missing Python module dependencies.

            Each item can be a string representing the name of the
            module, or a tuple of possible interchangeable module names.
    """

    #: A type alias for a tuple of missing interchangeable dependencies.
    #:
    #: Any item in the list would have satisfied the dependency check.
    #:
    #: The tuple is presented in search order.
    MissingOneOfDep: TypeAlias = Tuple[str, ...]

    #: A type alias for a missing dependency.
    #:
    #: This can be a string naming the dependency, or a tuple of
    #: interchangeable dependencies.
    MissingItem: TypeAlias = Union[str, MissingOneOfDep]

    #: A type alias for a list of missing dependencies.
    MissingList: TypeAlias = List[MissingItem]

    def __init__(
        self,
        missing_exes: MissingList = [],
        missing_modules: MissingList = [],
    ) -> None:
        """Initialize the error.

        Args:
            missing_exes (list, optional):
                A list of missing executable dependencies.

                Each item can be a string representing the name of the tool,
                or a tuple of possible interchangeable names.

            missing_modules (list, optional):
                A list of missing Python module dependencies.

                Each item can be a string representing the name of the
                module, or a tuple of possible interchangeable module names.
        """
        self.missing_exes = missing_exes
        self.missing_modules = missing_modules

        if missing_exes and missing_modules:
            message = (
                'Command line tools (%s) and Python modules (%s) are missing.'
                % (self._serialize_missing(missing_exes),
                   self._serialize_missing(missing_modules))
            )
        elif missing_exes:
            message = (
                'Command line tools (%s) are missing.'
                % self._serialize_missing(missing_exes)
            )
        else:
            message = (
                'Python modules (%s) are missing.'
                % self._serialize_missing(missing_modules)
            )

        super(SCMClientDependencyError, self).__init__(message)

    def _serialize_missing(
        self,
        missing: Union[MissingList, MissingOneOfDep],
    ) -> str:
        """Return a serialized version of missing dependencies.

        Args:
            missing (list or tuple):
                A list of missing dependencies.

                Each item can be a string representing the name of the
                dependency, or a tuple of possible interchangeable
                dependencies.

        Returns:
            str:
            The string representation of ``missing``.
        """
        parts: list[str] = []

        for item in missing:
            if not item:
                continue

            if isinstance(item, tuple):
                # If this contains multiple items, show those.
                if len(item) > 1:
                    parts.append('one of (%s)' % self._serialize_missing(item))
                    continue

                # Otherwise, fall back to treating this as a single item.
                item = item[0]

            parts.append("'%s'" % item)

        return ', '.join(parts)


class SCMClientNotFoundError(Exception):
    """An error indicating a specified SCMClient could not be found.

    Version Added:
        4.0

    Attributes:
        scmclient_id (str):
            The ID of the SCMClient that could not be found.
    """

    def __init__(
        self,
        scmclient_id: str,
    ) -> None:
        """Initialize the error.

        Args:
            scmclient_id (str):
                The ID of the SCMClient that could not be found.
        """
        self.scmclient_id = scmclient_id

        super().__init__('No client support was found for "%s".'
                         % scmclient_id)
