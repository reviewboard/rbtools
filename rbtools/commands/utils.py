import getpass
from json import dumps 


def json_to_string(json):
    return dumps(json, sort_keys=True, indent=4)


class ReviewBoardPasswordInputer(object):
    def __init__(self):
        super(ReviewBoardPasswordInputer, self).__init__()

    def get_user_password(self, realm, uri):
        raise NotImplementedError('This method needs to be implemented.')


class DefaultPasswordInputer(ReviewBoardPasswordInputer):
    def __init__(self):
        super(DefaultPasswordInputer, self).__init__()

    def get_user_password(self, realm, uri):
        print "==> HTTP Authentication required"
        print "Enter username and password for %s at %s" % (realm, uri)
        username = raw_input('Username: ')
        password = getpass.getpass('Password: ')
        return username, password
