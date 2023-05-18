"""Utilities for working with console interactions."""

import getpass
import logging
import os
import subprocess
import sys

from rbtools.utils.encoding import force_unicode
from rbtools.utils.errors import EditorError
from rbtools.utils.filesystem import make_tempfile


logger = logging.getLogger(__name__)


def get_input(prompt, require=False, stderr=sys.stderr, stdin=sys.stdin):
    """Ask the user for input.

    Version Changed:
        3.1:
        ``stdout`` and ``stderr`` streams are now supported. This can now be
        used with a non-TTY input stream.

    If ``stdin`` is not a TTY, this will read lines of input until it
    receives a valid answer.

    Args:
        prompt (unicode):
            The text to prompt the user with.

        require (bool, optional):
            Whether to require a result. If ``True``, this will keep prompting
            until a non-empty value is entered.

        stderr (io.TextIOWrapper or file, optional):
            The error stream to use for the prompt.

            Version Added:
                3.1

        stdin (io.TextIOWrapper or file, optional):
            The input stream to use.

            Version Added:
                3.1

    Returns:
        unicode:
        The entered user data.
    """
    def _get_input():
        # `input`'s usual prompt gets written to stdout, which results in
        # really crummy behavior if stdout is redirected to a file. Because
        # this is often paired with getpass (entering a username/password
        # combination), we mimic the behavior there, writing the prompt to
        # stderr.
        stderr.write(prompt)

        if hasattr(stdin, 'isatty') and stdin.isatty():
            result = input()
        else:
            result = stdin.readline().rstrip()

        return result

    prompt = str(prompt)

    if require:
        value = None

        while not value:
            value = _get_input()
    else:
        value = _get_input()

    return value


def get_pass(prompt, require=False, stderr=sys.stderr, stdin=sys.stdin):
    """Ask the user for a password.

    Version Changed:
        3.1:
        ``stdout`` and ``stderr`` streams are now supported. This can now be
        used with a non-TTY input stream.

    If ``stdin`` is not a TTY, this will read lines of input until it
    receives a valid answer.

    Args:
        prompt (unicode):
            The text to prompt the user with.

        require (bool, optional):
            Whether to require a result. If ``True``, this will keep prompting
            until a non-empty value is entered.

        stderr (io.TextIOWrapper or file, optional):
            The error stream to use for the prompt.

            Version Added:
                3.1

        stdin (io.TextIOWrapper or file, optional):
            The input stream to use.

            Version Added:
                3.1

    Returns:
        bytes:
        The entered password.
    """
    def _get_pass(prompt):
        if hasattr(stdin, 'isatty') and stdin.isatty():
            result = getpass.getpass(prompt)
        else:
            stderr.write(prompt)
            result = stdin.readline()

        return result.strip()

    prompt = str(prompt)

    if require:
        password = None

        while not password:
            password = _get_pass(prompt)
    else:
        password = _get_pass(prompt)

    return password


def confirm(question, stderr=sys.stderr, stdin=sys.stdin):
    """Interactively prompt for a Yes/No answer.

    This requires a Yes or a No answer. These are case-insensitive.

    Valid Yes answers include: ``y``, ``yes``, ``t``, ``true``, ``on``, ``1``.

    Valid No answers include: ``n``, ``no``, ``f``, ``false``, ``off``, ``0``.

    If ``stdin`` is not a TTY, this will read lines of input until it
    receives a valid answer.

    Version Changed:
        3.1:
        ``stdout`` and ``stderr`` streams are now supported. This can now be
        used with a non-TTY input stream.

    Args:
        question (unicode):
            The question to ask.

        stderr (io.TextIOWrapper or file, optional):
            The error stream to use for the prompt.

            Version Added:
                3.1

        stdin (io.TextIOWrapper or file, optional):
            The input stream to use.

            Version Added:
                3.1

    Returns:
        bool:
        The confirmed value.
    """
    valid_yes = ('yes', 'y', 'true', 't', 'on', '1')
    valid_no = ('no', 'n', 'false', 'f', 'off', '0')

    full_question = '%s [Yes/No]: ' % question

    while True:
        answer = get_input(full_question,
                           stderr=stderr,
                           stdin=stdin).lower()

        if answer in valid_yes:
            return True
        elif answer in valid_no:
            return False
        else:
            stderr.write('"%s" is not a valid answer.\n' % answer)


