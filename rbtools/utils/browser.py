"""Utilities for working with web browsers.

Version Added:
    5.0
"""

from __future__ import annotations

import logging
import platform
import sys


logger = logging.getLogger(__name__)


def open_browser(
    url: str
) -> bool:
    """Open a page at the URL in the system's browser.

    If a browser window is already open this will open a new tab, otherwise
    this will open a new window.

    Version Added:
        5.0

    Args:
        url (str):
            The web URL to open in the browser.

    Returns:
        bool:
        Whether the page was successfully opened.
    """
    try:
        if (sys.platform == 'darwin' and
            platform.mac_ver()[0] == '10.12.5'):
            # The 'webbrowser' module currently does a bunch of stuff
            # with AppleScript, which is broken on macOS 10.12.5. This
            # was fixed in 10.12.6. See
            # https://bugs.python.org/issue30392 for more discussion.
            open(['open', url])
        else:
            import webbrowser
            webbrowser.open_new_tab(url)

        return True
    except Exception as e:
        logger.exception('Error opening URL %s: %s', url, e)

        return False
