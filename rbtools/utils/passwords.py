import keyring

"""
The PasswordStore class is used to resolve authentication parameters for both the
Review Board HTTP server and the Review Board instance.  The resolution mechanism
will check the following locations.

    1) Check the command line options
    2) Check .reviewboardrc
    3) Check the OS Keychain
    4) Prompt the user
"""
class PasswordStore(object):

    def getReviewBoardUser(self):
        return ""

    def getReviewBoardPassword(self):
        return ""

    def getHttpUser(self):
        return ""

    def getHttpPassword(self):
        return ""

    def resolve(self, reviewboardProperty, keychainProperty):
        return ""
