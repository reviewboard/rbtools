"""Configuration for RBTools.

These classes manage access to loaded RBTools configuration, and provide
type hints for all RBTools-provided settings.

Version Added:
    5.0
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Dict, Optional

from typing_extensions import Self, TypeAlias


#: A dictionary storing raw configuration data.
ConfigDict: TypeAlias = Dict[str, Any]


class ConfigData:
    """Wrapper for configuration data.

    This stores raw configuration data, providing both dictionary-like and
    attribute-like access to it, as well as allowing subclasses to wrap
    dictionaries in another :py:class:`ConfigData` instance.

    Subclasses are expected to add type annotations for every known field
    that should be accessed through the class.
    """

    #: A mapping of configuration keys to ConfigData wrappers.
    #:
    #: This can be set by subclasses to add type hints to nested dictionaries.
    _wrappers: dict[str, type[ConfigData]] = {}

    ######################
    # Instance variables #
    ######################

    #: The filename that stored this configuration, if any.
    filename: Optional[str]

    #: The underlying raw configuration.
    _raw_config: ConfigDict

    def __init__(
        self,
        *,
        config_dict: Optional[ConfigDict] = None,
        filename: Optional[str] = None,
    ) -> None:
        """Initialize the configuration data wrapper.

        Args:
            config_dict (dict, optional):
                Loaded configuration data to wrap.

            filename (str, optional):
                The name of the associated configuration file.
        """
        self.filename = filename

        if config_dict is None:
            config_dict = {}

        # Load the configuration, and apply any wrappers if needed.
        wrappers = self._wrappers
        raw_config: ConfigDict = {}

        for key, value in config_dict.items():
            if key in wrappers:
                wrapper = wrappers[key](filename=filename,
                                        config_dict=value)
                self.__dict__[key] = wrapper
                value = wrapper._raw_config

            raw_config[key] = value

        self._raw_config = raw_config

    def copy(self) -> Self:
        """Return a copy of this configuration data.

        Returns:
            ConfigData:
            A copy of this instance's class with a copy of the data.
        """
        cls = type(self)

        return cls(filename=self.filename,
                   config_dict=deepcopy(self._raw_config))

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Return a value from a configuration item.

        This will return the value from the loaded configuration data, falling
        back to class-specified default value or the provided default value.

        This helps emulate dictionary-based access.

        Args:
            key (str):
                The configuration key.

            default (object, optional):
                The default value if the key cannot be found.

        Returns:
            object:
            The configuration value, or a default value if the key was
            not found.
        """
        return getattr(self, key, default)

    def merge(
        self,
        other_config: ConfigData,
    ) -> None:
        """Merge other configuration into this one.

        Any :py:class:`ConfigData` or dictionary values will be merged
        recursively.

        Args:
            other_config (ConfigData):
                The configuration data to merge in.
        """
        cur_config = self._raw_config

        for key in other_config._raw_config.keys():
            value = other_config[key]

            if key in self:
                cur_value = self[key]

                if isinstance(cur_value, ConfigData):
                    assert isinstance(value, ConfigData)

                    cur_value.merge(value)
                    continue
                elif isinstance(cur_value, dict):
                    assert isinstance(value, dict)

                    cur_value.update(value)
                    continue

            cur_config[key] = value

    def __eq__(
        self,
        other: Any,
    ) -> bool:
        """Return whether this configuration is equal to another.

        Configurations are equal if they are of the same type and have the
        same stored settings.

        The filename is not factored in.

        Args:
            other (object):
                The other object to compare to.

        Returns:
            bool:
            ``True`` if the two objects are equal. ``False`` if they are not.
        """
        return (type(self) is type(other) and
                self._raw_config == other._raw_config)

    def __delitem__(
        self,
        name: str,
    ) -> None:
        """Remove a key from the configuration.

        Args:
            name (str):
                The name of the key to remove.
        """
        del self._raw_config[name]

    def __contains__(
        self,
        key: str,
    ) -> bool:
        """Return whether a key is found in the configuration.

        A key will be considered found if it either has a default value or
        is present in the loaded configuration data.

        Args:
            key (str):
                The key to look for.

        Returns:
            bool:
            ``True`` if the key was found. ``False`` if it was not.
        """
        try:
            getattr(self, key)
            return True
        except AttributeError:
            return False

    def __getattribute__(
        self,
        name: str,
    ) -> Any:
        """Return the value for a configuration key as an attribute.

        This will return the value from the loaded configuration data, falling
        back to class-specified default value if one exists.

        Args:
            name (str):
                The configuration key.

        Returns:
            object:
            The configuration value, if found or if it has a default.

        Raises:
            AttributeError:
                The configuration key or default was not found.
        """
        if (name not in ('__dict__',
                         '__annotations__',
                         '_raw_config',
                         '_wrappers',
                         'filename') and
            (name in self.__annotations__ or
             name in self._raw_config)):

            if name in self._wrappers:
                try:
                    return self.__dict__[name]
                except KeyError:
                    pass

            try:
                return self._raw_config[name]
            except KeyError:
                # Try a default from a class.
                try:
                    value = getattr(type(self), name)
                except AttributeError:
                    raise AttributeError(
                        f'"{name}" is not a valid configuration key')

                if isinstance(value, (ConfigData, dict, list)):
                    # Copy it and set it back in the dictionary.
                    value = deepcopy(value)
                    self._raw_config[name] = value

                return value

        return super().__getattribute__(name)

    def __getitem__(
        self,
        name: str,
    ) -> Any:
        """Return the value for a configuration key as a dictionary key.

        This will return the value from the loaded configuration data, falling
        back to class-specified default value if one exists.

        Args:
            name (str):
                The configuration key.

        Returns:
            object:
            The configuration value, if found or if it has a default.

        Raises:
            KeyError:
                The configuration key or default was not found.
        """
        try:
            return getattr(self, name)
        except AttributeError as e:
            raise KeyError(str(e))

    def __set_name__(
        self,
        owner: type[object],
        name: str,
    ) -> None:
        """Handle an assignment of this instance to a class.

        If setting this on another :py:class:`ConfigData`, this will be
        registered in the owner class's list of wrappers.

        Args:
            owner (type):
                The class this is being set on.

            name (str):
                The attribute name being used for the assignment.
        """
        if issubclass(owner, ConfigData):
            owner._wrappers[name] = type(self)

    def __repr__(self) -> str:
        """Return a string representation of the configuration data.

        Returns:
            str:
            The string representation.
        """
        return (f'<RBToolsConfig(filename={self.filename}, '
                f'config={self._raw_config})>')


