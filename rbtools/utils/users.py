import getpass
import logging
import sys

from rbtools.api.errors import AuthorizationError
from rbtools.commands import CommandError

def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes":True,   "y":True,  "ye":True,
             "no":False,     "n":False}
    if default == None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "\
                             "(or 'y' or 'n').\n")

def get_user(api_client, api_root, auth_required=False):
    """Return the user resource for the current session

    None will be returned if the user is not authenticated, unless the
    'auth_required' parameter is True, in which case the user will be
    prompted to login.
    """
    session = api_root.get_session()

    if not session.authenticated:
        if not auth_required:
            return None

        logging.warning('You are not authenticated with the Review Board'
                        'server at %s, please login.' % api_client.url)
        sys.stderr.write('Username: ')
        username = raw_input()
        password = getpass.getpass('Password: ')
        api_client.login(username, password)

        try:
            session = session.get_self()
        except AuthorizationError:
            raise CommandError('You are not authenticated.')

    return session.get_user()
