import os
import subprocess

from rbtools.utils.filesystem import make_tempfile


def edit_text(content):
    """Allows a user to edit a block of text and returns the saved result.

    The environment's default text editor is used if available, otherwise
    vim is used.
    """
    tempfile = make_tempfile(content)
    editor = os.environ.get('EDITOR', 'vim')
    subprocess.call([editor, tempfile])
    f = open(tempfile)
    result = f.read()
    f.close()

    return result
