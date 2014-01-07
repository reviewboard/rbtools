import os
import subprocess
from distutils.util import strtobool

from rbtools.utils.filesystem import make_tempfile


def confirm(question):
    """Interactively prompt for a Yes/No answer.

    Accepted values (case-insensitive) depend on distutils.util.strtobool():
    'Yes' values: y, yes, t, true, on, 1
    'No' values: n, no , f, false, off, 0
    """
    while True:
        try:
            answer = raw_input("%s [Yes/No]: " % question).lower()
            return strtobool(answer)
        except ValueError:
            print '%s is not a valid answer.' % answer


def edit_text(content):
    """Allows a user to edit a block of text and returns the saved result.

    The environment's default text editor is used if available, otherwise
    vim is used.
    """
    tempfile = make_tempfile(content.encode('utf8'))
    editor = os.environ.get('EDITOR', 'vim')
    subprocess.call([editor, tempfile])
    f = open(tempfile)
    result = f.read()
    f.close()

    return result.decode('utf8')
