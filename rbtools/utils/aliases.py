from __future__ import unicode_literals

import logging
import re
import shlex
import sys
import subprocess

import six

from rbtools.commands import RB_MAIN


# Regular expression for matching argument replacement
_arg_re = re.compile(r'\$(\d+)')

# Prior to Python 2.7.3, the shlex module could not accept unicode input.
_SHLEX_SUPPORTS_UNICODE = sys.version_info >= (2, 7, 3)


def replace_arguments(cmd, args, posix):
    """Do parameter substitution for the given command.

    Occurrances of variables ``$1``, ``$2``, etc. are replaced with the nth
    element of ``args`` (1-indexed). The special variable ``$*`` is expanded to
    contain all arguments.

    If neither of these are present in the command, all arguments will be
    appended to the end.

    Args:
        cmd (unicode):
            The alias to replace positional variables in.

        args (list of unicode):
            The arguments being provided to the alias.

        posix (boolean):
            Whether or not to use the POSIX processing of commands.

            This should be ``False`` when parsing a command that will be given
            directly to the shell.

    Returns:
        list of unicode:
        The command and its arguments.

    Raises:
        ValueError:
            An invalid escape or missing quote was encountered.
    """
    def arg_sub(m):
        """Replace a positional variable with the appropriate argument."""
        index = int(m.group(1)) - 1

        try:
            return args[index]
        except IndexError:
            return ''

    did_replacement = False

    shlex_convert_text_type = (not _SHLEX_SUPPORTS_UNICODE and
                               isinstance(cmd, six.text_type))

    if shlex_convert_text_type:
        # This version of Python does not have a shlex module that supports
        # unicode arguments. We will encode it to a bytestring and then decode
        # it as we are processing the results.
        cmd = cmd.encode('utf-8')

    processed_cmd = []

    # When parsing a command for the shell, we do not operate in POSIX mode so
    # that:
    #
    # 1. Aliases do not have to be double escaped so that they will be properly
    #    be escaped by both us and the shell.
    #
    # 2. Quoted tokens will be returned in their original quotes, which would
    #    be removed in POSIX mode. We need to keep these quotes so aliases that
    #    contain single-quoted shell-specific characters (e.g., `'*'`) are
    #    returned as-is. Otherwise, the shell will try to evaluate these
    #    arguments when that is not the intention.
    for token in shlex.split(cmd, posix=posix):
        if token == '$*':
            did_replacement = True
            processed_cmd += args
        else:
            token, num_subs = _arg_re.subn(arg_sub, token)

            if shlex_convert_text_type:
                # Above we encoded our token into a byte string, so we need
                # to decode it back into a unicode string.
                token = token.decode('utf-8')

            if num_subs != 0:
                did_replacement = True

            if len(token):
                processed_cmd.append(token)

    # We did not do any positional variable replacement, so we will add all
    # arguments to the end of the command.
    if not did_replacement:
        processed_cmd += args

    return processed_cmd


def expand_alias(alias, args):
    """Expand the given alias.

    This function returns a tuple of the list of command line arguments and
    whether or not shell execution is required for the alias.

    Args:
        alias (unicode):
            The alias to expand.

        args (list of unicode):
            The arguments to provide to the command.

    Returns:
        tuple:
        A 2-tuple of:

        * The expanded alias (:py:class:`unicode` or :py:class:`list` of
          :py:class:`unicode`).
        * Whether or not the command should be passed to the shell or not
          (:py:class:`boolean`).
    """
    use_shell = alias.startswith('!')

    if use_shell:
        command = ' '.join(replace_arguments(alias[1:], args, posix=True))
    else:
        command = [RB_MAIN] + replace_arguments(alias, args, posix=False)

    return command, use_shell


def run_alias(alias_name, alias, args):
    """Run the alias with the given arguments after expanding parameters.

    Args:
        alias_name (unicode):
            The name of the alias being run.

        alias (unicode):
            The alias to run.

        args (list of unicode):
            The arguments to the command being run.

    Returns:
        int:
        The exit code of the executed command (if it executed) or ``1`` if the
        alias could not be expanded.
    """
    try:
        cmd, use_shell = expand_alias(alias, args)
    except ValueError as e:
        logging.critical(
            'Could not parse alias "%s" (`%s`): %s',
            alias_name, alias, e)
        return 1

    return subprocess.call(cmd, shell=use_shell)
