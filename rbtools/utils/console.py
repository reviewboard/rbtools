from __future__ import print_function, unicode_literals

import os
import subprocess
from distutils.util import strtobool

from six.moves import input

from rbtools.utils.filesystem import make_tempfile


def confirm(question):
    """Interactively prompt for a Yes/No answer.

    Accepted values (case-insensitive) depend on distutils.util.strtobool():
    'Yes' values: y, yes, t, true, on, 1
    'No' values: n, no , f, false, off, 0
    """
    while True:
        full_question = '%s [Yes/No]: ' % question
        answer = input(full_question.encode('utf-8')).lower()
        try:
            return strtobool(answer)
        except ValueError:
            print('%s is not a valid answer.' % answer)


def edit_text(content):
    """Allows a user to edit a block of text and returns the saved result.

    The environment's default text editor is used if available, otherwise
    vi is used.
    """
    tempfile = make_tempfile(content.encode('utf8'))
    editor = os.environ.get('VISUAL') or os.environ.get('EDITOR') or 'vi'
    try:
        subprocess.call(editor.split() + [tempfile])
    except OSError:
        print('No editor found. Set EDITOR environment variable or install '
              'vi.')
        raise

    f = open(tempfile)
    result = f.read()
    f.close()

    return result.decode('utf8')
