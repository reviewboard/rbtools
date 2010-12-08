import os
import sys

from rbtools.api.settings import Settings
from rbtools.clients.getclient import get_client


def main():
    valid = True

    if len(sys.argv) > 0:
        settings = Settings(config_file='rb_scripts.dat')
        server_url = settings.get_server_url()
        client = get_client(server_url)
        diff, parent_diff = client.diff(None)
        cwd = os.getcwd()

        if len(sys.argv) > 1:
            out_file = os.path.join(cwd, sys.argv[1])
        else:
            out_file = os.path.join(cwd, 'diff')

        diff_file = open(out_file, 'w')
        diff_file.write(diff)
        diff_file.close()
        print "Diff created and stored in %s" % out_file


if __name__ == "__main__":
    main()