class GuessFlag(str, Enum):
    """A flag indicating whether to guess state.

    Version Added:
        5.0
    """

    #: Automatically guess, based on whether a review request is new.
    AUTO = 'auto'

    #: Enable guessing of state.
    YES = 'yes'

    #: Disable guessing of state.
    NO = 'no'


class ColorsConfig(ConfigData):
    """Configuration for terminal colors.

    Version Added:
        5.0
    """

    #: A color value for information output.
    INFO: Optional[str] = None

    #: A color value for debug output.
    DEBUG: Optional[str] = None

    #: A color value for warning output.
    WARNING: Optional[str] = 'yellow'

    #: A color value for error output.
    ERROR: Optional[str] = 'red'

    #: A color value for critical error output.
    CRITICAL: Optional[str] = 'red'


class RBToolsConfig(ConfigData):
    """Configuration for a .reviewboardrc file.

    Version Added:
        5.0
    """

    wrappers = {
        'COLOR': ColorsConfig,
    }

    #######################################################################
    # Output control
    #######################################################################

    #: Whether debug output is enabled.
    DEBUG: bool = False

    #: Whether JSON output is enabled.
    #:
    #: Version Added:
    #:     3.0
    JSON_OUTPUT: bool = False

    #######################################################################
    # User customization
    #######################################################################

    #: A mapping of RBTools aliases to commands.
    #:
    #: Version Added:
    #:     1.0
    ALIASES: dict[str, str] = {}

    #: Colors used for log/text output.
    #:
    #: Version Added:
    #:     1.0
    COLOR: ColorsConfig = ColorsConfig()

    #: Whether to automatically open a browser for any URLs.
    OPEN_BROWSER: bool = False

    #: A mapping of paths to directory- or repository-specific configuration.
    #:
    #: This allows the creation of a single .reviewboardrc file which can
    #: contain separate configurations for multiple repositories. The keys
    #: for this can be the repository path (remote) or the local directories.
    #: The values are dictionaries which can contain any valid .reviewboardrc
    #: config keys.
    #:
    #: This existed in older versions (4 and below) but was limited to just the
    #: REVIEWBOARD_URL setting.
    #:
    #: Version Added:
    #:     5.1
    TREES: dict[str, Any] = {}

    #######################################################################
    # Review Board server communication/authentication
    #######################################################################

    #: The URL for the Review Board server.
    REVIEWBOARD_URL: Optional[str] = None

    #: An API token to use for authentication.
    #:
    #: This takes place over a password.
    #:
    #: Version Added:
    #:     0.7
    API_TOKEN: Optional[str] = None

    #: A username to use for authentication.
    USERNAME: Optional[str] = None

    #: A password to use for authentication.
    PASSWORD: Optional[str] = None

    #: Whether to save new cookies to disk.
    #:
    #: Version Added:
    #:     0.7.3
    SAVE_COOKIES: bool = True

    #: The path to an external cookies file with pre-fetched cookies.
    #:
    #: This is useful with servers that require extra web authentication to
    #: access the Review Board server itself, such as certain Single Sign-On
    #: services or proxies.
    #:
    #: Version Added:
    #:     0.7.5
    EXT_AUTH_COOKIES: Optional[str] = None

    #: Whether to enable strict domain matching for cookies.
    #:
    #: By default, cookies that match both a domain and a parent domain
    #: (e.g., ``subdomain.example.com`` and ``example.com``) will both be
    #: sent in requests.
    #:
    #: Strict domains can be enabled if there's a risk of conflict between
    #: cookies on a domain and a parent domain.
    #:
    #: This is off by default for backwards-compatibility.
    #:
    #: Version Added:
    #:     5.1
    COOKIES_STRICT_DOMAIN_MATCH: bool = False

    #: Whether to default to using web-based login for authentication.
    #:
    #: If this is set, web-based login will be used instead of prompting
    #: for authentication credentials in the terminal.
    #:
    #: Version Added:
    #:     5.0
    WEB_LOGIN: bool = False

    #######################################################################
    # HTTP proxy
    #######################################################################

    #: Whether to allow usage of a configured HTTP(S) proxy server.
    ENABLE_PROXY: bool = False

    #: A value to send in Proxy-Authorization headers for HTTP requests.
    #:
    #: This can be used to authenticate with proxy services.
    PROXY_AUTHORIZATION: Optional[str] = None

    #######################################################################
    # API caching
    #######################################################################

    #: The file to use for the API cache database.
    #:
    #: If not explicitly provided, a default will be chosen.
    #:
    #: Version Added:
    #:     0.7.3
    CACHE_LOCATION: Optional[str] = None

    #: Whether to disable HTTP caching completely.
    #:
    #: This will result in slower requests.
    #:
    #: Version Added:
    #:     0.7.3
    DISABLE_CACHE: bool = False

    #: Whether to use an in-memory cache, instead of writing to disk.
    #:
    #: Version Added:
    #:     0.7.3
    IN_MEMORY_CACHE: bool = False

    #######################################################################
    # SSL/TLS
    #######################################################################

    #: A path to an additional SSL/TLS CA bundle.
    CA_CERTS: Optional[str] = None

    #: A path to a SSL/TLS certificate for communicating with the server.
    CLIENT_CERT: Optional[str] = None

    #: A path to a SSL/TLS key for communicating with the server.
    CLIENT_KEY: Optional[str] = None

    #: Whether to disable SSL/TLS verification.
    DISABLE_SSL_VERIFICATION: bool = False

    #######################################################################
    # Repositories
    #######################################################################

    #: The name of the repository on Review Board to communicate with.
    #:
    #: Version Changed:
    #:     0.6:
    #:     This previously supported taking a configured repository URL.
    #:     That now must be provided in :py:attr:`REPOSITORY_URL`.
    REPOSITORY: Optional[str] = None

    #: The type of the repository on Review Board.
    #:
    #: This must be a value found in :command:`rbt list-repo-types`.
    REPOSITORY_TYPE: Optional[str] = None

    #: The URL to the repository.
    #:
    #: This can be used to override the detected URL for some SCMs or to
    #: influence certain operations.
    #:
    #: For Subversion, this can be used to generate a diff outside of a
    #: working copy.
    #:
    #: For Git, this can override the origin URL.
    #:
    #: Version Changed:
    #:     0.6:
    #:     This previously supported taking a configured repository name.
    #:     That now must be provided in :py:attr:`REPOSITORY`.
    REPOSITORY_URL: Optional[str] = None

    #######################################################################
    # Diff generation
    #######################################################################

    #: The path within the repository where the diff is generated.
    #:
    #: This will be prepended to any relative URLs in the path. Specifying
    #: this overrides any detected paths.
    #:
    #: It's currently only supported for Subversion, usually when using
    #: :option:`--diff-filename` options.
    BASEDIR: Optional[str] = None

    #: A list of file patterns to exclude from the diff.
    #:
    #: Version Added:
    #:     0.7
    EXCLUDE_PATTERNS: list[str] = []

    #: The parent branch the generate diffs relative to.
    #:
    #: This is only supported by some SCMs. In general, this should not be
    #: used. Instead, revision ranges should be provided.
    PARENT_BRANCH: Optional[str] = None

    #: The remote tracking branch that the local branch corresponds to.
    #:
    #: This is used for Git and Mercurial, and will override any automatic
    #: tracking branch detection implemented by the SCM client.
    TRACKING_BRANCH: Optional[str] = None

    #######################################################################
    # Review requests
    #######################################################################

    #: The value of the Branch field on a review request.
    #:
    #: This will update the field when posting a change for review using
    #: :rbt-command:`post`.
    #:
    #: Other commands may use it to inspect client-side defaults, but it's
    #: recommended to inspect the review request where possible.
    BRANCH: Optional[str] = None

    #: A comma-separated list of review request IDs to depend on.
    #:
    #: This will update the field when posting a change for review using
    #: :rbt-command:`post`.
    #:
    #: Other commands may use it to inspect client-side defaults, but it's
    #: recommended to inspect the review request where possible.
    #:
    #: Version Added:
    #:     0.6.1
    DEPENDS_ON: Optional[str] = None

    #: Whether to enable Markdown for any text content.
    #:
    #: If set, review request, review, and comment text content will be
    #: uploaded in Markdown format.
    #:
    #: Version Added:
    #:     0.6
    MARKDOWN: bool = False

    #: A comma-separated list of group names to list as reviewers.
    #:
    #: This will update the field when posting a change for review using
    #: :rbt-command:`post`.
    #:
    #: Other commands may use it to inspect client-side defaults, but it's
    #: recommended to inspect the review request where possible.
    TARGET_GROUPS: Optional[str] = None

    #: A comma-separated list of usernames to list as reviewers.
    #:
    #: This will update the field when posting a change for review using
    #: :rbt-command:`post`.
    #:
    #: Other commands may use it to inspect client-side defaults, but it's
    #: recommended to inspect the review request where possible.
    TARGET_PEOPLE: Optional[str] = None

    #######################################################################
    # Perforce support
    #######################################################################

    #: The Perforce client name for the repository.
    P4_CLIENT: Optional[str] = None

    #: The IP address/port for the Perforce server.
    P4_PORT: Optional[str] = None

    #: The password or ticket of the user in Perforce.
    P4_PASSWD: Optional[str] = None

    #######################################################################
    # Subversion support
    #######################################################################

    #: Whether to prompt for a user's Subversion password.
    #:
    #: Version Added:
    #:     0.7.3
    SVN_PROMPT_PASSWORD: bool = False

    #######################################################################
    # Team Foundation Server support
    #######################################################################

    #: The full path to the :command:`tf` command.
    #:
    #: This will override any detected path.
    #:
    #: Version Added:
    #:     0.7.6
    TF_CMD: Optional[str] = None

    #######################################################################
    # rbt land
    #######################################################################

    #: Whether to delete the local branch when landed.
    #:
    #: This is only used when deleting local branches.
    #:
    #: Version Added:
    #:     0.7
    LAND_DELETE_BRANCH: bool = True

    #: The name of a destination branch that changes should land on.
    #:
    #: This is required when landing.
    #:
    #: Version Added:
    #:     0.7
    LAND_DEST_BRANCH: Optional[str] = None

    #: Whether to push the destination branch after landing the change.
    #:
    #: Version Added:
    #:     0.7
    LAND_PUSH: bool = False

    #: Whether to squash multiple commits into one when landing.
    #:
    #: Version Added:
    #:     0.7
    LAND_SQUASH: bool = False

    #######################################################################
    # rbt post
    #######################################################################

    #: Whether to guess and set review request fields from a commit.
    #:
    #: This will control the values for the following settings:
    #:
    #: * :py:attr:`GUESS_DESCRIPTION`
    #: * :py:attr:`GUESS_SUMMARY`
    GUESS_FIELDS: Optional[str] = GuessFlag.AUTO

    #: Whether to guess and set a review request description from a commit.
    GUESS_DESCRIPTION: Optional[GuessFlag] = None

    #: Whether to guess and set a review request summary from a commit.
    GUESS_SUMMARY: Optional[GuessFlag] = None

    #: Whether to publish a change immediately after posting it.
    #:
    #: To succeed, all required fields must already be filled in on the
    #: review request.
    PUBLISH: bool = False

    #: Whether to create the review request in legacy single-commit mode.
    #:
    #: If set, the review request will not be able to display multi-commit
    #: reviews.
    #:
    #: This should be considered a legacy setting.
    #:
    #: Version Added:
    #:     2.0
    SQUASH_HISTORY: bool = False

    #: Whether to stamp the commit message with the review request URL.
    #:
    #: This is used by :rbt-command:`post` to perform the stamping once
    #: posted.
    #:
    #: Version Added:
    #:     0.7.3
    STAMP_WHEN_POSTING: bool = False

    #: A username to use as the author of the review request.
    #:
    #: This requires the logged-in user to have the special
    #: ``reviews.can_submit_as`` permission. See :ref:`automating-rbt-post`.
    SUBMIT_AS: Optional[str] = None

    #######################################################################
    # rbt api-get
    #######################################################################

    #: Whether to pretty-print the resulting API payload.
    #:
    #: Version Added:
    #:     0.5.2
    API_GET_PRETTY_PRINT: bool = False