def confirm_select(question, options_length, stderr=sys.stderr,
                   stdin=sys.stdin):
    """Interactively prompt for a specific answer from a list of options.

    Accepted answers are integers starting from 1 until an integer n
    representing the nth of element within options.

    If ``stdin`` is not a TTY, this will read lines of input until it
    receives a valid answer.

    Version Changed:
        3.1:
        ``stdout`` and ``stderr`` streams are now supported. This can now be
        used with a non-TTY input stream.

    Args:
        question (unicode):
            The prompt to be displayed.

        options_length (int):
            The number of available options that the user can choose a
            response from.

        stderr (io.TextIOWrapper or file, optional):
            The error stream to use for the prompt.

            Version Added:
                3.1

        stdin (io.TextIOWrapper or file, optional):
            The input stream to use.

            Version Added:
                3.1

    Returns:
        unicode:
        The user's chosen response. If the user decides to cancel the
        prompt, None is returned.
    """
    while True:
        answer = get_input('%s [1-%i]: ' % (question, options_length),
                           stderr=stderr,
                           stdin=stdin)

        try:
            int_answer = int(answer)

            if 1 <= int_answer <= options_length:
                return int_answer

            raise ValueError
        except ValueError:
            stderr.write('"%s" is not a valid answer.\n' % answer)


def edit_file(filename):
    """Run a user-configured editor to edit an existing file.

    This will run a configured text editor (trying the :envvar:`VISUAL` or
    :envvar:`EDITOR` environment variables, falling back on :program:`vi`)
    to request text for use in a commit message or some other purpose.

    Args:
        filename (unicode):
            The file to edit.

    Returns:
        unicode:
        The resulting content.

    Raises:
        rbcommons.utils.errors.EditorError:
            The configured editor could not be run, or it failed with an
            error.
    """
    if not os.path.exists(filename):
        raise EditorError('The file "%s" does not exist or is not accessible.'
                          % filename)

    editor = force_unicode(
        os.environ.get(str('RBTOOLS_EDITOR')) or
        os.environ.get(str('VISUAL')) or
        os.environ.get(str('EDITOR')) or
        'vi'
    )

    try:
        subprocess.call(editor.split() + [filename])
    except OSError:
        raise EditorError('The editor "%s" was not found or could not be run. '
                          'Make sure the EDITOR environment variable is set '
                          'to your preferred editor.'
                          % editor)

    try:
        with open(filename, 'r') as fp:
            return force_unicode(fp.read())
    except IOError:
        raise EditorError('The edited file "%s" was deleted during edit.'
                          % filename)


def edit_text(content='', filename=None):
    """Run a user-configured editor to prompt for text.

    This will run a configured text editor (trying the :envvar:`VISUAL` or
    :envvar:`EDITOR` environment variables, falling back on :program:`vi`)
    to request text for use in a commit message or some other purpose.

    Args:
        content (unicode, optional):
            Existing content to edit.

        filename (unicode, optional):
            The optional name of the temp file to edit. This can be used to
            help the editor provide a proper editing environment for the
            file.

    Returns:
        unicode:
        The resulting content.

    Raises:
        rbcommons.utils.errors.EditorError:
            The configured editor could not be run, or it failed with an
            error.
    """
    tempfile = make_tempfile(content=content.encode('utf8'),
                             filename=filename)
    result = edit_file(tempfile)
    os.unlink(tempfile)

    return result
