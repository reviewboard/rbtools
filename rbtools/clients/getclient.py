from rbtools.api.utilities import RBUtilities

from rbtools.clients.clearcase import ClearCaseClient
from rbtools.clients.cvs import CVSClient
from rbtools.clients.git import GitClient
from rbtools.clients.mercurial import MercurialClient
from rbtools.clients.perforce import PerforceClient
from rbtools.clients.svn import SVNClient

CLIENTS = (
SVNClient(),
CVSClient(),
PerforceClient(),
ClearCaseClient(),
GitClient(),
MercurialClient(),
)


def get_client(url=None, types=CLIENTS):
    """Returns the source control manager client

    Determines the correct type of repository being used
    (using a list of possible types) in order to return
    the correct client
    """

    client = None
    info = None
    util = RBUtilities()

    if not url:
        type = 'missingRequiredParameter'
        message = 'get_client requires a url to be passed as a parameter'
        util.raise_error(type, message)

    for client in CLIENTS:
        client.set_url(url)

        info = client.get_info()

        if info:
            break

    if not info:
        client = None

        if url:
            type = 'repositoryNotFound'
            message = 'No repository could be accessed at: ' + url
            util.raise_error(type, message)

    return client
